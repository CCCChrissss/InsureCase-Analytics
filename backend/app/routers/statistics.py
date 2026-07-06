from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas import CountItem, DateCountItem, OverviewStatistics
from backend.app.services.statistics_service import (
    get_decision_date_counts,
    get_dispute_type_counts,
    get_overview,
)


router = APIRouter(prefix="/api/statistics", tags=["statistics"])


@router.get("/overview", response_model=OverviewStatistics)
def overview() -> dict:
    return get_overview()


@router.get("/dispute-types", response_model=list[CountItem])
def dispute_types() -> list[dict]:
    return get_dispute_type_counts()


@router.get("/decision-dates", response_model=list[DateCountItem])
def decision_dates() -> list[dict]:
    return get_decision_date_counts()
