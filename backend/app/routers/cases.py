from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from backend.app.schemas import CaseDetail, CountItem, PaginatedCases
from backend.app.services.case_service import get_case, get_pdf_path, list_cases, list_dispute_types


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


@router.get("/dispute-types", response_model=list[CountItem])
def get_dispute_types() -> list[dict]:
    return list_dispute_types()


@router.get("/files/{case_id}/pdf")
def get_case_pdf(case_id: str) -> FileResponse:
    pdf_path = get_pdf_path(case_id)
    if pdf_path is None or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found.")
    return FileResponse(str(pdf_path), media_type="application/pdf", filename=pdf_path.name)
