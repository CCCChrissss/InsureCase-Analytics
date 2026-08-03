from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.scripts import evaluate_semantic_benchmark


LABELS = evaluate_semantic_benchmark.VALID_LABELS
LABEL_NAMES = evaluate_semantic_benchmark.LABEL_NAMES


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def validate_annotator(annotation_payload: dict[str, Any], *, source_name: str) -> str:
    annotator = str(annotation_payload.get("annotator", "")).strip()
    if not annotator:
        raise ValueError(f"{source_name} must contain a non-empty annotator name.")
    return annotator


def calculate_cohens_kappa(confusion_matrix: dict[str, dict[str, int]]) -> float | None:
    total = sum(sum(row.values()) for row in confusion_matrix.values())
    if total == 0:
        raise ValueError("Cannot calculate agreement without annotations.")

    observed = sum(confusion_matrix[label][label] for label in LABELS) / total
    row_totals = {label: sum(confusion_matrix[label].values()) for label in LABELS}
    column_totals = {
        label: sum(confusion_matrix[row_label][label] for row_label in LABELS)
        for label in LABELS
    }
    expected = sum(row_totals[label] * column_totals[label] for label in LABELS) / (total * total)
    if expected == 1.0:
        return None
    return round((observed - expected) / (1.0 - expected), 4)


def compare_annotations(
    result_payload: dict[str, Any],
    annotation_a: dict[str, Any],
    annotation_b: dict[str, Any],
    *,
    expected_top_k: int = 5,
) -> dict[str, Any]:
    annotator_a = validate_annotator(annotation_a, source_name="annotations-a")
    annotator_b = validate_annotator(annotation_b, source_name="annotations-b")
    if annotator_a.casefold() == annotator_b.casefold():
        raise ValueError("The two annotation files must use different annotator names.")

    evaluation_a = evaluate_semantic_benchmark.evaluate_results(
        result_payload,
        annotation_a,
        expected_top_k=expected_top_k,
    )
    evaluation_b = evaluate_semantic_benchmark.evaluate_results(
        result_payload,
        annotation_b,
        expected_top_k=expected_top_k,
    )
    details_a = {(item["query"], item["chunk_id"]): item for item in evaluation_a["details"]}
    details_b = {(item["query"], item["chunk_id"]): item for item in evaluation_b["details"]}

    confusion_matrix = {
        label_a: {label_b: 0 for label_b in LABELS}
        for label_a in LABELS
    }
    query_stats: dict[str, dict[str, int]] = {}
    conflicts = []
    agreements = 0

    for item_a in evaluation_a["details"]:
        key = (item_a["query"], item_a["chunk_id"])
        item_b = details_b[key]
        label_a = item_a["label"]
        label_b = item_b["label"]
        confusion_matrix[label_a][label_b] += 1

        stats = query_stats.setdefault(item_a["query"], {"total": 0, "agreements": 0})
        stats["total"] += 1
        if label_a == label_b:
            agreements += 1
            stats["agreements"] += 1
            continue

        conflicts.append(
            {
                "query": item_a["query"],
                "rank": item_a["rank"],
                "score": item_a["score"],
                "case_number": item_a["case_number"],
                "dispute_type": item_a["dispute_type"],
                "chunk_id": item_a["chunk_id"],
                "label_a": label_a,
                "evidence_a": item_a["evidence_summary"],
                "label_b": label_b,
                "evidence_b": item_b["evidence_summary"],
            }
        )

    total = len(details_a)
    per_query = [
        {
            "query": query,
            "total": stats["total"],
            "agreements": stats["agreements"],
            "disagreements": stats["total"] - stats["agreements"],
            "agreement_rate": round(stats["agreements"] / stats["total"], 4),
        }
        for query, stats in query_stats.items()
    ]
    return {
        "query_set": result_payload.get("query_set", "custom"),
        "embedding_model": result_payload.get("embedding_model", ""),
        "top_k": expected_top_k,
        "annotator_a": annotator_a,
        "annotator_b": annotator_b,
        "query_count": len(per_query),
        "total_results": total,
        "agreements": agreements,
        "disagreements": total - agreements,
        "agreement_rate": round(agreements / total, 4),
        "cohens_kappa": calculate_cohens_kappa(confusion_matrix),
        "confusion_matrix": confusion_matrix,
        "queries": per_query,
        "conflicts": conflicts,
    }


def markdown_cell(value: object) -> str:
    return " ".join(str(value or "").split()).replace("|", "\\|")


def display_metric(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def build_markdown_report(comparison: dict[str, Any]) -> str:
    lines = [
        "# 語意搜尋 Benchmark v1 標註一致性報告",
        "",
        f"- 查詢集：`{comparison['query_set']}`",
        f"- Embedding model：`{comparison['embedding_model']}`",
        f"- 標註者 A：`{comparison['annotator_a']}`",
        f"- 標註者 B：`{comparison['annotator_b']}`",
        f"- 判讀結果數：`{comparison['total_results']}`",
        "",
        "## 整體一致性",
        "",
        "| 一致筆數 | 衝突筆數 | 原始一致率 | Cohen's Kappa |",
        "| ---: | ---: | ---: | ---: |",
        f"| {comparison['agreements']} | {comparison['disagreements']} | "
        f"{comparison['agreement_rate']:.4f} | {display_metric(comparison['cohens_kappa'])} |",
        "",
        "Cohen's Kappa 會扣除隨機一致的可能性；若兩位標註者都只使用同一標籤，Kappa 無法定義，報告會顯示 `N/A`。",
        "",
        "## 標籤混淆矩陣",
        "",
        "列為標註者 A，欄為標註者 B。",
        "",
        "| A \\ B | 相關 | 部分相關 | 不相關 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label_a in LABELS:
        row = comparison["confusion_matrix"][label_a]
        lines.append(
            f"| {LABEL_NAMES[label_a]} | {row['relevant']} | {row['partially_relevant']} | {row['not_relevant']} |"
        )

    lines.extend(
        [
            "",
            "## 各查詢一致率",
            "",
            "| 查詢詞 | 一致 | 衝突 | 一致率 |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for item in comparison["queries"]:
        lines.append(
            f"| {markdown_cell(item['query'])} | {item['agreements']} | "
            f"{item['disagreements']} | {item['agreement_rate']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## 待仲裁衝突",
            "",
        ]
    )
    if not comparison["conflicts"]:
        lines.append("兩位標註者的標記完全一致，沒有待仲裁項目。")
    else:
        lines.extend(
            [
                "| 查詢詞 | 排名 | 案號 | chunk_id | A 標記與依據 | B 標記與依據 |",
                "| --- | ---: | --- | --- | --- | --- |",
            ]
        )
        for item in comparison["conflicts"]:
            lines.append(
                f"| {markdown_cell(item['query'])} | {item['rank']} | `{markdown_cell(item['case_number'])}` | "
                f"`{item['chunk_id']}` | {LABEL_NAMES[item['label_a']]}：{markdown_cell(item['evidence_a'])} | "
                f"{LABEL_NAMES[item['label_b']]}：{markdown_cell(item['evidence_b'])} |"
            )

    lines.extend(
        [
            "",
            "## 使用限制",
            "",
            "- 一致率與 Kappa 衡量標註一致性，不代表標註本身一定正確。",
            "- 衝突項目需要由雙方或第三位仲裁者回查案件原文後決定最終標記。",
            "- 本報告只適用於相同查詢結果集，不可用來比較不同候選資料或不同排名結果。",
            "",
        ]
    )
    return "\n".join(lines)


def compact_summary(comparison: dict[str, Any]) -> dict[str, Any]:
    return {
        key: comparison[key]
        for key in (
            "query_set",
            "embedding_model",
            "top_k",
            "annotator_a",
            "annotator_b",
            "query_count",
            "total_results",
            "agreements",
            "disagreements",
            "agreement_rate",
            "cohens_kappa",
        )
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two completed semantic benchmark annotation files.")
    parser.add_argument("--results", type=Path, required=True, help="Benchmark result JSON.")
    parser.add_argument("--annotations-a", type=Path, required=True, help="First completed annotation JSON.")
    parser.add_argument("--annotations-b", type=Path, required=True, help="Second completed annotation JSON.")
    parser.add_argument("--out", type=Path, default=None, help="Optional Markdown agreement report path.")
    parser.add_argument("--top-k", type=int, default=5, help="Expected result count per query.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.top_k <= 0:
        raise SystemExit("--top-k must be greater than 0.")

    result_payload = evaluate_semantic_benchmark.load_json(resolve_project_path(args.results))
    annotation_a = evaluate_semantic_benchmark.load_json(resolve_project_path(args.annotations_a))
    annotation_b = evaluate_semantic_benchmark.load_json(resolve_project_path(args.annotations_b))
    comparison = compare_annotations(
        result_payload,
        annotation_a,
        annotation_b,
        expected_top_k=args.top_k,
    )
    if args.out:
        out_path = resolve_project_path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(build_markdown_report(comparison), encoding="utf-8")
    print(json.dumps(compact_summary(comparison), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
