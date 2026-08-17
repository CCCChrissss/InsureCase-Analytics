from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

from backend.app.config import EMBEDDING_DIMS
from backend.app.config import EMBEDDING_MODEL
from backend.app.config import EMBEDDING_PROVIDER
from backend.app.services import embedding_service
from backend.app.services.case_service import clamp_pagination
from backend.app.services.search_service import classify_decision_result
from backend.app.services.search_service import search_all_cases


# RRF combines rank positions instead of incomparable BM25 and cosine values.
# Semantic recall receives the larger weight because natural-language retrieval
# is the primary product goal; literal matching remains a useful precision cue.
RRF_K = 60
SEMANTIC_RRF_WEIGHT = 2.0
KEYWORD_RRF_WEIGHT = 1.0
HYBRID_SEARCH_CACHE_SIZE = 16
RESULT_SCOPES = {"all", "keyword"}
SORT_DIRECTIONS = {"desc", "asc"}

_HYBRID_SEARCH_CACHE: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
_HYBRID_SEARCH_CACHE_LOCK = threading.Lock()


def reciprocal_rank(rank: int | None, *, weight: float) -> float:
    """Return one weighted RRF contribution, or zero for a missing channel."""
    if rank is None:
        return 0.0
    return weight / (RRF_K + rank)


def clear_hybrid_search_cache() -> None:
    """Clear process-local complete rankings after tests or a database refresh."""
    with _HYBRID_SEARCH_CACHE_LOCK:
        _HYBRID_SEARCH_CACHE.clear()


def _keyword_fallback_result(
    query: str,
    *,
    keyword_matches: dict[str, Any],
    page: int,
    page_size: int,
    error: embedding_service.EmbeddingProviderError,
    started_at: float,
    provider_name: str | None,
    model_name: str | None,
    result_scope: str,
    sort_direction: str,
) -> dict[str, Any]:
    """Preserve basic retrieval when the local semantic model is unavailable."""
    items = []
    for keyword_rank, item in enumerate(keyword_matches["items"], start=1):
        items.append(
            {
                **item,
                "similarity_score": None,
                "ranking_score": round(
                    reciprocal_rank(keyword_rank, weight=KEYWORD_RRF_WEIGHT),
                    8,
                ),
                "semantic_rank": None,
                "keyword_rank": keyword_rank,
                "section_hint": None,
                "chunk_index": None,
                "semantic_snippet": None,
                "match_type": "keyword",
            }
        )

    # Fallback has only keyword rank. Reverse the complete list before slicing
    # so ascending order remains stable across every page.
    if sort_direction == "asc":
        items.reverse()
    _, safe_page_size, offset = clamp_pagination(page, page_size)
    return {
        "query": query,
        "embedding_provider": provider_name or EMBEDDING_PROVIDER,
        "embedding_model": model_name or EMBEDDING_MODEL,
        "embedding_dims": EMBEDDING_DIMS,
        "embedding_device": "unavailable",
        "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "cached": False,
        "search_mode": "keyword_fallback",
        "result_scope": result_scope,
        "sort_direction": sort_direction,
        "fallback_reason": str(error),
        "items": items[offset : offset + safe_page_size],
        "total": len(items),
        "keyword_match_count": len(items),
        "semantic_case_count": 0,
        "total_candidates": 0,
        "match_source": keyword_matches["match_source"],
        "page": page,
        "page_size": safe_page_size,
    }


def hybrid_search(
    query: str,
    *,
    page: int = 1,
    page_size: int = 20,
    model_name: str | None = None,
    provider_name: str | None = None,
    result_scope: str = "all",
    sort_direction: str = "desc",
) -> dict[str, Any]:
    """Combine full-database semantic recall with literal keyword precision.

    Every embedded case participates in semantic ranking. FTS5/LIKE results are
    then fused by rank, so literal matching can improve precision but can never
    prevent a semantically relevant case from entering the result set.
    """
    if result_scope not in RESULT_SCOPES:
        raise ValueError(f"Unsupported hybrid search result scope: {result_scope}")
    if sort_direction not in SORT_DIRECTIONS:
        raise ValueError(f"Unsupported hybrid search sort direction: {sort_direction}")

    started_at = time.perf_counter()
    cleaned_query = query.strip()
    safe_page, safe_page_size, offset = clamp_pagination(page, page_size)
    resolved_provider = (provider_name or EMBEDDING_PROVIDER).strip().lower()
    resolved_model = (model_name or EMBEDDING_MODEL).strip()
    cache_key = (
        cleaned_query,
        resolved_provider,
        resolved_model,
        embedding_service.semantic_ranked_database_key(),
    )

    with _HYBRID_SEARCH_CACHE_LOCK:
        cached_result = _HYBRID_SEARCH_CACHE.get(cache_key)
        if cached_result is not None:
            _HYBRID_SEARCH_CACHE.move_to_end(cache_key)

    cache_hit = cached_result is not None
    if cached_result is None:
        keyword_matches = search_all_cases(cleaned_query)
        try:
            semantic_matches = embedding_service.semantic_case_rankings(
                cleaned_query,
                model_name=resolved_model,
                provider_name=resolved_provider,
            )
        except embedding_service.EmbeddingProviderError as error:
            return _keyword_fallback_result(
                cleaned_query,
                keyword_matches=keyword_matches,
                page=safe_page,
                page_size=safe_page_size,
                error=error,
                started_at=started_at,
                provider_name=resolved_provider,
                model_name=resolved_model,
                result_scope=result_scope,
                sort_direction=sort_direction,
            )

        keyword_by_case = {
            item["case_id"]: (rank, item)
            for rank, item in enumerate(keyword_matches["items"], start=1)
        }
        semantic_by_case = {
            item["case_id"]: (rank, item)
            for rank, item in enumerate(semantic_matches["items"], start=1)
        }

        # Semantic rankings normally cover every case. The union also preserves
        # keyword-only cases if an embedding is missing or temporarily stale.
        ranked_items = []
        for case_id in semantic_by_case.keys() | keyword_by_case.keys():
            semantic_entry = semantic_by_case.get(case_id)
            keyword_entry = keyword_by_case.get(case_id)
            semantic_rank, semantic_item = semantic_entry if semantic_entry is not None else (None, None)
            keyword_rank, keyword_item = keyword_entry if keyword_entry is not None else (None, None)

            ranking_score = reciprocal_rank(semantic_rank, weight=SEMANTIC_RRF_WEIGHT)
            ranking_score += reciprocal_rank(keyword_rank, weight=KEYWORD_RRF_WEIGHT)
            source_item = semantic_item or keyword_item
            assert source_item is not None
            decision_result = (
                classify_decision_result(semantic_item["decision_result"], semantic_item["holding"])
                if semantic_item is not None
                else keyword_item["decision_result"]
            )
            match_type = "hybrid" if semantic_item is not None and keyword_item is not None else (
                "semantic" if semantic_item is not None else "keyword"
            )
            ranked_items.append(
                {
                    "case_id": case_id,
                    "case_number": source_item["case_number"],
                    "decision_date": source_item["decision_date"],
                    "dispute_type": source_item["dispute_type"],
                    "decision_result": decision_result,
                    "snippet": (
                        semantic_item["semantic_snippet"]
                        if semantic_item is not None
                        else keyword_item["snippet"]
                    ),
                    "match_source": (
                        keyword_item["match_source"] if keyword_item is not None else "semantic"
                    ),
                    "similarity_score": (
                        semantic_item["similarity_score"] if semantic_item is not None else None
                    ),
                    "ranking_score": round(ranking_score, 8),
                    "semantic_rank": semantic_rank,
                    "keyword_rank": keyword_rank,
                    "section_hint": semantic_item["section_hint"] if semantic_item is not None else None,
                    "chunk_index": semantic_item["chunk_index"] if semantic_item is not None else None,
                    "semantic_snippet": (
                        semantic_item["semantic_snippet"] if semantic_item is not None else None
                    ),
                    "match_type": match_type,
                }
            )

        ranked_items.sort(
            key=lambda item: (
                item["ranking_score"],
                item["similarity_score"] if item["similarity_score"] is not None else -1.0,
                item["decision_date"] or "",
                item["case_number"] or "",
            ),
            reverse=True,
        )
        cached_result = {
            "query": cleaned_query,
            "embedding_provider": semantic_matches["embedding_provider"],
            "embedding_model": semantic_matches["embedding_model"],
            "embedding_dims": semantic_matches["embedding_dims"],
            "embedding_device": semantic_matches["embedding_device"],
            "search_mode": "hybrid",
            "fallback_reason": None,
            "items": ranked_items,
            "total": len(ranked_items),
            "keyword_match_count": keyword_matches["total"],
            "semantic_case_count": semantic_matches["total_cases"],
            "total_candidates": semantic_matches["total_candidates"],
            "match_source": keyword_matches["match_source"],
        }
        with _HYBRID_SEARCH_CACHE_LOCK:
            _HYBRID_SEARCH_CACHE[cache_key] = cached_result
            _HYBRID_SEARCH_CACHE.move_to_end(cache_key)
            while len(_HYBRID_SEARCH_CACHE) > HYBRID_SEARCH_CACHE_SIZE:
                _HYBRID_SEARCH_CACHE.popitem(last=False)

    assert cached_result is not None
    # Scope and direction are presentation controls over the same cached full
    # ranking. Apply both before pagination so page boundaries stay correct.
    scoped_items = cached_result["items"]
    if result_scope == "keyword":
        scoped_items = [item for item in scoped_items if item["keyword_rank"] is not None]
    if sort_direction == "asc":
        scoped_items = list(reversed(scoped_items))

    return {
        **{key: value for key, value in cached_result.items() if key != "items"},
        "items": scoped_items[offset : offset + safe_page_size],
        "total": len(scoped_items),
        "result_scope": result_scope,
        "sort_direction": sort_direction,
        "page": safe_page,
        "page_size": safe_page_size,
        "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "cached": cache_hit,
    }
