from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.schemas import AiCaseSummaryResponse
from backend.app.services.ai_summary_service import AiSummaryDataError, get_case_ai_summary
from backend.app.services.case_service import get_case


router = APIRouter(prefix="/api", tags=["ai-summaries"])


@router.get("/cases/{case_id}/ai-summary", response_model=AiCaseSummaryResponse)
def get_ai_summary(case_id: str) -> dict:
    """Return an approved summary, or the latest unreviewed trial when no approved version exists."""

    if get_case(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    try:
        item = get_case_ai_summary(case_id)
    except AiSummaryDataError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "case_id": case_id,
        "available": item is not None,
        "item": item,
    }
