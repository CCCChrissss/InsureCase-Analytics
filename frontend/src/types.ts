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

export type Route = "dashboard" | "cases" | "search" | "statistics";
