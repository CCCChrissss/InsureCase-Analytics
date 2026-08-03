from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALID_LABELS = ("relevant", "partially_relevant", "not_relevant")
LABEL_NAMES = {
    "relevant": "相關",
    "partially_relevant": "部分相關",
    "not_relevant": "不相關",
}


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def validate_results(payload: dict[str, Any], *, expected_top_k: int) -> list[dict[str, Any]]:
    queries = payload.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("Result payload must contain a non-empty queries list.")

    seen_queries: set[str] = set()
    validated: list[dict[str, Any]] = []
    for query_result in queries:
        query = str(query_result.get("query", "")).strip()
        top = query_result.get("top")
        if not query or not isinstance(top, list):
            raise ValueError("Each query result must contain query text and a top list.")
        if query in seen_queries:
            raise ValueError(f"Duplicate query in result payload: {query}")
        if len(top) != expected_top_k:
            raise ValueError(f"Query '{query}' has {len(top)} results; expected {expected_top_k}.")

        seen_queries.add(query)
        seen_chunks: set[str] = set()
        rows: list[dict[str, Any]] = []
        for expected_rank, item in enumerate(top, start=1):
            chunk_id = str(item.get("chunk_id", "")).strip()
            if not chunk_id:
                raise ValueError(f"Query '{query}' rank {expected_rank} is missing chunk_id.")
            if chunk_id in seen_chunks:
                raise ValueError(f"Query '{query}' contains duplicate chunk_id: {chunk_id}")
            seen_chunks.add(chunk_id)
            rows.append(
                {
                    "query": query,
                    "rank": expected_rank,
                    "score": item.get("score"),
                    "chunk_id": chunk_id,
                    "case_id": str(item.get("case_id", "")),
                    "case_number": str(item.get("case_number", "")),
                    "dispute_type": str(item.get("dispute_type") or ""),
                    "section_hint": str(item.get("section_hint") or ""),
                    "chunk_text": str(item.get("chunk_text") or ""),
                }
            )
        validated.append({"query": query, "rows": rows})
    return validated


def build_annotation_template(payload: dict[str, Any], *, expected_top_k: int = 5) -> dict[str, Any]:
    query_rows = validate_results(payload, expected_top_k=expected_top_k)
    annotations = []
    for query_result in query_rows:
        for row in query_result["rows"]:
            annotations.append(
                {
                    **row,
                    "label": "",
                    "evidence_summary": "",
                }
            )

    return {
        "query_set": payload.get("query_set", "custom"),
        "embedding_model": payload.get("embedding_model", ""),
        "annotator": "",
        "label_policy": {
            "relevant": "原文直接回答或討論查詢概念。",
            "partially_relevant": "原文與查詢概念有實質關聯，但不是主要爭點或只涵蓋部分概念。",
            "not_relevant": "原文沒有足以支持查詢概念的內容。",
        },
        "annotations": annotations,
    }


def evaluate_results(
    result_payload: dict[str, Any],
    annotation_payload: dict[str, Any],
    *,
    expected_top_k: int = 5,
) -> dict[str, Any]:
    query_rows = validate_results(result_payload, expected_top_k=expected_top_k)
    annotations = annotation_payload.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("Annotation payload must contain an annotations list.")

    annotation_map: dict[tuple[str, str], dict[str, Any]] = {}
    for annotation in annotations:
        key = (str(annotation.get("query", "")).strip(), str(annotation.get("chunk_id", "")).strip())
        if not all(key):
            raise ValueError("Every annotation must contain query and chunk_id.")
        if key in annotation_map:
            raise ValueError(f"Duplicate annotation: query={key[0]}, chunk_id={key[1]}")
        label = str(annotation.get("label", "")).strip()
        if label not in VALID_LABELS:
            raise ValueError(f"Invalid or missing label for query={key[0]}, chunk_id={key[1]}: {label!r}")
        if not str(annotation.get("evidence_summary", "")).strip():
            raise ValueError(f"Missing evidence_summary for query={key[0]}, chunk_id={key[1]}")
        annotation_map[key] = annotation

    expected_keys = {
        (row["query"], row["chunk_id"])
        for query_result in query_rows
        for row in query_result["rows"]
    }
    actual_keys = set(annotation_map)
    missing = sorted(expected_keys - actual_keys)
    extra = sorted(actual_keys - expected_keys)
    if missing or extra:
        raise ValueError(f"Annotation/result mismatch: missing={len(missing)}, extra={len(extra)}")

    query_metrics = []
    detail_rows = []
    total_counts = {label: 0 for label in VALID_LABELS}
    for query_result in query_rows:
        counts = {label: 0 for label in VALID_LABELS}
        case_ids: set[str] = set()
        for row in query_result["rows"]:
            annotation = annotation_map[(row["query"], row["chunk_id"])]
            label = str(annotation["label"])
            counts[label] += 1
            total_counts[label] += 1
            if row["case_id"]:
                case_ids.add(row["case_id"])
            detail_rows.append(
                {
                    **row,
                    "label": label,
                    "evidence_summary": str(annotation["evidence_summary"]).strip(),
                }
            )

        strict_precision = counts["relevant"] / expected_top_k
        lenient_precision = (counts["relevant"] + counts["partially_relevant"]) / expected_top_k
        query_metrics.append(
            {
                "query": query_result["query"],
                "relevant": counts["relevant"],
                "partially_relevant": counts["partially_relevant"],
                "not_relevant": counts["not_relevant"],
                "strict_precision_at_k": round(strict_precision, 4),
                "lenient_precision_at_k": round(lenient_precision, 4),
                "unique_cases": len(case_ids),
            }
        )

    total_results = len(detail_rows)
    return {
        "query_set": result_payload.get("query_set", "custom"),
        "embedding_model": result_payload.get("embedding_model", ""),
        "annotator": annotation_payload.get("annotator", ""),
        "top_k": expected_top_k,
        "query_count": len(query_metrics),
        "total_results": total_results,
        "totals": total_counts,
        "micro_strict_precision_at_k": round(total_counts["relevant"] / total_results, 4),
        "micro_lenient_precision_at_k": round(
            (total_counts["relevant"] + total_counts["partially_relevant"]) / total_results,
            4,
        ),
        "macro_strict_precision_at_k": round(
            sum(item["strict_precision_at_k"] for item in query_metrics) / len(query_metrics),
            4,
        ),
        "macro_lenient_precision_at_k": round(
            sum(item["lenient_precision_at_k"] for item in query_metrics) / len(query_metrics),
            4,
        ),
        "queries": query_metrics,
        "details": detail_rows,
    }


def markdown_cell(value: object) -> str:
    return " ".join(str(value or "").split()).replace("|", "\\|")


def build_markdown_report(evaluation: dict[str, Any]) -> str:
    totals = evaluation["totals"]
    top_k = evaluation["top_k"]
    lines = [
        "# Hugging Face Semantic Benchmark v1 Evaluation",
        "",
        f"- Query set: `{evaluation['query_set']}`",
        f"- Embedding model: `{evaluation['embedding_model']}`",
        f"- Annotator: `{evaluation['annotator'] or 'not specified'}`",
        f"- Queries: `{evaluation['query_count']}`",
        f"- Results: `{evaluation['total_results']}`",
        "",
        "## Metric Definitions",
        "",
        f"- Strict Precision@{top_k}: only `relevant` counts as correct.",
        f"- Lenient Precision@{top_k}: `relevant` and `partially_relevant` count as correct.",
        "- The metric is chunk-level. Multiple chunks from the same case are counted separately; `unique_cases` exposes that duplication.",
        "",
        "## Overall Results",
        "",
        f"| relevant | partially_relevant | not_relevant | micro strict P@{top_k} | micro lenient P@{top_k} | macro strict P@{top_k} | macro lenient P@{top_k} |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| {totals['relevant']} | {totals['partially_relevant']} | {totals['not_relevant']} | "
        f"{evaluation['micro_strict_precision_at_k']:.4f} | {evaluation['micro_lenient_precision_at_k']:.4f} | "
        f"{evaluation['macro_strict_precision_at_k']:.4f} | {evaluation['macro_lenient_precision_at_k']:.4f} |",
        "",
        "## Per-Query Results",
        "",
        f"| query | relevant | partial | not relevant | strict P@{top_k} | lenient P@{top_k} | unique cases |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in evaluation["queries"]:
        lines.append(
            f"| {markdown_cell(item['query'])} | {item['relevant']} | {item['partially_relevant']} | "
            f"{item['not_relevant']} | {item['strict_precision_at_k']:.4f} | "
            f"{item['lenient_precision_at_k']:.4f} | {item['unique_cases']} |"
        )

    lines.extend(
        [
            "",
            "## Detailed Judgements",
            "",
            "| query | rank | score | case_number | dispute_type | chunk_id | label | evidence summary |",
            "| --- | ---: | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for item in evaluation["details"]:
        lines.append(
            f"| {markdown_cell(item['query'])} | {item['rank']} | {item['score']} | "
            f"`{markdown_cell(item['case_number'])}` | {markdown_cell(item['dispute_type'])} | "
            f"`{item['chunk_id']}` | {LABEL_NAMES[item['label']]} | {markdown_cell(item['evidence_summary'])} |"
        )

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- This evaluates only the stored trial candidate pool, not the complete production database.",
            "- A single annotator can introduce subjective bias; a second independent annotation pass is recommended.",
            "- Precision@5 measures ranking relevance, not legal correctness or the correctness of an insurance decision.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create annotations or evaluate a semantic benchmark result JSON.")
    parser.add_argument("--results", type=Path, required=True, help="JSON output from run_semantic_query_trial.py.")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--template-out", type=Path, help="Create a blank annotation JSON template.")
    action.add_argument("--annotations", type=Path, help="Completed annotation JSON used for evaluation.")
    parser.add_argument("--out", type=Path, default=None, help="Optional Markdown evaluation report path.")
    parser.add_argument("--top-k", type=int, default=5, help="Expected result count per query.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.top_k <= 0:
        raise SystemExit("--top-k must be greater than 0.")
    results_path = resolve_project_path(args.results)
    result_payload = load_json(results_path)

    if args.template_out:
        template = build_annotation_template(result_payload, expected_top_k=args.top_k)
        template_path = resolve_project_path(args.template_out)
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"template": str(template_path), "annotations": len(template["annotations"])}, ensure_ascii=False))
        return

    annotation_payload = load_json(resolve_project_path(args.annotations))
    evaluation = evaluate_results(result_payload, annotation_payload, expected_top_k=args.top_k)
    print(json.dumps(evaluation, ensure_ascii=False, indent=2))
    if args.out:
        out_path = resolve_project_path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(build_markdown_report(evaluation), encoding="utf-8")


if __name__ == "__main__":
    main()
