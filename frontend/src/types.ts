export type HealthResponse = {
  status: string;
  database_ready: boolean;
};

export type OverviewStatistics = {
  case_count: number;
  dispute_type_count: number;
  roc_years: number[];
  first_decision_date: string | null;
  last_decision_date: string | null;
};

export type CountItem = {
  name: string;
  count: number;
};

export type DateCountItem = {
  decision_date: string;
  count: number;
};

export type CaseSummary = {
  case_id: string;
  case_number: string;
  roc_year: number;
  decision_date: string | null;
  decision_category: string | null;
  decision_result: string | null;
  industry: string | null;
  industry_subcategory: string | null;
  dispute_type: string | null;
  pdf_path: string | null;
  normalized_text_path: string | null;
};

export type PaginatedCases = {
  items: CaseSummary[];
  total: number;
  page: number;
  page_size: number;
};

export type CaseDetail = CaseSummary & {
  source_pdf_url: string | null;
  case_directory: string | null;
  raw_text_path: string | null;
  metadata_path: string | null;
  raw_text: string | null;
  normalized_text: string | null;
  raw_text_chars: number | null;
  normalized_text_chars: number | null;
  page_count: number | null;
  extraction_method: string | null;
};

export type CaseSummaryDetail = {
  case_id: string;
  holding: string | null;
  applicant_claim: string | null;
  reasoning: string | null;
  summary_method: string | null;
  created_at: string | null;
};

export type SimilarCase = {
  case_id: string;
  case_number: string;
  decision_date: string | null;
  dispute_type: string | null;
  decision_result: string | null;
  score: number;
  matched_reasons: string[];
};

export type SimilarCasesResponse = {
  case_id: string;
  items: SimilarCase[];
  total_candidates: number;
};

export type SearchResult = {
  case_id: string;
  case_number: string;
  decision_date: string | null;
  dispute_type: string | null;
  snippet: string | null;
  match_source: string;
};

export type SearchResponse = {
  items: SearchResult[];
  total: number;
  query: string;
  page: number;
  page_size: number;
};

export type SemanticSearchResult = {
  chunk_id: string;
  case_id: string;
  case_number: string;
  decision_date: string | null;
  dispute_type: string | null;
  section_hint: string | null;
  chunk_index: number;
  score: number;
  chunk_text: string;
};

export type SemanticSearchResponse = {
  query: string;
  embedding_model: string;
  items: SemanticSearchResult[];
  total_candidates: number;
};

export type QualityReport = {
  report_title: string;
  report_date: string;
  method_version: string;
  scope: {
    roc_year: number;
    case_count: number;
    dispute_type_count: number;
    formal_database_case_count: number;
    formal_database_year_distribution: Record<string, number>;
  };
  top_dispute_types: CountItem[];
  summary_field_stats: Array<{
    field: string;
    non_empty: number;
    min_length: number;
    median_length: number;
    average_length: number;
    max_length: number;
  }>;
  contamination_checks: Array<{
    name: string;
    issue_count: number;
  }>;
  scoring_rules: Array<{
    name: string;
    points: number;
    description: string;
  }>;
  sample_cases: Array<{
    case_number: string;
    dispute_type: string;
    decision_date: string;
    holding_length: number;
    applicant_claim_length: number;
    reasoning_length: number;
    top5_same_dispute_type_count: number;
  }>;
  similar_stats: {
    evaluated_cases: number;
    top1_same_dispute_type: number;
    top1_same_dispute_type_rate: number;
    top5_contains_same_dispute_type: number;
    top5_contains_same_dispute_type_rate: number;
    average_same_type_count_in_top5: number;
    min_same_type_count_in_top5: number;
  };
  known_exceptions: Array<{
    case_number: string;
    dispute_type: string;
    decision_date: string;
    reason: string;
  }>;
  conclusions: Array<{
    title: string;
    items: string[];
  }>;
  limitations: string[];
  next_steps: string[];
};

export type Route = "dashboard" | "cases" | "search" | "semantic" | "statistics" | "quality";
