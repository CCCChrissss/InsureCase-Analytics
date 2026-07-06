from __future__ import annotations

import sqlite3
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


def search_cases(query: str, *, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    safe_page, safe_page_size, offset = clamp_pagination(page, page_size)
    cleaned_query = query.strip()
    if not cleaned_query:
        return {"items": [], "total": 0, "query": query, "page": safe_page, "page_size": safe_page_size}

    with connect() as connection:
        rows: list[sqlite3.Row]
        total: int
        match_source = "fts5"
        try:
            total = connection.execute(
                "SELECT COUNT(*) FROM case_search WHERE case_search MATCH ?",
                (cleaned_query,),
            ).fetchone()[0]
            rows = connection.execute(
                """
                SELECT cases.case_id, cases.case_number, cases.decision_date,
                       cases.dispute_type, case_texts.normalized_text
                FROM case_search
                JOIN cases ON cases.case_id = case_search.case_id
                JOIN case_texts ON case_texts.case_id = cases.case_id
                WHERE case_search MATCH ?
                ORDER BY bm25(case_search), cases.decision_date DESC
                LIMIT ? OFFSET ?;
                """,
                (cleaned_query, safe_page_size, offset),
            ).fetchall()
        except sqlite3.OperationalError:
            match_source = "like"
            like_query = f"%{cleaned_query}%"
            total = connection.execute(
                "SELECT COUNT(*) FROM case_texts WHERE normalized_text LIKE ?",
                (like_query,),
            ).fetchone()[0]
            rows = connection.execute(
                """
                SELECT cases.case_id, cases.case_number, cases.decision_date,
                       cases.dispute_type, case_texts.normalized_text
                FROM case_texts
                JOIN cases ON cases.case_id = case_texts.case_id
                WHERE case_texts.normalized_text LIKE ?
                ORDER BY cases.decision_date DESC, cases.case_number DESC
                LIMIT ? OFFSET ?;
                """,
                (like_query, safe_page_size, offset),
            ).fetchall()

    return {
        "items": [
            {
                "case_id": row["case_id"],
                "case_number": row["case_number"],
                "decision_date": row["decision_date"],
                "dispute_type": row["dispute_type"],
                "snippet": make_snippet(row["normalized_text"], cleaned_query),
                "match_source": match_source,
            }
            for row in rows
        ],
        "total": total,
        "query": query,
        "page": safe_page,
        "page_size": safe_page_size,
    }
