from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas import SimilarCasesResponse
from backend.app.services.similar_case_service import similar_cases


router = APIRouter(prefix="/api", tags=["similar cases"])


@router.get("/cases/{case_id}/similar", response_model=SimilarCasesResponse)
def get_similar_cases(case_id: str, limit: int = Query(5, ge=1, le=20)) -> dict:
    result = similar_cases(case_id, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return result
