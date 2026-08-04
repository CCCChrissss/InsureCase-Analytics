from __future__ import annotations

import pytest

from backend.app.services import query_suggestion_service
from backend.scripts import run_semantic_query_suggestion_trial


APPROVED_QUERIES = (
    "違反告知義務",
    "手術認定",
    "業務招攬",
    "豁免保費",
)


@pytest.mark.parametrize("query", APPROVED_QUERIES)
def test_get_query_suggestion_returns_explainable_optional_suggestion(query: str) -> None:
    suggestion = query_suggestion_service.get_query_suggestion(query)

    assert suggestion is not None
    assert suggestion["original_query"] == query
    assert suggestion["suggested_query"] != query
    assert suggestion["rule_id"]
    assert suggestion["explanation"]
    assert suggestion["auto_apply"] is False


def test_approved_rules_match_the_validated_experiment() -> None:
    experiment_specs = {
        spec["original_query"]: spec
        for spec in run_semantic_query_suggestion_trial.QUERY_SUGGESTIONS_V1
    }

    assert tuple(
        rule.original_query
        for rule in query_suggestion_service.APPROVED_QUERY_SUGGESTIONS
    ) == APPROVED_QUERIES

    for rule in query_suggestion_service.APPROVED_QUERY_SUGGESTIONS:
        experiment_spec = experiment_specs[rule.original_query]
        assert rule.suggested_query == experiment_spec["suggested_query"]
        assert rule.rule_id == experiment_spec["rule_id"]
        assert rule.explanation == experiment_spec["explanation"]


@pytest.mark.parametrize(
    "query",
    (
        "",
        "不存在的查詢",
        "除外責任",
        "理賠金額",
        "必要性醫療",
    ),
)
def test_get_query_suggestion_returns_none_for_unapproved_queries(query: str) -> None:
    assert query_suggestion_service.get_query_suggestion(query) is None


def test_get_query_suggestion_ignores_surrounding_whitespace() -> None:
    suggestion = query_suggestion_service.get_query_suggestion("  豁免保費  ")

    assert suggestion is not None
    assert suggestion["original_query"] == "豁免保費"
