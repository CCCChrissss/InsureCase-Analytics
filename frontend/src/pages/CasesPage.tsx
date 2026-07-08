import React from "react";

import { apiGet, apiGetOptional, apiPath } from "../api/client";
import { CaseDetailView } from "../components/CaseDetailView";
import { AsyncBlock, EmptyState, PageHeader, PanelHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type {
  CaseDetail,
  CaseSummaryDetail,
  CountItem,
  OverviewStatistics,
  PaginatedCases,
  SemanticSimilarCasesResponse,
  SimilarCasesResponse
} from "../types";

export function CasesPage({
  selectedCaseId,
  onSelectCase
}: {
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}) {
  const [page, setPage] = React.useState(1);
  const [caseNumber, setCaseNumber] = React.useState("");
  const [disputeType, setDisputeType] = React.useState("");
  const [rocYear, setRocYear] = React.useState("");

  const cases = useAsyncData(() => apiGet<PaginatedCases>(apiPath("/cases", {
    page,
    page_size: 12,
    roc_year: rocYear,
    dispute_type: disputeType,
    case_number: caseNumber
  })), [
    page,
    caseNumber,
    disputeType,
    rocYear
  ]);
  const overview = useAsyncData(() => apiGet<OverviewStatistics>("/statistics/overview"), []);
  const disputeTypes = useAsyncData(() => apiGet<CountItem[]>(apiPath("/statistics/dispute-types", { roc_year: rocYear })), [rocYear]);
  const detail = useAsyncData(
    () => (selectedCaseId ? apiGet<CaseDetail>(`/cases/${selectedCaseId}`) : Promise.resolve(null)),
    [selectedCaseId]
  );
  const summary = useAsyncData(
    () => (selectedCaseId ? apiGetOptional<CaseSummaryDetail>(`/cases/${selectedCaseId}/summary`) : Promise.resolve(null)),
    [selectedCaseId]
  );
  const similar = useAsyncData(
    () => (selectedCaseId ? apiGet<SimilarCasesResponse>(`/cases/${selectedCaseId}/similar?limit=5`) : Promise.resolve(null)),
    [selectedCaseId]
  );
  const semanticSimilar = useAsyncData(
    () => (selectedCaseId ? apiGet<SemanticSimilarCasesResponse>(`/cases/${selectedCaseId}/semantic-similar?limit=5&chunks_per_case=2`) : Promise.resolve(null)),
    [selectedCaseId]
  );

  const totalPages = Math.max(1, Math.ceil((cases.data?.total ?? 0) / (cases.data?.page_size ?? 12)));
  const years = overview.data?.roc_years ?? [];

  return (
    <section className="page">
      <PageHeader title="案件管理" description="依年度、爭議類型、案號查詢評議案件，並查看全文與 PDF。" />
      <div className="filters">
        <label>
          年度
          <select value={rocYear} onChange={(event) => { setPage(1); setRocYear(event.target.value); }}>
            <option value="">全部年度</option>
            {years.map((year) => (
              <option key={year} value={year}>ROC {year}</option>
            ))}
          </select>
        </label>
        <label>
          爭議類型
          <select value={disputeType} onChange={(event) => { setPage(1); setDisputeType(event.target.value); }}>
            <option value="">全部</option>
            {(disputeTypes.data ?? []).map((item) => (
              <option key={item.name} value={item.name}>{item.name} ({item.count})</option>
            ))}
          </select>
        </label>
        <label>
          案號
          <input value={caseNumber} onChange={(event) => { setPage(1); setCaseNumber(event.target.value); }} placeholder="例如 000625" />
        </label>
      </div>

      <div className="content-grid case-layout">
        <section className="panel">
          <PanelHeader title={`案件列表 ${cases.data ? `(${cases.data.total})` : ""}`} />
          <AsyncBlock loading={cases.loading} error={cases.error}>
            <div className="case-list">
              {(cases.data?.items ?? []).map((item) => (
                <button
                  key={item.case_id}
                  type="button"
                  className={item.case_id === selectedCaseId ? "case-row active" : "case-row"}
                  onClick={() => onSelectCase(item.case_id)}
                >
                  <span className="case-number">{item.case_number}</span>
                  <span className="case-meta">{item.decision_date} · {item.dispute_type}</span>
                </button>
              ))}
            </div>
            <div className="pagination">
              <button type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>上一頁</button>
              <span>{page} / {totalPages}</span>
              <button type="button" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>下一頁</button>
            </div>
          </AsyncBlock>
        </section>

        <section className="panel detail-panel">
          <PanelHeader title="案件詳情" />
          {!selectedCaseId && <EmptyState text="請從左側選擇案件。" />}
          {selectedCaseId && (
            <AsyncBlock loading={detail.loading} error={detail.error}>
              {detail.data && (
                <CaseDetailView
                  caseDetail={detail.data}
                  summary={summary.data}
                  summaryError={summary.error}
                  summaryLoading={summary.loading}
                  similar={similar.data}
                  similarError={similar.error}
                  similarLoading={similar.loading}
                  semanticSimilar={semanticSimilar.data}
                  semanticSimilarError={semanticSimilar.error}
                  semanticSimilarLoading={semanticSimilar.loading}
                  onOpenCase={onSelectCase}
                />
              )}
            </AsyncBlock>
          )}
        </section>
      </div>
    </section>
  );
}
