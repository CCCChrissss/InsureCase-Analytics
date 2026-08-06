from __future__ import annotations

from backend.app.services.document_section_service import structure_document_text


SAMPLE_DOCUMENT = """財團法人金融消費評議中心評議書
【114 年評字第 9999 號】
主文
本中心尚難為有利申請人之認定。
事實及理由
一、程序事項：
程序內容。
二、申請人之主張：
申請人內容。
三、相對人之主張：
相對人完整內容。
四、兩造不爭執之事實：
不爭執內容。
五、本件爭點：
爭點內容。
六、判斷理由：
理由內容。
七、綜上所述，本件請求無理由。
八、據上論結，本件評議申請為無理由。
中 華 民 國 1 1 4 年 1 月 1 日
以上正本與原本無異。
"""


def test_structure_document_text_preserves_every_character() -> None:
    # The central safety property is exact reconstruction, not merely section count.
    result = structure_document_text("case_test", SAMPLE_DOCUMENT, "normalized")

    assert result["complete_coverage"] is True
    assert result["source_chars"] == len(SAMPLE_DOCUMENT)
    assert result["covered_chars"] == len(SAMPLE_DOCUMENT)
    assert "".join(section["content"] for section in result["sections"]) == SAMPLE_DOCUMENT


def test_structure_document_text_includes_respondent_claim() -> None:
    result = structure_document_text("case_test", SAMPLE_DOCUMENT, "normalized")
    respondent = next(
        section for section in result["sections"] if section["section_type"] == "respondent_claim"
    )

    assert respondent["title"] == "相對人主張"
    assert "相對人完整內容" in respondent["content"]
    assert respondent["char_count"] == len(respondent["content"])


def test_structure_document_text_keeps_unknown_format_as_other() -> None:
    source = "沒有標準標題，但內容仍必須完整保留。"

    result = structure_document_text("case_unknown", source, "raw")

    assert result["complete_coverage"] is True
    assert result["sections"][0]["section_type"] == "other"
    assert result["sections"][0]["content"] == source


def test_structure_document_text_accepts_shifted_numbers_and_legacy_glyphs() -> None:
    # Some official decisions add an extra substantive section, shifting the
    # conclusion numbers, and older PDFs use the compatibility glyph "論".
    source = """主文
請求無理由。
事實及理由
一、程序事項：
程序內容。
二、實體事項：
申請人內容。
三、相對人之主張：
相對人內容。
四、兩造不爭執事實：
不爭執內容。
三、本件爭點：
爭點內容。
四、判斷理由：
理由內容。
八、綜上所述，請求無理由。
九、據上論結，決定如主文。
中華民國 114 年 1 月 1 日
"""

    result = structure_document_text("case_variant", source, "normalized")
    section_types = {section["section_type"] for section in result["sections"]}

    assert result["complete_coverage"] is True
    assert {
        "applicant_claim",
        "respondent_claim",
        "undisputed_facts",
        "issues",
        "reasoning",
        "conclusion",
        "disposition",
    } <= section_types
