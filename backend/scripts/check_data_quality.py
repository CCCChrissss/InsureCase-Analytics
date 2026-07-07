from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


TEXT_FIELDS = (
    "case_number",
    "dispute_type.label",
    "local_files.case_directory",
    "local_files.pdf_path",
    "local_files.raw_text_path",
    "local_files.normalized_text_path",
    "local_files.case_metadata_path",
)


DB_FIELDS = (
    "case_number",
    "dispute_type",
    "case_directory",
    "pdf_path",
    "raw_text_path",
    "normalized_text_path",
    "metadata_path",
)


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def is_suspicious_text(value: str) -> bool:
    if "\ufffd" in value:
        return True
    return any("\u0400" <= character <= "\u04ff" for character in value)


def nested_get(data: dict[str, Any], dotted_key: str) -> Any:
    value: Any = data
    for key in dotted_key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def load_metadata_records(metadata_path: Path) -> list[dict[str, Any]]:
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError(f"Metadata records must be a list: {metadata_path}")
    return records


def check_metadata(metadata_path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for index, record in enumerate(load_metadata_records(metadata_path), start=1):
        case_number = record.get("case_number")
        for field_name in TEXT_FIELDS:
            value = nested_get(record, field_name)
            if isinstance(value, str) and is_suspicious_text(value):
                issues.append(
                    {
                        "source": str(metadata_path),
                        "source_type": "metadata",
                        "record_index": index,
                        "case_number": case_number,
                        "field": field_name,
                        "value": value,
                    }
                )
    return issues


def check_database(db_path: Path) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        fields = ", ".join(DB_FIELDS)
        rows = connection.execute(f"SELECT case_id, {fields} FROM cases ORDER BY roc_year, case_number").fetchall()
        for row in rows:
            for field_name in DB_FIELDS:
                value = row[field_name]
                if isinstance(value, str) and is_suspicious_text(value):
                    issues.append(
                        {
                            "source": str(db_path),
                            "source_type": "database",
                            "case_id": row["case_id"],
                            "case_number": row["case_number"],
                            "field": field_name,
                            "value": value,
                        }
                    )
    return issues


def check_inputs(metadata_paths: list[Path], db_paths: list[Path]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for metadata_path in metadata_paths:
        issues.extend(check_metadata(resolve_project_path(metadata_path)))
    for db_path in db_paths:
        issues.extend(check_database(resolve_project_path(db_path)))

    return {
        "metadata_files": [str(path) for path in metadata_paths],
        "database_files": [str(path) for path in db_paths],
        "issue_count": len(issues),
        "issues": issues,
        "passed": len(issues) == 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check FOI ODS metadata and SQLite DB for mojibake-like text.")
    parser.add_argument("--metadata", action="append", type=Path, default=[], help="Metadata JSON path.")
    parser.add_argument("--db", action="append", type=Path, default=[], help="SQLite DB path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.metadata and not args.db:
        raise SystemExit("Provide at least one --metadata or --db path.")
    report = check_inputs(args.metadata, args.db)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
