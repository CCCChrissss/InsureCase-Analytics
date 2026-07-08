from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPECTED_COUNT = 2992


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


DEFAULT_DB_PATH = resolve_project_path(os.environ.get("INSURANCE_CASES_DB_PATH", "backend/data/insurance_cases.db"))


class VerificationError(RuntimeError):
    pass


def connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise VerificationError(f"Database file does not exist: {db_path}")
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def count_table(connection: sqlite3.Connection, table_name: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type IN ('table', 'view')
          AND name = ?
        LIMIT 1;
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def verify_chunks(connection: sqlite3.Connection, require_chunks: bool) -> tuple[dict[str, Any], list[str]]:
    checks: dict[str, Any] = {
        "required": require_chunks,
        "table_exists": table_exists(connection, "case_chunks"),
        "chunk_count": 0,
        "cases_without_chunks": None,
        "min_chunk_chars": None,
    }
    errors: list[str] = []

    if not checks["table_exists"]:
        if require_chunks:
            errors.append("case_chunks table does not exist")
        return checks, errors

    checks["chunk_count"] = count_table(connection, "case_chunks")
    aggregate = connection.execute(
        """
        SELECT
          COUNT(*) AS chunk_count,
          MIN(chunk_chars) AS min_chunk_chars
        FROM case_chunks;
        """
    ).fetchone()
    checks["min_chunk_chars"] = aggregate["min_chunk_chars"]
    missing = connection.execute(
        """
        SELECT COUNT(*)
        FROM cases
        LEFT JOIN case_chunks ON case_chunks.case_id = cases.case_id
        WHERE case_chunks.case_id IS NULL;
        """
    ).fetchone()[0]
    checks["cases_without_chunks"] = int(missing)

    if require_chunks:
        if checks["chunk_count"] <= 0:
            errors.append("case_chunks table has no rows")
        if checks["cases_without_chunks"] != 0:
            errors.append(f"{checks['cases_without_chunks']} cases have no chunks")
        if checks["min_chunk_chars"] is None or checks["min_chunk_chars"] <= 0:
            errors.append("case_chunks contains empty chunks")

    return checks, errors


def like_count(connection: sqlite3.Connection, keyword: str) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*)
        FROM case_texts
        WHERE normalized_text LIKE ?;
        """,
        (f"%{keyword}%",),
    ).fetchone()
    return int(row[0])


def fts_count(connection: sqlite3.Connection, keyword: str) -> int | str:
    try:
        row = connection.execute(
            """
            SELECT COUNT(*)
            FROM case_search
            WHERE case_search MATCH ?;
            """,
            (keyword,),
        ).fetchone()
        return int(row[0])
    except sqlite3.OperationalError as error:
        return f"error: {error}"


def verify_paths(connection: sqlite3.Connection, limit: int = 20) -> list[str]:
    errors: list[str] = []
    rows = connection.execute(
        """
        SELECT case_number, pdf_path, raw_text_path, normalized_text_path, metadata_path
        FROM cases;
        """
    ).fetchall()
    for row in rows:
        for key in ("pdf_path", "raw_text_path", "normalized_text_path", "metadata_path"):
            value = row[key]
            path = Path(value)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            if not path.is_file():
                errors.append(f"{row['case_number']}: missing {key}: {value}")
                if len(errors) >= limit:
                    return errors
    return errors


def verify_database(db_path: Path, expected_count: int, require_chunks: bool = False) -> dict[str, Any]:
    with connect(db_path) as connection:
        counts = {
            "cases": count_table(connection, "cases"),
            "case_texts": count_table(connection, "case_texts"),
            "case_search": count_table(connection, "case_search"),
            "case_summaries": count_table(connection, "case_summaries"),
            "case_chunks": count_table(connection, "case_chunks") if table_exists(connection, "case_chunks") else 0,
        }
        sample = connection.execute(
            """
            SELECT cases.case_id, case_number, decision_date, dispute_type, pdf_path,
                   LENGTH(case_texts.normalized_text) AS normalized_text_length
            FROM cases
            JOIN case_texts ON case_texts.case_id = cases.case_id
            ORDER BY case_number
            LIMIT 1;
            """
        ).fetchone()
        keyword_checks = {
            keyword: {
                "fts_count": fts_count(connection, keyword),
                "like_count": like_count(connection, keyword),
            }
            for keyword in ("必要性醫療", "癌症", "除外責任")
        }
        path_errors = verify_paths(connection)
        chunk_checks, chunk_errors = verify_chunks(connection, require_chunks)

    errors: list[str] = []
    for table_name in ("cases", "case_texts", "case_search"):
        if counts[table_name] != expected_count:
            errors.append(f"{table_name} count expected {expected_count}, got {counts[table_name]}")
    for keyword, result in keyword_checks.items():
        if result["like_count"] <= 0:
            errors.append(f"LIKE search returned no results for {keyword!r}")
    errors.extend(path_errors)
    errors.extend(chunk_errors)

    return {
        "database": str(db_path),
        "expected_count": expected_count,
        "counts": counts,
        "keyword_checks": keyword_checks,
        "chunk_checks": chunk_checks,
        "sample_case": dict(sample) if sample else None,
        "path_error_count": len(path_errors),
        "path_errors": path_errors,
        "passed": not errors,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify imported FOI ODS SQLite database.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--expected-count", type=int, default=DEFAULT_EXPECTED_COUNT)
    parser.add_argument("--require-chunks", action="store_true", help="Require every imported case to have chunks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = verify_database(args.db, args.expected_count, require_chunks=args.require_chunks)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
