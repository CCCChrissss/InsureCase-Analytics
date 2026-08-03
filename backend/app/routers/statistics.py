from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query

from backend.app.schemas import OverviewStatistics
from backend.app.services.statistics_service import get_overview


router = APIRouter(prefix="/api/statistics", tags=["statistics"])


@router.get("/overview", response_model=OverviewStatistics)
def overview(roc_year: int | None = Query(default=None, ge=1)) -> dict:
    return get_overview(roc_year=roc_year)
