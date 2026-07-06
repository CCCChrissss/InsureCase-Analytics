import React from "react";

import { apiGet } from "../api/client";
import { AsyncBlock, PageHeader, PanelHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { SearchResponse } from "../types";

export function SearchPage({ onOpenCase }: { onOpenCase: (caseId: string) => void }) {
  const [query, setQuery] = React.useState("癌症");
  const [submittedQuery, setSubmittedQuery] = React.useState("癌症");
  const results = useAsyncData(
    () => apiGet<SearchResponse>(`/search?q=${encodeURIComponent(submittedQuery)}&page_size=20`),
    [submittedQuery]
  );

  return (
    <section className="page">
      <PageHeader title="全文搜尋" description="搜尋 normalized text，回傳命中案件與文字片段。" />
      <form
        className="search-form"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmittedQuery(query.trim() || "癌症");
        }}
      >
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="輸入關鍵字，例如 癌症、除外責任、手術" />
        <button className="primary-button" type="submit">搜尋</button>
      </form>
      <section className="panel">
        <PanelHeader title={`搜尋結果 ${results.data ? `(${results.data.total})` : ""}`} />
        <AsyncBlock loading={results.loading} error={results.error}>
          <div className="search-results">
            {(results.data?.items ?? []).map((item) => (
              <button key={item.case_id} className="result-row" type="button" onClick={() => onOpenCase(item.case_id)}>
                <span className="case-number">{item.case_number}</span>
                <span className="case-meta">{item.decision_date} · {item.dispute_type} · {item.match_source}</span>
                <span className="snippet">{item.snippet}</span>
              </button>
            ))}
          </div>
        </AsyncBlock>
      </section>
    </section>
  );
}
