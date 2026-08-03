from __future__ import annotations

import pytest

from backend.scripts import evaluate_semantic_benchmark
from backend.scripts import run_semantic_query_trial


def test_local_bge_query_report_states_offline_execution() -> None:
    report = run_semantic_query_trial.build_markdown_report(
        {
            "created_at": "2026-01-01T00:00:00+00:00",
            "database": "trial.db",
            "embedding_provider": "local_bge",
            "embedding_model": "BAAI/bge-large-zh-v1.5-local",
            "query_set": "benchmark-v1",
            "queries": [],
        }
    )

    assert report.startswith("# Semantic Query Trial")
    assert "local BGE model cache" in report
    assert "does not call an external inference API" in report
    assert "consumes API quota" not in report


def make_results() -> dict:
    return {
        "query_set": "test-v1",
        "embedding_model": "test-model",
        "queries": [
            {
                "query": "癌症",
                "top": [
                    {
                        "score": 0.9,
                        "chunk_id": "chunk_1",
                        "case_id": "case_1",
                        "case_number": "114年評字第1號",
                        "dispute_type": "癌症或其併發症認定",
                        "section_hint": "判斷理由",
                        "chunk_text": "原文直接討論癌症給付。",
                    },
                    {
                        "score": 0.8,
                        "chunk_id": "chunk_2",
                        "case_id": "case_1",
                        "case_number": "114年評字第1號",
                        "dispute_type": "理賠金額認定",
                        "section_hint": "判斷理由",
                    },
                ],
            },
            {
                "query": "住院",
                "top": [
                    {
                        "score": 0.7,
                        "chunk_id": "chunk_3",
                        "case_id": "case_2",
                        "case_number": "114年評字第2號",
                        "dispute_type": "承保範圍",
                        "section_hint": "相對人主張",
                    },
                    {
                        "score": 0.6,
                        "chunk_id": "chunk_4",
                        "case_id": "case_3",
                        "case_number": "114年評字第3號",
                        "dispute_type": "必要性醫療",
                        "section_hint": "判斷理由",
                    },
                ],
            },
        ],
    }


def complete_annotations(template: dict) -> dict:
    labels = ["relevant", "partially_relevant", "not_relevant", "relevant"]
    template["annotator"] = "tester"
    for annotation, label in zip(template["annotations"], labels, strict=True):
        annotation["label"] = label
        annotation["evidence_summary"] = f"Evidence for {annotation['chunk_id']}"
    return template


def test_benchmark_v1_has_fifteen_unique_queries() -> None:
    queries = run_semantic_query_trial.BENCHMARK_QUERY_SETS["benchmark-v1"]

    assert len(queries) == 15
    assert len(set(queries)) == 15
    assert {"除外責任", "必要性醫療", "癌症", "住院", "失能"}.issubset(queries)


def test_resolve_queries_rejects_query_and_query_set_together() -> None:
    with pytest.raises(ValueError, match="either --query or --query-set"):
        run_semantic_query_trial.resolve_queries(["癌症"], "benchmark-v1")


def test_annotation_template_contains_every_ranked_result() -> None:
    template = evaluate_semantic_benchmark.build_annotation_template(make_results(), expected_top_k=2)

    assert len(template["annotations"]) == 4
    assert template["annotations"][0]["query"] == "癌症"
    assert template["annotations"][0]["rank"] == 1
    assert template["annotations"][0]["label"] == ""
    assert template["annotations"][0]["chunk_text"] == "原文直接討論癌症給付。"


def test_evaluate_results_calculates_strict_and_lenient_precision() -> None:
    results = make_results()
    annotations = complete_annotations(
        evaluate_semantic_benchmark.build_annotation_template(results, expected_top_k=2)
    )

    evaluation = evaluate_semantic_benchmark.evaluate_results(results, annotations, expected_top_k=2)

    assert evaluation["totals"] == {
        "relevant": 2,
        "partially_relevant": 1,
        "not_relevant": 1,
    }
    assert evaluation["macro_strict_precision_at_k"] == 0.5
    assert evaluation["macro_lenient_precision_at_k"] == 0.75
    assert evaluation["queries"][0]["unique_cases"] == 1
    assert "逐筆判讀" in evaluate_semantic_benchmark.build_markdown_report(evaluation)
    assert "strict P@2" in evaluate_semantic_benchmark.build_markdown_report(evaluation)
    assert "details" not in evaluate_semantic_benchmark.compact_evaluation_summary(evaluation)
    assert evaluate_semantic_benchmark.compact_evaluation_summary(evaluation)["total_results"] == 4


def test_evaluate_results_requires_evidence_summary() -> None:
    results = make_results()
    annotations = complete_annotations(
        evaluate_semantic_benchmark.build_annotation_template(results, expected_top_k=2)
    )
    annotations["annotations"][0]["evidence_summary"] = ""

    with pytest.raises(ValueError, match="Missing evidence_summary"):
        evaluate_semantic_benchmark.evaluate_results(results, annotations, expected_top_k=2)
