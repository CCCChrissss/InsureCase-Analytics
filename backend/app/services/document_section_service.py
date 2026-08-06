from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SectionMarker:
    """A recognized top-level heading and its exact position in the source text."""

    section_type: str
    title: str
    start: int
    heading: str


SECTION_TITLES = {
    "basic_info": "案件基本資料",
    "holding": "主文",
    "procedure": "程序事項",
    "applicant_claim": "申請人主張",
    "respondent_claim": "相對人主張",
    "undisputed_facts": "兩造不爭執事項",
    "issues": "本件爭點",
    "reasoning": "判斷理由",
    "conclusion": "綜上所述",
    "disposition": "據上論結",
    "notice": "決定書附註與權利說明",
    "other": "其他原文內容",
}

_HOLDING_PATTERN = re.compile(r"(?m)^[ \t]*主[ \t]*文[ \t]*$")
_FACTS_PATTERN = re.compile(r"(?m)^[ \t]*事[ \t]*實[ \t]*及[ \t]*理[ \t]*由[ \t]*$")
_NUMBERED_HEADING_PATTERN = re.compile(
    r"(?m)^[ \t]*([一二三四五六七八九十]{1,3})[、，,.．][ \t]*(.+?)[ \t]*$"
)
_NOTICE_PATTERN = re.compile(r"(?m)^[ \t]*中[ \t]*華[ \t]*民[ \t]*國[ \t]*")

_NUMBERED_SECTION_RULES = (
    ("procedure", ("程序事項",)),
    ("applicant_claim", ("申請人之主張", "申請人主張")),
    ("respondent_claim", ("相對人之主張", "相對人主張")),
    ("undisputed_facts", ("兩造不爭執之事實", "兩造不爭執事實", "兩造不爭執事項")),
    ("issues", ("本件爭點",)),
    ("reasoning", ("判斷理由",)),
    ("conclusion", ("綜上所述",)),
    ("disposition", ("據上論結",)),
)


def _compact(value: str) -> str:
    """Normalize only for heading comparison; source text itself is never rewritten."""

    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).rstrip("：:")


def _numbered_markers(text: str) -> dict[str, SectionMarker]:
    markers: dict[str, SectionMarker] = {}
    for match in _NUMBERED_HEADING_PATTERN.finditer(text):
        number = match.group(1)
        heading_body = _compact(match.group(2))
        for section_type, prefixes in _NUMBERED_SECTION_RULES:
            if section_type in markers:
                continue
            if any(heading_body.startswith(prefix) for prefix in prefixes):
                markers[section_type] = SectionMarker(
                    section_type=section_type,
                    title=SECTION_TITLES[section_type],
                    start=match.start(),
                    heading=match.group(0).strip(),
                )
                break

        # A small set of decisions labels the applicant's entire submission as
        # "二、實體事項". It occupies the same structural position and contains
        # the request plus statement, so expose it as applicant_claim.
        if number == "二" and heading_body.startswith("實體事項") and "applicant_claim" not in markers:
            markers["applicant_claim"] = SectionMarker(
                section_type="applicant_claim",
                title=SECTION_TITLES["applicant_claim"],
                start=match.start(),
                heading=match.group(0).strip(),
            )
    return markers


def _first_marker(pattern: re.Pattern[str], text: str, section_type: str) -> SectionMarker | None:
    match = pattern.search(text)
    if match is None:
        return None
    return SectionMarker(
        section_type=section_type,
        title=SECTION_TITLES[section_type],
        start=match.start(),
        heading=match.group(0).strip(),
    )


def _ordered_markers(text: str) -> list[SectionMarker]:
    numbered = _numbered_markers(text)
    holding = _first_marker(_HOLDING_PATTERN, text, "holding")
    facts = _first_marker(_FACTS_PATTERN, text, "procedure")

    # "事實及理由" belongs to the procedure block. Keeping the later numbered
    # heading inside that block preserves every character without a tiny heading-only section.
    if facts is not None:
        numbered["procedure"] = facts

    candidates = [marker for marker in (holding, *numbered.values()) if marker is not None]
    candidates.sort(key=lambda marker: marker.start)

    notice_match = _NOTICE_PATTERN.search(text)
    if notice_match is not None:
        candidates.append(
            SectionMarker(
                section_type="notice",
                title=SECTION_TITLES["notice"],
                start=notice_match.start(),
                heading=notice_match.group(0).strip(),
            )
        )
        candidates.sort(key=lambda marker: marker.start)

    # Keep only the first marker of each type and enforce source order. This avoids
    # quoted headings inside a party's submission from splitting the document again.
    ordered: list[SectionMarker] = []
    seen_types: set[str] = set()
    for marker in candidates:
        if marker.section_type in seen_types:
            continue
        if ordered and marker.start <= ordered[-1].start:
            continue
        ordered.append(marker)
        seen_types.add(marker.section_type)
    return ordered


def structure_document_text(case_id: str, text: str, source_type: str) -> dict[str, Any]:
    """Split a decision into display sections while retaining byte-for-byte text coverage.

    Sections are contiguous source slices. Therefore joining every ``content`` value
    must recreate the supplied text exactly; unknown or missing headings can reduce
    granularity but can never silently remove source content.
    """

    markers = _ordered_markers(text)
    if not markers:
        markers = [
            SectionMarker(
                section_type="other",
                title=SECTION_TITLES["other"],
                start=0,
                heading="",
            )
        ]
    elif markers[0].start > 0:
        markers.insert(
            0,
            SectionMarker(
                section_type="basic_info",
                title=SECTION_TITLES["basic_info"],
                start=0,
                heading="",
            ),
        )

    sections: list[dict[str, Any]] = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start if index + 1 < len(markers) else len(text)
        content = text[marker.start:end]
        sections.append(
            {
                "section_id": f"{marker.section_type}_{index + 1}",
                "section_type": marker.section_type,
                "title": marker.title,
                "heading": marker.heading or None,
                "content": content,
                "order": index + 1,
                "char_count": len(content),
                "start_offset": marker.start,
                "end_offset": end,
            }
        )

    reconstructed = "".join(section["content"] for section in sections)
    covered_chars = sum(section["char_count"] for section in sections)
    return {
        "case_id": case_id,
        "source_type": source_type,
        "source_chars": len(text),
        "covered_chars": covered_chars,
        "complete_coverage": reconstructed == text and covered_chars == len(text),
        "sections": sections,
    }


def structure_case_document(case: dict[str, Any]) -> dict[str, Any]:
    """Select the best available case text and return its structured representation."""

    normalized_text = case.get("normalized_text") or ""
    raw_text = case.get("raw_text") or ""
    if normalized_text:
        return structure_document_text(case["case_id"], normalized_text, "normalized")
    return structure_document_text(case["case_id"], raw_text, "raw")
