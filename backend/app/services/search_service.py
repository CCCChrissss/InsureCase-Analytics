from __future__ import annotations

import sqlite3
import re
from typing import Any

from backend.app.database import connect
from backend.app.services.case_service import clamp_pagination


def make_snippet(text: str | None, query: str, radius: int = 70) -> str | None:
    if not text:
        return None
    index = text.find(query)
    if index < 0:
        return text[: radius * 2].strip()
    start = max(index - radius, 0)
    end = min(index + len(query) + radius, len(text))
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def classify_decision_result(metadata_value: str | None, holding: str | None) -> str | None:
    cleaned_holding = re.sub(r"\s+", "", holding or "")
    if cleaned_holding:
        favorable = bool(
            re.search(
                r"應(?:再)?給付|應恢復|確認.*契約.*存在|評議申請為有理由|請求為有理由",
                cleaned_holding,
            )
        )
        rejected = bool(re.search(r"尚難為?有利|無理由|駁回", cleaned_holding))
        inadmissible = "不予受理" in cleaned_holding or "不受理" in cleaned_holding
        if favorable and (rejected or inadmissible):
            return "部分有理由"
        if favorable:
            return "有理由"
        if inadmissible and not rejected:
            return "不受理"
        if rejected:
            return "無理由"

    cleaned_metadata = (metadata_value or "").strip()
    if cleaned_metadata and cleaned_metadata != "全部":
        return cleaned_metadata
    return None


def search_with_like(
    connection: sqlite3.Connection,
    query: str,
    *,
    page_size: int | None,
    offset: int = 0,
) -> tuple[int, list[sqlite3.Row]]:
    """Use literal substring matching when FTS5 is unavailable or misses Chinese text."""
    like_query = f"%{query}%"
    like_params = (like_query, like_query, like_query)
    total = connection.execute(
        """
        SELECT COUNT(*)
        FROM case_texts
        JOIN cases ON cases.case_id = case_texts.case_id
        WHERE cases.case_number LIKE ?
           OR cases.dispute_type LIKE ?
           OR case_texts.normalized_text LIKE ?;
        """,
        like_params,
    ).fetchone()[0]
    pagination_sql = "" if page_size is None else "LIMIT ? OFFSET ?"
    params: tuple[Any, ...] = like_params if page_size is None else (*like_params, page_size, offset)
    rows = connection.execute(
        f"""
        SELECT cases.case_id, cases.case_number, cases.decision_date,
               cases.dispute_type, cases.decision_result, case_summaries.holding,
               case_texts.normalized_text
        FROM case_texts
        JOIN cases ON cases.case_id = case_texts.case_id
        LEFT JOIN case_summaries ON case_summaries.case_id = cases.case_id
        WHERE cases.case_number LIKE ?
           OR cases.dispute_type LIKE ?
           OR case_texts.normalized_text LIKE ?
        ORDER BY cases.decision_date DESC, cases.case_number DESC
        {pagination_sql};
        """,
        params,
    ).fetchall()
    return total, rows


def search_rows(
    connection: sqlite3.Connection,
    query: str,
    *,
    page_size: int | None,
    offset: int = 0,
) -> tuple[int, list[sqlite3.Row], str]:
    """Run the shared FTS5-first search and preserve the fallback source for every row."""
    match_source = "fts5"
    pagination_sql = "" if page_size is None else "LIMIT ? OFFSET ?"
    params: tuple[Any, ...] = (query,) if page_size is None else (query, page_size, offset)
    try:
        total = connection.execute(
            "SELECT COUNT(*) FROM case_search WHERE case_search MATCH ?",
            (query,),
        ).fetchone()[0]
        rows = connection.execute(
            f"""
            SELECT cases.case_id, cases.case_number, cases.decision_date,
                   cases.dispute_type, cases.decision_result, case_summaries.holding,
                   case_texts.normalized_text
            FROM case_search
            JOIN cases ON cases.case_id = case_search.case_id
            JOIN case_texts ON case_texts.case_id = cases.case_id
            LEFT JOIN case_summaries ON case_summaries.case_id = cases.case_id
            WHERE case_search MATCH ?
            ORDER BY bm25(case_search), cases.decision_date DESC
            {pagination_sql};
            """,
            params,
        ).fetchall()
    except sqlite3.OperationalError:
        match_source = "like_fallback_error"
        total, rows = search_with_like(
            connection,
            query,
            page_size=page_size,
            offset=offset,
        )
    else:
        if total == 0:
            match_source = "like_fallback_empty_fts5"
            total, rows = search_with_like(
                connection,
                query,
                page_size=page_size,
                offset=offset,
            )
    return total, rows, match_source


def serialize_rows(rows: list[sqlite3.Row], query: str, match_source: str) -> list[dict[str, Any]]:
    """Convert database rows to the stable API shape used by both paged and ranked search."""
    return [
        {
            "case_id": row["case_id"],
            "case_number": row["case_number"],
            "decision_date": row["decision_date"],
            "dispute_type": row["dispute_type"],
            "decision_result": classify_decision_result(row["decision_result"], row["holding"]),
            "snippet": make_snippet(row["normalized_text"], query),
            "match_source": match_source,
        }
        for row in rows
    ]


def search_cases(query: str, *, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    """Return one page in keyword relevance order, with Chinese LIKE fallback support."""
    safe_page, safe_page_size, offset = clamp_pagination(page, page_size)
    cleaned_query = query.strip()
    if not cleaned_query:
        return {"items": [], "total": 0, "query": query, "page": safe_page, "page_size": safe_page_size}

    with connect() as connection:
        total, rows, match_source = search_rows(
            connection,
            cleaned_query,
            page_size=safe_page_size,
            offset=offset,
        )

    return {
        "items": serialize_rows(rows, cleaned_query, match_source),
        "total": total,
        "query": query,
        "page": safe_page,
        "page_size": safe_page_size,
    }


def search_all_cases(query: str) -> dict[str, Any]:
    """Return every keyword match so semantic ranking can happen before pagination."""
    cleaned_query = query.strip()
    if not cleaned_query:
        return {"items": [], "total": 0, "query": query, "match_source": "fts5"}

    with connect() as connection:
        total, rows, match_source = search_rows(
            connection,
            cleaned_query,
            page_size=None,
        )
    return {
        "items": serialize_rows(rows, cleaned_query, match_source),
        "total": total,
        "query": query,
        "match_source": match_source,
    }
