from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import OLLAMA_BASE_URL
from backend.app.config import SUMMARY_MODEL
from backend.app.config import SUMMARY_MAX_OUTPUT_TOKENS
from backend.app.config import SUMMARY_NUM_CTX
from backend.app.config import SUMMARY_REQUEST_TIMEOUT_SECONDS
from backend.app.config import SUMMARY_SECTION_MAX_CHARS
from backend.app.services.document_section_service import structure_document_text
from backend.app.services.summary_generation_service import build_source_packets
from backend.app.services.summary_generation_service import create_summary_provider
from backend.app.services.summary_generation_service import generate_case_summary
from backend.app.services.summary_generation_service import utc_now_iso


DEFAULT_DB_PATH = PROJECT_ROOT / "backend" / "data" / "insurance_cases_local_bge_trial.db"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "local_llm_summary_trial_qwen3_4b.json"


def configure_utf8_console() -> None:
    """Prevent Windows CP950 from failing when a local model emits Unicode text."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def connect_read_only(db_path: Path) -> sqlite3.Connection:
    """Open SQLite in read-only mode so a POC trial cannot alter formal case data."""

    if not db_path.is_file():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def select_representative_case_ids(
    connection: sqlite3.Connection,
    *,
    limit: int,
) -> list[str]:
    """Select deterministic length quantiles while preferring different dispute types."""

    if limit <= 0:
        raise ValueError("limit must be greater than 0.")
    rows = connection.execute(
        """
        SELECT cases.case_id, cases.dispute_type, cases.decision_result,
               COALESCE(case_texts.normalized_text_chars, LENGTH(case_texts.normalized_text), 0) AS text_chars
        FROM cases
        JOIN case_texts ON case_texts.case_id = cases.case_id
        WHERE COALESCE(case_texts.normalized_text, '') <> ''
          AND COALESCE(case_texts.normalized_text_chars, LENGTH(case_texts.normalized_text), 0) >= 1000
        ORDER BY text_chars, cases.case_number;
        """
    ).fetchall()
    if not rows:
        return []

    indexed_rows = list(enumerate(rows))
    targets = [round(index * (len(rows) - 1) / max(limit - 1, 1)) for index in range(limit)]
    selected: list[sqlite3.Row] = []
    used_case_ids: set[str] = set()
    used_dispute_types: set[str] = set()
    for target in targets:
        ranked = sorted(
            indexed_rows,
            key=lambda indexed_row: (
                indexed_row[1]["case_id"] in used_case_ids,
                indexed_row[1]["dispute_type"] in used_dispute_types,
                abs(indexed_row[0] - target),
                indexed_row[1]["case_id"],
            ),
        )
        choice = next(
            (row for _, row in ranked if row["case_id"] not in used_case_ids),
            None,
        )
        if choice is None:
            break
        selected.append(choice)
        used_case_ids.add(choice["case_id"])
        used_dispute_types.add(choice["dispute_type"])
    return [str(row["case_id"]) for row in selected]


def load_cases(
    connection: sqlite3.Connection,
    *,
    limit: int,
    case_numbers: list[str] | None = None,
) -> list[dict[str, Any]]:
    if case_numbers:
        placeholders = ",".join("?" for _ in case_numbers)
        rows = connection.execute(
            f"""
            SELECT cases.case_id, cases.case_number, cases.decision_date,
                   cases.dispute_type, cases.decision_result,
                   case_texts.normalized_text, case_texts.raw_text
            FROM cases
            JOIN case_texts ON case_texts.case_id = cases.case_id
            WHERE cases.case_number IN ({placeholders});
            """,
            case_numbers,
        ).fetchall()
        by_number = {row["case_number"]: dict(row) for row in rows}
        missing = [number for number in case_numbers if number not in by_number]
        if missing:
            raise ValueError(f"Case numbers not found: {missing}")
        return [by_number[number] for number in case_numbers]

    case_ids = select_representative_case_ids(connection, limit=limit)
    if not case_ids:
        return []
    placeholders = ",".join("?" for _ in case_ids)
    rows = connection.execute(
        f"""
        SELECT cases.case_id, cases.case_number, cases.decision_date,
               cases.dispute_type, cases.decision_result,
               case_texts.normalized_text, case_texts.raw_text
        FROM cases
        JOIN case_texts ON case_texts.case_id = cases.case_id
        WHERE cases.case_id IN ({placeholders});
        """,
        case_ids,
    ).fetchall()
    by_id = {row["case_id"]: dict(row) for row in rows}
    return [by_id[case_id] for case_id in case_ids]


def write_json_atomic(output_path: Path, payload: dict[str, Any]) -> None:
    """Replace the report only after a complete UTF-8 JSON document is written."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(output_path)


def build_trial_report(
    *,
    db_path: Path,
    output_path: Path,
    limit: int,
    case_numbers: list[str] | None,
    model_name: str,
    base_url: str,
    timeout_seconds: int,
    num_ctx: int,
    max_output_tokens: int,
    max_section_chars: int,
    dry_run: bool,
) -> dict[str, Any]:
    with connect_read_only(db_path) as connection:
        cases = load_cases(connection, limit=limit, case_numbers=case_numbers)
    selected: list[dict[str, Any]] = []
    for case in cases:
        source_text = case.get("normalized_text") or case.get("raw_text") or ""
        source_type = "normalized" if case.get("normalized_text") else "raw"
        structured_document = structure_document_text(case["case_id"], source_text, source_type)
        packet_count = len(build_source_packets(structured_document, max_chars=max_section_chars))
        selected.append(
            {
                "case_id": case["case_id"],
                "case_number": case["case_number"],
                "dispute_type": case["dispute_type"],
                "decision_result": case["decision_result"],
                "source_chars": len(source_text),
                "packet_count": packet_count,
                "estimated_request_count": packet_count + 1,
            }
        )
    report: dict[str, Any] = {
        "trial_version": "local_llm_summary_trial_v1",
        "database": str(db_path),
        "database_mode": "read_only",
        "output": str(output_path),
        "provider": "ollama_local",
        "model": model_name,
        "base_url": base_url,
        "num_ctx": num_ctx,
        "max_output_tokens": max_output_tokens,
        "max_section_chars": max_section_chars,
        "selected_cases": selected,
        "dry_run": dry_run,
        "results": [],
        "errors": [],
        "created_at": utc_now_iso(),
    }
    if dry_run:
        return report

    provider = create_summary_provider(
        model_name=model_name,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
        num_ctx=num_ctx,
        max_output_tokens=max_output_tokens,
    )
    try:
        report["model_inventory"] = provider.ensure_model_available()
        for index, case in enumerate(cases, start=1):
            print(f"[{index}/{len(cases)}] 產生摘要：{case['case_number']}", file=sys.stderr, flush=True)
            source_text = case.get("normalized_text") or case.get("raw_text") or ""
            source_type = "normalized" if case.get("normalized_text") else "raw"
            structured_document = structure_document_text(case["case_id"], source_text, source_type)
            try:
                result = generate_case_summary(
                    case_metadata=case,
                    structured_document=structured_document,
                    provider=provider,
                    max_section_chars=max_section_chars,
                )
                report["results"].append(result)
            except Exception as error:  # Keep completed cases available for POC diagnosis.
                report["errors"].append(
                    {
                        "case_id": case["case_id"],
                        "case_number": case["case_number"],
                        "error_type": type(error).__name__,
                        "message": str(error),
                    }
                )
                write_json_atomic(output_path, report)
    finally:
        provider.close()
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a read-only local Ollama summary trial for representative cases.")
    parser.add_argument(
        "--db",
        type=Path,
        default=resolve_project_path(os.environ.get("INSURANCE_CASES_DB_PATH", DEFAULT_DB_PATH)),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--case-number", action="append", dest="case_numbers")
    parser.add_argument("--model", default=SUMMARY_MODEL)
    parser.add_argument("--base-url", default=OLLAMA_BASE_URL)
    parser.add_argument("--timeout-seconds", type=int, default=SUMMARY_REQUEST_TIMEOUT_SECONDS)
    parser.add_argument("--num-ctx", type=int, default=SUMMARY_NUM_CTX)
    parser.add_argument("--max-output-tokens", type=int, default=SUMMARY_MAX_OUTPUT_TOKENS)
    parser.add_argument("--max-section-chars", type=int, default=SUMMARY_SECTION_MAX_CHARS)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    configure_utf8_console()
    args = parse_args()
    if args.limit <= 0 or args.limit > 20:
        raise SystemExit("--limit must be between 1 and 20 for a bounded POC trial.")
    db_path = resolve_project_path(args.db)
    output_path = resolve_project_path(args.output)
    report = build_trial_report(
        db_path=db_path,
        output_path=output_path,
        limit=args.limit,
        case_numbers=args.case_numbers,
        model_name=args.model,
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
        num_ctx=args.num_ctx,
        max_output_tokens=args.max_output_tokens,
        max_section_chars=args.max_section_chars,
        dry_run=args.dry_run,
    )
    if not args.dry_run:
        write_json_atomic(output_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
