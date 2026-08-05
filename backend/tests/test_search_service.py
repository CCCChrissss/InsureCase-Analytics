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
              dispute_type TEXT,
              decision_result TEXT
            );

            CREATE TABLE case_texts (
              case_id TEXT PRIMARY KEY,
              normalized_text TEXT
            );

            CREATE TABLE case_summaries (
              case_id TEXT PRIMARY KEY,
              holding TEXT
            );

            CREATE VIRTUAL TABLE case_search USING fts5(
              case_id UNINDEXED,
              case_number,
              dispute_type,
              normalized_text
            );

            INSERT INTO cases (
              case_id, case_number, roc_year, decision_date, dispute_type, decision_result
            )
            VALUES (
              'case_1', '115年評字第000001號', 115, '115.01.09', '保險金給付', '無理由'
            );

            INSERT INTO case_texts (case_id, normalized_text)
            VALUES ('case_1', '申請人主張其癌症治療費用應由保險公司給付。');

            INSERT INTO case_summaries (case_id, holding)
            VALUES ('case_1', '本中心就申請人之請求尚難為有利申請人之認定。');

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
    assert result["items"][0]["decision_result"] == "無理由"
    assert result["items"][0]["match_source"] == "like_fallback_empty_fts5"
    assert "癌症" in result["items"][0]["snippet"]


def test_classify_decision_result_uses_holding_instead_of_filter_metadata() -> None:
    assert search_service.classify_decision_result("全部", "相對人應給付申請人新臺幣十萬元整。") == "有理由"
    assert search_service.classify_decision_result(
        "全部",
        "相對人應給付申請人新臺幣十萬元整。申請人其餘請求尚難為有利之認定。",
    ) == "部分有理由"
    assert search_service.classify_decision_result("全部", "本中心就申請人之請求尚難為有利之認定。") == "無理由"
    assert search_service.classify_decision_result("全部", "本中心不予受理。") == "不受理"
    assert search_service.classify_decision_result("全部", "確認兩造間保險契約關係存在。") == "有理由"
    assert search_service.classify_decision_result("全部", "相對人應恢復保險契約之效力。") == "有理由"
    assert search_service.classify_decision_result("全部", "文字不足以判斷。") is None


def test_like_fallback_searches_case_number_when_fts5_returns_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "test_cases.db"
    create_search_fixture(db_path)

    monkeypatch.setattr(search_service, "connect", lambda: connect_test_db(db_path))

    result = search_service.search_cases("000001", page=1, page_size=10)

    assert result["total"] == 1
    assert result["items"][0]["case_number"] == "115年評字第000001號"
    assert result["items"][0]["match_source"] == "like_fallback_empty_fts5"


def test_like_fallback_searches_dispute_type_when_fts5_returns_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "test_cases.db"
    create_search_fixture(db_path)

    monkeypatch.setattr(search_service, "connect", lambda: connect_test_db(db_path))

    result = search_service.search_cases("給付", page=1, page_size=10)

    assert result["total"] == 1
    assert result["items"][0]["dispute_type"] == "保險金給付"
    assert result["items"][0]["match_source"] == "like_fallback_empty_fts5"


def test_search_all_cases_returns_every_keyword_match(
    tmp_path: Path,
    monkeypatch,
) -> None:
    # 全域語意排序需要完整命中集合，不能沿用一般搜尋的 LIMIT/OFFSET。
    db_path = tmp_path / "test_cases.db"
    create_search_fixture(db_path)

    with connect_test_db(db_path) as connection:
        connection.execute(
            """
            INSERT INTO cases (
              case_id, case_number, roc_year, decision_date, dispute_type, decision_result
            ) VALUES ('case_2', '115年評字第000002號', 115, '115.01.10', '癌症理賠', '有理由');
            """
        )
        connection.execute(
            "INSERT INTO case_texts (case_id, normalized_text) VALUES ('case_2', '癌症標靶治療理賠爭議。');"
        )
        connection.execute(
            "INSERT INTO case_summaries (case_id, holding) VALUES ('case_2', '相對人應給付保險金。');"
        )
        connection.execute(
            """
            INSERT INTO case_search (case_id, case_number, dispute_type, normalized_text)
            VALUES ('case_2', '115年評字第000002號', '癌症理賠', '癌症標靶治療理賠爭議。');
            """
        )

    monkeypatch.setattr(search_service, "connect", lambda: connect_test_db(db_path))

    result = search_service.search_all_cases("癌症")

    assert result["total"] == 2
    assert {item["case_id"] for item in result["items"]} == {"case_1", "case_2"}
    assert result["match_source"] in {"fts5", "like_fallback_empty_fts5"}
