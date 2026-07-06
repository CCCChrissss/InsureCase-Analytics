from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.app.services import summary_service
from backend.scripts.extract_case_summaries import extract_summary


def connect_test_db(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def test_extract_summary_from_standard_sections() -> None:
    text = """
    財團法人金融消費評議中心評議書
    主文
    本中心就申請人之請求尚難為有利申請人之認定。
    事實及理由
    一、程序事項：
    程序內容。
    二、申請人之主張：
    (一) 請求標的：
    相對人應給付保險金。
    三、相對人之主張：
    申請人之請求為無理由。
    四、兩造不爭執之事實：
    不爭執內容。
    五、本件爭點：
    爭點內容。
    六、判斷理由：
    本中心審酌相關資料後，認為尚難認定相對人應負給付責任。
    七、綜上所述，本中心就申請人之請求尚難為有利申請人之認定。
    """

    summary = extract_summary(text)

    assert summary["holding"] == "本中心就申請人之請求尚難為有利申請人之認定。"
    assert summary["applicant_claim"] is not None
    assert "相對人應給付保險金" in summary["applicant_claim"]
    assert summary["reasoning"] is not None
    assert "尚難認定相對人應負給付責任" in summary["reasoning"]


def test_extract_summary_accepts_substantive_section_as_claim() -> None:
    text = """
    主 文
    本中心就申請人之請求尚難為有利申請人之認定。
    事實及理由
    一、 程序事項：
    程序內容。
    二、 實體事項：
    (一) 請求標的：
    相對人應給付申請人新臺幣100萬元。
    (二) 陳述：
    申請人因車禍受傷，主張符合失能給付。
    三、 相對人之主張：
    申請人之請求為無理由。
    六、 判斷理由：
    本中心認為尚難認定符合失能程度。
    七、 綜上所述，本中心就申請人之請求尚難為有利申請人之認定。
    """

    summary = extract_summary(text)

    assert summary["applicant_claim"] is not None
    assert "相對人應給付申請人新臺幣100萬元" in summary["applicant_claim"]
    assert "符合失能給付" in summary["applicant_claim"]


def test_get_case_summary_from_database(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "test_cases.db"
    with connect_test_db(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE case_summaries (
              case_id TEXT PRIMARY KEY,
              holding TEXT,
              applicant_claim TEXT,
              reasoning TEXT,
              summary_method TEXT,
              created_at TEXT
            );

            INSERT INTO case_summaries (
              case_id, holding, applicant_claim, reasoning, summary_method, created_at
            )
            VALUES (
              'case_1', '主文內容', '申請人主張', '判斷理由', 'rule_based_v1', '2026-07-06T00:00:00+00:00'
            );
            """
        )

    monkeypatch.setattr(summary_service, "connect", lambda: connect_test_db(db_path))

    summary = summary_service.get_case_summary("case_1")

    assert summary is not None
    assert summary["case_id"] == "case_1"
    assert summary["holding"] == "主文內容"
    assert summary["summary_method"] == "rule_based_v1"
