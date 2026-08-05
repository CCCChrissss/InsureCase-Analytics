from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas import EmbeddingStatusResponse
from backend.app.schemas import SemanticSearchResponse
from backend.app.services.embedding_service import EmbeddingProviderError
from backend.app.services.embedding_service import get_embedding_status
from backend.app.services.embedding_service import semantic_search


router = APIRouter(prefix="/api", tags=["semantic search"])


@router.get("/embedding-status", response_model=EmbeddingStatusResponse)
def embedding_status() -> dict:
    return get_embedding_status()


@router.get("/semantic-search", response_model=SemanticSearchResponse)
def get_semantic_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    embedding_model: str | None = Query(None, min_length=1),
    embedding_provider: str | None = Query(None, min_length=1),
) -> dict:
    try:
        return semantic_search(
            q,
            limit=limit,
            min_score=min_score,
            model_name=embedding_model,
            provider_name=embedding_provider,
        )
    except EmbeddingProviderError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
