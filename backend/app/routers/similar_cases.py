from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas import SemanticSimilarCasesResponse
from backend.app.schemas import SimilarCasesResponse
from backend.app.services.embedding_service import semantic_similar_cases
from backend.app.services.similar_case_service import similar_cases


router = APIRouter(prefix="/api", tags=["similar cases"])


@router.get("/cases/{case_id}/similar", response_model=SimilarCasesResponse)
def get_similar_cases(case_id: str, limit: int = Query(5, ge=1, le=20)) -> dict:
    result = similar_cases(case_id, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return result


@router.get("/cases/{case_id}/semantic-similar", response_model=SemanticSimilarCasesResponse)
def get_semantic_similar_cases(
    case_id: str,
    limit: int = Query(5, ge=1, le=20),
    chunks_per_case: int = Query(2, ge=1, le=5),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
) -> dict:
    result = semantic_similar_cases(
        case_id,
        limit=limit,
        chunks_per_case=chunks_per_case,
        min_score=min_score,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Case not found.")
    return result
