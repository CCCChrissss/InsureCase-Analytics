from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.app.database import PROJECT_ROOT, connect


VALID_PAGE_SIZE_MAX = 100


def clamp_pagination(page: int, page_size: int) -> tuple[int, int, int]:
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), VALID_PAGE_SIZE_MAX)
    offset = (safe_page - 1) * safe_page_size
    return safe_page, safe_page_size, offset


def build_case_filters(
    *,
    roc_year: int | None = None,
    dispute_type: str | None = None,
    case_number: str | None = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if roc_year is not None:
        clauses.append("roc_year = ?")
        params.append(roc_year)
    if dispute_type:
        clauses.append("dispute_type = ?")
        params.append(dispute_type)
    if case_number:
        clauses.append("case_number LIKE ?")
        params.append(f"%{case_number}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


def list_cases(
    *,
    page: int = 1,
    page_size: int = 20,
    roc_year: int | None = None,
    dispute_type: str | None = None,
    case_number: str | None = None,
) -> dict[str, Any]:
    safe_page, safe_page_size, offset = clamp_pagination(page, page_size)
    where, params = build_case_filters(
        roc_year=roc_year,
        dispute_type=dispute_type,
        case_number=case_number,
    )
    with connect() as connection:
        total = connection.execute(f"SELECT COUNT(*) FROM cases {where}", params).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT case_id, case_number, roc_year, decision_date, decision_category,
                   decision_result, industry, industry_subcategory, dispute_type,
                   pdf_path, normalized_text_path
            FROM cases
            {where}
            ORDER BY decision_date DESC, case_number DESC
            LIMIT ? OFFSET ?;
            """,
            [*params, safe_page_size, offset],
        ).fetchall()
    return {
        "items": [dict(row) for row in rows],
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
    }


def get_case(case_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT cases.case_id, case_number, roc_year, decision_date,
                   decision_category, decision_result, industry,
                   industry_subcategory, dispute_type, source_pdf_url,
                   case_directory, pdf_path, raw_text_path, normalized_text_path,
                   metadata_path, raw_text, normalized_text, raw_text_chars,
                   normalized_text_chars, page_count, extraction_method
            FROM cases
            JOIN case_texts ON case_texts.case_id = cases.case_id
            WHERE cases.case_id = ?;
            """,
            (case_id,),
        ).fetchone()
    return dict(row) if row else None


def list_dispute_types() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT dispute_type AS name, COUNT(*) AS count
            FROM cases
            WHERE dispute_type IS NOT NULL AND dispute_type != ''
            GROUP BY dispute_type
            ORDER BY count DESC, dispute_type ASC;
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_pdf_path(case_id: str) -> Path | None:
    with connect() as connection:
        row = connection.execute("SELECT pdf_path FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if row is None or not row["pdf_path"]:
        return None
    path = Path(row["pdf_path"])
    return path if path.is_absolute() else PROJECT_ROOT / path
