from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.services import embedding_service
from backend.app.services import search_service


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


class FakeSentenceTransformerModel:
    def __init__(self, vectors: list[list[float]], *, dims: int = 1024, error: Exception | None = None) -> None:
        self.vectors = vectors
        self.dims = dims
        self.error = error
        self.calls = []

    def get_embedding_dimension(self) -> int:
        return self.dims

    def encode(self, texts: list[str], **kwargs):
        self.calls.append({"texts": texts, **kwargs})
        if self.error is not None:
            raise self.error
        return self.vectors[: len(texts)]


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


def test_create_local_bge_provider_uses_separate_storage_model() -> None:
    provider = embedding_service.create_embedding_provider(provider_name="local_bge")

    assert provider.provider_name == "local_bge"
    assert provider.model_name == embedding_service.LOCAL_BGE_MODEL_NAME
    assert provider.source_model_name == embedding_service.HUGGINGFACE_DEFAULT_MODEL_NAME
    assert provider.dims == 1024


def test_load_local_bge_model_uses_local_files_only(monkeypatch) -> None:
    calls = []
    fake_model = object()

    def fake_sentence_transformer(model_name: str, **kwargs):
        calls.append({"model_name": model_name, **kwargs})
        return fake_model

    monkeypatch.setitem(
        sys.modules,
        "sentence_transformers",
        SimpleNamespace(SentenceTransformer=fake_sentence_transformer),
    )
    embedding_service._LOCAL_BGE_MODEL_CACHE.clear()
    try:
        loaded_model = embedding_service.load_local_bge_model(
            embedding_service.LOCAL_BGE_SOURCE_MODEL_NAME,
            "cpu",
        )
    finally:
        embedding_service._LOCAL_BGE_MODEL_CACHE.clear()

    assert loaded_model is fake_model
    assert calls == [
        {
            "model_name": embedding_service.LOCAL_BGE_SOURCE_MODEL_NAME,
            "device": "cpu",
            "local_files_only": True,
        }
    ]


def test_local_bge_provider_embeds_with_fake_model_and_skips_empty_text() -> None:
    first_vector = [3.0, 4.0, *([0.0] * 1022)]
    second_vector = [0.0, 5.0, *([0.0] * 1022)]
    fake_model = FakeSentenceTransformerModel([first_vector, second_vector])
    loader_calls = []

    def fake_loader(model_name: str, device: str):
        loader_calls.append((model_name, device))
        return fake_model

    provider = embedding_service.LocalSentenceTransformerEmbeddingProvider(
        device="cpu",
        batch_size=2,
        model_loader=fake_loader,
    )
    embeddings = provider.embed_texts(["癌症保險金", " ", "住院日額"])

    assert len(embeddings) == 3
    assert embeddings[0].vector[:2] == [0.6, 0.8]
    assert embeddings[0].norm == 5.0
    assert embeddings[1].norm == 0.0
    assert embeddings[1].token_count == 0
    assert embeddings[2].vector[:2] == [0.0, 1.0]
    assert loader_calls == [(embedding_service.HUGGINGFACE_DEFAULT_MODEL_NAME, "cpu")]
    assert fake_model.calls[0]["texts"] == ["癌症保險金", "住院日額"]
    assert fake_model.calls[0]["normalize_embeddings"] is True
    assert fake_model.calls[0]["show_progress_bar"] is False


def test_local_bge_provider_rejects_model_dimension_mismatch() -> None:
    fake_model = FakeSentenceTransformerModel([], dims=768)
    provider = embedding_service.LocalSentenceTransformerEmbeddingProvider(
        device="cpu",
        model_loader=lambda *_: fake_model,
    )

    try:
        provider.embed_texts(["癌症保險金"])
    except embedding_service.EmbeddingProviderError as error:
        assert "returned 768 dimensions" in str(error)
        assert "expected 1024" in str(error)
    else:
        raise AssertionError("Expected EmbeddingProviderError")


def test_local_bge_provider_explains_out_of_memory_recovery() -> None:
    fake_model = FakeSentenceTransformerModel([], error=RuntimeError("CUDA out of memory"))
    provider = embedding_service.LocalSentenceTransformerEmbeddingProvider(
        device="cpu",
        model_loader=lambda *_: fake_model,
    )

    try:
        provider.embed_texts(["癌症保險金"])
    except embedding_service.EmbeddingProviderError as error:
        assert "LOCAL_BGE_BATCH_SIZE" in str(error)
        assert "LOCAL_BGE_DEVICE=cpu" in str(error)
    else:
        raise AssertionError("Expected EmbeddingProviderError")


def test_local_bge_rejects_unknown_device() -> None:
    try:
        embedding_service.resolve_local_bge_device("metal")
    except embedding_service.EmbeddingProviderError as error:
        assert "auto, cpu, cuda" in str(error)
    else:
        raise AssertionError("Expected EmbeddingProviderError")


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
        assert "huggingface" in message
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


def test_remote_huggingface_aliases_are_removed_even_when_token_exists(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_API_KEY", "hf_test")
    monkeypatch.setenv("HF_TOKEN", "hf_test")

    for alias in ("hf", "huggingface"):
        try:
            embedding_service.create_embedding_provider(provider_name=alias)
        except embedding_service.EmbeddingProviderError as error:
            assert "Inference API support was removed" in str(error)
            assert "local_bge" in str(error)
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


def test_build_chunk_embeddings_resume_only_writes_missing_chunks(tmp_path: Path) -> None:
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="case_resume",
            case_number="115年評字第000002號",
            dispute_type="理賠爭議",
            chunks=["第一段。", "第二段。", "第三段。"],
        )

    first_report = embedding_service.build_chunk_embeddings(
        db_path,
        dims=64,
        limit=1,
        write_batch_size=1,
    )
    with make_connection(db_path) as connection:
        first_row_before = connection.execute(
            """
            SELECT embedding, created_at
            FROM chunk_embeddings
            WHERE chunk_id = 'case_resume_chunk_0'
              AND embedding_model = 'local_hashing_cjk_v1';
            """
        ).fetchone()

    progress = []
    second_report = embedding_service.build_chunk_embeddings(
        db_path,
        dims=64,
        limit=1,
        resume=True,
        write_batch_size=1,
        progress_callback=progress.append,
    )
    with make_connection(db_path) as connection:
        first_row_after = connection.execute(
            """
            SELECT embedding, created_at
            FROM chunk_embeddings
            WHERE chunk_id = 'case_resume_chunk_0'
              AND embedding_model = 'local_hashing_cjk_v1';
            """
        ).fetchone()

    assert first_report["total_embeddings_in_table"] == 1
    assert first_report["remaining_chunks"] == 2
    assert second_report["existing_embeddings_before"] == 1
    assert second_report["selected_chunks"] == 1
    assert second_report["processed_chunks"] == 1
    assert second_report["total_embeddings_in_table"] == 2
    assert second_report["remaining_chunks"] == 1
    assert second_report["resume"] is True
    assert first_row_after["embedding"] == first_row_before["embedding"]
    assert first_row_after["created_at"] == first_row_before["created_at"]
    assert progress == [
        {
            "batch": 1,
            "batch_chunks": 1,
            "processed_chunks": 1,
            "selected_chunks": 1,
            "total_embeddings_in_table": 2,
        }
    ]


def test_build_chunk_embeddings_commits_completed_batches_before_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="case_partial",
            case_number="115年評字第000003號",
            dispute_type="理賠爭議",
            chunks=["第一段。", "第二段。"],
        )

    class FailingProvider:
        provider_name = "fake"
        model_name = "fake_model_v1"
        dims = 3

        def __init__(self) -> None:
            self.calls = 0

        def embed_texts(self, texts: list[str]) -> list[embedding_service.EmbeddedText]:
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("simulated provider failure")
            return [make_embedding([1.0, 0.0, 0.0]) for _ in texts]

    provider = FailingProvider()
    monkeypatch.setattr(embedding_service, "create_embedding_provider", lambda **_: provider)

    with pytest.raises(RuntimeError, match="simulated provider failure"):
        embedding_service.build_chunk_embeddings(
            db_path,
            provider_name=provider.provider_name,
            model_name=provider.model_name,
            dims=provider.dims,
            write_batch_size=1,
        )

    with make_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT chunk_id
            FROM chunk_embeddings
            WHERE embedding_model = ?
            ORDER BY chunk_id;
            """,
            (provider.model_name,),
        ).fetchall()

    assert [row["chunk_id"] for row in rows] == ["case_partial_chunk_0"]


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


def test_semantic_case_scores_returns_best_chunk_for_each_requested_case(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="case_cancer",
            case_number="115年評字第000001號",
            dispute_type="理賠爭議",
            chunks=["癌症治療後申請保險金。", "本段內容與住院日數有關。"],
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

    result = embedding_service.semantic_case_scores(
        "癌症保險金",
        case_ids=["case_hospital", "case_cancer", "case_hospital"],
    )

    assert result["embedding_provider"] == "local"
    assert [item["case_id"] for item in result["items"]] == ["case_hospital", "case_cancer"]
    scores = {item["case_id"]: item for item in result["items"]}
    assert scores["case_cancer"]["score"] > scores["case_hospital"]["score"]
    assert "癌症" in scores["case_cancer"]["chunk_text"]
    assert result["total_candidates"] == 3


def test_semantic_case_rankings_scans_all_cases_and_keeps_best_chunk(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Full semantic recall must not depend on a prior keyword candidate list."""
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="case_best",
            case_number="115年評字第000001號",
            dispute_type="必要性醫療",
            chunks=["背景段落", "住院必要性判斷"],
        )
        insert_case_with_chunks(
            connection,
            case_id="case_second",
            case_number="115年評字第000002號",
            dispute_type="承保範圍",
            chunks=["保單承保範圍"],
        )
        vectors = {
            "case_best_chunk_0": [0.2, 0.98, 0.0],
            "case_best_chunk_1": [0.95, 0.1, 0.0],
            "case_second_chunk_0": [0.8, 0.2, 0.0],
        }
        for chunk_id, vector in vectors.items():
            normalized = embedding_service.normalize_vector(vector)
            connection.execute(
                """
                INSERT INTO chunk_embeddings (
                  chunk_id, embedding_model, embedding_dims, embedding,
                  embedding_norm, created_at
                ) VALUES (?, 'fake_model_v1', 3, ?, 1.0, '2026-01-01T00:00:00Z');
                """,
                (chunk_id, embedding_service.pack_vector(normalized)),
            )

    provider = FakeEmbeddingProvider([make_embedding([1.0, 0.0, 0.0])])
    monkeypatch.setattr(embedding_service, "connect", lambda: make_connection(db_path))
    monkeypatch.setattr(embedding_service, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(embedding_service, "create_embedding_provider", lambda **_: provider)

    result = embedding_service.semantic_case_rankings(
        "住院後遭拒賠",
        provider_name="fake",
        model_name="fake_model_v1",
    )

    assert result["total_cases"] == 2
    assert result["total_candidates"] == 3
    assert [item["case_id"] for item in result["items"]] == ["case_best", "case_second"]
    assert result["items"][0]["semantic_snippet"] == "住院必要性判斷"
    assert result["items"][0]["similarity_score"] > result["items"][1]["similarity_score"]


def test_semantic_ranked_search_sorts_all_matches_before_pagination_and_uses_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    # 兩案都命中關鍵字，但只有 case_high 的 chunk 與查詢高度接近。
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="case_low",
            case_number="115年評字第000001號",
            dispute_type="癌症理賠",
            chunks=["住院日額與住院天數計算爭議。"],
        )
        insert_case_with_chunks(
            connection,
            case_id="case_high",
            case_number="115年評字第000002號",
            dispute_type="癌症理賠",
            chunks=["癌症標靶治療後申請癌症保險金。"],
        )
        for case_id, case_number, normalized_text in (
            ("case_low", "115年評字第000001號", "癌症保險金爭議，涉及住院日數。"),
            ("case_high", "115年評字第000002號", "癌症標靶治療後申請癌症保險金。"),
        ):
            connection.execute(
                "INSERT INTO case_texts (case_id, normalized_text) VALUES (?, ?);",
                (case_id, normalized_text),
            )
            connection.execute(
                "INSERT INTO case_summaries (case_id, holding) VALUES (?, '本中心就申請人之請求尚難為有利之認定。');",
                (case_id,),
            )
            connection.execute(
                """
                INSERT INTO case_search (case_id, case_number, dispute_type, normalized_text)
                VALUES (?, ?, '癌症理賠', ?);
                """,
                (case_id, case_number, normalized_text),
            )
    embedding_service.build_chunk_embeddings(db_path)

    monkeypatch.setattr(embedding_service, "connect", lambda: make_connection(db_path))
    monkeypatch.setattr(search_service, "connect", lambda: make_connection(db_path))
    monkeypatch.setattr(embedding_service, "DEFAULT_DB_PATH", db_path)
    embedding_service.clear_semantic_ranked_search_cache()

    # 第二頁必須沿用同一份全域排名；若先分頁再評分，這個順序就無法成立。
    first_page = embedding_service.semantic_ranked_search(
        "癌症",
        page=1,
        page_size=1,
        provider_name="local",
        model_name=embedding_service.LOCAL_MODEL_NAME,
    )
    second_page = embedding_service.semantic_ranked_search(
        "癌症",
        page=2,
        page_size=1,
        provider_name="local",
        model_name=embedding_service.LOCAL_MODEL_NAME,
    )

    assert first_page["total"] == 2
    assert first_page["items"][0]["case_id"] == "case_high"
    assert first_page["cached"] is False
    assert second_page["items"][0]["case_id"] == "case_low"
    assert second_page["cached"] is True
    assert first_page["items"][0]["similarity_score"] > second_page["items"][0]["similarity_score"]


def test_semantic_search_uses_stored_dims_when_global_dims_differ(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="case_cancer",
            case_number="115年評字第000001號",
            dispute_type="承保範圍",
            chunks=["癌症住院治療是否屬於保險契約承保範圍"],
        )
    embedding_service.build_chunk_embeddings(db_path)

    monkeypatch.setattr(embedding_service, "connect", lambda: make_connection(db_path))
    monkeypatch.setattr(embedding_service, "EMBEDDING_DIMS", 1024)

    result = embedding_service.semantic_search(
        "癌症保險",
        provider_name="local",
        model_name=embedding_service.LOCAL_MODEL_NAME,
        limit=1,
    )

    assert result["embedding_dims"] == 384
    assert result["embedding_provider"] == "local"
    assert result["items"][0]["case_id"] == "case_cancer"


def test_semantic_search_rejects_model_without_embeddings_before_embedding(tmp_path: Path, monkeypatch) -> None:
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
    embedding_service.build_chunk_embeddings(db_path)

    monkeypatch.setattr(embedding_service, "connect", lambda: make_connection(db_path))

    embed_calls = 0

    @dataclass(frozen=True)
    class MissingModelProvider:
        provider_name: str = "local"
        model_name: str = "missing_model_v1"
        dims: int = 384

        def embed_texts(self, texts: list[str]):
            nonlocal embed_calls
            embed_calls += 1
            return []

    monkeypatch.setattr(
        embedding_service,
        "create_embedding_provider",
        lambda **_: MissingModelProvider(),
    )

    try:
        embedding_service.semantic_search(
            "癌症保險金",
            provider_name="local",
            model_name="missing_model_v1",
            limit=2,
        )
    except embedding_service.EmbeddingProviderError as error:
        assert "No stored embeddings" in str(error)
        assert "missing_model_v1" in str(error)
    else:
        raise AssertionError("Expected EmbeddingProviderError")

    assert embed_calls == 0


def test_embedding_status_reports_models_without_loading_provider(tmp_path: Path, monkeypatch) -> None:
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
    embedding_service.build_chunk_embeddings(db_path)
    monkeypatch.setattr(embedding_service, "connect", lambda: make_connection(db_path))
    monkeypatch.setattr(embedding_service, "DEFAULT_DB_PATH", db_path)

    status = embedding_service.get_embedding_status()

    assert status["database_name"] == "insurance_cases.db"
    assert status["models"] == [
        {
            "embedding_model": "local_hashing_cjk_v1",
            "embedding_dims": 384,
            "embedding_count": 1,
            "suggested_provider": "local",
        }
    ]


def test_semantic_search_rejects_query_provider_dimension_mismatch(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "insurance_cases.db"
    bge_model = embedding_service.HUGGINGFACE_DEFAULT_MODEL_NAME
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="case_cancer",
            case_number="115年評字第000001號",
            dispute_type="理賠爭議",
            chunks=["癌症治療後申請保險金，保險公司拒絕理賠。"],
        )
        connection.execute(
            """
            INSERT INTO chunk_embeddings (
              chunk_id, embedding_model, embedding_dims, embedding,
              embedding_norm, created_at
            )
            VALUES (?, ?, ?, ?, 1.0, '2026-01-01T00:00:00Z');
            """,
            (
                "case_cancer_chunk_0",
                bge_model,
                embedding_service.HUGGINGFACE_DEFAULT_DIMS,
                embedding_service.pack_vector([1.0] + [0.0] * (embedding_service.HUGGINGFACE_DEFAULT_DIMS - 1)),
            ),
        )

    monkeypatch.setattr(embedding_service, "connect", lambda: make_connection(db_path))

    try:
        embedding_service.semantic_search(
            "癌症保險金",
            provider_name="local",
            model_name=bge_model,
            limit=2,
        )
    except embedding_service.EmbeddingProviderError as error:
        assert "Use a matching embedding_provider" in str(error)
        assert bge_model in str(error)
        assert embedding_service.LOCAL_MODEL_NAME in str(error)
    else:
        raise AssertionError("Expected EmbeddingProviderError")


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


def test_semantic_similar_cases_returns_empty_for_model_without_embeddings(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "insurance_cases.db"
    with make_connection(db_path) as connection:
        connection.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        insert_case_with_chunks(
            connection,
            case_id="source_case",
            case_number="115年評字第000001號",
            dispute_type="理賠爭議",
            chunks=["癌症治療後申請保險金，保險公司拒絕理賠。"],
        )
    embedding_service.build_chunk_embeddings(db_path)
    with make_connection(db_path) as connection:
        connection.execute(
            "DELETE FROM chunk_embeddings WHERE embedding_model = ?;",
            (embedding_service.LOCAL_MODEL_NAME,),
        )

    monkeypatch.setattr(embedding_service, "connect", lambda: make_connection(db_path))

    result = embedding_service.semantic_similar_cases(
        "source_case",
        provider_name="local",
        model_name=embedding_service.LOCAL_MODEL_NAME,
        limit=2,
    )

    assert result is not None
    assert result["case_id"] == "source_case"
    assert result["embedding_model"] == embedding_service.LOCAL_MODEL_NAME
    assert result["source_chunk_count"] == 0
    assert result["total_candidates"] == 0
    assert result["items"] == []


def test_semantic_similar_cases_returns_none_for_missing_case() -> None:
    assert embedding_service.semantic_similar_cases("not-a-real-case-id") is None
