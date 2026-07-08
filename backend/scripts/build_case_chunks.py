from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "backend" / "schema.sql"

DEFAULT_TARGET_CHARS = 1000
DEFAULT_OVERLAP_CHARS = 180
MIN_CHUNK_CHARS = 250

SECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("主文", re.compile(r"^主\s*文\s*$")),
    ("事實及理由", re.compile(r"^事實及理由\s*$")),
    ("程序事項", re.compile(r"^[一二三四五六七八九十]+、\s*程序事項")),
    ("申請人主張", re.compile(r"^[一二三四五六七八九十]+、\s*申請人(?:之)?主張")),
    ("相對人主張", re.compile(r"^[一二三四五六七八九十]+、\s*相對人(?:之)?主張")),
    ("兩造不爭執之事實", re.compile(r"^[一二三四五六七八九十]+、\s*兩造不爭執")),
    ("本件爭點", re.compile(r"^[一二三四五六七八九十]+、\s*本件爭點")),
    ("判斷理由", re.compile(r"^[一二三四五六七八九十]+、\s*判斷理由")),
    ("結論", re.compile(r"^[一二三四五六七八九十]+、\s*(綜上所述|據上論結)")),
)


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    section_hint: str | None
    chunk_text: str
    char_start: int
    char_end: int

    @property
    def chunk_chars(self) -> int:
        return len(self.chunk_text)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


DEFAULT_DB_PATH = resolve_project_path(os.environ.get("INSURANCE_CASES_DB_PATH", "backend/data/insurance_cases.db"))


def chunk_id_for(case_id: str, chunk_index: int) -> str:
    digest = hashlib.sha1(f"{case_id}:{chunk_index}".encode("utf-8")).hexdigest()[:16]
    return f"chunk_{digest}"


def connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def normalize_text(text: str | None) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def line_starts(text: str) -> list[tuple[int, str]]:
    starts: list[tuple[int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped:
            starts.append((offset + line.index(stripped), stripped))
        offset += len(line)
    return starts


def detect_section_markers(text: str) -> list[tuple[int, str]]:
    markers: list[tuple[int, str]] = []
    for offset, line in line_starts(text):
        for label, pattern in SECTION_PATTERNS:
            if pattern.match(line):
                markers.append((offset, label))
                break
    return markers


def section_for_span(markers: list[tuple[int, str]], start: int, end: int) -> str | None:
    candidate: str | None = None
    first_marker_inside_span: str | None = None
    for offset, label in markers:
        if offset <= start:
            candidate = label
        elif start < offset < end:
            first_marker_inside_span = label
            break
        else:
            break
    return candidate or first_marker_inside_span


def choose_breakpoint(text: str, start: int, target_end: int) -> int:
    if target_end >= len(text):
        return len(text)

    lower_bound = start + max(MIN_CHUNK_CHARS, int((target_end - start) * 0.65))
    search_text = text[lower_bound:target_end]
    candidates = [search_text.rfind("\n"), search_text.rfind("。"), search_text.rfind("；")]
    best = max(candidates)
    if best >= 0:
        return lower_bound + best + 1
    return target_end


def build_chunks(
    text: str | None,
    *,
    target_chars: int = DEFAULT_TARGET_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> list[Chunk]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    if target_chars <= overlap_chars:
        raise ValueError("target_chars must be greater than overlap_chars.")

    markers = detect_section_markers(normalized)
    chunks: list[Chunk] = []
    start = 0
    while start < len(normalized):
        target_end = min(len(normalized), start + target_chars)
        end = choose_breakpoint(normalized, start, target_end)
        span = normalized[start:end]
        chunk_text = span.strip()
        if chunk_text:
            left_trim = len(span) - len(span.lstrip())
            right_trim = len(span) - len(span.rstrip())
            actual_start = start + left_trim
            actual_end = end - right_trim
            chunks.append(
                Chunk(
                    chunk_index=len(chunks),
                    section_hint=section_for_span(markers, actual_start, actual_end),
                    chunk_text=chunk_text,
                    char_start=actual_start,
                    char_end=actual_end,
                )
            )
        if end >= len(normalized):
            break
        start = max(end - overlap_chars, start + 1)

    return chunks


def replace_case_chunks(
    connection: sqlite3.Connection,
    *,
    case_id: str,
    chunks: list[Chunk],
    created_at: str,
) -> None:
    connection.execute("DELETE FROM case_chunks WHERE case_id = ?;", (case_id,))
    connection.executemany(
        """
        INSERT INTO case_chunks (
          chunk_id, case_id, chunk_index, section_hint, chunk_text,
          char_start, char_end, chunk_chars, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        [
            (
                chunk_id_for(case_id, chunk.chunk_index),
                case_id,
                chunk.chunk_index,
                chunk.section_hint,
                chunk.chunk_text,
                chunk.char_start,
                chunk.char_end,
                chunk.chunk_chars,
                created_at,
            )
            for chunk in chunks
        ],
    )


def build_case_chunks(
    db_path: Path,
    *,
    target_chars: int = DEFAULT_TARGET_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
    limit: int | None = None,
) -> dict[str, Any]:
    created_at = now_iso()
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT cases.case_id, cases.case_number, case_texts.normalized_text
            FROM cases
            JOIN case_texts ON case_texts.case_id = cases.case_id
            ORDER BY cases.case_number;
            """
        ).fetchall()
        if limit is not None:
            rows = rows[:limit]

        total_chunks = 0
        empty_cases: list[str] = []
        max_chunks_per_case = 0
        min_chunks_per_case: int | None = None
        for row in rows:
            chunks = build_chunks(row["normalized_text"], target_chars=target_chars, overlap_chars=overlap_chars)
            if not chunks:
                empty_cases.append(row["case_number"])
            replace_case_chunks(connection, case_id=row["case_id"], chunks=chunks, created_at=created_at)
            total_chunks += len(chunks)
            max_chunks_per_case = max(max_chunks_per_case, len(chunks))
            min_chunks_per_case = len(chunks) if min_chunks_per_case is None else min(min_chunks_per_case, len(chunks))

        section_counts = [
            dict(row)
            for row in connection.execute(
                """
                SELECT COALESCE(section_hint, '未標示') AS section_hint, COUNT(*) AS count
                FROM case_chunks
                GROUP BY COALESCE(section_hint, '未標示')
                ORDER BY count DESC, section_hint ASC;
                """
            ).fetchall()
        ]
        total_table_chunks = connection.execute("SELECT COUNT(*) FROM case_chunks").fetchone()[0]

    return {
        "database": str(db_path),
        "processed_cases": len(rows),
        "total_chunks_created": total_chunks,
        "total_chunks_in_table": total_table_chunks,
        "target_chars": target_chars,
        "overlap_chars": overlap_chars,
        "min_chunks_per_case": min_chunks_per_case or 0,
        "max_chunks_per_case": max_chunks_per_case,
        "empty_case_count": len(empty_cases),
        "empty_cases": empty_cases[:20],
        "section_counts": section_counts,
        "created_at": created_at,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build text chunks for imported FOI ODS cases.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--target-chars", type=int, default=DEFAULT_TARGET_CHARS)
    parser.add_argument("--overlap-chars", type=int, default=DEFAULT_OVERLAP_CHARS)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_case_chunks(
        resolve_project_path(args.db),
        target_chars=args.target_chars,
        overlap_chars=args.overlap_chars,
        limit=args.limit,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["empty_case_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
