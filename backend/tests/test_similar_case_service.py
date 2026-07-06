from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.app.services import similar_case_service


def connect_test_db(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def create_similar_fixture(db_path: Path) -> None:
    with connect_test_db(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE cases (
              case_id TEXT PRIMARY KEY,
              case_number TEXT NOT NULL UNIQUE,
              decision_date TEXT,
              decision_category TEXT,
              decision_result TEXT,
              dispute_type TEXT
            );

            CREATE TABLE case_summaries (
              case_id TEXT PRIMARY KEY,
              holding TEXT,
              applicant_claim TEXT,
              reasoning TEXT,
              summary_method TEXT,
              created_at TEXT
            );

            INSERT INTO cases (
              case_id, case_number, decision_date, decision_category, decision_result, dispute_type
            )
            VALUES
              ('case_source', '115年評字第000001號', '115.01.01', '評議決定', '無理由', '保險金給付'),
              ('case_same', '115年評字第000002號', '115.01.02', '評議決定', '無理由', '保險金給付'),
              ('case_other', '115年評字第000003號', '115.01.03', '評議決定', '有理由', '契約變更');

            INSERT INTO case_summaries (
              case_id, holding, applicant_claim, reasoning, summary_method, created_at
            )
            VALUES
              ('case_source', '主文', '申請人主張癌症住院保險金應給付。', '本件涉及癌症、住院、理賠及保險金。', 'rule_based_v1', 'now'),
              ('case_same', '主文', '申請人主張癌症住院費用應理賠。', '本件同涉及癌症、住院、理賠及保險金。', 'rule_based_v1', 'now'),
              ('case_other', '主文', '申請人主張契約變更。', '本件涉及保單價值與契約變更。', 'rule_based_v1', 'now');
            """
        )


def test_similar_cases_excludes_source_and_scores_candidates(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "test_cases.db"
    create_similar_fixture(db_path)
    monkeypatch.setattr(similar_case_service, "connect", lambda: connect_test_db(db_path))

    result = similar_case_service.similar_cases("case_source", limit=5)

    assert result is not None
    assert result["case_id"] == "case_source"
    assert all(item["case_id"] != "case_source" for item in result["items"])
    assert result["items"][0]["case_id"] == "case_same"
    assert "相同爭議類型" in result["items"][0]["matched_reasons"]
    assert any(reason.startswith("共同關鍵詞") for reason in result["items"][0]["matched_reasons"])


def test_similar_cases_returns_none_for_missing_case(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "test_cases.db"
    create_similar_fixture(db_path)
    monkeypatch.setattr(similar_case_service, "connect", lambda: connect_test_db(db_path))

    result = similar_case_service.similar_cases("missing", limit=5)

    assert result is None
