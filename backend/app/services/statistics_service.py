from __future__ import annotations

from typing import Any

from backend.app.database import connect


def get_overview() -> dict[str, Any]:
    with connect() as connection:
        case_count = connection.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
        dispute_type_count = connection.execute(
            "SELECT COUNT(DISTINCT dispute_type) FROM cases WHERE dispute_type IS NOT NULL AND dispute_type != ''"
        ).fetchone()[0]
        years = connection.execute("SELECT DISTINCT roc_year FROM cases ORDER BY roc_year").fetchall()
        date_range = connection.execute(
            "SELECT MIN(decision_date) AS first_decision_date, MAX(decision_date) AS last_decision_date FROM cases"
        ).fetchone()
    return {
        "case_count": case_count,
        "dispute_type_count": dispute_type_count,
        "roc_years": [row["roc_year"] for row in years],
        "first_decision_date": date_range["first_decision_date"],
        "last_decision_date": date_range["last_decision_date"],
    }


def get_dispute_type_counts() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT dispute_type AS name, COUNT(*) AS count
            FROM cases
            WHERE dispute_type IS NOT NULL AND dispute_type != ''
            GROUP BY dispute_type
            ORDER BY count DESC, dispute_type ASC;
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_decision_date_counts() -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT decision_date, COUNT(*) AS count
            FROM cases
            WHERE decision_date IS NOT NULL AND decision_date != ''
            GROUP BY decision_date
            ORDER BY decision_date ASC;
            """
        ).fetchall()
    return [dict(row) for row in rows]
