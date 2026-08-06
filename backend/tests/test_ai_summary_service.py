from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.routers import ai_summaries as ai_summaries_router
from backend.app.services import ai_summary_service
from backend.app.services.ai_summary_service import (
    find_ai_summary_for_review,
    get_case_ai_summary,
    import_summary_report,
    list_ai_summaries,
    review_ai_summary,
)


def connect_test_db(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def create_case_database(db_path: Path) -> None:
    with connect_test_db(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE cases (
              case_id TEXT PRIMARY KEY,
              case_number TEXT NOT NULL UNIQUE
            );
            INSERT INTO cases (case_id, case_number)
            VALUES ('case_1', '114年評字第000001號');
            """
        )


def make_report(*, model: str = "qwen3:4b", generated_at: str = "2026-08-06T01:00:00+00:00") -> dict:
    return {
        "results": [
            {
                "case_id": "case_1",
                "case_number": "114年評字第000001號",
                "summary": {
                    "background": "申請人投保醫療保險。",
                    "applicant_position": "申請人請求給付保險金。",
                    "respondent_position": "相對人主張不符合給付條件。",
                    "core_issues": ["是否符合保險金給付條件？"],
                    "reasoning_points": ["評議中心依病歷資料判斷。"],
                    "decision_result": "申請無理由。",
                    "legal_references": [],
                    "evidence": [],
                },
                "generation": {
                    "provider": "ollama_local",
                    "model": model,
                    "prompt_version": "local_llm_summary_v4",
                    "source_hash_sha256": "a" * 64,
                    "review_status": "unreviewed",
                    "generated_at": generated_at,
                    "failed_request_count": 0,
                    "request_errors": [],
                    "final_merge_fallback": False,
                },
            }
        ]
    }


def test_import_is_idempotent_and_preserves_review(tmp_path: Path) -> None:
    db_path = tmp_path / "cases.db"
    create_case_database(db_path)

    with connect_test_db(db_path) as connection:
        first = import_summary_report(connection, make_report())
        summary_id = first["summary_ids"][0]
        review_ai_summary(
            connection,
            summary_id=summary_id,
            status="approved",
            reviewer="reviewer_1",
            note="已核對原文",
        )
        second = import_summary_report(connection, make_report())
        row = find_ai_summary_for_review(connection, summary_id=summary_id)

    assert first["inserted"] == 1
    assert second["updated"] == 1
    assert row is not None
    assert row["review_status"] == "approved"
    assert row["reviewer"] == "reviewer_1"
    assert row["review_note"] == "已核對原文"


def test_get_case_ai_summary_prefers_approved_and_hides_rejected(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cases.db"
    create_case_database(db_path)
    with connect_test_db(db_path) as connection:
        first = import_summary_report(connection, make_report(model="qwen3:4b"))
        review_ai_summary(
            connection,
            summary_id=first["summary_ids"][0],
            status="approved",
            reviewer="reviewer_1",
        )
        # A newer unreviewed model version must not displace the approved one.
        import_summary_report(
            connection,
            make_report(model="qwen3:8b", generated_at="2026-08-07T01:00:00+00:00"),
        )

    monkeypatch.setattr(ai_summary_service, "connect", lambda: connect_test_db(db_path))
    item = get_case_ai_summary("case_1")
    assert item is not None
    assert item["model"] == "qwen3:4b"
    assert item["official"] is True
    # Reviewer identity and internal notes remain CLI-only until authentication exists.
    assert "reviewer" not in item
    assert "review_note" not in item

    with connect_test_db(db_path) as connection:
        queue = list_ai_summaries(connection)
        for queue_item in queue:
            review_ai_summary(
                connection,
                summary_id=queue_item["summary_id"],
                status="rejected",
                reviewer="reviewer_2",
            )

    assert get_case_ai_summary("case_1") is None


def test_ai_summary_api_returns_availability_wrapper(monkeypatch) -> None:
    case_id = "case_1"
    monkeypatch.setattr(ai_summaries_router, "get_case", lambda requested_id: {"case_id": requested_id})
    monkeypatch.setattr(ai_summaries_router, "get_case_ai_summary", lambda requested_id: None)

    response = TestClient(app).get(f"/api/cases/{case_id}/ai-summary")

    assert response.status_code == 200
    assert response.json() == {"case_id": case_id, "available": False, "item": None}


def test_ai_summary_api_returns_not_found_for_unknown_case(monkeypatch) -> None:
    monkeypatch.setattr(ai_summaries_router, "get_case", lambda requested_id: None)

    response = TestClient(app).get("/api/cases/missing/ai-summary")

    assert response.status_code == 404
