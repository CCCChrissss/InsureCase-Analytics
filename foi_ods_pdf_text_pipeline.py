from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pdfplumber
import requests
from pypdf import PdfReader


DEFAULT_METADATA = Path("data/foi_ods/metadata/foi_ods_life_roc115_metadata.json")
DEFAULT_REPORT = Path("data/foi_ods/metadata/foi_ods_life_roc115_pdf_text_report.json")


class PipelineError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_embedding_text(record: dict[str, Any], normalized_text: str) -> str:
    parts = [
        record.get("case_number"),
        record.get("decision_date"),
        (record.get("decision_category") or {}).get("label"),
        (record.get("decision_result") or {}).get("label"),
        (record.get("industry") or {}).get("label"),
        (record.get("industry_subcategory") or {}).get("label"),
        (record.get("dispute_type") or {}).get("label"),
        ((record.get("result_row") or {}).get("keyword_context")),
        normalized_text,
    ]
    return "\n".join(str(part).strip() for part in parts if part and str(part).strip())


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def path_from_record(record: dict[str, Any], planned_key: str) -> Path:
    local_files = record.get("local_files") or {}
    planned_path = local_files.get(planned_key)
    if not planned_path:
        raise PipelineError(f"Missing local_files.{planned_key} for {record.get('case_number')!r}")
    return Path(planned_path)


def download_pdf(
    *,
    session: requests.Session,
    url: str,
    target_path: Path,
    overwrite: bool,
) -> dict[str, Any]:
    if target_path.exists() and target_path.stat().st_size > 0 and not overwrite:
        return {
            "status": "skipped_existing",
            "bytes": target_path.stat().st_size,
            "content_type": None,
            "downloaded_at": None,
        }

    ensure_parent(target_path)
    response = session.get(url, timeout=60)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    content = response.content
    if "pdf" not in content_type.lower() and not content.startswith(b"%PDF"):
        raise PipelineError(f"Download is not a PDF: content-type={content_type!r}, url={url}")
    target_path.write_bytes(content)
    return {
        "status": "downloaded",
        "bytes": len(content),
        "content_type": content_type,
        "downloaded_at": now_iso(),
    }


def extract_with_pdfplumber(pdf_path: Path) -> tuple[str, int]:
    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        page_count = len(pdf.pages)
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            pages.append(f"\n\n--- page {index} ---\n{text}".strip())
    return "\n\n".join(pages).strip(), page_count


def extract_with_pypdf(pdf_path: Path) -> tuple[str, int]:
    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append(f"\n\n--- page {index} ---\n{text}".strip())
    return "\n\n".join(pages).strip(), len(reader.pages)


def extract_text(pdf_path: Path) -> dict[str, Any]:
    try:
        raw_text, page_count = extract_with_pdfplumber(pdf_path)
        method = "pdfplumber"
    except Exception as pdfplumber_error:
        try:
            raw_text, page_count = extract_with_pypdf(pdf_path)
            method = "pypdf"
        except Exception as pypdf_error:
            raise PipelineError(
                f"Text extraction failed with pdfplumber and pypdf: "
                f"pdfplumber={pdfplumber_error!r}; pypdf={pypdf_error!r}"
            ) from pypdf_error

    normalized = normalize_text(raw_text)
    return {
        "method": method,
        "page_count": page_count,
        "raw_text": raw_text,
        "normalized_text": normalized,
        "raw_text_chars": len(raw_text),
        "normalized_text_chars": len(normalized),
    }


def process_record(
    *,
    session: requests.Session,
    record: dict[str, Any],
    overwrite: bool,
) -> dict[str, Any]:
    case_number = record.get("case_number") or "<missing case_number>"
    source = record.get("source") or {}
    pdf_url = source.get("pdf_url")
    if not pdf_url:
        raise PipelineError(f"Missing source.pdf_url for {case_number}")

    pdf_path = path_from_record(record, "planned_pdf_path")
    raw_text_path = path_from_record(record, "planned_raw_text_path")
    normalized_text_path = path_from_record(record, "planned_normalized_text_path")

    download_info = download_pdf(session=session, url=pdf_url, target_path=pdf_path, overwrite=overwrite)
    extracted = extract_text(pdf_path)

    ensure_parent(raw_text_path)
    ensure_parent(normalized_text_path)
    raw_text_path.write_text(extracted["raw_text"], encoding="utf-8")
    normalized_text_path.write_text(extracted["normalized_text"], encoding="utf-8")

    embedding_text = build_embedding_text(record, extracted["normalized_text"])
    local_files = record.setdefault("local_files", {})
    local_files["pdf_path"] = str(pdf_path)
    local_files["raw_text_path"] = str(raw_text_path)
    local_files["normalized_text_path"] = str(normalized_text_path)

    record["text"] = {
        "raw": None,
        "normalized": None,
        "raw_text_chars": extracted["raw_text_chars"],
        "normalized_text_chars": extracted["normalized_text_chars"],
        "page_count": extracted["page_count"],
        "extraction_method": extracted["method"],
        "raw_text_stored_in_file": True,
        "normalized_text_stored_in_file": True,
    }
    record["retrieval"] = {
        "keywords": (record.get("retrieval") or {}).get("keywords", []),
        "embedding_text": None,
        "embedding_text_path": str(normalized_text_path),
        "embedding_text_chars": len(embedding_text),
    }
    record["pdf_download"] = download_info
    record["text_extraction"] = {
        "status": "ok",
        "method": extracted["method"],
        "page_count": extracted["page_count"],
        "raw_text_chars": extracted["raw_text_chars"],
        "normalized_text_chars": extracted["normalized_text_chars"],
        "extracted_at": now_iso(),
        "error": None,
    }
    record.setdefault("crawl", {})
    record["crawl"]["status"] = "ok"
    record["crawl"]["error"] = None
    return {
        "case_number": case_number,
        "status": "ok",
        "pdf_path": str(pdf_path),
        "raw_text_path": str(raw_text_path),
        "normalized_text_path": str(normalized_text_path),
        "download_status": download_info["status"],
        "page_count": extracted["page_count"],
        "normalized_text_chars": extracted["normalized_text_chars"],
    }


def validate_files(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for index, record in enumerate(data.get("records", []), start=1):
        case_number = record.get("case_number", f"record {index}")
        local_files = record.get("local_files") or {}
        for key in ("pdf_path", "raw_text_path", "normalized_text_path"):
            value = local_files.get(key)
            if not value:
                errors.append(f"{case_number}: missing local_files.{key}")
                continue
            path = Path(value)
            if not path.exists():
                errors.append(f"{case_number}: file does not exist: {value}")
            elif path.stat().st_size <= 0:
                errors.append(f"{case_number}: file is empty: {value}")

        extraction = record.get("text_extraction") or {}
        if extraction.get("status") != "ok":
            errors.append(f"{case_number}: extraction status is not ok")
        elif (extraction.get("normalized_text_chars") or 0) <= 0:
            errors.append(f"{case_number}: normalized text is empty")
    return errors


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    data = load_json(args.metadata)
    records = data.get("records")
    if not isinstance(records, list):
        raise PipelineError("metadata JSON must contain a top-level records list.")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Accept": "application/pdf,text/html;q=0.8,*/*;q=0.7",
            "Referer": "https://ods.foi.org.tw/",
        }
    )

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        case_number = record.get("case_number", f"record-{index}")
        try:
            result = process_record(session=session, record=record, overwrite=args.overwrite)
            results.append(result)
            if args.progress_every and index % args.progress_every == 0:
                print(f"processed {index}/{len(records)}")
        except Exception as error:
            message = repr(error)
            failures.append({"case_number": case_number, "error": message})
            record.setdefault("crawl", {})
            record["crawl"]["status"] = "error"
            record["crawl"]["error"] = message
            record["text_extraction"] = {
                "status": "error",
                "method": None,
                "page_count": None,
                "raw_text_chars": 0,
                "normalized_text_chars": 0,
                "extracted_at": now_iso(),
                "error": message,
            }
        time.sleep(args.delay_seconds)

    data.setdefault("storage", {})
    data["storage"].update(
        {
            "pdf_downloaded": len(failures) == 0,
            "pdf_text_extracted": len(failures) == 0,
        }
    )
    data["pdf_text_pipeline"] = {
        "processed_at": now_iso(),
        "record_count": len(records),
        "success_count": len(results),
        "failure_count": len(failures),
        "failures": failures,
        "raw_text_embedded_in_json": False,
        "normalized_text_embedded_in_json": False,
    }
    data.setdefault("validation", {})
    data["validation"]["pdf_downloaded"] = len(failures) == 0
    data["validation"]["pdf_text_extracted"] = len(failures) == 0
    data["validation"]["file_validation_errors"] = validate_files(data)

    save_json(args.metadata, data)
    report = {
        "metadata": str(args.metadata),
        "processed_at": data["pdf_text_pipeline"]["processed_at"],
        "record_count": len(records),
        "success_count": len(results),
        "failure_count": len(failures),
        "failures": failures,
        "file_validation_errors": data["validation"]["file_validation_errors"],
        "sample_results": results[:5],
    }
    save_json(args.report, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download FOI ODS PDFs and extract text files.")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--delay-seconds", type=float, default=0.2)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_pipeline(args)
    print(
        json.dumps(
            {
                "metadata": report["metadata"],
                "record_count": report["record_count"],
                "success_count": report["success_count"],
                "failure_count": report["failure_count"],
                "file_validation_error_count": len(report["file_validation_errors"]),
                "report": str(args.report),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
