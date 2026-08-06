from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.app.schemas import CaseDetail, CaseDocumentSections, CountItem, PaginatedCases
from backend.app.services.case_service import get_case, get_pdf_path, list_cases, list_dispute_types
from backend.app.services.document_section_service import structure_case_document


router = APIRouter(prefix="/api", tags=["cases"])


@router.get("/cases", response_model=PaginatedCases)
def get_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    roc_year: int | None = None,
    dispute_type: str | None = None,
    case_number: str | None = None,
) -> dict:
    return list_cases(
        page=page,
        page_size=page_size,
        roc_year=roc_year,
        dispute_type=dispute_type,
        case_number=case_number,
    )


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case_detail(case_id: str) -> dict:
    case = get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case


@router.get("/cases/{case_id}/document-sections", response_model=CaseDocumentSections)
def get_case_document_sections(case_id: str) -> dict:
    """Return complete source text as ordered sections for the case workspace."""

    case = get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    if not case.get("normalized_text") and not case.get("raw_text"):
        raise HTTPException(status_code=404, detail="Case text not found.")
    return structure_case_document(case)


@router.get("/dispute-types", response_model=list[CountItem])
def get_dispute_types(roc_year: int | None = Query(default=None, ge=1)) -> list[dict]:
    return list_dispute_types(roc_year=roc_year)


@router.get("/files/{case_id}/pdf")
def get_case_pdf(case_id: str) -> FileResponse:
    pdf_path = get_pdf_path(case_id)
    if pdf_path is None or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found.")
    return FileResponse(str(pdf_path), media_type="application/pdf", filename=pdf_path.name)
