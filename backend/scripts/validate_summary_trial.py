from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.services.document_section_service import structure_document_text
from backend.app.services.summary_generation_service import LAW_NAME_RE
from backend.app.services.summary_generation_service import POLICY_REFERENCE_RE
from backend.app.services.summary_generation_service import SUMMARY_CATEGORY_BY_SECTION_TYPE
from backend.app.services.summary_generation_service import _is_supported_quote
from backend.app.services.summary_generation_service import normalize_evidence
from backend.scripts.run_summary_trial import connect_read_only
from backend.scripts.run_summary_trial import configure_utf8_console
from backend.scripts.run_summary_trial import resolve_project_path


DEFAULT_REPORT_PATH = PROJECT_ROOT / "outputs" / "local_llm_summary_trial_qwen3_4b_final_v4.json"


def load_structured_document(connection: Any, case_id: str) -> dict[str, Any]:
    """Load one source through the same parser used by summary generation."""

    row = connection.execute(
        """
        SELECT case_texts.normalized_text, case_texts.raw_text
        FROM case_texts
        WHERE case_texts.case_id = ?;
        """,
        (case_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Case text not found for {case_id}.")
    source_text = row["normalized_text"] or row["raw_text"] or ""
    source_type = "normalized" if row["normalized_text"] else "raw"
    return structure_document_text(case_id, source_text, source_type)


def validate_report(report: dict[str, Any], *, database_path: Path) -> dict[str, Any]:
    """Validate actual evidence, role boundaries, laws, and degraded requests."""

    violations: list[dict[str, Any]] = []
    evidence_checked = 0
    legal_references_checked = 0
    required_fields = ("background", "applicant_position", "respondent_position", "decision_result")

    if report.get("database_mode") != "read_only":
        violations.append({"scope": "report", "message": "database_mode is not read_only"})
    if report.get("errors"):
        violations.append({"scope": "report", "message": "top-level case errors are present"})
    if len(report.get("results") or []) != len(report.get("selected_cases") or []):
        violations.append({"scope": "report", "message": "selected/result case counts differ"})

    with connect_read_only(database_path) as connection:
        for result in report.get("results") or []:
            case_number = str(result.get("case_number") or "")
            summary = result.get("summary") or {}
            generation = result.get("generation") or {}
            structured_document = load_structured_document(connection, str(result.get("case_id") or ""))
            section_map = {str(section["section_id"]): section for section in structured_document.get("sections", [])}

            for field in required_fields:
                if not str(summary.get(field) or "").strip():
                    violations.append({"case_number": case_number, "scope": field, "message": "required field is empty"})
            for field in ("core_issues", "reasoning_points"):
                if not summary.get(field):
                    violations.append({"case_number": case_number, "scope": field, "message": "required list is empty"})
            if int(generation.get("failed_request_count") or 0) > 0:
                violations.append(
                    {"case_number": case_number, "scope": "generation", "message": "failed local requests are present"}
                )
            if generation.get("final_merge_fallback"):
                violations.append(
                    {"case_number": case_number, "scope": "generation", "message": "final merge used fallback"}
                )

            for evidence in summary.get("evidence") or []:
                evidence_checked += 1
                section_id = str(evidence.get("section_id") or "")
                section = section_map.get(section_id)
                if section is None:
                    violations.append(
                        {"case_number": case_number, "scope": "evidence", "message": f"unknown section {section_id}"}
                    )
                    continue
                expected_category = SUMMARY_CATEGORY_BY_SECTION_TYPE.get(str(section.get("section_type") or ""))
                if evidence.get("category") != expected_category:
                    violations.append(
                        {
                            "case_number": case_number,
                            "scope": "evidence",
                            "message": f"category mismatch for {section_id}",
                        }
                    )
                if not _is_supported_quote(str(evidence.get("evidence_quote") or ""), str(section.get("content") or "")):
                    violations.append(
                        {
                            "case_number": case_number,
                            "scope": "evidence",
                            "message": f"quote is not in source section {section_id}",
                        }
                    )

            for reference in summary.get("legal_references") or []:
                legal_references_checked += 1
                section_id = str(reference.get("section_id") or "")
                section = section_map.get(section_id)
                law_name = str(reference.get("law_name") or "")
                article = str(reference.get("article") or "")
                section_text = str(section.get("content") or "") if section else ""
                if (
                    section is None
                    or not LAW_NAME_RE.search(law_name)
                    or POLICY_REFERENCE_RE.search(law_name)
                    or normalize_evidence(law_name) not in normalize_evidence(section_text)
                    or normalize_evidence(article) not in normalize_evidence(section_text)
                    or not _is_supported_quote(str(reference.get("evidence_quote") or ""), section_text)
                ):
                    violations.append(
                        {
                            "case_number": case_number,
                            "scope": "legal_reference",
                            "message": f"invalid source-grounded law: {law_name} {article}",
                        }
                    )

    return {
        "valid": not violations,
        "database": str(database_path),
        "case_count": len(report.get("results") or []),
        "evidence_checked": evidence_checked,
        "legal_references_checked": legal_references_checked,
        "violations": violations,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a local LLM summary trial against the read-only source DB.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--db", type=Path)
    return parser.parse_args()


def main() -> None:
    configure_utf8_console()
    args = parse_args()
    report_path = resolve_project_path(args.report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    database_path = resolve_project_path(args.db or report["database"])
    validation = validate_report(report, database_path=database_path)
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    if not validation["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
