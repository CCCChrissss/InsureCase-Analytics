from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.schemas import SemanticSearchResponse
from backend.app.services.embedding_service import semantic_search


router = APIRouter(prefix="/api", tags=["semantic search"])


@router.get("/semantic-search", response_model=SemanticSearchResponse)
def get_semantic_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
) -> dict:
    return semantic_search(q, limit=limit, min_score=min_score)
