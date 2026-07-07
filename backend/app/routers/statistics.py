from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query

from backend.app.schemas import CountItem, DateCountItem, OverviewStatistics
from backend.app.services.statistics_service import (
    get_decision_date_counts,
    get_dispute_type_counts,
    get_overview,
)


router = APIRouter(prefix="/api/statistics", tags=["statistics"])


@router.get("/overview", response_model=OverviewStatistics)
def overview(roc_year: int | None = Query(default=None, ge=1)) -> dict:
    return get_overview(roc_year=roc_year)


@router.get("/dispute-types", response_model=list[CountItem])
def dispute_types(roc_year: int | None = Query(default=None, ge=1)) -> list[dict]:
    return get_dispute_type_counts(roc_year=roc_year)


@router.get("/decision-dates", response_model=list[DateCountItem])
def decision_dates(roc_year: int | None = Query(default=None, ge=1)) -> list[dict]:
    return get_decision_date_counts(roc_year=roc_year)
