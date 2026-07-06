from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


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
