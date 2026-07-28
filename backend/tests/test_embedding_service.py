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


class FakeEmbeddingProvider:
    provider_name = "fake"
    model_name = "fake_model_v1"
    dims = 3

    def __init__(self, embeddings: list[embedding_service.EmbeddedText]) -> None:
        self.embeddings = embeddings

    def embed_texts(self, texts: list[str]) -> list[embedding_service.EmbeddedText]:
        return self.embeddings


def make_embedding(vector: list[float], *, norm: float = 1.0, token_count: int = 1) -> embedding_service.EmbeddedText:
    return embedding_service.EmbeddedText(vector=vector, norm=norm, token_count=token_count)


def select_chunk_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT chunk_id, chunk_text
        FROM case_chunks
        ORDER BY case_id, chunk_index;
        """
    ).fetchall()


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
        assert "EMBEDDING_PROVIDER=local" in str(error)
    else:
        raise AssertionError("Expected EmbeddingProviderError")


def test_ai_embedding_provider_is_explicitly_reserved() -> None:
    try:
        embedding_service.create_embedding_provider(provider_name="ai")
    except embedding_service.EmbeddingProviderError as error:
        assert "reserved for a future external AI integration" in str(error)
        assert "embedding_service.py" in str(error)
    else:
        raise AssertionError("Expected EmbeddingProviderError")


def test_unsupported_embedding_provider_lists_known_options() -> None:
    try:
        embedding_service.create_embedding_provider(provider_name="unknown")
    except embedding_service.EmbeddingProviderError as error:
        message = str(error)
        assert "Unsupported embedding provider: unknown" in message
        assert "local" in message
        assert "openai" in message
    else:
        raise AssertionError("Expected EmbeddingProviderError")


def test_embedding_provider_rejects_invalid_dimensions() -> None:
    try:
        embedding_service.create_embedding_provider(provider_name="local", dims=0)
    except embedding_service.EmbeddingProviderError as error:
        assert "dimensions must be greater than 0" in str(error)
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
    assert report["embedding_provider"] == "local"
    assert report["embedding_model"] == "local_hashing_cjk_v1"
    assert report["embedding_dims"] == 64
    assert report["total_embeddings_in_table"] == 2
    assert report["empty_chunk_count"] == 0


def test_replace_chunk_embeddings_accepts_fake_provider_output(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="case_fake",
            case_number="115年評字第000010號",
            dispute_type="理賠爭議",
            chunks=["癌症保險金爭議。", "保單條款解釋。"],
        )
        fake_provider = FakeEmbeddingProvider(
            [
                make_embedding([1.0, 0.0, 0.0]),
                make_embedding([0.0, 1.0, 0.0]),
            ]
        )
        monkeypatch.setattr(embedding_service, "create_embedding_provider", lambda **_: fake_provider)

        report = embedding_service.replace_chunk_embeddings(connection, select_chunk_rows(connection))
        row = connection.execute(
            """
            SELECT COUNT(*) AS count, MIN(embedding_dims) AS dims
            FROM chunk_embeddings
            WHERE embedding_model = ?;
            """,
            (fake_provider.model_name,),
        ).fetchone()

    assert report["processed_chunks"] == 2
    assert report["embedded_chunks"] == 2
    assert report["empty_chunk_count"] == 0
    assert row["count"] == 2
    assert row["dims"] == fake_provider.dims


def test_replace_chunk_embeddings_skips_empty_fake_provider_output(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="case_empty",
            case_number="115年評字第000011號",
            dispute_type="理賠爭議",
            chunks=["   "],
        )
        fake_provider = FakeEmbeddingProvider([make_embedding([0.0, 0.0, 0.0], norm=0.0, token_count=0)])
        monkeypatch.setattr(embedding_service, "create_embedding_provider", lambda **_: fake_provider)

        report = embedding_service.replace_chunk_embeddings(connection, select_chunk_rows(connection))
        count = connection.execute("SELECT COUNT(*) FROM chunk_embeddings;").fetchone()[0]

    assert report["processed_chunks"] == 1
    assert report["embedded_chunks"] == 0
    assert report["empty_chunk_count"] == 1
    assert report["empty_chunk_ids"] == ["case_empty_chunk_0"]
    assert count == 0


def test_validate_provider_embeddings_rejects_count_mismatch() -> None:
    provider = FakeEmbeddingProvider([make_embedding([1.0, 0.0, 0.0])])

    try:
        embedding_service.validate_provider_embeddings(
            provider,
            provider.embeddings,
            expected_count=2,
            context_ids=["chunk_1", "chunk_2"],
        )
    except embedding_service.EmbeddingProviderError as error:
        assert "returned 1 embeddings for 2 input texts" in str(error)
    else:
        raise AssertionError("Expected EmbeddingProviderError")


def test_validate_provider_embeddings_rejects_dimension_mismatch() -> None:
    provider = FakeEmbeddingProvider([make_embedding([1.0, 0.0])])

    try:
        embedding_service.validate_provider_embeddings(
            provider,
            provider.embeddings,
            expected_count=1,
            context_ids=["chunk_bad_dims"],
        )
    except embedding_service.EmbeddingProviderError as error:
        assert "chunk_bad_dims" in str(error)
        assert "expected 3" in str(error)
    else:
        raise AssertionError("Expected EmbeddingProviderError")


def test_validate_provider_embeddings_rejects_non_finite_values() -> None:
    provider = FakeEmbeddingProvider([make_embedding([1.0, float("nan"), 0.0])])

    try:
        embedding_service.validate_provider_embeddings(
            provider,
            provider.embeddings,
            expected_count=1,
            context_ids=["chunk_nan"],
        )
    except embedding_service.EmbeddingProviderError as error:
        assert "chunk_nan" in str(error)
        assert "non-finite" in str(error)
    else:
        raise AssertionError("Expected EmbeddingProviderError")


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
