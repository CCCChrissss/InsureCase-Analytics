from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.scripts import build_case_chunks


def test_build_chunks_preserves_offsets_and_overlap() -> None:
    text = (
        "一、申請人主張\n"
        "申請人主張其於癌症治療後申請保險金，保險公司仍拒絕理賠。\n"
        "申請人另主張保單條款未明確排除該治療方式，應依有利於被保險人解釋。\n"
        "二、判斷理由\n"
        "評議中心審酌診斷證明、病歷資料與保單條款後，認為仍需比較條款文字與醫療事實。\n"
        "本段文字用來拉長測試資料，確認 chunk 會依指定長度切分並保留重疊區間。\n"
    )

    chunks = build_case_chunks.build_chunks(text, target_chars=90, overlap_chars=25)
    normalized = build_case_chunks.normalize_text(text)

    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[1].char_start < chunks[0].char_end
    for chunk in chunks:
        assert normalized[chunk.char_start : chunk.char_end] == chunk.chunk_text


def test_build_chunks_detects_section_hint() -> None:
    text = (
        "一、申請人主張\n"
        "申請人主張癌症保險金應給付。\n"
        "二、判斷理由\n"
        "本中心認為應先確認保單條款與診斷內容。\n"
    )

    chunks = build_case_chunks.build_chunks(text, target_chars=35, overlap_chars=5)

    section_hints = {chunk.section_hint for chunk in chunks}
    assert "申請人主張" in section_hints
    assert "判斷理由" in section_hints


def insert_case(connection: sqlite3.Connection, case_id: str, case_number: str, text: str) -> None:
    connection.execute(
        """
        INSERT INTO cases (
          case_id, case_number, roc_year, decision_date, dispute_type,
          created_at, updated_at
        )
        VALUES (?, ?, 115, '115.01.01', '理賠爭議', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z');
        """,
        (case_id, case_number),
    )
    connection.execute(
        """
        INSERT INTO case_texts (
          case_id, raw_text, normalized_text, raw_text_chars, normalized_text_chars,
          page_count, extraction_method
        )
        VALUES (?, ?, ?, ?, ?, 1, 'test');
        """,
        (case_id, text, text, len(text), len(text)),
    )


def test_build_case_chunks_writes_chunks_to_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "insurance_cases.db"
    with sqlite3.connect(db_path) as connection:
        connection.executescript(build_case_chunks.SCHEMA_PATH.read_text(encoding="utf-8"))
        insert_case(
            connection,
            "case_a",
            "115年評字第000001號",
            "一、申請人主張\n申請人主張癌症治療費用應給付。\n二、判斷理由\n本中心認為應檢視保單條款。",
        )
        insert_case(
            connection,
            "case_b",
            "115年評字第000002號",
            "一、申請人主張\n申請人主張住院日額應給付。\n二、判斷理由\n本中心認為需比較診斷內容。",
        )

    report = build_case_chunks.build_case_chunks(db_path, target_chars=60, overlap_chars=10)

    assert report["processed_cases"] == 2
    assert report["empty_case_count"] == 0
    assert report["total_chunks_created"] >= 2
    assert report["total_chunks_in_table"] == report["total_chunks_created"]

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT case_id, COUNT(*) AS chunk_count
            FROM case_chunks
            GROUP BY case_id
            ORDER BY case_id;
            """
        ).fetchall()

    assert rows[0][0] == "case_a"
    assert rows[0][1] >= 1
    assert rows[1][0] == "case_b"
    assert rows[1][1] >= 1
