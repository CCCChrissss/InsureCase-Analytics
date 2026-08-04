from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.schemas import QuerySuggestionResponse
from backend.app.services.query_suggestion_service import get_query_suggestion


router = APIRouter(prefix="/api", tags=["query suggestions"])


@router.get("/query-suggestions", response_model=QuerySuggestionResponse)
def get_query_suggestion_response(
    q: str = Query(..., min_length=1),
) -> dict:
    normalized_query = q.strip()
    if not normalized_query:
        raise HTTPException(status_code=422, detail="Query must not be blank.")

    suggestion = get_query_suggestion(normalized_query)
    if suggestion is None:
        return {
            "available": False,
            "original_query": normalized_query,
            "suggested_query": None,
            "rule_id": None,
            "explanation": None,
            "auto_apply": False,
        }

    return {"available": True, **suggestion}
