from __future__ import annotations

from typing import Any

from backend.app.database import connect


def year_filter_clause(roc_year: int | None) -> tuple[str, list[Any]]:
    if roc_year is None:
        return "", []
    return "WHERE roc_year = ?", [roc_year]


def append_year_filter(base_where: str, roc_year: int | None) -> tuple[str, list[Any]]:
    if roc_year is None:
        return base_where, []
    prefix = "AND" if base_where.strip().upper().startswith("WHERE") else "WHERE"
    return f"{base_where} {prefix} roc_year = ?", [roc_year]


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


def get_dispute_type_counts(roc_year: int | None = None) -> list[dict[str, Any]]:
    where, params = append_year_filter("WHERE dispute_type IS NOT NULL AND dispute_type != ''", roc_year)
    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT dispute_type AS name, COUNT(*) AS count
            FROM cases
            {where}
            GROUP BY dispute_type
            ORDER BY count DESC, dispute_type ASC;
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def get_decision_date_counts(roc_year: int | None = None) -> list[dict[str, Any]]:
    where, params = append_year_filter("WHERE decision_date IS NOT NULL AND decision_date != ''", roc_year)
    with connect() as connection:
        rows = connection.execute(
            f"""
            SELECT decision_date, COUNT(*) AS count
            FROM cases
            {where}
            GROUP BY decision_date
            ORDER BY decision_date ASC;
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]
