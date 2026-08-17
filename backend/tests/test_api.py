from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.database import connect
from backend.app.routers import search as search_router
from backend.app.routers import semantic_search as semantic_search_router
from backend.app.routers import similar_cases as similar_cases_router


client = TestClient(app)


def first_case_id() -> str:
    response = client.get("/api/cases", params={"page_size": 1})
    assert response.status_code == 200
    return response.json()["items"][0]["case_id"]


def test_health() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert isinstance(data["database_ready"], bool)


def test_statistics_overview() -> None:
    response = client.get("/api/statistics/overview")

    assert response.status_code == 200
    data = response.json()
    assert data["case_count"] >= 1
    assert data["dispute_type_count"] >= 1
    assert isinstance(data["roc_years"], list)


def test_statistics_supports_roc_year_filter() -> None:
    overview_response = client.get("/api/statistics/overview")
    roc_year = overview_response.json()["roc_years"][0]

    filtered_overview = client.get("/api/statistics/overview", params={"roc_year": roc_year})
    filtered_disputes = client.get("/api/dispute-types", params={"roc_year": roc_year})

    assert filtered_overview.status_code == 200
    assert filtered_overview.json()["case_count"] >= 1
    assert filtered_disputes.status_code == 200
    assert len(filtered_disputes.json()) >= 1
    assert sum(item["count"] for item in filtered_disputes.json()) == filtered_overview.json()["case_count"]


def test_cases() -> None:
    response = client.get("/api/cases", params={"page_size": 1})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["case_id"]
    assert data["items"][0]["case_number"]


def test_case_detail_includes_metadata_and_text() -> None:
    case_id = first_case_id()

    response = client.get(f"/api/cases/{case_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == case_id
    assert data["case_number"]
    assert data["roc_year"] in {114, 115}
    assert data["dispute_type"]
    assert data["pdf_path"]
    assert data["metadata_path"]
    assert data["normalized_text"]
    assert data["normalized_text_chars"] == len(data["normalized_text"])
    assert data["raw_text_chars"] >= data["normalized_text_chars"]


def test_case_detail_returns_complete_longest_normalized_text() -> None:
    # 使用目前資料庫最長案件，比短樣本更容易抓到 API 或序列化層的靜默截斷。
    with connect() as connection:
        row = connection.execute(
            """
            SELECT case_id, normalized_text, normalized_text_chars
            FROM case_texts
            WHERE normalized_text IS NOT NULL
            ORDER BY LENGTH(normalized_text) DESC
            LIMIT 1;
            """
        ).fetchone()

    assert row is not None
    response = client.get(f"/api/cases/{row['case_id']}")

    assert response.status_code == 200
    returned_text = response.json()["normalized_text"]
    assert returned_text == row["normalized_text"]
    assert len(returned_text) == row["normalized_text_chars"]
    assert returned_text[:200] == row["normalized_text"][:200]
    assert returned_text[len(returned_text) // 2 - 100 : len(returned_text) // 2 + 100] == (
        row["normalized_text"][len(row["normalized_text"]) // 2 - 100 : len(row["normalized_text"]) // 2 + 100]
    )
    assert returned_text[-200:] == row["normalized_text"][-200:]


def test_case_detail_not_found() -> None:
    response = client.get("/api/cases/not-a-real-case-id")

    assert response.status_code == 404


def test_case_document_sections_preserve_source_and_respondent_claim() -> None:
    # Select a real decision with the respondent heading so the API test covers
    # the exact field that was previously absent from the Dashboard.
    with connect() as connection:
        row = connection.execute(
            """
            SELECT case_id, normalized_text
            FROM case_texts
            WHERE normalized_text LIKE '%三、相對人之主張%'
            ORDER BY LENGTH(normalized_text) DESC
            LIMIT 1;
            """
        ).fetchone()

    assert row is not None
    response = client.get(f"/api/cases/{row['case_id']}/document-sections")

    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "normalized"
    assert data["complete_coverage"] is True
    assert data["source_chars"] == len(row["normalized_text"])
    assert data["covered_chars"] == data["source_chars"]
    assert "".join(section["content"] for section in data["sections"]) == row["normalized_text"]
    assert any(section["section_type"] == "respondent_claim" for section in data["sections"])


def test_case_document_sections_not_found() -> None:
    response = client.get("/api/cases/not-a-real-case-id/document-sections")

    assert response.status_code == 404


def test_case_pdf() -> None:
    case_id = first_case_id()

    response = client.get(f"/api/files/{case_id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_case_pdf_not_found() -> None:
    response = client.get("/api/files/not-a-real-case-id/pdf")

    assert response.status_code == 404


def test_search_cancer() -> None:
    response = client.get("/api/search", params={"q": "癌症", "page_size": 5})

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "癌症"
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    assert "decision_result" in data["items"][0]
    assert data["items"][0]["match_source"] in {
        "fts5",
        "like_fallback_error",
        "like_fallback_empty_fts5",
    }


@pytest.mark.parametrize(
    ("query", "expected_suggestion"),
    (
        ("違反告知義務", "要保人隱匿病史保險公司解除契約"),
        ("手術認定", "醫療處置是否符合保單手術定義"),
        ("業務招攬", "業務員招攬過程未充分說明保單"),
        ("豁免保費", "被保險人失能或罹癌後免繳保險費"),
    ),
)
def test_query_suggestions_returns_approved_suggestion(
    query: str,
    expected_suggestion: str,
) -> None:
    response = client.get("/api/query-suggestions", params={"q": query})

    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert data["original_query"] == query
    assert data["suggested_query"] == expected_suggestion
    assert data["rule_id"]
    assert data["explanation"]
    assert data["auto_apply"] is False


@pytest.mark.parametrize("query", ("癌症", "除外責任", "理賠金額"))
def test_query_suggestions_returns_unavailable_for_unapproved_query(query: str) -> None:
    response = client.get("/api/query-suggestions", params={"q": query})

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "original_query": query,
        "suggested_query": None,
        "rule_id": None,
        "explanation": None,
        "auto_apply": False,
    }


def test_query_suggestions_rejects_blank_query() -> None:
    response = client.get("/api/query-suggestions", params={"q": "   "})

    assert response.status_code == 422
    assert response.json()["detail"] == "Query must not be blank."


def test_case_summary_not_found() -> None:
    response = client.get("/api/cases/not-a-real-case-id/summary")

    assert response.status_code == 404


def test_case_summary() -> None:
    case_id = first_case_id()

    response = client.get(f"/api/cases/{case_id}/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == case_id
    assert data["summary_method"] == "rule_based_v1"
    assert data["holding"]
    assert data["reasoning"]


def test_similar_cases() -> None:
    case_id = first_case_id()

    response = client.get(f"/api/cases/{case_id}/similar", params={"limit": 5})

    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == case_id
    assert data["total_candidates"] >= 1
    assert 1 <= len(data["items"]) <= 5
    assert all(item["case_id"] != case_id for item in data["items"])
    assert data["items"][0]["score"] > 0
    assert data["items"][0]["matched_reasons"]


def test_similar_cases_not_found() -> None:
    response = client.get("/api/cases/not-a-real-case-id/similar")

    assert response.status_code == 404


def test_semantic_similar_cases() -> None:
    case_id = first_case_id()

    response = client.get(
        f"/api/cases/{case_id}/semantic-similar",
        params={"limit": 2, "chunks_per_case": 1},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == case_id
    assert data["embedding_model"] == "local_hashing_cjk_v1"
    assert data["source_chunk_count"] >= 1
    assert data["total_candidates"] >= 1
    assert 1 <= len(data["items"]) <= 2
    assert all(item["case_id"] != case_id for item in data["items"])
    assert data["items"][0]["score"] > 0
    assert len(data["items"][0]["matched_chunks"]) == 1
    assert data["items"][0]["matched_chunks"][0]["chunk_text"]


def test_semantic_similar_cases_not_found() -> None:
    response = client.get("/api/cases/not-a-real-case-id/semantic-similar")

    assert response.status_code == 404


def test_semantic_search_accepts_embedding_model_params(monkeypatch) -> None:
    captured = {}

    def fake_semantic_search(query: str, **kwargs):
        kwargs["query"] = query
        captured.update(kwargs)
        return {
            "query": query,
            "embedding_provider": kwargs["provider_name"],
            "embedding_model": kwargs["model_name"],
            "embedding_dims": 1024,
            "embedding_device": "cuda",
            "elapsed_ms": 12.5,
            "items": [],
            "total_candidates": 0,
        }

    monkeypatch.setattr(semantic_search_router, "semantic_search", fake_semantic_search)

    response = client.get(
        "/api/semantic-search",
        params={
            "q": "癌症保險金",
            "embedding_model": "BAAI/bge-large-zh-v1.5",
            "embedding_provider": "huggingface",
        },
    )

    assert response.status_code == 200
    assert captured["query"] == "癌症保險金"
    assert captured["model_name"] == "BAAI/bge-large-zh-v1.5"
    assert captured["provider_name"] == "huggingface"
    assert response.json()["embedding_model"] == "BAAI/bge-large-zh-v1.5"
    assert response.json()["embedding_provider"] == "huggingface"
    assert response.json()["embedding_device"] == "cuda"


def test_semantic_case_scores_accepts_page_case_ids(monkeypatch) -> None:
    captured = {}

    def fake_semantic_case_scores(query: str, **kwargs):
        captured["query"] = query
        captured.update(kwargs)
        return {
            "query": query,
            "embedding_provider": kwargs["provider_name"],
            "embedding_model": kwargs["model_name"],
            "embedding_dims": 1024,
            "embedding_device": "cuda",
            "elapsed_ms": 8.5,
            "items": [
                {
                    "case_id": "case_1",
                    "score": 0.8123,
                    "section_hint": "判斷理由",
                    "chunk_index": 2,
                    "chunk_text": "癌症住院治療是否符合保單約定。",
                }
            ],
            "total_candidates": 6,
        }

    monkeypatch.setattr(semantic_search_router, "semantic_case_scores", fake_semantic_case_scores)

    response = client.get(
        "/api/semantic-case-scores",
        params={
            "q": "癌症住院",
            "case_ids": "case_1,case_2,case_1",
            "embedding_model": "BAAI/bge-large-zh-v1.5-local",
            "embedding_provider": "local_bge",
        },
    )

    assert response.status_code == 200
    assert captured["query"] == "癌症住院"
    assert captured["case_ids"] == ["case_1", "case_2"]
    assert response.json()["items"][0]["score"] == 0.8123


def test_semantic_case_scores_rejects_more_than_twenty_cases() -> None:
    response = client.get(
        "/api/semantic-case-scores",
        params={
            "q": "癌症住院",
            "case_ids": ",".join(f"case_{index}" for index in range(21)),
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "At most 20 case IDs can be scored at once."


def test_semantic_ranked_search_accepts_pagination_and_model_params(monkeypatch) -> None:
    # Router 測試隔離本機模型，只驗證參數轉交與 response schema。
    captured = {}

    def fake_semantic_ranked_search(query: str, **kwargs):
        captured["query"] = query
        captured.update(kwargs)
        return {
            "query": query,
            "embedding_provider": kwargs["provider_name"],
            "embedding_model": kwargs["model_name"],
            "embedding_dims": 1024,
            "embedding_device": "cuda",
            "elapsed_ms": 7.5,
            "cached": False,
            "items": [
                {
                    "case_id": "case_1",
                    "case_number": "115年評字第000001號",
                    "decision_date": "115.01.09",
                    "dispute_type": "癌症理賠",
                    "decision_result": "無理由",
                    "snippet": "癌症保險金爭議。",
                    "match_source": "fts5",
                    "similarity_score": 0.8123,
                    "section_hint": "判斷理由",
                    "chunk_index": 2,
                    "semantic_snippet": "癌症住院治療是否符合約定。",
                }
            ],
            "total": 21,
            "total_candidates": 120,
            "match_source": "fts5",
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
        }

    monkeypatch.setattr(semantic_search_router, "semantic_ranked_search", fake_semantic_ranked_search)

    response = client.get(
        "/api/semantic-ranked-search",
        params={
            "q": "癌症",
            "page": 2,
            "page_size": 15,
            "embedding_model": "BAAI/bge-large-zh-v1.5-local",
            "embedding_provider": "local_bge",
        },
    )

    assert response.status_code == 200
    assert captured["query"] == "癌症"
    assert captured["page"] == 2
    assert captured["page_size"] == 15
    assert response.json()["items"][0]["similarity_score"] == 0.8123
    assert response.json()["total"] == 21


def test_hybrid_search_accepts_narrative_and_model_params(monkeypatch) -> None:
    """The public route must pass the full narrative to semantic recall unchanged."""
    captured = {}

    def fake_hybrid_search(query: str, **kwargs):
        captured["query"] = query
        captured.update(kwargs)
        return {
            "query": query,
            "embedding_provider": kwargs["provider_name"],
            "embedding_model": kwargs["model_name"],
            "embedding_dims": 1024,
            "embedding_device": "cuda",
            "elapsed_ms": 12.5,
            "cached": False,
            "search_mode": "hybrid",
            "fallback_reason": None,
            "items": [
                {
                    "case_id": "case_1",
                    "case_number": "115年評字第000001號",
                    "decision_date": "115.01.09",
                    "dispute_type": "必要性醫療",
                    "decision_result": "無理由",
                    "snippet": "住院治療並不符合醫療必要性。",
                    "match_source": "semantic",
                    "similarity_score": 0.8123,
                    "ranking_score": 0.03278689,
                    "semantic_rank": 1,
                    "keyword_rank": None,
                    "section_hint": "判斷理由",
                    "chunk_index": 2,
                    "semantic_snippet": "住院治療並不符合醫療必要性。",
                    "match_type": "semantic",
                }
            ],
            "total": 2992,
            "keyword_match_count": 0,
            "semantic_case_count": 2992,
            "total_candidates": 17254,
            "match_source": "fts5",
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
        }

    monkeypatch.setattr(search_router, "hybrid_search", fake_hybrid_search)
    narrative = "住院幾天後，保險公司認為沒有住院必要性，因此拒絕理賠。"
    response = client.post(
        "/api/hybrid-search",
        json={
            "q": narrative,
            "page": 1,
            "page_size": 15,
            "embedding_model": "BAAI/bge-large-zh-v1.5-local",
            "embedding_provider": "local_bge",
        },
    )

    assert response.status_code == 200
    assert captured["query"] == narrative
    assert captured["provider_name"] == "local_bge"
    assert response.json()["items"][0]["match_type"] == "semantic"
    assert response.json()["keyword_match_count"] == 0


def test_embedding_status_reports_available_models(monkeypatch) -> None:
    monkeypatch.setattr(
        semantic_search_router,
        "get_embedding_status",
        lambda: {
            "database_name": "insurance_cases_local_bge_trial.db",
            "configured_provider": "local_bge",
            "configured_model": "BAAI/bge-large-zh-v1.5-local",
            "local_bge_requested_device": "cuda",
            "models": [
                {
                    "embedding_model": "BAAI/bge-large-zh-v1.5-local",
                    "embedding_dims": 1024,
                    "embedding_count": 17254,
                    "suggested_provider": "local_bge",
                }
            ],
        },
    )

    response = client.get("/api/embedding-status")

    assert response.status_code == 200
    data = response.json()
    assert data["database_name"] == "insurance_cases_local_bge_trial.db"
    assert data["models"][0]["embedding_count"] == 17254
    assert data["models"][0]["suggested_provider"] == "local_bge"


def test_semantic_search_returns_400_for_invalid_embedding_provider(monkeypatch) -> None:
    def fake_semantic_search(*_, **__):
        raise semantic_search_router.EmbeddingProviderError("Unsupported embedding provider: bad.")

    monkeypatch.setattr(semantic_search_router, "semantic_search", fake_semantic_search)

    response = client.get(
        "/api/semantic-search",
        params={"q": "癌症保險金", "embedding_provider": "bad"},
    )

    assert response.status_code == 400
    assert "Unsupported embedding provider" in response.json()["detail"]


def test_semantic_similar_accepts_embedding_model_params(monkeypatch) -> None:
    captured = {}

    def fake_semantic_similar_cases(case_id: str, **kwargs):
        captured["case_id"] = case_id
        captured.update(kwargs)
        return {
            "case_id": case_id,
            "embedding_model": kwargs["model_name"],
            "source_chunk_count": 0,
            "items": [],
            "total_candidates": 0,
        }

    monkeypatch.setattr(similar_cases_router, "semantic_similar_cases", fake_semantic_similar_cases)

    response = client.get(
        "/api/cases/case_demo/semantic-similar",
        params={
            "embedding_model": "BAAI/bge-large-zh-v1.5",
            "embedding_provider": "huggingface",
        },
    )

    assert response.status_code == 200
    assert captured["case_id"] == "case_demo"
    assert captured["model_name"] == "BAAI/bge-large-zh-v1.5"
    assert captured["provider_name"] == "huggingface"
    assert response.json()["embedding_model"] == "BAAI/bge-large-zh-v1.5"


def test_semantic_similar_returns_400_for_invalid_embedding_provider(monkeypatch) -> None:
    def fake_semantic_similar_cases(*_, **__):
        raise similar_cases_router.EmbeddingProviderError("Unsupported embedding provider: bad.")

    monkeypatch.setattr(similar_cases_router, "semantic_similar_cases", fake_semantic_similar_cases)

    response = client.get(
        "/api/cases/case_demo/semantic-similar",
        params={"embedding_provider": "bad"},
    )

    assert response.status_code == 400
    assert "Unsupported embedding provider" in response.json()["detail"]


def test_roc114_quality_report() -> None:
    response = client.get("/api/quality/roc114-summary-similarity")

    assert response.status_code == 200
    data = response.json()
    assert data["scope"]["roc_year"] == 114
    assert data["scope"]["case_count"] == 2500
    assert data["similar_stats"]["top1_same_dispute_type_rate"] == 99.92
    assert len(data["sample_cases"]) == 10
    assert len(data["known_exceptions"]) == 2
