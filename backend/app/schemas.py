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


class CaseSummaryDetail(BaseModel):
    case_id: str
    holding: str | None
    applicant_claim: str | None
    reasoning: str | None
    summary_method: str | None
    created_at: str | None


class SimilarCase(BaseModel):
    case_id: str
    case_number: str
    decision_date: str | None
    dispute_type: str | None
    decision_result: str | None
    score: float
    matched_reasons: list[str]


class SimilarCasesResponse(BaseModel):
    case_id: str
    items: list[SimilarCase]
    total_candidates: int


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


class SemanticSearchResult(BaseModel):
    chunk_id: str
    case_id: str
    case_number: str
    decision_date: str | None
    dispute_type: str | None
    section_hint: str | None
    chunk_index: int
    score: float
    chunk_text: str


class SemanticSearchResponse(BaseModel):
    query: str
    embedding_model: str
    items: list[SemanticSearchResult]
    total_candidates: int


class SemanticSimilarChunk(BaseModel):
    chunk_id: str
    section_hint: str | None
    chunk_index: int
    score: float
    chunk_text: str


class SemanticSimilarCase(BaseModel):
    case_id: str
    case_number: str
    decision_date: str | None
    dispute_type: str | None
    score: float
    matched_chunks: list[SemanticSimilarChunk]


class SemanticSimilarCasesResponse(BaseModel):
    case_id: str
    embedding_model: str
    source_chunk_count: int
    items: list[SemanticSimilarCase]
    total_candidates: int


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


class QualityScope(BaseModel):
    roc_year: int
    case_count: int
    dispute_type_count: int
    formal_database_case_count: int
    formal_database_year_distribution: dict[str, int]


class QualitySummaryFieldStat(BaseModel):
    field: str
    non_empty: int
    min_length: int
    median_length: float
    average_length: float
    max_length: int


class QualityContaminationCheck(BaseModel):
    name: str
    issue_count: int


class QualityScoringRule(BaseModel):
    name: str
    points: int
    description: str


class QualitySampleCase(BaseModel):
    case_number: str
    dispute_type: str
    decision_date: str
    holding_length: int
    applicant_claim_length: int
    reasoning_length: int
    top5_same_dispute_type_count: int


class QualitySimilarStats(BaseModel):
    evaluated_cases: int
    top1_same_dispute_type: int
    top1_same_dispute_type_rate: float
    top5_contains_same_dispute_type: int
    top5_contains_same_dispute_type_rate: float
    average_same_type_count_in_top5: float
    min_same_type_count_in_top5: int


class QualityKnownException(BaseModel):
    case_number: str
    dispute_type: str
    decision_date: str
    reason: str


class QualityConclusion(BaseModel):
    title: str
    items: list[str]


class QualityReport(BaseModel):
    report_title: str
    report_date: str
    method_version: str
    scope: QualityScope
    top_dispute_types: list[CountItem]
    summary_field_stats: list[QualitySummaryFieldStat]
    contamination_checks: list[QualityContaminationCheck]
    scoring_rules: list[QualityScoringRule]
    sample_cases: list[QualitySampleCase]
    similar_stats: QualitySimilarStats
    known_exceptions: list[QualityKnownException]
    conclusions: list[QualityConclusion]
    limitations: list[str]
    next_steps: list[str]
