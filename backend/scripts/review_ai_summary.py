from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.ai_summary_service import (
    decode_summary_json,
    find_ai_summary_for_review,
    list_ai_summaries,
    review_ai_summary,
)
from backend.scripts.import_summary_trial import DEFAULT_DB_PATH, guard_database_target, resolve_project_path


def configure_utf8_console() -> None:
    """Keep Chinese review output readable in Windows PowerShell."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def connect_review_database(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def review_display(row: sqlite3.Row) -> dict[str, Any]:
    """Expose the summary fields needed for a human decision, not internal metrics."""

    summary = decode_summary_json(
        row["summary_json"],
        field_name="summary_json",
        summary_id=str(row["summary_id"]),
    )
    return {
        "summary_id": row["summary_id"],
        "case_id": row["case_id"],
        "case_number": row["case_number"],
        "model": row["model"],
        "prompt_version": row["prompt_version"],
        "review_status": row["review_status"],
        "reviewer": row["reviewer"],
        "review_note": row["review_note"],
        "generated_at": row["generated_at"],
        "reviewed_at": row["reviewed_at"],
        "summary": summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect and review locally generated case summaries.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite trial database.")
    parser.add_argument("--list", action="store_true", help="List the complete review queue.")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--summary-id", help="Select an exact AI summary version.")
    selector.add_argument("--case-number", help="Select the latest AI summary for one case number.")
    parser.add_argument("--show", action="store_true", help="Print all human-review summary fields.")
    parser.add_argument("--status", choices=("unreviewed", "approved", "rejected"))
    parser.add_argument("--reviewer", help="Reviewer name or stable local identifier.")
    parser.add_argument("--note", help="Optional review reason or correction note.")
    parser.add_argument(
        "--allow-formal-db",
        action="store_true",
        help="Explicitly allow writing backend/data/insurance_cases.db.",
    )
    return parser


def main() -> None:
    configure_utf8_console()
    args = build_parser().parse_args()
    db_path = resolve_project_path(args.db)
    guard_database_target(db_path, allow_formal_db=args.allow_formal_db)

    if args.list:
        if any((args.summary_id, args.case_number, args.show, args.status, args.reviewer, args.note)):
            raise ValueError("--list cannot be combined with selection or review options.")
        with connect_review_database(db_path) as connection:
            rows = list_ai_summaries(connection)
        print(json.dumps({"database": str(db_path), "items": rows}, ensure_ascii=False, indent=2))
        return

    if not args.summary_id and not args.case_number:
        raise ValueError("Choose --list, --summary-id, or --case-number.")
    if not args.show and not args.status:
        raise ValueError("A selected summary requires --show or --status.")
    if args.status and not args.reviewer:
        raise ValueError("--reviewer is required when --status is used.")

    with connect_review_database(db_path) as connection:
        row = find_ai_summary_for_review(
            connection,
            summary_id=args.summary_id,
            case_number=args.case_number,
        )
        if row is None:
            raise ValueError("Selected AI summary was not found.")
        output: dict[str, Any] = {"database": str(db_path)}
        if args.show:
            output["item"] = review_display(row)
        if args.status:
            # The transaction commits only after a valid row and review payload
            # have both been resolved.
            with connection:
                output["review"] = review_ai_summary(
                    connection,
                    summary_id=str(row["summary_id"]),
                    status=args.status,
                    reviewer=args.reviewer,
                    note=args.note,
                )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
