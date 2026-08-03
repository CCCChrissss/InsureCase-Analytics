from __future__ import annotations

from typing import Any

from backend.app.database import connect


def year_filter_clause(roc_year: int | None) -> tuple[str, list[Any]]:
    if roc_year is None:
        return "", []
    return "WHERE roc_year = ?", [roc_year]


def get_overview(roc_year: int | None = None) -> dict[str, Any]:
    where, params = year_filter_clause(roc_year)
    with connect() as connection:
        case_count = connection.execute(f"SELECT COUNT(*) FROM cases {where}", params).fetchone()[0]
        dispute_type_count = connection.execute(
            f"""
            SELECT COUNT(DISTINCT dispute_type)
            FROM cases
            {where}
            {"AND" if where else "WHERE"} dispute_type IS NOT NULL AND dispute_type != ''
            """,
            params,
        ).fetchone()[0]
        years = connection.execute("SELECT DISTINCT roc_year FROM cases ORDER BY roc_year").fetchall()
        date_range = connection.execute(
            f"SELECT MIN(decision_date) AS first_decision_date, MAX(decision_date) AS last_decision_date FROM cases {where}",
            params,
        ).fetchone()
    return {
        "case_count": case_count,
        "dispute_type_count": dispute_type_count,
        "roc_years": [row["roc_year"] for row in years],
        "first_decision_date": date_range["first_decision_date"],
        "last_decision_date": date_range["last_decision_date"],
    }
