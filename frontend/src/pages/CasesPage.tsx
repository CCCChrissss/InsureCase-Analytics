import React from "react";
import { ChevronLeft, ChevronRight, FileSearch, Search, X } from "lucide-react";

import { apiGet, apiPath } from "../api/client";
import { AsyncBlock, EmptyState, PageHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type {
  CountItem,
  OverviewStatistics,
  PaginatedCases,
} from "../types";

const PAGE_SIZE_OPTIONS = [10, 15, 20] as const;

export function CasesPage({
  onOpenCase,
  onOpenSearch,
}: {
  onOpenCase: (caseId: string, label?: string) => void;
  onOpenSearch: () => void;
}) {
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(15);
  const [caseNumberInput, setCaseNumberInput] = React.useState("");
  const [caseNumber, setCaseNumber] = React.useState("");
  const [disputeType, setDisputeType] = React.useState("");
  const [rocYear, setRocYear] = React.useState("");

  const cases = useAsyncData(() => apiGet<PaginatedCases>(apiPath("/cases", {
    page,
    page_size: pageSize,
    roc_year: rocYear,
    dispute_type: disputeType,
    case_number: caseNumber,
  })), [page, pageSize, caseNumber, disputeType, rocYear]);
  const overview = useAsyncData(() => apiGet<OverviewStatistics>("/statistics/overview"), []);
  const disputeTypes = useAsyncData(
    () => apiGet<CountItem[]>(apiPath("/dispute-types", { roc_year: rocYear })),
    [rocYear]
  );
  const totalPages = Math.max(1, Math.ceil((cases.data?.total ?? 0) / (cases.data?.page_size ?? pageSize)));
  const years = overview.data?.roc_years ?? [];
  const hasFilters = Boolean(caseNumber || disputeType || rocYear);

  const clearFilters = () => {
    setPage(1);
    setCaseNumberInput("");
    setCaseNumber("");
    setDisputeType("");
    setRocYear("");
  };

  return (
    <section className="page claims-page">
      <PageHeader
        title="案件工作台"
        description="依案件線索快速查找評議決定，集中閱讀結論、爭點、判斷理由與引用依據。"
        action={
          <button className="secondary-button" type="button" onClick={onOpenSearch}>
            <FileSearch size={17} />
            搜尋案件全文
          </button>
        }
      />

      <form
        className="case-filter-bar"
        onSubmit={(event) => {
          event.preventDefault();
          setPage(1);
          setCaseNumber(caseNumberInput.trim());
        }}
      >
        <label className="case-number-filter">
          <span>案號</span>
          <div className="input-with-icon">
            <Search size={17} />
            <input
              value={caseNumberInput}
              onChange={(event) => setCaseNumberInput(event.target.value)}
              placeholder="輸入完整或部分案號"
            />
          </div>
        </label>
        <label>
          <span>年度</span>
          <select value={rocYear} onChange={(event) => { setPage(1); setRocYear(event.target.value); }}>
            <option value="">全部年度</option>
            {years.map((year) => (
              <option key={year} value={year}>民國 {year} 年</option>
            ))}
          </select>
        </label>
        <label>
          <span>爭議類型</span>
          <select value={disputeType} onChange={(event) => { setPage(1); setDisputeType(event.target.value); }}>
            <option value="">全部類型</option>
            {(disputeTypes.data ?? []).map((item) => (
              <option key={item.name} value={item.name}>{item.name} ({item.count})</option>
            ))}
          </select>
        </label>
        <button className="primary-button" type="submit">
          <Search size={17} />
          查詢
        </button>
        {hasFilters && (
          <button className="icon-button" type="button" onClick={clearFilters} aria-label="清除篩選" title="清除篩選">
            <X size={18} />
          </button>
        )}
      </form>

      <div className="claims-workspace case-dashboard-list">
        <section className="case-index" aria-label="案件列表">
          <div className="workspace-section-header">
            <div>
              <h3>案件清單</h3>
              <span>{cases.data ? `共 ${cases.data.total.toLocaleString("zh-TW")} 件` : "讀取中"}</span>
            </div>
            <label className="result-size-control">
              <span>每頁顯示</span>
              <select
                value={pageSize}
                onChange={(event) => {
                  setPage(1);
                  setPageSize(Number(event.target.value));
                }}
              >
                {PAGE_SIZE_OPTIONS.map((value) => (
                  <option key={value} value={value}>{value} 筆</option>
                ))}
              </select>
            </label>
          </div>
          <AsyncBlock loading={cases.loading} error={cases.error}>
            <div className="case-list">
              {(cases.data?.items ?? []).map((item) => (
                <button
                  key={item.case_id}
                  type="button"
                  className="case-row"
                  onClick={() => onOpenCase(item.case_id, item.case_number)}
                >
                  <span className="case-row-heading">
                    <span className="case-number">{item.case_number}</span>
                    <span className="case-date">{item.decision_date ?? "日期未標示"}</span>
                  </span>
                  <span className="case-dispute">{item.dispute_type ?? "爭議類型未標示"}</span>
                  {isMeaningfulOutcome(item.decision_result) && (
                    <span className="case-outcome">{item.decision_result}</span>
                  )}
                </button>
              ))}
              {cases.data?.items.length === 0 && <EmptyState text="目前沒有符合條件的案件。" />}
            </div>
            <div className="pagination compact-pagination">
              <button
                className="icon-button"
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((value) => value - 1)}
                aria-label="上一頁"
                title="上一頁"
              >
                <ChevronLeft size={18} />
              </button>
              <span>第 {page} 頁，共 {totalPages} 頁</span>
              <button
                className="icon-button"
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage((value) => value + 1)}
                aria-label="下一頁"
                title="下一頁"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </AsyncBlock>
        </section>

      </div>
    </section>
  );
}

function isMeaningfulOutcome(value: string | null) {
  return Boolean(value?.trim() && value.trim() !== "全部");
}
