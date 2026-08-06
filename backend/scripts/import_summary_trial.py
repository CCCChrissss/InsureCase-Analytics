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

from backend.app.services.ai_summary_service import AiSummaryDataError, import_summary_report


DEFAULT_DB_PATH = PROJECT_ROOT / "backend" / "data" / "insurance_cases_local_bge_trial.db"
FORMAL_DB_PATH = (PROJECT_ROOT / "backend" / "data" / "insurance_cases.db").resolve()
DEFAULT_REPORT_PATH = PROJECT_ROOT / "outputs" / "local_llm_summary_trial_qwen3_4b_final_v4.json"


def configure_utf8_console() -> None:
    """Keep Chinese case content readable in Windows PowerShell output."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def guard_database_target(db_path: Path, *, allow_formal_db: bool) -> None:
    """Require an explicit override before a POC import can touch the formal DB."""

    if db_path == FORMAL_DB_PATH and not allow_formal_db:
        raise ValueError(
            "Refusing to modify backend/data/insurance_cases.db. "
            "Use the Local BGE trial DB, or pass --allow-formal-db after review."
        )
    if not db_path.is_file():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")


def load_report(report_path: Path) -> dict[str, Any]:
    if not report_path.is_file():
        raise FileNotFoundError(f"Summary report does not exist: {report_path}")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AiSummaryDataError("Summary report root must be an object.")
    return payload


def import_report_to_database(db_path: Path, report_path: Path) -> dict[str, Any]:
    """Import one report transactionally so partial case imports cannot remain."""

    report = load_report(report_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    try:
        with connection:
            result = import_summary_report(connection, report)
    finally:
        connection.close()
    return {
        "database": str(db_path),
        "report": str(report_path),
        **result,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import an evidence-validated local summary trial into the versioned review store."
    )
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Target SQLite trial database.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Validated summary trial JSON.")
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
    report_path = resolve_project_path(args.report)
    guard_database_target(db_path, allow_formal_db=args.allow_formal_db)
    result = import_report_to_database(db_path, report_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
