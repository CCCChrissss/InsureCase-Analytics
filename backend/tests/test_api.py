from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app
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


def test_case_detail_not_found() -> None:
    response = client.get("/api/cases/not-a-real-case-id")

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
    assert data["items"][0]["match_source"] in {
        "fts5",
        "like_fallback_error",
        "like_fallback_empty_fts5",
    }


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
            "embedding_model": kwargs["model_name"],
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
