from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import struct
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence

import requests

from backend.app.config import EMBEDDING_API_KEY
from backend.app.config import EMBEDDING_BATCH_SIZE
from backend.app.config import EMBEDDING_DIMS
from backend.app.config import EMBEDDING_MAX_RETRIES
from backend.app.config import EMBEDDING_MODEL
from backend.app.config import EMBEDDING_PROVIDER
from backend.app.config import EMBEDDING_RETRY_BACKOFF_SECONDS
from backend.app.config import EMBEDDING_TIMEOUT_SECONDS
from backend.app.config import HUGGINGFACE_API_BASE_URL
from backend.app.database import connect

LOCAL_PROVIDER_NAME = "local"
LOCAL_MODEL_NAME = "local_hashing_cjk_v1"
HUGGINGFACE_PROVIDER_NAME = "huggingface"
HUGGINGFACE_DEFAULT_MODEL_NAME = "BAAI/bge-large-zh-v1.5"
HUGGINGFACE_DEFAULT_DIMS = 1024
RESERVED_AI_PROVIDER_NAMES = {"openai", "ai"}
MODEL_NAME = EMBEDDING_MODEL
DEFAULT_DIMS = EMBEDDING_DIMS
TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class EmbeddingProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmbeddedText:
    vector: list[float]
    norm: float
    token_count: int


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dims: int

    def embed_texts(self, texts: list[str]) -> list[EmbeddedText]:
        pass


@dataclass(frozen=True)
class LocalHashingEmbeddingProvider:
    model_name: str = LOCAL_MODEL_NAME
    dims: int = 384
    provider_name: str = LOCAL_PROVIDER_NAME

    def embed_texts(self, texts: list[str]) -> list[EmbeddedText]:
        return [EmbeddedText(*vectorize_text(text, dims=self.dims)) for text in texts]


class HuggingFaceEmbeddingProvider:
    provider_name = HUGGINGFACE_PROVIDER_NAME

    def __init__(
        self,
        *,
        model_name: str,
        dims: int,
        api_key: str,
        api_base_url: str = HUGGINGFACE_API_BASE_URL,
        batch_size: int = EMBEDDING_BATCH_SIZE,
        max_retries: int = EMBEDDING_MAX_RETRIES,
        retry_backoff_seconds: float = EMBEDDING_RETRY_BACKOFF_SECONDS,
        timeout_seconds: float = EMBEDDING_TIMEOUT_SECONDS,
        http_client: Any = requests,
    ) -> None:
        if not api_key:
            raise EmbeddingProviderError(
                "Hugging Face embedding provider requires EMBEDDING_API_KEY or HF_TOKEN. "
                "Store the token in .env or your shell environment; do not commit it."
            )
        if batch_size <= 0:
            raise EmbeddingProviderError("EMBEDDING_BATCH_SIZE must be greater than 0.")
        if max_retries < 0:
            raise EmbeddingProviderError("EMBEDDING_MAX_RETRIES must not be negative.")
        if retry_backoff_seconds < 0:
            raise EmbeddingProviderError("EMBEDDING_RETRY_BACKOFF_SECONDS must not be negative.")
        if timeout_seconds <= 0:
            raise EmbeddingProviderError("EMBEDDING_TIMEOUT_SECONDS must be greater than 0.")

        self.model_name = model_name
        self.dims = dims
        self.api_key = api_key
        self.api_base_url = api_base_url.rstrip("/")
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client

    def embed_texts(self, texts: list[str]) -> list[EmbeddedText]:
        results = [EmbeddedText(vector=[0.0] * self.dims, norm=0.0, token_count=0) for _ in texts]
        indexed_texts = [(index, text) for index, text in enumerate(texts) if text and text.strip()]

        for start in range(0, len(indexed_texts), self.batch_size):
            batch = indexed_texts[start : start + self.batch_size]
            batch_vectors = self._request_embeddings([text for _, text in batch])
            if len(batch_vectors) != len(batch):
                raise EmbeddingProviderError(
                    f"Hugging Face returned {len(batch_vectors)} embeddings for {len(batch)} input texts."
                )
            for (original_index, text), vector in zip(batch, batch_vectors):
                normalized_vector, norm = normalize_external_vector(vector)
                results[original_index] = EmbeddedText(
                    vector=normalized_vector,
                    norm=norm,
                    token_count=len(tokenize(text)),
                )

        return results

    def _request_embeddings(self, texts: list[str]) -> list[list[float]]:
        url = f"{self.api_base_url}/{self.model_name}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": texts,
            "options": {"wait_for_model": True},
        }

        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.http_client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as error:
                last_error = str(error)
            else:
                if response.status_code < 400:
                    try:
                        response_payload = response.json()
                    except ValueError as error:
                        raise EmbeddingProviderError("Hugging Face response was not valid JSON.") from error
                    return parse_huggingface_feature_response(response_payload, expected_count=len(texts))

                response_text = getattr(response, "text", "")
                last_error = f"HTTP {response.status_code}: {response_text[:300]}"
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break

            if attempt < self.max_retries:
                time.sleep(self.retry_backoff_seconds * (attempt + 1))

        raise EmbeddingProviderError(f"Hugging Face embedding request failed for model {self.model_name}: {last_error}")


def create_embedding_provider(
    *,
    provider_name: str | None = None,
    model_name: str | None = None,
    dims: int | None = None,
) -> EmbeddingProvider:
    resolved_provider = (provider_name or EMBEDDING_PROVIDER).strip().lower()
    resolved_model = (model_name or EMBEDDING_MODEL).strip()
    resolved_dims = EMBEDDING_DIMS if dims is None else dims

    if resolved_dims <= 0:
        raise EmbeddingProviderError("Embedding dimensions must be greater than 0.")

    if resolved_provider in {LOCAL_PROVIDER_NAME, "local_hashing"}:
        return LocalHashingEmbeddingProvider(
            model_name=resolved_model or LOCAL_MODEL_NAME,
            dims=resolved_dims,
        )

    if resolved_provider in {HUGGINGFACE_PROVIDER_NAME, "hf"}:
        resolved_model = HUGGINGFACE_DEFAULT_MODEL_NAME if resolved_model == LOCAL_MODEL_NAME else resolved_model
        if resolved_model == HUGGINGFACE_DEFAULT_MODEL_NAME and resolved_dims == DEFAULT_DIMS:
            resolved_dims = HUGGINGFACE_DEFAULT_DIMS
        return HuggingFaceEmbeddingProvider(
            model_name=resolved_model,
            dims=resolved_dims,
            api_key=EMBEDDING_API_KEY,
        )

    if resolved_provider in RESERVED_AI_PROVIDER_NAMES:
        raise EmbeddingProviderError(
            f"Embedding provider '{resolved_provider}' is reserved for a future external AI integration "
            "but is not implemented in this code path yet. Use EMBEDDING_PROVIDER=local for the current MVP, "
            "or implement the provider in backend/app/services/embedding_service.py before rebuilding embeddings."
        )

    supported = ", ".join(
        sorted({LOCAL_PROVIDER_NAME, "local_hashing", HUGGINGFACE_PROVIDER_NAME, "hf", *RESERVED_AI_PROVIDER_NAMES})
    )
    raise EmbeddingProviderError(f"Unsupported embedding provider: {resolved_provider}. Known providers: {supported}.")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def tokenize(text: str) -> list[str]:
    normalized = text.lower()
    tokens = TOKEN_RE.findall(normalized)
    cjk_chars = CJK_RE.findall(normalized)

    for size in (2, 3):
        if len(cjk_chars) >= size:
            tokens.extend("".join(cjk_chars[index : index + size]) for index in range(len(cjk_chars) - size + 1))

    if not tokens:
        tokens.extend(char for char in normalized if not char.isspace())
    return tokens


def token_index(token: str, dims: int) -> int:
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little") % dims


def vectorize_text(text: str, *, dims: int = DEFAULT_DIMS) -> tuple[list[float], float, int]:
    if dims <= 0:
        raise ValueError("dims must be greater than 0.")

    counts = Counter(tokenize(text))
    vector = [0.0] * dims
    for token, count in counts.items():
        vector[token_index(token, dims)] += 1.0 + math.log(count)

    norm = math.sqrt(sum(value * value for value in vector))
    if norm > 0:
        vector = [value / norm for value in vector]
    return vector, norm, len(counts)


def pack_vector(vector: Iterable[float]) -> bytes:
    values = list(vector)
    return struct.pack(f"<{len(values)}f", *values)


def unpack_vector(blob: bytes, dims: int) -> tuple[float, ...]:
    expected_size = dims * 4
    if len(blob) != expected_size:
        raise ValueError(f"Vector blob size {len(blob)} does not match dims {dims}.")
    return struct.unpack(f"<{dims}f", blob)


def dot_product(left: Iterable[float], right: Iterable[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def normalize_external_vector(vector: Sequence[float]) -> tuple[list[float], float]:
    values = [float(value) for value in vector]
    norm = math.sqrt(sum(value * value for value in values))
    if norm > 0:
        return [value / norm for value in values], norm
    return values, norm


def is_number_sequence(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, int | float) for item in value)


def average_vectors(vectors: Sequence[Sequence[float]]) -> list[float]:
    if not vectors:
        return []
    first_dims = len(vectors[0])
    if first_dims == 0:
        return []
    sums = [0.0] * first_dims
    count = 0
    for vector in vectors:
        if len(vector) != first_dims:
            raise EmbeddingProviderError("Hugging Face token embeddings have inconsistent dimensions.")
        for index, value in enumerate(vector):
            sums[index] += float(value)
        count += 1
    return [value / count for value in sums]


def coerce_huggingface_embedding(value: Any) -> list[float]:
    if isinstance(value, dict) and "embedding" in value:
        return coerce_huggingface_embedding(value["embedding"])
    if is_number_sequence(value):
        return [float(item) for item in value]
    if isinstance(value, list) and value and all(is_number_sequence(item) for item in value):
        return average_vectors(value)
    raise EmbeddingProviderError("Hugging Face response contains an unsupported embedding shape.")


def parse_huggingface_feature_response(payload: Any, *, expected_count: int) -> list[list[float]]:
    if isinstance(payload, dict):
        if "error" in payload:
            raise EmbeddingProviderError(f"Hugging Face returned an error: {payload['error']}")
        if "embeddings" in payload:
            payload = payload["embeddings"]
        elif "data" in payload:
            payload = payload["data"]
        else:
            raise EmbeddingProviderError("Hugging Face response is missing embeddings data.")

    if expected_count == 1:
        if is_number_sequence(payload):
            return [coerce_huggingface_embedding(payload)]
        if isinstance(payload, list) and payload and all(is_number_sequence(item) for item in payload):
            return [coerce_huggingface_embedding(payload)]

    if not isinstance(payload, list):
        raise EmbeddingProviderError("Hugging Face response must be a list of embeddings.")

    embeddings = [coerce_huggingface_embedding(item) for item in payload]
    if len(embeddings) != expected_count:
        raise EmbeddingProviderError(
            f"Hugging Face response contains {len(embeddings)} embeddings for {expected_count} inputs."
        )
    return embeddings


def validate_provider_embeddings(
    provider: EmbeddingProvider,
    embeddings: Sequence[EmbeddedText],
    *,
    expected_count: int,
    context_ids: Sequence[str],
) -> None:
    if len(embeddings) != expected_count:
        raise EmbeddingProviderError(
            f"Embedding provider '{provider.provider_name}' returned {len(embeddings)} embeddings "
            f"for {expected_count} input texts."
        )

    for index, embedded in enumerate(embeddings):
        context_id = context_ids[index] if index < len(context_ids) else str(index)
        if len(embedded.vector) != provider.dims:
            raise EmbeddingProviderError(
                f"Embedding vector for {context_id} has {len(embedded.vector)} dimensions, "
                f"expected {provider.dims}."
            )
        if embedded.token_count < 0:
            raise EmbeddingProviderError(f"Embedding token_count for {context_id} must not be negative.")
        if not math.isfinite(embedded.norm) or embedded.norm < 0:
            raise EmbeddingProviderError(f"Embedding norm for {context_id} must be a finite non-negative number.")
        if any(not math.isfinite(value) for value in embedded.vector):
            raise EmbeddingProviderError(f"Embedding vector for {context_id} contains non-finite values.")


def initialize_schema(connection: sqlite3.Connection) -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schema.sql"
    connection.executescript(schema_path.read_text(encoding="utf-8"))


def replace_chunk_embeddings(
    connection: sqlite3.Connection,
    rows: list[sqlite3.Row],
    *,
    model_name: str = MODEL_NAME,
    dims: int = DEFAULT_DIMS,
    provider_name: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    timestamp = created_at or now_iso()
    provider = create_embedding_provider(provider_name=provider_name, model_name=model_name, dims=dims)
    payloads: list[tuple[Any, ...]] = []
    empty_chunk_ids: list[str] = []

    texts = [row["chunk_text"] or "" for row in rows]
    embeddings = provider.embed_texts(texts)
    validate_provider_embeddings(
        provider,
        embeddings,
        expected_count=len(texts),
        context_ids=[row["chunk_id"] for row in rows],
    )
    for row, embedded in zip(rows, embeddings):
        if embedded.token_count == 0 or embedded.norm == 0:
            empty_chunk_ids.append(row["chunk_id"])
            continue
        payloads.append(
            (
                row["chunk_id"],
                provider.model_name,
                provider.dims,
                pack_vector(embedded.vector),
                embedded.norm,
                timestamp,
            )
        )

    connection.executemany(
        """
        DELETE FROM chunk_embeddings
        WHERE chunk_id = ?
          AND embedding_model = ?;
        """,
        [(row["chunk_id"], provider.model_name) for row in rows],
    )
    connection.executemany(
        """
        INSERT INTO chunk_embeddings (
          chunk_id, embedding_model, embedding_dims, embedding,
          embedding_norm, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        payloads,
    )
    return {
        "processed_chunks": len(rows),
        "embedded_chunks": len(payloads),
        "empty_chunk_count": len(empty_chunk_ids),
        "empty_chunk_ids": empty_chunk_ids[:20],
    }


def list_chunks_for_embedding(connection: sqlite3.Connection, limit: int | None = None) -> list[sqlite3.Row]:
    sql = """
        SELECT chunk_id, chunk_text
        FROM case_chunks
        ORDER BY case_id, chunk_index;
    """
    rows = connection.execute(sql).fetchall()
    return rows[:limit] if limit is not None else rows


def build_chunk_embeddings(
    db_path: Path,
    *,
    model_name: str = MODEL_NAME,
    dims: int = DEFAULT_DIMS,
    provider_name: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        initialize_schema(connection)
        rows = list_chunks_for_embedding(connection, limit)
        provider = create_embedding_provider(provider_name=provider_name, model_name=model_name, dims=dims)
        report = replace_chunk_embeddings(
            connection,
            rows,
            model_name=provider.model_name,
            dims=provider.dims,
            provider_name=provider.provider_name,
        )
        total_embeddings = connection.execute(
            """
            SELECT COUNT(*)
            FROM chunk_embeddings
            WHERE embedding_model = ?;
            """,
            (provider.model_name,),
        ).fetchone()[0]

    return {
        "database": str(db_path),
        "embedding_provider": provider.provider_name,
        "embedding_model": provider.model_name,
        "embedding_dims": provider.dims,
        "total_embeddings_in_table": int(total_embeddings),
        "created_at": now_iso(),
        **report,
    }


def semantic_search(
    query: str,
    *,
    limit: int = 10,
    model_name: str = MODEL_NAME,
    provider_name: str | None = None,
    min_score: float = 0.0,
) -> dict[str, Any]:
    provider = create_embedding_provider(provider_name=provider_name, model_name=model_name)
    query_embeddings = provider.embed_texts([query])
    validate_provider_embeddings(
        provider,
        query_embeddings,
        expected_count=1,
        context_ids=["query"],
    )
    embedded_query = query_embeddings[0]
    safe_limit = min(max(limit, 1), 50)
    if embedded_query.token_count == 0 or embedded_query.norm == 0:
        return {
            "query": query,
            "embedding_model": provider.model_name,
            "items": [],
            "total_candidates": 0,
        }

    with connect() as connection:
        rows = connection.execute(
            """
            SELECT chunk_embeddings.chunk_id, chunk_embeddings.embedding,
                   chunk_embeddings.embedding_dims,
                   case_chunks.case_id, case_chunks.chunk_index,
                   case_chunks.section_hint, case_chunks.chunk_text,
                   cases.case_number, cases.decision_date, cases.dispute_type
            FROM chunk_embeddings
            JOIN case_chunks ON case_chunks.chunk_id = chunk_embeddings.chunk_id
            JOIN cases ON cases.case_id = case_chunks.case_id
            WHERE chunk_embeddings.embedding_model = ?;
            """,
            (provider.model_name,),
        ).fetchall()

    scored: list[dict[str, Any]] = []
    for row in rows:
        candidate_vector = unpack_vector(row["embedding"], row["embedding_dims"])
        score = dot_product(embedded_query.vector, candidate_vector)
        if score <= min_score:
            continue
        scored.append(
            {
                "chunk_id": row["chunk_id"],
                "case_id": row["case_id"],
                "case_number": row["case_number"],
                "decision_date": row["decision_date"],
                "dispute_type": row["dispute_type"],
                "section_hint": row["section_hint"],
                "chunk_index": row["chunk_index"],
                "score": round(score, 4),
                "chunk_text": row["chunk_text"],
            }
        )

    scored.sort(
        key=lambda item: (
            item["score"],
            item["decision_date"] or "",
            item["case_number"] or "",
            -item["chunk_index"],
        ),
        reverse=True,
    )
    return {
        "query": query,
        "embedding_model": provider.model_name,
        "items": scored[:safe_limit],
        "total_candidates": len(scored),
    }


def case_exists(case_id: str) -> bool:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM cases
            WHERE case_id = ?
            LIMIT 1;
            """,
            (case_id,),
        ).fetchone()
    return row is not None


def normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def source_case_centroid(
    connection: sqlite3.Connection,
    *,
    case_id: str,
    model_name: str,
) -> tuple[list[float] | None, int]:
    rows = connection.execute(
        """
        SELECT chunk_embeddings.embedding, chunk_embeddings.embedding_dims
        FROM chunk_embeddings
        JOIN case_chunks ON case_chunks.chunk_id = chunk_embeddings.chunk_id
        WHERE case_chunks.case_id = ?
          AND chunk_embeddings.embedding_model = ?
        ORDER BY case_chunks.chunk_index;
        """,
        (case_id, model_name),
    ).fetchall()
    if not rows:
        return None, 0

    dims = rows[0]["embedding_dims"]
    centroid = [0.0] * dims
    for row in rows:
        vector = unpack_vector(row["embedding"], row["embedding_dims"])
        for index, value in enumerate(vector):
            centroid[index] += value

    return normalize_vector(centroid), len(rows)


def semantic_similar_cases(
    case_id: str,
    *,
    limit: int = 5,
    model_name: str = MODEL_NAME,
    provider_name: str | None = None,
    min_score: float = 0.0,
    chunks_per_case: int = 2,
) -> dict[str, Any] | None:
    if not case_exists(case_id):
        return None

    provider = create_embedding_provider(provider_name=provider_name, model_name=model_name)
    safe_limit = min(max(limit, 1), 20)
    safe_chunks_per_case = min(max(chunks_per_case, 1), 5)
    with connect() as connection:
        source_vector, source_chunk_count = source_case_centroid(
            connection,
            case_id=case_id,
            model_name=provider.model_name,
        )
        if source_vector is None:
            return {
                "case_id": case_id,
                "embedding_model": provider.model_name,
                "source_chunk_count": 0,
                "items": [],
                "total_candidates": 0,
            }

        rows = connection.execute(
            """
            SELECT chunk_embeddings.chunk_id, chunk_embeddings.embedding,
                   chunk_embeddings.embedding_dims,
                   case_chunks.case_id, case_chunks.chunk_index,
                   case_chunks.section_hint, case_chunks.chunk_text,
                   cases.case_number, cases.decision_date, cases.dispute_type
            FROM chunk_embeddings
            JOIN case_chunks ON case_chunks.chunk_id = chunk_embeddings.chunk_id
            JOIN cases ON cases.case_id = case_chunks.case_id
            WHERE chunk_embeddings.embedding_model = ?
              AND case_chunks.case_id != ?;
            """,
            (provider.model_name, case_id),
        ).fetchall()

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_vector = unpack_vector(row["embedding"], row["embedding_dims"])
        score = dot_product(source_vector, candidate_vector)
        if score <= min_score:
            continue

        candidate_case = grouped.setdefault(
            row["case_id"],
            {
                "case_id": row["case_id"],
                "case_number": row["case_number"],
                "decision_date": row["decision_date"],
                "dispute_type": row["dispute_type"],
                "score": 0.0,
                "matched_chunks": [],
            },
        )
        candidate_case["score"] = max(candidate_case["score"], score)
        candidate_case["matched_chunks"].append(
            {
                "chunk_id": row["chunk_id"],
                "section_hint": row["section_hint"],
                "chunk_index": row["chunk_index"],
                "score": round(score, 4),
                "chunk_text": row["chunk_text"],
            }
        )

    items = list(grouped.values())
    for item in items:
        item["matched_chunks"].sort(
            key=lambda chunk: (
                chunk["score"],
                -chunk["chunk_index"],
            ),
            reverse=True,
        )
        item["matched_chunks"] = item["matched_chunks"][:safe_chunks_per_case]
        item["score"] = round(item["score"], 4)

    items.sort(
        key=lambda item: (
            item["score"],
            item["decision_date"] or "",
            item["case_number"] or "",
        ),
        reverse=True,
    )
    return {
        "case_id": case_id,
        "embedding_model": provider.model_name,
        "source_chunk_count": source_chunk_count,
        "items": items[:safe_limit],
        "total_candidates": len(items),
    }
