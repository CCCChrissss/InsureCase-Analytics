from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.app.services import search_service


def connect_test_db(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def create_search_fixture(db_path: Path) -> None:
    with connect_test_db(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE cases (
              case_id TEXT PRIMARY KEY,
              case_number TEXT NOT NULL UNIQUE,
              roc_year INTEGER NOT NULL,
              decision_date TEXT,
              dispute_type TEXT
            );

            CREATE TABLE case_texts (
              case_id TEXT PRIMARY KEY,
              normalized_text TEXT
            );

            CREATE VIRTUAL TABLE case_search USING fts5(
              case_id UNINDEXED,
              case_number,
              dispute_type,
              normalized_text
            );

            INSERT INTO cases (
              case_id, case_number, roc_year, decision_date, dispute_type
            )
            VALUES (
              'case_1', '115年評字第000001號', 115, '115.01.09', '保險金給付'
            );

            INSERT INTO case_texts (case_id, normalized_text)
            VALUES ('case_1', '申請人主張其癌症治療費用應由保險公司給付。');

            INSERT INTO case_search (
              case_id, case_number, dispute_type, normalized_text
            )
            VALUES (
              'case_1', '115年評字第000001號', '保險金給付', '這段索引文字沒有測試關鍵字'
            );
            """
        )


def test_search_uses_like_fallback_when_fts5_returns_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "test_cases.db"
    create_search_fixture(db_path)

    monkeypatch.setattr(search_service, "connect", lambda: connect_test_db(db_path))

    result = search_service.search_cases("癌症", page=1, page_size=10)

    assert result["total"] == 1
    assert result["items"][0]["case_id"] == "case_1"
    assert result["items"][0]["match_source"] == "like_fallback_empty_fts5"
    assert "癌症" in result["items"][0]["snippet"]
