from __future__ import annotations

from typing import Any

from backend.app.database import connect


DOMAIN_TERMS = (
    "癌症",
    "住院",
    "手術",
    "門診",
    "理賠",
    "保險金",
    "醫療",
    "必要性",
    "除外責任",
    "告知義務",
    "停效",
    "復效",
    "寬限期間",
    "催告",
    "意外傷害",
    "失能",
    "身故",
    "重大傷病",
    "豁免",
    "保險費",
    "保單價值",
    "生存保險金",
    "契約變更",
    "診斷",
    "病理",
    "既往症",
    "等待期間",
    "自費",
    "實支實付",
)


def case_text(row: dict[str, Any]) -> str:
    parts = [
        row.get("dispute_type"),
        row.get("decision_result"),
        row.get("holding"),
        row.get("applicant_claim"),
        row.get("reasoning"),
    ]
    return "\n".join(str(part) for part in parts if part)


def collect_terms(text: str) -> set[str]:
    return {term for term in DOMAIN_TERMS if term in text}


def get_case_profile(case_id: str) -> dict[str, Any] | None:
    with connect() as connection:
        row = connection.execute(
            """
            SELECT cases.case_id, cases.case_number, cases.decision_date,
                   cases.decision_category, cases.decision_result, cases.dispute_type,
                   case_summaries.holding, case_summaries.applicant_claim,
                   case_summaries.reasoning
            FROM cases
            LEFT JOIN case_summaries ON case_summaries.case_id = cases.case_id
            WHERE cases.case_id = ?;
            """,
            (case_id,),
        ).fetchone()
    return dict(row) if row else None


def list_candidate_profiles(case_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT cases.case_id, cases.case_number, cases.decision_date,
                   cases.decision_category, cases.decision_result, cases.dispute_type,
                   case_summaries.holding, case_summaries.applicant_claim,
                   case_summaries.reasoning
            FROM cases
            LEFT JOIN case_summaries ON case_summaries.case_id = cases.case_id
            WHERE cases.case_id != ?;
            """,
            (case_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def score_candidate(source: dict[str, Any], candidate: dict[str, Any]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if source.get("dispute_type") and source.get("dispute_type") == candidate.get("dispute_type"):
        score += 60.0
        reasons.append("相同爭議類型")

    if source.get("decision_result") and source.get("decision_result") == candidate.get("decision_result"):
        score += 15.0
        reasons.append("相同評議結果")

    if source.get("decision_category") and source.get("decision_category") == candidate.get("decision_category"):
        score += 5.0
        reasons.append("相同決定類別")

    source_terms = collect_terms(case_text(source))
    candidate_terms = collect_terms(case_text(candidate))
    shared_terms = sorted(source_terms & candidate_terms)
    if shared_terms:
        score += min(30.0, len(shared_terms) * 6.0)
        reasons.append(f"共同關鍵詞：{'、'.join(shared_terms[:5])}")

    return score, reasons


def similar_cases(case_id: str, *, limit: int = 5) -> dict[str, Any] | None:
    source = get_case_profile(case_id)
    if source is None:
        return None

    scored: list[dict[str, Any]] = []
    for candidate in list_candidate_profiles(case_id):
        score, reasons = score_candidate(source, candidate)
        if score <= 0:
            continue
        scored.append(
            {
                "case_id": candidate["case_id"],
                "case_number": candidate["case_number"],
                "decision_date": candidate["decision_date"],
                "dispute_type": candidate["dispute_type"],
                "decision_result": candidate["decision_result"],
                "score": round(score, 2),
                "matched_reasons": reasons,
            }
        )

    scored.sort(
        key=lambda item: (
            item["score"],
            item["decision_date"] or "",
            item["case_number"] or "",
        ),
        reverse=True,
    )
    safe_limit = min(max(limit, 1), 20)
    return {
        "case_id": source["case_id"],
        "items": scored[:safe_limit],
        "total_candidates": len(scored),
    }
