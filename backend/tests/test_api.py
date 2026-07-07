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


def test_statistics_supports_roc_year_filter() -> None:
    overview_response = client.get("/api/statistics/overview")
    roc_year = overview_response.json()["roc_years"][0]

    filtered_overview = client.get("/api/statistics/overview", params={"roc_year": roc_year})
    filtered_disputes = client.get("/api/statistics/dispute-types", params={"roc_year": roc_year})
    filtered_dates = client.get("/api/statistics/decision-dates", params={"roc_year": roc_year})

    assert filtered_overview.status_code == 200
    assert filtered_overview.json()["case_count"] >= 1
    assert filtered_disputes.status_code == 200
    assert len(filtered_disputes.json()) >= 1
    assert filtered_dates.status_code == 200
    assert len(filtered_dates.json()) >= 1


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


def test_case_summary_not_found() -> None:
    response = client.get("/api/cases/not-a-real-case-id/summary")

    assert response.status_code == 404


def test_case_summary() -> None:
    cases_response = client.get("/api/cases", params={"page_size": 1})
    case_id = cases_response.json()["items"][0]["case_id"]

    response = client.get(f"/api/cases/{case_id}/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == case_id
    assert data["summary_method"] == "rule_based_v1"
    assert data["holding"]
    assert data["reasoning"]


def test_similar_cases() -> None:
    cases_response = client.get("/api/cases", params={"page_size": 1})
    case_id = cases_response.json()["items"][0]["case_id"]

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
