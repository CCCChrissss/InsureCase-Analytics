from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database_ready: bool


class CaseSummary(BaseModel):
    case_id: str
    case_number: str
    roc_year: int
    decision_date: str | None
    decision_category: str | None
    decision_result: str | None
    industry: str | None
    industry_subcategory: str | None
    dispute_type: str | None
    pdf_path: str | None
    normalized_text_path: str | None


class PaginatedCases(BaseModel):
    items: list[CaseSummary]
    total: int
    page: int
    page_size: int


class CaseDetail(CaseSummary):
    source_pdf_url: str | None
    case_directory: str | None
    raw_text_path: str | None
    metadata_path: str | None
    raw_text: str | None
    normalized_text: str | None
    raw_text_chars: int | None
    normalized_text_chars: int | None
    page_count: int | None
    extraction_method: str | None


class SearchResult(BaseModel):
    case_id: str
    case_number: str
    decision_date: str | None
    dispute_type: str | None
    snippet: str | None
    match_source: str


class SearchResponse(BaseModel):
    items: list[SearchResult]
    total: int
    query: str
    page: int
    page_size: int


class OverviewStatistics(BaseModel):
    case_count: int
    dispute_type_count: int
    roc_years: list[int]
    first_decision_date: str | None
    last_decision_date: str | None


class CountItem(BaseModel):
    name: str
    count: int


class DateCountItem(BaseModel):
    decision_date: str
    count: int
