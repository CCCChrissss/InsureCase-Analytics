from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.schemas import HybridSearchRequest, HybridSearchResponse
from backend.app.schemas import SearchResponse
from backend.app.services.hybrid_search_service import hybrid_search
from backend.app.services.search_service import search_cases


router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    return search_cases(q, page=page, page_size=page_size)


@router.get("/hybrid-search", response_model=HybridSearchResponse)
def hybrid_search_cases(
    q: str = Query(..., min_length=1, max_length=2000),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=20),
    embedding_model: str | None = Query(None, min_length=1),
    embedding_provider: str | None = Query(None, min_length=1),
    result_scope: str = Query("all", pattern="^(all|keyword)$"),
    sort_direction: str = Query("desc", pattern="^(desc|asc)$"),
) -> dict:
    """Search all embedded cases semantically and fuse exact text matches."""
    return hybrid_search(
        q,
        page=page,
        page_size=page_size,
        model_name=embedding_model,
        provider_name=embedding_provider,
        result_scope=result_scope,
        sort_direction=sort_direction,
    )


@router.post("/hybrid-search", response_model=HybridSearchResponse)
def hybrid_search_narrative(request: HybridSearchRequest) -> dict:
    """Use a JSON body so longer incident narratives are not constrained by URL size."""
    return hybrid_search(
        request.q,
        page=request.page,
        page_size=request.page_size,
        model_name=request.embedding_model,
        provider_name=request.embedding_provider,
        result_scope=request.result_scope,
        sort_direction=request.sort_direction,
    )
