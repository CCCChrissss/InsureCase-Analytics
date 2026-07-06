from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.schemas import CaseSummaryDetail
from backend.app.services.summary_service import get_case_summary


router = APIRouter(prefix="/api", tags=["summaries"])


@router.get("/cases/{case_id}/summary", response_model=CaseSummaryDetail)
def get_summary(case_id: str) -> dict:
    summary = get_case_summary(case_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Case summary not found.")
    return summary
