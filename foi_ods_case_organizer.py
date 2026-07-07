from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_METADATA = Path("data/foi_ods/metadata/foi_ods_life_roc115_metadata.json")
DEFAULT_CASE_ROOT = Path("data/foi_ods/cases")


class OrganizeError(RuntimeError):
    pass


def default_report_path(metadata_path: Path) -> Path:
    if metadata_path.name.endswith("_metadata.json"):
        return metadata_path.with_name(metadata_path.name.replace("_metadata.json", "_case_organize_report.json"))
    return metadata_path.with_name(f"{metadata_path.stem}_case_organize_report.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_path_part(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.rstrip(". ") or "unknown"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def existing_path(record: dict[str, Any], keys: list[str]) -> Path:
    local_files = record.get("local_files") or {}
    candidates = [local_files.get(key) for key in keys]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    raise OrganizeError(f"Missing source file for {record.get('case_number')!r}: {keys}")


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() == destination.resolve():
        return
    shutil.copy2(source, destination)


def record_year(record: dict[str, Any], fallback_year: int | None) -> int:
    crawl_batch = record.get("crawl_batch") or {}
    year = crawl_batch.get("roc_year") or fallback_year
    if not isinstance(year, int):
        raise OrganizeError(f"Missing ROC year for {record.get('case_number')!r}")
    return year


def case_metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_number": record.get("case_number"),
        "decision_date": record.get("decision_date"),
        "decision_category": record.get("decision_category"),
        "decision_result": record.get("decision_result"),
        "industry": record.get("industry"),
        "industry_subcategory": record.get("industry_subcategory"),
        "dispute_type": record.get("dispute_type"),
        "source": record.get("source"),
        "local_files": record.get("local_files"),
        "text": record.get("text"),
        "retrieval": record.get("retrieval"),
        "crawl_batch": record.get("crawl_batch"),
        "crawl": record.get("crawl"),
        "pdf_download": record.get("pdf_download"),
        "text_extraction": record.get("text_extraction"),
    }


def organize_record(
    *,
    record: dict[str, Any],
    case_root: Path,
    fallback_year: int | None,
) -> dict[str, Any]:
    case_number = record.get("case_number")
    if not case_number:
        raise OrganizeError("Record is missing case_number.")

    dispute_type = record.get("dispute_type") or {}
    dispute_label = dispute_type.get("label")
    if not dispute_label:
        raise OrganizeError(f"{case_number}: missing dispute_type.label")

    roc_year = record_year(record, fallback_year)
    year_dir_name = f"roc{roc_year}"
    dispute_dir_name = safe_path_part(str(dispute_label))
    case_dir_name = safe_path_part(str(case_number))
    case_dir = case_root / year_dir_name / dispute_dir_name / case_dir_name

    pdf_source = existing_path(
        record,
        [
            "pdf_path",
            "source_pdf_path_before_case_organize",
            "planned_pdf_path",
        ],
    )
    raw_text_source = existing_path(
        record,
        [
            "raw_text_path",
            "source_raw_text_path_before_case_organize",
            "planned_raw_text_path",
        ],
    )
    normalized_text_source = existing_path(
        record,
        [
            "normalized_text_path",
            "source_normalized_text_path_before_case_organize",
            "planned_normalized_text_path",
        ],
    )

    pdf_dest = case_dir / "decision.pdf"
    raw_text_dest = case_dir / "raw_text.txt"
    normalized_text_dest = case_dir / "normalized_text.txt"
    metadata_dest = case_dir / "metadata.json"

    copy_file(pdf_source, pdf_dest)
    copy_file(raw_text_source, raw_text_dest)
    copy_file(normalized_text_source, normalized_text_dest)

    local_files = record.setdefault("local_files", {})
    local_files.setdefault("source_pdf_path_before_case_organize", str(pdf_source))
    local_files.setdefault("source_raw_text_path_before_case_organize", str(raw_text_source))
    local_files.setdefault("source_normalized_text_path_before_case_organize", str(normalized_text_source))
    local_files["year_directory"] = str(case_root / year_dir_name)
    local_files["dispute_type_directory"] = str(case_root / year_dir_name / dispute_dir_name)
    local_files["case_directory"] = str(case_dir)
    local_files["pdf_path"] = str(pdf_dest)
    local_files["raw_text_path"] = str(raw_text_dest)
    local_files["normalized_text_path"] = str(normalized_text_dest)
    local_files["case_metadata_path"] = str(metadata_dest)

    retrieval = record.setdefault("retrieval", {})
    retrieval["embedding_text_path"] = str(normalized_text_dest)

    save_json(metadata_dest, case_metadata(record))

    return {
        "case_number": case_number,
        "roc_year": roc_year,
        "dispute_type": dispute_label,
        "case_directory": str(case_dir),
        "pdf_path": str(pdf_dest),
        "raw_text_path": str(raw_text_dest),
        "normalized_text_path": str(normalized_text_dest),
        "metadata_path": str(metadata_dest),
    }


def validate_organized(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for record in records:
        case_number = record.get("case_number", "<unknown>")
        local_files = record.get("local_files") or {}
        for key in ("case_directory", "pdf_path", "raw_text_path", "normalized_text_path", "case_metadata_path"):
            value = local_files.get(key)
            if not value:
                errors.append(f"{case_number}: missing local_files.{key}")
                continue
            path = Path(value)
            if key == "case_directory":
                if not path.is_dir():
                    errors.append(f"{case_number}: case directory does not exist: {value}")
            elif not path.is_file():
                errors.append(f"{case_number}: file does not exist: {value}")
            elif path.stat().st_size <= 0:
                errors.append(f"{case_number}: file is empty: {value}")
    return errors


def organize(args: argparse.Namespace) -> dict[str, Any]:
    data = load_json(args.metadata)
    records = data.get("records")
    if not isinstance(records, list):
        raise OrganizeError("metadata JSON must contain a records list.")

    fallback_year = (data.get("query") or {}).get("roc_year")
    if not isinstance(fallback_year, int):
        fallback_year = None

    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for record in records:
        try:
            results.append(
                organize_record(record=record, case_root=args.case_root, fallback_year=fallback_year)
            )
        except Exception as error:
            failures.append(
                {
                    "case_number": str(record.get("case_number")),
                    "error": repr(error),
                }
            )

    validation_errors = validate_organized(records)
    dispute_counts = Counter(result["dispute_type"] for result in results)
    year_counts = Counter(str(result["roc_year"]) for result in results)

    data.setdefault("storage", {})
    data["storage"]["case_root"] = str(args.case_root)
    data["storage"]["case_organized"] = not failures and not validation_errors
    data["case_organization"] = {
        "organized_at": now_iso(),
        "structure": "year/dispute_type/case",
        "case_root": str(args.case_root),
        "record_count": len(records),
        "success_count": len(results),
        "failure_count": len(failures),
        "failures": failures,
        "year_counts": dict(sorted(year_counts.items())),
        "dispute_type_counts": dict(sorted(dispute_counts.items())),
        "validation_errors": validation_errors,
    }
    data.setdefault("validation", {})
    data["validation"]["case_organized"] = not failures and not validation_errors
    data["validation"]["case_organization_errors"] = validation_errors

    save_json(args.metadata, data)
    report = data["case_organization"] | {
        "metadata": str(args.metadata),
        "sample_results": results[:5],
    }
    save_json(args.report, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize FOI ODS files by year, dispute type, and case.")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--case-root", type=Path, default=DEFAULT_CASE_ROOT)
    args = parser.parse_args()
    if args.report is None:
        args.report = default_report_path(args.metadata)
    return args


def main() -> None:
    args = parse_args()
    report = organize(args)
    print(
        json.dumps(
            {
                "metadata": str(args.metadata),
                "case_root": str(args.case_root),
                "record_count": report["record_count"],
                "success_count": report["success_count"],
                "failure_count": report["failure_count"],
                "validation_error_count": len(report["validation_errors"]),
                "report": str(args.report),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
