import React from "react";
import { FileText, Search } from "lucide-react";

import { apiGet, apiPath } from "../api/client";
import { AsyncBlock, PageHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { SearchResponse } from "../types";

export function SearchPage({ onOpenCase }: { onOpenCase: (caseId: string, label?: string) => void }) {
  const [query, setQuery] = React.useState("");
  const [submittedQuery, setSubmittedQuery] = React.useState("");
  const results = useAsyncData(
    () => submittedQuery
      ? apiGet<SearchResponse>(apiPath("/search", { q: submittedQuery, page_size: 30 }))
      : Promise.resolve<SearchResponse | null>(null),
    [submittedQuery]
  );

  return (
    <section className="page claims-search-page">
      <PageHeader
        title="案件全文搜尋"
        description="輸入疾病、醫療處置、保單條款或理賠爭點，查找決定書中的相關案件。"
      />
      <form
        className="claims-search-form"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmittedQuery(query.trim());
        }}
      >
        <div className="input-with-icon">
          <Search size={19} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如：癌症、除外責任、剖腹產、失能保險金"
            aria-label="搜尋案件全文"
          />
        </div>
        <button className="primary-button" type="submit" disabled={!query.trim()}>
          <Search size={17} />
          搜尋
        </button>
      </form>

      {!submittedQuery && (
        <div className="search-start-state">
          <FileText size={30} />
          <h3>從案件原文查找理賠參考</h3>
          <p>搜尋結果會顯示命中的案號、爭議類型與原文片段。</p>
        </div>
      )}

      {submittedQuery && (
        <section className="search-result-section">
          <div className="workspace-section-header">
            <div>
              <h3>搜尋結果</h3>
              <span>
                {results.data
                  ? `「${results.data.query}」共找到 ${results.data.total.toLocaleString("zh-TW")} 件`
                  : "查詢中"}
              </span>
            </div>
          </div>
          <AsyncBlock loading={results.loading} error={results.error}>
            <div className="claims-search-results">
              {(results.data?.items ?? []).map((item) => (
                <button
                  key={item.case_id}
                  className="claims-search-row"
                  type="button"
                  onClick={() => onOpenCase(item.case_id, item.case_number)}
                >
                  <span className="search-row-heading">
                    <strong>{item.case_number}</strong>
                    <span>{item.decision_date || "日期未標示"}</span>
                  </span>
                  <span className="search-row-dispute">{item.dispute_type || "爭議類型未標示"}</span>
                  <p>{item.snippet || "此案件沒有可顯示的命中片段。"}</p>
                </button>
              ))}
              {results.data?.items.length === 0 && (
                <div className="state-box">目前沒有符合「{submittedQuery}」的案件，請嘗試較短的關鍵字。</div>
              )}
            </div>
          </AsyncBlock>
        </section>
      )}
    </section>
  );
}
