from __future__ import annotations

from pathlib import Path

import requests

from foi_ods_case_organizer import default_report_path as organizer_report_path
from foi_ods_life_mvp_crawler import default_metadata_path
from foi_ods_life_mvp_crawler import response_text
from foi_ods_pdf_text_pipeline import default_report_path as pdf_text_report_path


def test_crawler_default_metadata_path_uses_selected_roc_year() -> None:
    assert default_metadata_path(114) == Path("data/foi_ods/metadata/foi_ods_life_roc114_metadata.json")
    assert default_metadata_path(116) == Path("data/foi_ods/metadata/foi_ods_life_roc116_metadata.json")


def test_pdf_text_report_path_follows_metadata_year() -> None:
    metadata_path = Path("data/foi_ods/metadata/foi_ods_life_roc114_metadata.json")

    assert pdf_text_report_path(metadata_path) == Path(
        "data/foi_ods/metadata/foi_ods_life_roc114_pdf_text_report.json"
    )


def test_case_organizer_report_path_follows_metadata_year() -> None:
    metadata_path = Path("data/foi_ods/metadata/foi_ods_life_roc116_metadata.json")

    assert organizer_report_path(metadata_path) == Path(
        "data/foi_ods/metadata/foi_ods_life_roc116_case_organize_report.json"
    )


def test_crawler_response_text_uses_declared_charset_before_apparent_encoding() -> None:
    response = requests.Response()
    response._content = "113\u5e74\u8a55\u5b57\u7b2c004313\u865f".encode("utf-8")
    response.encoding = "utf-8"

    assert response_text(response) == "113\u5e74\u8a55\u5b57\u7b2c004313\u865f"
