from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA = PROJECT_ROOT / "data" / "foi_ods" / "metadata" / "foi_ods_life_roc115_metadata.json"
SCHEMA_PATH = PROJECT_ROOT / "backend" / "schema.sql"


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


DEFAULT_DB_PATH = resolve_project_path(os.environ.get("INSURANCE_CASES_DB_PATH", "backend/data/insurance_cases.db"))


class ImportError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def case_id_for(case_number: str) -> str:
    digest = hashlib.sha1(case_number.encode("utf-8")).hexdigest()[:16]
    return f"case_{digest}"


def label(record: dict[str, Any], key: str) -> str | None:
    value = record.get(key)
    if isinstance(value, dict):
        item = value.get("label")
        return str(item) if item is not None else None
    return str(value) if value is not None else None


def resolve_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_text_file(path_value: str | None) -> str:
    path = resolve_path(path_value)
    if path is None:
        return ""
    if not path.is_file():
        raise ImportError(f"Missing text file: {path}")
    return path.read_text(encoding="utf-8")


def load_metadata(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ImportError(f"Metadata file does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("records"), list):
        raise ImportError("Metadata JSON must contain a top-level records list.")
    return data


def resolve_metadata_inputs(
    metadata_paths: Sequence[Path] | None = None,
    metadata_dirs: Sequence[Path] | None = None,
) -> list[Path]:
    paths: list[Path] = []

    for metadata_path in metadata_paths or []:
        paths.append(metadata_path)

    for metadata_dir in metadata_dirs or []:
        if not metadata_dir.is_dir():
            raise ImportError(f"Metadata directory does not exist: {metadata_dir}")
        matched_paths = sorted(metadata_dir.glob("*_metadata.json"))
        if not matched_paths:
            raise ImportError(f"Metadata directory contains no *_metadata.json files: {metadata_dir}")
        paths.extend(matched_paths)

    if not paths:
        paths.append(DEFAULT_METADATA)

    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(path)

    return unique_paths


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def reset_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DELETE FROM case_search;
        DELETE FROM chunk_embeddings;
        DELETE FROM case_chunks;
        DELETE FROM case_summaries;
        DELETE FROM case_texts;
        DELETE FROM cases;
        """
    )


def validate_record_paths(record: dict[str, Any]) -> None:
    case_number = record.get("case_number", "<unknown>")
    local_files = record.get("local_files") or {}
    for key in ("pdf_path", "raw_text_path", "normalized_text_path", "case_metadata_path"):
        path = resolve_path(local_files.get(key))
        if path is None or not path.is_file():
            raise ImportError(f"{case_number}: missing local_files.{key}: {path}")


def record_to_case_row(record: dict[str, Any], imported_at: str) -> tuple[Any, ...]:
    case_number = record.get("case_number")
    if not case_number:
        raise ImportError("Record is missing case_number.")

    local_files = record.get("local_files") or {}
    source = record.get("source") or {}
    crawl_batch = record.get("crawl_batch") or {}
    roc_year = crawl_batch.get("roc_year")
    if not isinstance(roc_year, int):
        query_year = ((record.get("query") or {}).get("roc_year"))
        roc_year = query_year if isinstance(query_year, int) else None
    if not isinstance(roc_year, int):
        raise ImportError(f"{case_number}: missing ROC year.")

    return (
        case_id_for(str(case_number)),
        str(case_number),
        roc_year,
        record.get("decision_date"),
        label(record, "decision_category"),
        label(record, "decision_result"),
        label(record, "industry"),
        label(record, "industry_subcategory"),
        label(record, "dispute_type"),
        source.get("pdf_url"),
        local_files.get("case_directory"),
        local_files.get("pdf_path"),
        local_files.get("raw_text_path"),
        local_files.get("normalized_text_path"),
        local_files.get("case_metadata_path"),
        imported_at,
        imported_at,
    )


def import_record(connection: sqlite3.Connection, record: dict[str, Any], imported_at: str) -> None:
    validate_record_paths(record)
    case_row = record_to_case_row(record, imported_at)
    case_id = case_row[0]
    case_number = case_row[1]
    dispute_type = case_row[8]
    local_files = record.get("local_files") or {}
    text_info = record.get("text") or {}
    extraction = record.get("text_extraction") or {}

    raw_text = read_text_file(local_files.get("raw_text_path"))
    normalized_text = read_text_file(local_files.get("normalized_text_path"))

    connection.execute(
        """
        INSERT INTO cases (
          case_id, case_number, roc_year, decision_date, decision_category,
          decision_result, industry, industry_subcategory, dispute_type,
          source_pdf_url, case_directory, pdf_path, raw_text_path,
          normalized_text_path, metadata_path, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
          case_number = excluded.case_number,
          roc_year = excluded.roc_year,
          decision_date = excluded.decision_date,
          decision_category = excluded.decision_category,
          decision_result = excluded.decision_result,
          industry = excluded.industry,
          industry_subcategory = excluded.industry_subcategory,
          dispute_type = excluded.dispute_type,
          source_pdf_url = excluded.source_pdf_url,
          case_directory = excluded.case_directory,
          pdf_path = excluded.pdf_path,
          raw_text_path = excluded.raw_text_path,
          normalized_text_path = excluded.normalized_text_path,
          metadata_path = excluded.metadata_path,
          updated_at = excluded.updated_at;
        """,
        case_row,
    )
    connection.execute(
        """
        INSERT INTO case_texts (
          case_id, raw_text, normalized_text, raw_text_chars,
          normalized_text_chars, page_count, extraction_method
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
          raw_text = excluded.raw_text,
          normalized_text = excluded.normalized_text,
          raw_text_chars = excluded.raw_text_chars,
          normalized_text_chars = excluded.normalized_text_chars,
          page_count = excluded.page_count,
          extraction_method = excluded.extraction_method;
        """,
        (
            case_id,
            raw_text,
            normalized_text,
            text_info.get("raw_text_chars") or extraction.get("raw_text_chars") or len(raw_text),
            text_info.get("normalized_text_chars") or extraction.get("normalized_text_chars") or len(normalized_text),
            text_info.get("page_count") or extraction.get("page_count"),
            text_info.get("extraction_method") or extraction.get("method"),
        ),
    )
    connection.execute("DELETE FROM case_search WHERE case_id = ?", (case_id,))
    connection.execute(
        """
        INSERT INTO case_search (case_id, case_number, dispute_type, normalized_text)
        VALUES (?, ?, ?, ?);
        """,
        (case_id, case_number, dispute_type, normalized_text),
    )


def normalize_metadata_paths(metadata_paths: Path | Sequence[Path]) -> list[Path]:
    if isinstance(metadata_paths, Path):
        return [metadata_paths]
    return list(metadata_paths)


def import_cases(metadata_paths: Path | Sequence[Path], db_path: Path, recreate: bool) -> dict[str, Any]:
    metadata_file_paths = normalize_metadata_paths(metadata_paths)
    metadata_sources = [
        {
            "path": str(metadata_path),
            "record_count": len(load_metadata(metadata_path)["records"]),
        }
        for metadata_path in metadata_file_paths
    ]
    imported_at = now_iso()

    with connect(db_path) as connection:
        initialize_schema(connection)
        if recreate:
            reset_tables(connection)
        failures: list[dict[str, str]] = []
        success_count = 0
        for metadata_path in metadata_file_paths:
            records = load_metadata(metadata_path)["records"]
            for record in records:
                try:
                    import_record(connection, record, imported_at)
                    success_count += 1
                except Exception as error:
                    failures.append(
                        {
                            "metadata": str(metadata_path),
                            "case_number": str(record.get("case_number")),
                            "error": repr(error),
                        }
                    )

        counts = {
            "cases": connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
            "case_texts": connection.execute("SELECT COUNT(*) FROM case_texts").fetchone()[0],
            "case_search": connection.execute("SELECT COUNT(*) FROM case_search").fetchone()[0],
        }

    return {
        "metadata": str(metadata_file_paths[0]) if len(metadata_file_paths) == 1 else [str(path) for path in metadata_file_paths],
        "metadata_files": [str(path) for path in metadata_file_paths],
        "metadata_sources": metadata_sources,
        "database": str(db_path),
        "record_count": sum(source["record_count"] for source in metadata_sources),
        "success_count": success_count,
        "failure_count": len(failures),
        "failures": failures[:20],
        "counts": counts,
        "imported_at": imported_at,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import FOI ODS case files into SQLite.")
    parser.add_argument(
        "--metadata",
        type=Path,
        action="append",
        default=None,
        help="Metadata JSON path. Can be provided multiple times.",
    )
    parser.add_argument(
        "--metadata-dir",
        type=Path,
        action="append",
        default=None,
        help="Directory containing *_metadata.json files. Can be provided multiple times.",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--recreate", action="store_true", help="Clear imported tables before importing.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata_paths = resolve_metadata_inputs(args.metadata, args.metadata_dir)
    report = import_cases(metadata_paths, args.db, args.recreate)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["failure_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
