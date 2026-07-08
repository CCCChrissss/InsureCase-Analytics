from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import struct
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from backend.app.database import connect

MODEL_NAME = "local_hashing_cjk_v1"
DEFAULT_DIMS = 384
TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


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
    created_at: str | None = None,
) -> dict[str, Any]:
    timestamp = created_at or now_iso()
    payloads: list[tuple[Any, ...]] = []
    empty_chunk_ids: list[str] = []

    for row in rows:
        vector, norm, token_count = vectorize_text(row["chunk_text"] or "", dims=dims)
        if token_count == 0 or norm == 0:
            empty_chunk_ids.append(row["chunk_id"])
            continue
        payloads.append(
            (
                row["chunk_id"],
                model_name,
                dims,
                pack_vector(vector),
                norm,
                timestamp,
            )
        )

    connection.executemany(
        """
        DELETE FROM chunk_embeddings
        WHERE chunk_id = ?
          AND embedding_model = ?;
        """,
        [(row["chunk_id"], model_name) for row in rows],
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
    limit: int | None = None,
) -> dict[str, Any]:
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        initialize_schema(connection)
        rows = list_chunks_for_embedding(connection, limit)
        report = replace_chunk_embeddings(connection, rows, model_name=model_name, dims=dims)
        total_embeddings = connection.execute(
            """
            SELECT COUNT(*)
            FROM chunk_embeddings
            WHERE embedding_model = ?;
            """,
            (model_name,),
        ).fetchone()[0]

    return {
        "database": str(db_path),
        "embedding_model": model_name,
        "embedding_dims": dims,
        "total_embeddings_in_table": int(total_embeddings),
        "created_at": now_iso(),
        **report,
    }


def semantic_search(
    query: str,
    *,
    limit: int = 10,
    model_name: str = MODEL_NAME,
    min_score: float = 0.0,
) -> dict[str, Any]:
    vector, norm, token_count = vectorize_text(query)
    safe_limit = min(max(limit, 1), 50)
    if token_count == 0 or norm == 0:
        return {
            "query": query,
            "embedding_model": model_name,
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
            (model_name,),
        ).fetchall()

    scored: list[dict[str, Any]] = []
    for row in rows:
        candidate_vector = unpack_vector(row["embedding"], row["embedding_dims"])
        score = dot_product(vector, candidate_vector)
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
        "embedding_model": model_name,
        "items": scored[:safe_limit],
        "total_candidates": len(scored),
    }
