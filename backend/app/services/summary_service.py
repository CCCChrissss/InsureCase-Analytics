from __future__ import annotations

from typing import Any

from backend.app.database import connect


def get_case_summary(case_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT case_id, holding, applicant_claim, reasoning, summary_method, created_at
            FROM case_summaries
            WHERE case_id = ?;
            """,
            (case_id,),
        ).fetchone()
    return dict(row) if row else None
