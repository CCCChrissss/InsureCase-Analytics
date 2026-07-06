from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_METHOD = "rule_based_v1"


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


DEFAULT_DB_PATH = resolve_project_path(os.environ.get("INSURANCE_CASES_DB_PATH", "backend/data/insurance_cases.db"))

PAGE_MARKER_RE = re.compile(r"^(--- page \d+ ---|-第\d+頁，共\d+頁-)$")
TOP_LEVEL_HEADING_RE = re.compile(r"^[一二三四五六七八九十]+、")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_marker(value: str) -> str:
    return re.sub(r"\s+", "", value).strip("：:")


def clean_lines(text: str | None) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    for line in text.replace("\r", "").splitlines():
        stripped = line.strip()
        if not stripped or PAGE_MARKER_RE.match(stripped):
            continue
        lines.append(stripped)
    return lines


def compact_text(lines: list[str], *, max_chars: int) -> str | None:
    text = "\n".join(lines).strip()
    if not text:
        return None
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}..."


def line_matches(line: str, markers: set[str]) -> bool:
    return normalize_marker(line) in markers


def find_marker_index(lines: list[str], markers: set[str], start: int = 0) -> int | None:
    for index in range(start, len(lines)):
        if line_matches(lines[index], markers):
            return index
    return None


def find_next_index(lines: list[str], start: int, end_markers: set[str]) -> int:
    for index in range(start, len(lines)):
        if line_matches(lines[index], end_markers):
            return index
    return len(lines)


def extract_between_markers(
    lines: list[str],
    *,
    start_markers: set[str],
    end_markers: set[str],
    max_chars: int,
) -> str | None:
    start_index = find_marker_index(lines, start_markers)
    if start_index is None:
        return None
    end_index = find_next_index(lines, start_index + 1, end_markers)
    return compact_text(lines[start_index + 1 : end_index], max_chars=max_chars)


def extract_reasoning(lines: list[str], *, max_chars: int = 1600) -> str | None:
    start_markers = {
        normalize_marker("六、判斷理由"),
        normalize_marker("六、 判斷理由"),
    }
    start_index = find_marker_index(lines, start_markers)
    if start_index is None:
        return None

    end_index = len(lines)
    for index in range(start_index + 1, len(lines)):
        normalized = normalize_marker(lines[index])
        if normalized.startswith("七、綜上所述") or normalized.startswith("八、據上論結"):
            end_index = index
            break
        if TOP_LEVEL_HEADING_RE.match(lines[index]) and normalize_marker(lines[index]).startswith(("七、", "八、")):
            end_index = index
            break
    return compact_text(lines[start_index + 1 : end_index], max_chars=max_chars)


def extract_summary(text: str | None) -> dict[str, str | None]:
    lines = clean_lines(text)
    holding = extract_between_markers(
        lines,
        start_markers={normalize_marker("主文")},
        end_markers={normalize_marker("事實及理由")},
        max_chars=500,
    )
    applicant_claim = extract_between_markers(
        lines,
        start_markers={
            normalize_marker("二、申請人之主張"),
            normalize_marker("二、 申請人之主張"),
            normalize_marker("二、實體事項"),
            normalize_marker("二、 實體事項"),
        },
        end_markers={normalize_marker("三、相對人之主張"), normalize_marker("三、 相對人之主張")},
        max_chars=1200,
    )
    reasoning = extract_reasoning(lines)
    return {
        "holding": holding,
        "applicant_claim": applicant_claim,
        "reasoning": reasoning,
    }


def connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def upsert_summary(
    connection: sqlite3.Connection,
    *,
    case_id: str,
    summary: dict[str, str | None],
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO case_summaries (
          case_id, holding, applicant_claim, reasoning, summary_method, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
          holding = excluded.holding,
          applicant_claim = excluded.applicant_claim,
          reasoning = excluded.reasoning,
          summary_method = excluded.summary_method,
          created_at = excluded.created_at;
        """,
        (
            case_id,
            summary["holding"],
            summary["applicant_claim"],
            summary["reasoning"],
            SUMMARY_METHOD,
            created_at,
        ),
    )


def extract_case_summaries(db_path: Path, *, limit: int | None = None) -> dict[str, Any]:
    created_at = now_iso()
    with connect(db_path) as connection:
        query = """
            SELECT cases.case_id, cases.case_number, case_texts.normalized_text
            FROM cases
            JOIN case_texts ON case_texts.case_id = cases.case_id
            ORDER BY cases.case_number;
        """
        rows = connection.execute(query).fetchall()
        if limit is not None:
            rows = rows[:limit]

        field_counts = {"holding": 0, "applicant_claim": 0, "reasoning": 0}
        empty_cases: list[str] = []
        for row in rows:
            summary = extract_summary(row["normalized_text"])
            for field_name in field_counts:
                if summary[field_name]:
                    field_counts[field_name] += 1
            if not any(summary.values()):
                empty_cases.append(row["case_number"])
            upsert_summary(
                connection,
                case_id=row["case_id"],
                summary=summary,
                created_at=created_at,
            )

        total_summaries = connection.execute("SELECT COUNT(*) FROM case_summaries").fetchone()[0]

    return {
        "database": str(db_path),
        "summary_method": SUMMARY_METHOD,
        "processed_count": len(rows),
        "total_summaries": total_summaries,
        "field_counts": field_counts,
        "empty_case_count": len(empty_cases),
        "empty_cases": empty_cases[:20],
        "created_at": created_at,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract rule-based summaries for imported FOI ODS cases.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = extract_case_summaries(args.db, limit=args.limit)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
