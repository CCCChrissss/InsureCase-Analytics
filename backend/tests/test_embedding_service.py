from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.app.services import embedding_service


def insert_case_with_chunks(
    connection: sqlite3.Connection,
    *,
    case_id: str,
    case_number: str,
    dispute_type: str,
    chunks: list[str],
) -> None:
    connection.execute(
        """
        INSERT INTO cases (
          case_id, case_number, roc_year, decision_date, dispute_type,
          created_at, updated_at
        )
        VALUES (?, ?, 115, '115.01.01', ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z');
        """,
        (case_id, case_number, dispute_type),
    )
    for index, chunk_text in enumerate(chunks):
        connection.execute(
            """
            INSERT INTO case_chunks (
              chunk_id, case_id, chunk_index, section_hint, chunk_text,
              char_start, char_end, chunk_chars, created_at
            )
            VALUES (?, ?, ?, '判斷理由', ?, 0, ?, ?, '2026-01-01T00:00:00Z');
            """,
            (
                f"{case_id}_chunk_{index}",
                case_id,
                index,
                chunk_text,
                len(chunk_text),
                len(chunk_text),
            ),
        )


def make_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def test_vectorize_text_is_deterministic() -> None:
    first, first_norm, first_token_count = embedding_service.vectorize_text("癌症 理賠 保險金", dims=32)
    second, second_norm, second_token_count = embedding_service.vectorize_text("癌症 理賠 保險金", dims=32)

    assert first == second
    assert first_norm == second_norm
    assert first_token_count == second_token_count
    assert first_token_count > 0


def test_create_local_embedding_provider() -> None:
    provider = embedding_service.create_embedding_provider(
        provider_name="local",
        model_name="local_hashing_cjk_v1",
        dims=32,
    )

    embedded = provider.embed_texts(["癌症 保險金"])[0]

    assert provider.provider_name == "local"
    assert provider.model_name == "local_hashing_cjk_v1"
    assert provider.dims == 32
    assert len(embedded.vector) == 32
    assert embedded.token_count > 0


def test_openai_embedding_provider_is_explicitly_not_implemented() -> None:
    try:
        embedding_service.create_embedding_provider(provider_name="openai")
    except embedding_service.EmbeddingProviderError as error:
        assert "not implemented" in str(error)
    else:
        raise AssertionError("Expected EmbeddingProviderError")


def test_build_chunk_embeddings_writes_one_embedding_per_chunk(tmp_path: Path) -> None:
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="case_a",
            case_number="115年評字第000001號",
            dispute_type="理賠爭議",
            chunks=["癌症治療後申請保險金，保險公司拒絕理賠。", "判斷理由認為需檢視保單條款。"],
        )

    report = embedding_service.build_chunk_embeddings(db_path, dims=64)

    assert report["processed_chunks"] == 2
    assert report["embedded_chunks"] == 2
    assert report["total_embeddings_in_table"] == 2
    assert report["empty_chunk_count"] == 0


def test_semantic_search_ranks_related_chunk_first(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="case_cancer",
            case_number="115年評字第000001號",
            dispute_type="理賠爭議",
            chunks=["癌症治療後申請保險金，保險公司拒絕理賠。"],
        )
        insert_case_with_chunks(
            connection,
            case_id="case_hospital",
            case_number="115年評字第000002號",
            dispute_type="住院爭議",
            chunks=["住院日額保險金與住院天數計算爭議。"],
        )
    embedding_service.build_chunk_embeddings(db_path)

    monkeypatch.setattr(embedding_service, "connect", lambda: make_connection(db_path))

    result = embedding_service.semantic_search("癌症保險金", limit=2)

    assert result["total_candidates"] >= 1
    assert result["items"][0]["case_id"] == "case_cancer"
    assert result["items"][0]["score"] > 0


def test_semantic_similar_cases_groups_chunks_by_case(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="source_case",
            case_number="115年評字第000001號",
            dispute_type="理賠爭議",
            chunks=["癌症治療後申請保險金，保險公司拒絕理賠。", "判斷理由檢視癌症保單條款。"],
        )
        insert_case_with_chunks(
            connection,
            case_id="related_case",
            case_number="115年評字第000002號",
            dispute_type="理賠爭議",
            chunks=["癌症保險金給付與保單條款解釋爭議。", "相對人主張不符合癌症給付條件。"],
        )
        insert_case_with_chunks(
            connection,
            case_id="unrelated_case",
            case_number="115年評字第000003號",
            dispute_type="住院爭議",
            chunks=["住院日額保險金與住院天數計算爭議。"],
        )
    embedding_service.build_chunk_embeddings(db_path)

    monkeypatch.setattr(embedding_service, "connect", lambda: make_connection(db_path))

    result = embedding_service.semantic_similar_cases("source_case", limit=2)

    assert result is not None
    assert result["case_id"] == "source_case"
    assert result["source_chunk_count"] == 2
    assert result["items"][0]["case_id"] == "related_case"
    assert result["items"][0]["score"] > 0
    assert result["items"][0]["matched_chunks"]
    assert result["items"][0]["matched_chunks"][0]["chunk_text"]


def test_semantic_similar_cases_returns_none_for_missing_case() -> None:
    assert embedding_service.semantic_similar_cases("not-a-real-case-id") is None
