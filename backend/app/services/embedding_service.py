from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import struct
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol

from backend.app.config import EMBEDDING_DIMS
from backend.app.config import EMBEDDING_MODEL
from backend.app.config import EMBEDDING_PROVIDER
from backend.app.database import connect

LOCAL_PROVIDER_NAME = "local"
LOCAL_MODEL_NAME = "local_hashing_cjk_v1"
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


def create_embedding_provider(
    *,
    provider_name: str | None = None,
    model_name: str | None = None,
    dims: int | None = None,
) -> EmbeddingProvider:
    resolved_provider = (provider_name or EMBEDDING_PROVIDER).strip().lower()
    resolved_model = (model_name or EMBEDDING_MODEL).strip()
    resolved_dims = dims or EMBEDDING_DIMS

    if resolved_provider in {LOCAL_PROVIDER_NAME, "local_hashing"}:
        return LocalHashingEmbeddingProvider(
            model_name=resolved_model or LOCAL_MODEL_NAME,
            dims=resolved_dims,
        )

    if resolved_provider in {"openai", "ai"}:
        raise EmbeddingProviderError(
            "OpenAI embedding provider is configured but not implemented in this code path yet. "
            "Use EMBEDDING_PROVIDER=local for the current MVP, or add an OpenAI provider implementation before rebuilding embeddings."
        )

    raise EmbeddingProviderError(f"Unsupported embedding provider: {resolved_provider}")


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
    embedded_query = provider.embed_texts([query])[0]
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
