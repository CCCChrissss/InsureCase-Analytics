from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.scripts import import_cases_to_db as importer


def write_case_files(base_dir: Path, case_number: str, text: str) -> dict[str, str]:
    case_dir = base_dir / case_number
    case_dir.mkdir(parents=True)
    pdf_path = case_dir / "decision.pdf"
    raw_text_path = case_dir / "raw_text.txt"
    normalized_text_path = case_dir / "normalized_text.txt"
    metadata_path = case_dir / "metadata.json"

    pdf_path.write_bytes(b"%PDF-1.4 test")
    raw_text_path.write_text(text, encoding="utf-8")
    normalized_text_path.write_text(text, encoding="utf-8")
    metadata_path.write_text("{}", encoding="utf-8")

    return {
        "case_directory": str(case_dir),
        "pdf_path": str(pdf_path),
        "raw_text_path": str(raw_text_path),
        "normalized_text_path": str(normalized_text_path),
        "case_metadata_path": str(metadata_path),
    }


def make_record(base_dir: Path, *, case_number: str, roc_year: int, text: str) -> dict[str, object]:
    return {
        "case_number": case_number,
        "decision_date": f"{roc_year}.01.01",
        "decision_category": {"label": "評議決定"},
        "decision_result": {"label": "申請駁回"},
        "industry": {"label": "保險業"},
        "industry_subcategory": {"label": "人壽保險"},
        "dispute_type": {"label": "必要性醫療"},
        "source": {"pdf_url": "https://example.test/case.pdf"},
        "crawl_batch": {"roc_year": roc_year},
        "local_files": write_case_files(base_dir, case_number, text),
        "text": {
            "raw_text_chars": len(text),
            "normalized_text_chars": len(text),
            "page_count": 1,
            "extraction_method": "test",
        },
    }


def write_metadata(path: Path, records: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps({"records": records}, ensure_ascii=False), encoding="utf-8")
    return path


def test_import_cases_accepts_multiple_metadata_files(tmp_path: Path) -> None:
    metadata_114 = write_metadata(
        tmp_path / "foi_ods_life_roc114_metadata.json",
        [
            make_record(
                tmp_path,
                case_number="114年評字第000001號",
                roc_year=114,
                text="第一筆 測試 癌症 理賠",
            )
        ],
    )
    metadata_115 = write_metadata(
        tmp_path / "foi_ods_life_roc115_metadata.json",
        [
            make_record(
                tmp_path,
                case_number="115年評字第000001號",
                roc_year=115,
                text="第二筆 測試 必要性醫療",
            )
        ],
    )
    db_path = tmp_path / "insurance_cases.db"

    report = importer.import_cases([metadata_114, metadata_115], db_path, recreate=True)

    assert report["record_count"] == 2
    assert report["success_count"] == 2
    assert report["failure_count"] == 0
    assert report["metadata_files"] == [str(metadata_114), str(metadata_115)]
    assert report["counts"] == {"cases": 2, "case_texts": 2, "case_search": 2}

    with sqlite3.connect(db_path) as connection:
        years = [
            row[0]
            for row in connection.execute("SELECT roc_year FROM cases ORDER BY roc_year ASC").fetchall()
        ]
        assert years == [114, 115]


def test_resolve_metadata_inputs_reads_metadata_directory(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "metadata"
    metadata_dir.mkdir()
    first = write_metadata(metadata_dir / "foi_ods_life_roc114_metadata.json", [])
    second = write_metadata(metadata_dir / "foi_ods_life_roc115_metadata.json", [])
    (metadata_dir / "foi_ods_life_roc115_pdf_text_report.json").write_text("{}", encoding="utf-8")

    paths = importer.resolve_metadata_inputs(metadata_dirs=[metadata_dir])

    assert paths == [first, second]
