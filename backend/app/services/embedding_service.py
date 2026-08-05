from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import struct
import threading
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol, Sequence

from backend.app.config import EMBEDDING_DIMS
from backend.app.config import EMBEDDING_MODEL
from backend.app.config import EMBEDDING_PROVIDER
from backend.app.config import LOCAL_BGE_BATCH_SIZE
from backend.app.config import LOCAL_BGE_DEVICE
from backend.app.database import connect
from backend.app.database import DEFAULT_DB_PATH
from backend.app.services.case_service import clamp_pagination
from backend.app.services.search_service import search_all_cases

LOCAL_PROVIDER_NAME = "local"
LOCAL_MODEL_NAME = "local_hashing_cjk_v1"
HUGGINGFACE_PROVIDER_NAME = "huggingface"
HUGGINGFACE_DEFAULT_MODEL_NAME = "BAAI/bge-large-zh-v1.5"
HUGGINGFACE_DEFAULT_DIMS = 1024
HUGGINGFACE_REMOTE_DISABLED_MESSAGE = (
    "Hugging Face Inference API support was removed to prevent external API usage and billing. "
    "Use provider 'local_bge' with model 'BAAI/bge-large-zh-v1.5-local'."
)
LOCAL_BGE_PROVIDER_NAME = "local_bge"
LOCAL_BGE_MODEL_NAME = "BAAI/bge-large-zh-v1.5-local"
LOCAL_BGE_SOURCE_MODEL_NAME = HUGGINGFACE_DEFAULT_MODEL_NAME
LOCAL_BGE_DIMS = HUGGINGFACE_DEFAULT_DIMS
LOCAL_BGE_PROVIDER_ALIASES = {LOCAL_BGE_PROVIDER_NAME, "local_transformer", "sentence_transformers"}
RESERVED_AI_PROVIDER_NAMES = {"openai", "ai"}
MODEL_NAME = EMBEDDING_MODEL
DEFAULT_DIMS = EMBEDDING_DIMS
TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_LOCAL_BGE_MODEL_CACHE: dict[tuple[str, str], Any] = {}
_LOCAL_BGE_MODEL_CACHE_LOCK = threading.Lock()
_LOCAL_BGE_INFERENCE_LOCK = threading.Lock()
# 全域排序成本較高；LRU 只保留最近 16 組完整排名，避免記憶體無限制成長。
_SEMANTIC_RANKED_SEARCH_CACHE: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
_SEMANTIC_RANKED_SEARCH_CACHE_LOCK = threading.Lock()
SEMANTIC_RANKED_SEARCH_CACHE_SIZE = 16


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


def resolve_local_bge_device(requested_device: str) -> str:
    device = requested_device.strip().lower()
    if device not in {"auto", "cpu", "cuda"}:
        raise EmbeddingProviderError("LOCAL_BGE_DEVICE must be one of: auto, cpu, cuda.")
    if device == "cpu":
        return device

    try:
        import torch
    except ImportError as error:
        raise EmbeddingProviderError(
            "local_bge requires the optional local AI dependencies. "
            "Install them with: py -m pip install -r requirements-local-ai.txt"
        ) from error

    cuda_available = bool(torch.cuda.is_available())
    if device == "cuda" and not cuda_available:
        raise EmbeddingProviderError(
            "LOCAL_BGE_DEVICE=cuda was requested, but PyTorch cannot access CUDA. "
            "Use LOCAL_BGE_DEVICE=cpu or install a CUDA-enabled PyTorch build."
        )
    return "cuda" if cuda_available else "cpu"


def load_local_bge_model(model_name: str, device: str) -> Any:
    cache_key = (model_name, device)
    with _LOCAL_BGE_MODEL_CACHE_LOCK:
        cached = _LOCAL_BGE_MODEL_CACHE.get(cache_key)
        if cached is not None:
            return cached
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise EmbeddingProviderError(
                "local_bge requires the optional local AI dependencies. "
                "Install them with: py -m pip install -r requirements-local-ai.txt"
            ) from error

        try:
            model = SentenceTransformer(model_name, device=device, local_files_only=True)
        except OSError as error:
            raise EmbeddingProviderError(
                f"Local BGE model '{model_name}' was not found in the local Hugging Face cache. "
                "Download the model explicitly before running local_bge; automatic network access is disabled."
            ) from error
        _LOCAL_BGE_MODEL_CACHE[cache_key] = model
        return model


class LocalSentenceTransformerEmbeddingProvider:
    provider_name = LOCAL_BGE_PROVIDER_NAME

    def __init__(
        self,
        *,
        model_name: str = LOCAL_BGE_MODEL_NAME,
        source_model_name: str = LOCAL_BGE_SOURCE_MODEL_NAME,
        dims: int = LOCAL_BGE_DIMS,
        device: str = LOCAL_BGE_DEVICE,
        batch_size: int = LOCAL_BGE_BATCH_SIZE,
        model_loader: Callable[[str, str], Any] = load_local_bge_model,
    ) -> None:
        if model_name != LOCAL_BGE_MODEL_NAME:
            raise EmbeddingProviderError(
                f"local_bge currently supports storage model '{LOCAL_BGE_MODEL_NAME}' only."
            )
        if dims != LOCAL_BGE_DIMS:
            raise EmbeddingProviderError(f"local_bge requires {LOCAL_BGE_DIMS} embedding dimensions.")
        if batch_size <= 0:
            raise EmbeddingProviderError("LOCAL_BGE_BATCH_SIZE must be greater than 0.")

        self.model_name = model_name
        self.source_model_name = source_model_name
        self.dims = dims
        self.requested_device = device
        self.batch_size = batch_size
        self.model_loader = model_loader
        self._model: Any | None = None
        self._resolved_device: str | None = None

    @property
    def resolved_device(self) -> str:
        if self._resolved_device is None:
            self._resolved_device = resolve_local_bge_device(self.requested_device)
        return self._resolved_device

    def _get_model(self) -> Any:
        if self._model is None:
            self._model = self.model_loader(self.source_model_name, self.resolved_device)
            get_dims = getattr(self._model, "get_embedding_dimension", None)
            if not callable(get_dims):
                get_dims = getattr(self._model, "get_sentence_embedding_dimension", None)
            model_dims = get_dims() if callable(get_dims) else None
            if model_dims is not None and int(model_dims) != self.dims:
                raise EmbeddingProviderError(
                    f"Local BGE model returned {model_dims} dimensions, expected {self.dims}."
                )
        return self._model

    def embed_texts(self, texts: list[str]) -> list[EmbeddedText]:
        results = [EmbeddedText(vector=[0.0] * self.dims, norm=0.0, token_count=0) for _ in texts]
        indexed_texts = [(index, text) for index, text in enumerate(texts) if text and text.strip()]
        if not indexed_texts:
            return results

        model = self._get_model()
        for start in range(0, len(indexed_texts), self.batch_size):
            batch = indexed_texts[start : start + self.batch_size]
            try:
                with _LOCAL_BGE_INFERENCE_LOCK:
                    encoded = model.encode(
                        [text for _, text in batch],
                        batch_size=self.batch_size,
                        normalize_embeddings=True,
                        convert_to_numpy=True,
                        show_progress_bar=False,
                    )
            except RuntimeError as error:
                if "out of memory" in str(error).lower():
                    raise EmbeddingProviderError(
                        "Local BGE ran out of memory. Lower LOCAL_BGE_BATCH_SIZE or set LOCAL_BGE_DEVICE=cpu."
                    ) from error
                raise

            vectors = encoded.tolist() if hasattr(encoded, "tolist") else encoded
            if not isinstance(vectors, list) or len(vectors) != len(batch):
                raise EmbeddingProviderError(
                    f"Local BGE returned an invalid batch with {len(vectors) if isinstance(vectors, list) else 0} "
                    f"embeddings for {len(batch)} texts."
                )
            for (original_index, text), vector in zip(batch, vectors, strict=True):
                if not isinstance(vector, list):
                    raise EmbeddingProviderError("Local BGE returned a non-list embedding vector.")
                normalized_vector, norm = normalize_external_vector(vector)
                results[original_index] = EmbeddedText(
                    vector=normalized_vector,
                    norm=norm,
                    token_count=len(tokenize(text)),
                )
        return results


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
        if resolved_model != LOCAL_MODEL_NAME:
            raise EmbeddingProviderError(
                f"Local hashing provider supports model '{LOCAL_MODEL_NAME}' only. "
                f"Use a matching embedding_provider for model '{resolved_model}'."
            )
        return LocalHashingEmbeddingProvider(
            model_name=resolved_model,
            dims=resolved_dims,
        )

    if resolved_provider in LOCAL_BGE_PROVIDER_ALIASES:
        if resolved_model in {LOCAL_MODEL_NAME, HUGGINGFACE_DEFAULT_MODEL_NAME}:
            resolved_model = LOCAL_BGE_MODEL_NAME
        if resolved_dims == DEFAULT_DIMS:
            resolved_dims = LOCAL_BGE_DIMS
        return LocalSentenceTransformerEmbeddingProvider(
            model_name=resolved_model,
            dims=resolved_dims,
            device=LOCAL_BGE_DEVICE,
            batch_size=LOCAL_BGE_BATCH_SIZE,
        )

    if resolved_provider in {HUGGINGFACE_PROVIDER_NAME, "hf"}:
        raise EmbeddingProviderError(HUGGINGFACE_REMOTE_DISABLED_MESSAGE)

    if resolved_provider in RESERVED_AI_PROVIDER_NAMES:
        raise EmbeddingProviderError(
            f"Embedding provider '{resolved_provider}' is reserved for a future external AI integration "
            "but is not implemented in this code path yet. Use EMBEDDING_PROVIDER=local for the current MVP, "
            "or implement the provider in backend/app/services/embedding_service.py before rebuilding embeddings."
        )

    supported = ", ".join(
        sorted(
            {
                LOCAL_PROVIDER_NAME,
                "local_hashing",
                *LOCAL_BGE_PROVIDER_ALIASES,
                HUGGINGFACE_PROVIDER_NAME,
                "hf",
                *RESERVED_AI_PROVIDER_NAMES,
            }
        )
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
    provider: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    timestamp = created_at or now_iso()
    provider = provider or create_embedding_provider(
        provider_name=provider_name,
        model_name=model_name,
        dims=dims,
    )
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


def list_chunks_for_embedding(
    connection: sqlite3.Connection,
    limit: int | None = None,
    *,
    missing_embedding_model: str | None = None,
) -> list[sqlite3.Row]:
    if limit is not None and limit <= 0:
        raise ValueError("limit must be greater than 0.")

    params: list[Any] = []
    if missing_embedding_model is None:
        sql = """
            SELECT c.chunk_id, c.chunk_text
            FROM case_chunks AS c
        """
    else:
        sql = """
            SELECT c.chunk_id, c.chunk_text
            FROM case_chunks AS c
            LEFT JOIN chunk_embeddings AS e
              ON e.chunk_id = c.chunk_id
             AND e.embedding_model = ?
            WHERE e.chunk_id IS NULL
        """
        params.append(missing_embedding_model)

    sql += " ORDER BY c.case_id, c.chunk_index"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)

    return connection.execute(f"{sql};", params).fetchall()


def build_chunk_embeddings(
    db_path: Path,
    *,
    model_name: str = MODEL_NAME,
    dims: int = DEFAULT_DIMS,
    provider_name: str | None = None,
    limit: int | None = None,
    resume: bool = False,
    write_batch_size: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if write_batch_size is not None and write_batch_size <= 0:
        raise ValueError("write_batch_size must be greater than 0.")

    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        initialize_schema(connection)
        provider = create_embedding_provider(provider_name=provider_name, model_name=model_name, dims=dims)
        existing_embeddings_before = int(
            connection.execute(
                "SELECT COUNT(*) FROM chunk_embeddings WHERE embedding_model = ?;",
                (provider.model_name,),
            ).fetchone()[0]
        )
        rows = list_chunks_for_embedding(
            connection,
            limit,
            missing_embedding_model=provider.model_name if resume else None,
        )
        effective_batch_size = write_batch_size or max(len(rows), 1)
        processed_chunks = 0
        embedded_chunks = 0
        empty_chunk_count = 0
        empty_chunk_ids: list[str] = []
        batches_completed = 0

        for batch_index, start in enumerate(range(0, len(rows), effective_batch_size), start=1):
            batch_rows = rows[start : start + effective_batch_size]
            try:
                batch_report = replace_chunk_embeddings(
                    connection,
                    batch_rows,
                    model_name=provider.model_name,
                    dims=provider.dims,
                    provider_name=provider.provider_name,
                    provider=provider,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

            processed_chunks += int(batch_report["processed_chunks"])
            embedded_chunks += int(batch_report["embedded_chunks"])
            empty_chunk_count += int(batch_report["empty_chunk_count"])
            empty_chunk_ids.extend(batch_report["empty_chunk_ids"])
            batches_completed = batch_index

            if progress_callback is not None:
                total_embeddings = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM chunk_embeddings WHERE embedding_model = ?;",
                        (provider.model_name,),
                    ).fetchone()[0]
                )
                progress_callback(
                    {
                        "batch": batch_index,
                        "batch_chunks": len(batch_rows),
                        "processed_chunks": processed_chunks,
                        "selected_chunks": len(rows),
                        "total_embeddings_in_table": total_embeddings,
                    }
                )

        total_embeddings = connection.execute(
            """
            SELECT COUNT(*)
            FROM chunk_embeddings
            WHERE embedding_model = ?;
            """,
            (provider.model_name,),
        ).fetchone()[0]
        remaining_chunks = connection.execute(
            """
            SELECT COUNT(*)
            FROM case_chunks AS c
            LEFT JOIN chunk_embeddings AS e
              ON e.chunk_id = c.chunk_id
             AND e.embedding_model = ?
            WHERE e.chunk_id IS NULL;
            """,
            (provider.model_name,),
        ).fetchone()[0]

    result = {
        "database": str(db_path),
        "embedding_provider": provider.provider_name,
        "embedding_model": provider.model_name,
        "embedding_dims": provider.dims,
        "total_embeddings_in_table": int(total_embeddings),
        "existing_embeddings_before": existing_embeddings_before,
        "selected_chunks": len(rows),
        "remaining_chunks": int(remaining_chunks),
        "resume": resume,
        "write_batch_size": write_batch_size,
        "batches_completed": batches_completed,
        "created_at": now_iso(),
        "processed_chunks": processed_chunks,
        "embedded_chunks": embedded_chunks,
        "empty_chunk_count": empty_chunk_count,
        "empty_chunk_ids": empty_chunk_ids[:20],
    }
    if isinstance(provider, LocalSentenceTransformerEmbeddingProvider):
        result["embedding_source_model"] = provider.source_model_name
        result["embedding_device"] = provider.resolved_device
    return result


def semantic_search(
    query: str,
    *,
    limit: int = 10,
    model_name: str = MODEL_NAME,
    provider_name: str | None = None,
    min_score: float = 0.0,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    resolved_provider_name = (provider_name or EMBEDDING_PROVIDER).strip().lower()
    resolved_model_name = (model_name or EMBEDDING_MODEL).strip()
    if resolved_provider_name in LOCAL_BGE_PROVIDER_ALIASES and resolved_model_name in {
        LOCAL_MODEL_NAME,
        HUGGINGFACE_DEFAULT_MODEL_NAME,
    }:
        resolved_model_name = LOCAL_BGE_MODEL_NAME

    if resolved_provider_name not in {LOCAL_PROVIDER_NAME, "local_hashing", *LOCAL_BGE_PROVIDER_ALIASES}:
        create_embedding_provider(
            provider_name=resolved_provider_name,
            model_name=resolved_model_name,
        )

    with connect() as connection:
        inventory_row = connection.execute(
            """
            SELECT COUNT(*) AS embedding_count,
                   MIN(embedding_dims) AS min_dims,
                   MAX(embedding_dims) AS max_dims
            FROM chunk_embeddings
            WHERE embedding_model = ?;
            """,
            (resolved_model_name,),
        ).fetchone()

    embedding_count = int(inventory_row["embedding_count"])
    if embedding_count == 0:
        raise EmbeddingProviderError(
            f"No stored embeddings were found for model '{resolved_model_name}' in database "
            f"'{DEFAULT_DB_PATH.name}'. Start the API with a database that contains this model."
        )

    min_dims = int(inventory_row["min_dims"])
    max_dims = int(inventory_row["max_dims"])
    if min_dims != max_dims:
        raise EmbeddingProviderError(
            f"Stored embeddings for model '{resolved_model_name}' contain mixed dimensions: "
            f"{min_dims} and {max_dims}. Rebuild the model embeddings before searching."
        )

    provider = create_embedding_provider(
        provider_name=resolved_provider_name,
        model_name=resolved_model_name,
        dims=min_dims,
    )
    if min_dims != provider.dims:
        raise EmbeddingProviderError(
            f"Stored embeddings for model '{provider.model_name}' have {min_dims} dimensions, "
            f"but query provider '{provider.provider_name}' produces {provider.dims} dimensions. "
            "Use a matching embedding_provider for the selected embedding_model."
        )

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
            "embedding_provider": provider.provider_name,
            "embedding_model": provider.model_name,
            "embedding_dims": provider.dims,
            "embedding_device": embedding_device(provider),
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "items": [],
            "total_candidates": embedding_count,
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
        "embedding_provider": provider.provider_name,
        "embedding_model": provider.model_name,
        "embedding_dims": provider.dims,
        "embedding_device": embedding_device(provider),
        "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "items": scored[:safe_limit],
        "total_candidates": len(rows),
    }


def semantic_case_scores(
    query: str,
    *,
    case_ids: Sequence[str],
    model_name: str = MODEL_NAME,
    provider_name: str | None = None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    unique_case_ids = list(dict.fromkeys(case_id.strip() for case_id in case_ids if case_id.strip()))
    if not unique_case_ids:
        raise EmbeddingProviderError("At least one case ID is required for semantic scoring.")
    if len(unique_case_ids) > 20:
        raise EmbeddingProviderError("At most 20 case IDs can be scored at once.")

    resolved_provider_name = (provider_name or EMBEDDING_PROVIDER).strip().lower()
    resolved_model_name = (model_name or EMBEDDING_MODEL).strip()
    if resolved_provider_name in LOCAL_BGE_PROVIDER_ALIASES and resolved_model_name in {
        LOCAL_MODEL_NAME,
        HUGGINGFACE_DEFAULT_MODEL_NAME,
    }:
        resolved_model_name = LOCAL_BGE_MODEL_NAME

    with connect() as connection:
        inventory_row = connection.execute(
            """
            SELECT COUNT(*) AS embedding_count,
                   MIN(embedding_dims) AS min_dims,
                   MAX(embedding_dims) AS max_dims
            FROM chunk_embeddings
            WHERE embedding_model = ?;
            """,
            (resolved_model_name,),
        ).fetchone()

    embedding_count = int(inventory_row["embedding_count"])
    if embedding_count == 0:
        raise EmbeddingProviderError(
            f"No stored embeddings were found for model '{resolved_model_name}' in database "
            f"'{DEFAULT_DB_PATH.name}'. Start the API with a database that contains this model."
        )
    min_dims = int(inventory_row["min_dims"])
    max_dims = int(inventory_row["max_dims"])
    if min_dims != max_dims:
        raise EmbeddingProviderError(
            f"Stored embeddings for model '{resolved_model_name}' contain mixed dimensions: "
            f"{min_dims} and {max_dims}. Rebuild the model embeddings before searching."
        )

    provider = create_embedding_provider(
        provider_name=resolved_provider_name,
        model_name=resolved_model_name,
        dims=min_dims,
    )
    if min_dims != provider.dims:
        raise EmbeddingProviderError(
            f"Stored embeddings for model '{provider.model_name}' have {min_dims} dimensions, "
            f"but query provider '{provider.provider_name}' produces {provider.dims} dimensions. "
            "Use a matching embedding_provider for the selected embedding_model."
        )

    query_embeddings = provider.embed_texts([query])
    validate_provider_embeddings(
        provider,
        query_embeddings,
        expected_count=1,
        context_ids=["query"],
    )
    embedded_query = query_embeddings[0]
    if embedded_query.token_count == 0 or embedded_query.norm == 0:
        rows: list[sqlite3.Row] = []
    else:
        placeholders = ", ".join("?" for _ in unique_case_ids)
        with connect() as connection:
            rows = connection.execute(
                f"""
                SELECT chunk_embeddings.chunk_id, chunk_embeddings.embedding,
                       chunk_embeddings.embedding_dims,
                       case_chunks.case_id, case_chunks.chunk_index,
                       case_chunks.section_hint, case_chunks.chunk_text
                FROM chunk_embeddings
                JOIN case_chunks ON case_chunks.chunk_id = chunk_embeddings.chunk_id
                WHERE chunk_embeddings.embedding_model = ?
                  AND case_chunks.case_id IN ({placeholders});
                """,
                (provider.model_name, *unique_case_ids),
            ).fetchall()

    best_by_case: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_vector = unpack_vector(row["embedding"], row["embedding_dims"])
        score = dot_product(embedded_query.vector, candidate_vector)
        current = best_by_case.get(row["case_id"])
        if current is None or score > current["score"]:
            best_by_case[row["case_id"]] = {
                "case_id": row["case_id"],
                "score": score,
                "section_hint": row["section_hint"],
                "chunk_index": row["chunk_index"],
                "chunk_text": row["chunk_text"],
            }

    items = []
    for case_id in unique_case_ids:
        item = best_by_case.get(case_id)
        if item is None:
            continue
        items.append({**item, "score": round(item["score"], 4)})

    return {
        "query": query,
        "embedding_provider": provider.provider_name,
        "embedding_model": provider.model_name,
        "embedding_dims": provider.dims,
        "embedding_device": embedding_device(provider),
        "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "items": items,
        "total_candidates": len(rows),
    }


def clear_semantic_ranked_search_cache() -> None:
    """Clear process-local ranked results after tests or an explicit data refresh."""
    with _SEMANTIC_RANKED_SEARCH_CACHE_LOCK:
        _SEMANTIC_RANKED_SEARCH_CACHE.clear()


def semantic_ranked_database_key() -> tuple[str, int | None, int | None]:
    """Include DB identity in cache keys so replacing the database invalidates old rankings."""
    try:
        stat = DEFAULT_DB_PATH.stat()
    except OSError:
        return str(DEFAULT_DB_PATH), None, None
    return str(DEFAULT_DB_PATH.resolve()), stat.st_mtime_ns, stat.st_size


def semantic_ranked_search(
    query: str,
    *,
    page: int = 1,
    page_size: int = 20,
    model_name: str | None = None,
    provider_name: str | None = None,
) -> dict[str, Any]:
    """Score all keyword matches, sort globally, then return the requested page."""
    started_at = time.perf_counter()
    cleaned_query = query.strip()
    safe_page, safe_page_size, offset = clamp_pagination(page, page_size)
    resolved_provider_name = (provider_name or EMBEDDING_PROVIDER).strip().lower()
    resolved_model_name = (model_name or EMBEDDING_MODEL).strip()
    if resolved_provider_name in LOCAL_BGE_PROVIDER_ALIASES and resolved_model_name in {
        LOCAL_MODEL_NAME,
        HUGGINGFACE_DEFAULT_MODEL_NAME,
    }:
        resolved_model_name = LOCAL_BGE_MODEL_NAME

    cache_key = (
        cleaned_query,
        resolved_provider_name,
        resolved_model_name,
        semantic_ranked_database_key(),
    )
    with _SEMANTIC_RANKED_SEARCH_CACHE_LOCK:
        cached_result = _SEMANTIC_RANKED_SEARCH_CACHE.get(cache_key)
        if cached_result is not None:
            _SEMANTIC_RANKED_SEARCH_CACHE.move_to_end(cache_key)

    cache_hit = cached_result is not None
    if cached_result is None:
        keyword_matches = search_all_cases(cleaned_query)
        with connect() as connection:
            inventory_row = connection.execute(
                """
                SELECT COUNT(*) AS embedding_count,
                       MIN(embedding_dims) AS min_dims,
                       MAX(embedding_dims) AS max_dims
                FROM chunk_embeddings
                WHERE embedding_model = ?;
                """,
                (resolved_model_name,),
            ).fetchone()

        embedding_count = int(inventory_row["embedding_count"])
        if embedding_count == 0:
            raise EmbeddingProviderError(
                f"No stored embeddings were found for model '{resolved_model_name}' in database "
                f"'{DEFAULT_DB_PATH.name}'. Start the API with a database that contains this model."
            )
        min_dims = int(inventory_row["min_dims"])
        max_dims = int(inventory_row["max_dims"])
        if min_dims != max_dims:
            raise EmbeddingProviderError(
                f"Stored embeddings for model '{resolved_model_name}' contain mixed dimensions: "
                f"{min_dims} and {max_dims}. Rebuild the model embeddings before searching."
            )

        provider = create_embedding_provider(
            provider_name=resolved_provider_name,
            model_name=resolved_model_name,
            dims=min_dims,
        )
        if min_dims != provider.dims:
            raise EmbeddingProviderError(
                f"Stored embeddings for model '{provider.model_name}' have {min_dims} dimensions, "
                f"but query provider '{provider.provider_name}' produces {provider.dims} dimensions. "
                "Use a matching embedding_provider for the selected embedding_model."
            )

        query_embeddings = provider.embed_texts([cleaned_query])
        validate_provider_embeddings(
            provider,
            query_embeddings,
            expected_count=1,
            context_ids=["query"],
        )
        embedded_query = query_embeddings[0]
        matched_case_ids = {item["case_id"] for item in keyword_matches["items"]}
        rows: list[sqlite3.Row] = []
        if matched_case_ids and embedded_query.token_count > 0 and embedded_query.norm > 0:
            ordered_case_ids = sorted(matched_case_ids)
            with connect() as connection:
                # 分批建立 IN 查詢，避免一次帶入過多 SQLite bind parameters。
                for start in range(0, len(ordered_case_ids), 500):
                    batch_case_ids = ordered_case_ids[start : start + 500]
                    placeholders = ", ".join("?" for _ in batch_case_ids)
                    rows.extend(
                        connection.execute(
                            f"""
                            SELECT chunk_embeddings.embedding, chunk_embeddings.embedding_dims,
                                   case_chunks.case_id, case_chunks.chunk_index,
                                   case_chunks.section_hint, case_chunks.chunk_text
                            FROM chunk_embeddings
                            JOIN case_chunks ON case_chunks.chunk_id = chunk_embeddings.chunk_id
                            WHERE chunk_embeddings.embedding_model = ?
                              AND case_chunks.case_id IN ({placeholders});
                            """,
                            (provider.model_name, *batch_case_ids),
                        ).fetchall()
                    )

        # 查詢對案件分數採用最高 chunk 分數，保留最能說明命中的段落。
        best_by_case: dict[str, dict[str, Any]] = {}
        for row in rows:
            candidate_vector = unpack_vector(row["embedding"], row["embedding_dims"])
            score = dot_product(embedded_query.vector, candidate_vector)
            current = best_by_case.get(row["case_id"])
            if current is None or score > current["similarity_score"]:
                best_by_case[row["case_id"]] = {
                    "similarity_score": score,
                    "section_hint": row["section_hint"],
                    "chunk_index": row["chunk_index"],
                    "semantic_snippet": row["chunk_text"],
                }

        ranked_items = []
        for item in keyword_matches["items"]:
            semantic_match = best_by_case.get(item["case_id"])
            ranked_items.append(
                {
                    **item,
                    "similarity_score": (
                        round(semantic_match["similarity_score"], 4) if semantic_match is not None else None
                    ),
                    "section_hint": semantic_match["section_hint"] if semantic_match is not None else None,
                    "chunk_index": semantic_match["chunk_index"] if semantic_match is not None else None,
                    "semantic_snippet": semantic_match["semantic_snippet"] if semantic_match is not None else None,
                }
            )

        # 缺少 embedding 的案件仍保留，但會排在所有有分數的案件之後。
        ranked_items.sort(
            key=lambda item: (
                item["similarity_score"] is not None,
                item["similarity_score"] if item["similarity_score"] is not None else -1.0,
                item["decision_date"] or "",
                item["case_number"] or "",
            ),
            reverse=True,
        )
        cached_result = {
            "query": query,
            "embedding_provider": provider.provider_name,
            "embedding_model": provider.model_name,
            "embedding_dims": provider.dims,
            "embedding_device": embedding_device(provider),
            "items": ranked_items,
            "total": keyword_matches["total"],
            "total_candidates": len(rows),
            "match_source": keyword_matches["match_source"],
        }
        with _SEMANTIC_RANKED_SEARCH_CACHE_LOCK:
            _SEMANTIC_RANKED_SEARCH_CACHE[cache_key] = cached_result
            _SEMANTIC_RANKED_SEARCH_CACHE.move_to_end(cache_key)
            # OrderedDict 最前方是最久未使用的結果，超量時逐筆淘汰。
            while len(_SEMANTIC_RANKED_SEARCH_CACHE) > SEMANTIC_RANKED_SEARCH_CACHE_SIZE:
                _SEMANTIC_RANKED_SEARCH_CACHE.popitem(last=False)

    assert cached_result is not None
    return {
        **{key: value for key, value in cached_result.items() if key != "items"},
        "items": cached_result["items"][offset : offset + safe_page_size],
        "page": safe_page,
        "page_size": safe_page_size,
        "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "cached": cache_hit,
    }


def embedding_device(provider: EmbeddingProvider) -> str:
    if isinstance(provider, LocalSentenceTransformerEmbeddingProvider):
        return provider.resolved_device
    return "cpu"


def suggested_provider_for_model(model_name: str) -> str:
    if model_name == LOCAL_BGE_MODEL_NAME:
        return LOCAL_BGE_PROVIDER_NAME
    if model_name == LOCAL_MODEL_NAME:
        return LOCAL_PROVIDER_NAME
    return "unknown"


def get_embedding_status() -> dict[str, Any]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT embedding_model, embedding_dims, COUNT(*) AS embedding_count
            FROM chunk_embeddings
            GROUP BY embedding_model, embedding_dims
            ORDER BY embedding_model, embedding_dims;
            """
        ).fetchall()

    return {
        "database_name": DEFAULT_DB_PATH.name,
        "configured_provider": EMBEDDING_PROVIDER,
        "configured_model": EMBEDDING_MODEL,
        "local_bge_requested_device": LOCAL_BGE_DEVICE,
        "models": [
            {
                "embedding_model": row["embedding_model"],
                "embedding_dims": int(row["embedding_dims"]),
                "embedding_count": int(row["embedding_count"]),
                "suggested_provider": suggested_provider_for_model(row["embedding_model"]),
            }
            for row in rows
        ],
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
