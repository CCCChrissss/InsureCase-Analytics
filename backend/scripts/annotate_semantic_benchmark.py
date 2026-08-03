from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.scripts.evaluate_semantic_benchmark import VALID_LABELS

DEFAULT_ANNOTATIONS_PATH = PROJECT_ROOT / "outputs" / "local_bge_semantic_benchmark_v1_1000_annotations.json"
DEFAULT_DB_PATH = PROJECT_ROOT / "backend" / "data" / "insurance_cases_local_bge_trial.db"
LABEL_SHORTCUTS = {
    "r": "relevant",
    "p": "partially_relevant",
    "n": "not_relevant",
    **{label: label for label in VALID_LABELS},
}
LABEL_NAMES = {
    "relevant": "相關",
    "partially_relevant": "部分相關",
    "not_relevant": "不相關",
}


def configure_stdout_utf8() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_annotation_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("annotations"), list):
        raise ValueError("Annotation file must contain an annotations list.")
    return payload


def save_annotation_payload(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def parse_label(value: str) -> str | None:
    return LABEL_SHORTCUTS.get(value.strip().lower())


def is_complete(annotation: dict[str, Any]) -> bool:
    return annotation.get("label") in VALID_LABELS and bool(str(annotation.get("evidence_summary", "")).strip())


def progress_counts(annotations: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("label", "")) for item in annotations if is_complete(item))
    completed = sum(counts.values())
    return {
        "total": len(annotations),
        "completed": completed,
        "remaining": len(annotations) - completed,
        **{label: counts[label] for label in VALID_LABELS},
    }


def pending_indices(
    annotations: list[dict[str, Any]],
    *,
    query: str | None = None,
    skipped: set[int] | None = None,
) -> list[int]:
    skipped = skipped or set()
    return [
        index
        for index, annotation in enumerate(annotations)
        if index not in skipped
        and not is_complete(annotation)
        and (query is None or str(annotation.get("query", "")) == query)
    ]


def load_context_chunks(db_path: Path, annotation: dict[str, Any], *, context_size: int) -> list[dict[str, Any]]:
    if context_size < 0:
        raise ValueError("context_size must not be negative.")
    if not db_path.is_file():
        return []

    case_id = str(annotation.get("case_id", "")).strip()
    chunk_index = int(annotation.get("chunk_index", 0))
    if not case_id:
        return []

    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT chunk_id, chunk_index, section_hint, chunk_text
            FROM case_chunks
            WHERE case_id = ? AND chunk_index BETWEEN ? AND ?
            ORDER BY chunk_index;
            """,
            (case_id, max(0, chunk_index - context_size), chunk_index + context_size),
        ).fetchall()
    return [dict(row) for row in rows]


def render_annotation(
    annotation: dict[str, Any],
    *,
    position: int,
    total: int,
    context_chunks: list[dict[str, Any]],
) -> str:
    lines = [
        "=" * 88,
        f"標註進度：第 {position} / {total} 筆",
        f"查詢詞：{annotation.get('query', '')} | 排名：{annotation.get('rank', '')} | 分數：{annotation.get('score', '')}",
        f"案號：{annotation.get('case_number', '')}",
        f"爭議類型：{annotation.get('dispute_type', '')} | 段落：{annotation.get('section_hint', '')}",
        f"chunk_id：{annotation.get('chunk_id', '')}",
        "-" * 88,
    ]

    if context_chunks:
        current_chunk_id = str(annotation.get("chunk_id", ""))
        for chunk in context_chunks:
            marker = ">>> 目前結果" if chunk["chunk_id"] == current_chunk_id else "    相鄰段落"
            lines.extend(
                [
                    f"{marker} | chunk {chunk['chunk_index']} | {chunk.get('section_hint') or '未標示段落'}",
                    str(chunk["chunk_text"]),
                    "-" * 88,
                ]
            )
    else:
        lines.extend([str(annotation.get("chunk_text", "")), "-" * 88])

    if is_complete(annotation):
        label = str(annotation["label"])
        lines.append(f"目前標註：{LABEL_NAMES[label]} | {annotation['evidence_summary']}")
    return "\n".join(lines)


def apply_annotation(annotation: dict[str, Any], *, label: str, evidence_summary: str) -> None:
    if label not in VALID_LABELS:
        raise ValueError(f"Unsupported label: {label}")
    evidence = evidence_summary.strip()
    if not evidence:
        raise ValueError("evidence_summary must not be empty.")
    annotation["label"] = label
    annotation["evidence_summary"] = evidence


def prompt_for_annotator(
    payload: dict[str, Any],
    *,
    input_func: Callable[[str], str] = input,
) -> bool:
    if str(payload.get("annotator", "")).strip():
        return False
    while True:
        name = input_func("請輸入標註者名稱或代號：").strip()
        if name:
            payload["annotator"] = name
            return True
        print("標註者名稱不可空白。")


def run_annotation_session(
    payload: dict[str, Any],
    *,
    annotations_path: Path,
    db_path: Path,
    query: str | None,
    index: int | None,
    context_size: int,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> dict[str, int]:
    annotations = payload["annotations"]
    if index is not None:
        if index < 1 or index > len(annotations):
            raise ValueError(f"index must be between 1 and {len(annotations)}.")
        selected_indices = [index - 1]
    else:
        selected_indices = []

    skipped: set[int] = set()
    while True:
        if selected_indices:
            current_index = selected_indices.pop(0)
        else:
            pending = pending_indices(annotations, query=query, skipped=skipped)
            if not pending:
                break
            current_index = pending[0]

        annotation = annotations[current_index]
        context_chunks = load_context_chunks(db_path, annotation, context_size=context_size)
        output_func(
            render_annotation(
                annotation,
                position=current_index + 1,
                total=len(annotations),
                context_chunks=context_chunks,
            )
        )
        output_func("標籤：r=相關、p=部分相關、n=不相關、s=略過、q=儲存並離開")

        while True:
            choice = input_func("請輸入標籤：").strip().lower()
            if choice == "q":
                return progress_counts(annotations)
            if choice == "s":
                skipped.add(current_index)
                break
            label = parse_label(choice)
            if label is None:
                output_func("無效標籤，請輸入 r、p、n、s 或 q。")
                continue

            evidence = input_func("請輸入判斷依據：").strip()
            if not evidence:
                output_func("判斷依據不可空白。")
                continue
            apply_annotation(annotation, label=label, evidence_summary=evidence)
            save_annotation_payload(annotations_path, payload)
            output_func(f"已儲存：{LABEL_NAMES[label]}")
            break

        if index is not None:
            break

    return progress_counts(annotations)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactively label semantic benchmark results without external APIs.")
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS_PATH, help="Annotation JSON path.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="Read-only trial DB for adjacent chunks.")
    parser.add_argument("--query", help="Only annotate one exact query text.")
    parser.add_argument("--index", type=int, help="Review or replace one 1-based annotation index.")
    parser.add_argument("--context-size", type=int, default=1, help="Adjacent chunks shown on each side. Default: 1.")
    return parser.parse_args()


def main() -> None:
    configure_stdout_utf8()
    args = parse_args()
    annotations_path = resolve_project_path(args.annotations)
    db_path = resolve_project_path(args.db)
    if not annotations_path.is_file():
        raise SystemExit(f"Annotation file not found: {annotations_path}")
    if args.context_size < 0:
        raise SystemExit("--context-size must not be negative.")

    payload = load_annotation_payload(annotations_path)
    if prompt_for_annotator(payload):
        save_annotation_payload(annotations_path, payload)

    try:
        progress = run_annotation_session(
            payload,
            annotations_path=annotations_path,
            db_path=db_path,
            query=args.query,
            index=args.index,
            context_size=args.context_size,
        )
    except KeyboardInterrupt:
        print("\n已停止；先前完成的每一筆都已個別儲存。")
        progress = progress_counts(payload["annotations"])

    print(
        f"進度：{progress['completed']} / {progress['total']}，剩餘 {progress['remaining']}；"
        f"相關 {progress['relevant']}、部分相關 {progress['partially_relevant']}、"
        f"不相關 {progress['not_relevant']}。"
    )


if __name__ == "__main__":
    main()
