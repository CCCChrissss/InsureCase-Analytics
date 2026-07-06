from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.schemas import SearchResponse
from backend.app.services.search_service import search_cases


router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    return search_cases(q, page=page, page_size=page_size)
