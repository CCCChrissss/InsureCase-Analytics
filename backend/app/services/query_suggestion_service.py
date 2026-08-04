from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QuerySuggestionRule:
    original_query: str
    suggested_query: str
    rule_id: str
    explanation: str


APPROVED_QUERY_SUGGESTIONS: tuple[QuerySuggestionRule, ...] = (
    QuerySuggestionRule(
        original_query="違反告知義務",
        suggested_query="要保人隱匿病史保險公司解除契約",
        rule_id="clarify_actor_action_effect",
        explanation="補足要保人、隱匿病史與解除契約的法律效果。",
    ),
    QuerySuggestionRule(
        original_query="手術認定",
        suggested_query="醫療處置是否符合保單手術定義",
        rule_id="clarify_procedure_definition",
        explanation="補足醫療處置與保單手術定義的判斷關係。",
    ),
    QuerySuggestionRule(
        original_query="業務招攬",
        suggested_query="業務員招攬過程未充分說明保單",
        rule_id="clarify_solicitation_defect",
        explanation="補足招攬過程、保單說明與可能瑕疵。",
    ),
    QuerySuggestionRule(
        original_query="豁免保費",
        suggested_query="被保險人失能或罹癌後免繳保險費",
        rule_id="clarify_trigger_and_effect",
        explanation="補足失能或癌症等啟動條件與免繳效果。",
    ),
)

_SUGGESTIONS_BY_QUERY = {
    rule.original_query: rule for rule in APPROVED_QUERY_SUGGESTIONS
}


def get_query_suggestion(query: str) -> dict[str, Any] | None:
    """Return an optional, explainable suggestion without applying it."""
    normalized_query = query.strip()
    if not normalized_query:
        return None

    rule = _SUGGESTIONS_BY_QUERY.get(normalized_query)
    if rule is None:
        return None

    return {
        "original_query": normalized_query,
        "suggested_query": rule.suggested_query,
        "rule_id": rule.rule_id,
        "explanation": rule.explanation,
        "auto_apply": False,
    }
