from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas import QualityReport
from backend.app.services.quality_service import get_roc114_summary_similarity_quality


router = APIRouter(prefix="/api/quality", tags=["quality"])


@router.get("/roc114-summary-similarity", response_model=QualityReport)
def roc114_summary_similarity_quality() -> dict:
    return get_roc114_summary_similarity_quality()
