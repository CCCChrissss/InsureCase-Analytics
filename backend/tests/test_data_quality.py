from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.scripts import check_data_quality


def test_check_metadata_reports_cyrillic_mojibake(tmp_path: Path) -> None:
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "case_number": "113еєіи©Хе≠Чзђђ004313иЩЯ",
                        "dispute_type": {"label": "ењЕи¶БжАІйЖЂзЩВ"},
                        "local_files": {},
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = check_data_quality.check_inputs([metadata_path], [])

    assert report["passed"] is False
    assert report["issue_count"] == 2
    assert {issue["field"] for issue in report["issues"]} == {"case_number", "dispute_type.label"}


def test_check_database_reports_cyrillic_mojibake(tmp_path: Path) -> None:
    db_path = tmp_path / "cases.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE cases (
              case_id TEXT,
              case_number TEXT,
              dispute_type TEXT,
              case_directory TEXT,
              pdf_path TEXT,
              raw_text_path TEXT,
              normalized_text_path TEXT,
              metadata_path TEXT,
              roc_year INTEGER
            );
            """
        )
        connection.execute(
            """
            INSERT INTO cases (
              case_id, case_number, dispute_type, case_directory, pdf_path,
              raw_text_path, normalized_text_path, metadata_path, roc_year
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                "case_bad",
                "113еєіи©Хе≠Чзђђ004313иЩЯ",
                "ењЕи¶БжАІйЖЂзЩВ",
                "data/foi_ods/cases/roc114/ењЕи¶БжАІйЖЂзЩВ",
                None,
                None,
                None,
                None,
                114,
            ),
        )

    report = check_data_quality.check_inputs([], [db_path])

    assert report["passed"] is False
    assert report["issue_count"] == 3
