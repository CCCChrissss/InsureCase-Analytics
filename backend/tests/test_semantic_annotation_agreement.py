from __future__ import annotations

from copy import deepcopy

import pytest

from backend.scripts import compare_semantic_annotations
from backend.scripts import evaluate_semantic_benchmark


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
                        "dispute_type": "癌症認定",
                        "chunk_text": "原文直接討論癌症給付。",
                    },
                    {
                        "score": 0.8,
                        "chunk_id": "chunk_2",
                        "case_id": "case_2",
                        "case_number": "114年評字第2號",
                        "dispute_type": "必要性醫療",
                        "chunk_text": "原文討論相鄰醫療概念。",
                    },
                ],
            },
            {
                "query": "住院",
                "top": [
                    {
                        "score": 0.7,
                        "chunk_id": "chunk_3",
                        "case_id": "case_3",
                        "case_number": "114年評字第3號",
                        "dispute_type": "承保範圍",
                        "chunk_text": "原文沒有住院內容。",
                    },
                    {
                        "score": 0.6,
                        "chunk_id": "chunk_4",
                        "case_id": "case_4",
                        "case_number": "114年評字第4號",
                        "dispute_type": "住院認定",
                        "chunk_text": "原文直接討論住院定義。",
                    },
                ],
            },
        ],
    }


def make_annotations(results: dict, *, annotator: str, labels: list[str]) -> dict:
    payload = evaluate_semantic_benchmark.build_annotation_template(results, expected_top_k=2)
    payload["annotator"] = annotator
    for item, label in zip(payload["annotations"], labels, strict=True):
        item["label"] = label
        item["evidence_summary"] = f"{annotator} evidence for {item['chunk_id']}"
    return payload


def test_compare_annotations_reports_perfect_agreement() -> None:
    results = make_results()
    labels = ["relevant", "partially_relevant", "not_relevant", "relevant"]
    comparison = compare_semantic_annotations.compare_annotations(
        results,
        make_annotations(results, annotator="reviewer-a", labels=labels),
        make_annotations(results, annotator="reviewer-b", labels=labels),
        expected_top_k=2,
    )

    assert comparison["agreements"] == 4
    assert comparison["disagreements"] == 0
    assert comparison["agreement_rate"] == 1.0
    assert comparison["cohens_kappa"] == 1.0
    assert comparison["conflicts"] == []
    assert "沒有待仲裁項目" in compare_semantic_annotations.build_markdown_report(comparison)


def test_compare_annotations_lists_conflicts_and_per_query_rates() -> None:
    results = make_results()
    comparison = compare_semantic_annotations.compare_annotations(
        results,
        make_annotations(
            results,
            annotator="reviewer-a",
            labels=["relevant", "partially_relevant", "not_relevant", "relevant"],
        ),
        make_annotations(
            results,
            annotator="reviewer-b",
            labels=["relevant", "not_relevant", "not_relevant", "partially_relevant"],
        ),
        expected_top_k=2,
    )

    assert comparison["agreements"] == 2
    assert comparison["disagreements"] == 2
    assert comparison["agreement_rate"] == 0.5
    assert len(comparison["conflicts"]) == 2
    assert comparison["queries"][0]["agreement_rate"] == 0.5
    assert comparison["confusion_matrix"]["partially_relevant"]["not_relevant"] == 1
    assert "reviewer-a evidence" in compare_semantic_annotations.build_markdown_report(comparison)
    assert "conflicts" not in compare_semantic_annotations.compact_summary(comparison)


def test_compare_annotations_rejects_same_annotator() -> None:
    results = make_results()
    annotations = make_annotations(
        results,
        annotator="same-reviewer",
        labels=["relevant", "partially_relevant", "not_relevant", "relevant"],
    )

    with pytest.raises(ValueError, match="different annotator names"):
        compare_semantic_annotations.compare_annotations(
            results,
            annotations,
            deepcopy(annotations),
            expected_top_k=2,
        )


def test_compare_annotations_rejects_result_key_mismatch() -> None:
    results = make_results()
    annotation_a = make_annotations(
        results,
        annotator="reviewer-a",
        labels=["relevant", "partially_relevant", "not_relevant", "relevant"],
    )
    annotation_b = make_annotations(
        results,
        annotator="reviewer-b",
        labels=["relevant", "partially_relevant", "not_relevant", "relevant"],
    )
    annotation_b["annotations"][0]["chunk_id"] = "wrong_chunk"

    with pytest.raises(ValueError, match="Annotation/result mismatch"):
        compare_semantic_annotations.compare_annotations(
            results,
            annotation_a,
            annotation_b,
            expected_top_k=2,
        )


def test_cohens_kappa_is_undefined_when_both_use_only_one_label() -> None:
    matrix = {
        "relevant": {"relevant": 4, "partially_relevant": 0, "not_relevant": 0},
        "partially_relevant": {"relevant": 0, "partially_relevant": 0, "not_relevant": 0},
        "not_relevant": {"relevant": 0, "partially_relevant": 0, "not_relevant": 0},
    }

    assert compare_semantic_annotations.calculate_cohens_kappa(matrix) is None
