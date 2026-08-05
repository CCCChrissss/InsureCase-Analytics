import React from "react";
import { FileText, Search } from "lucide-react";

import { apiGet, apiPath } from "../api/client";
import { AsyncBlock, PageHeader } from "../components/ui";
import {
  LOCAL_BGE_MODEL,
  LOCAL_BGE_PROVIDER,
  SEMANTIC_SEARCH_CANDIDATE_LIMIT,
} from "../config/semantic";
import { useAsyncData } from "../hooks/useAsyncData";
import type {
  SearchResponse,
  SearchResult,
  SemanticSearchResponse,
  SemanticSearchResult,
} from "../types";

const PAGE_SIZE_OPTIONS = [10, 15, 20] as const;

type HybridSource = "keyword" | "semantic" | "both";

type HybridSearchItem = SearchResult & {
  hybridSource: HybridSource;
  semanticScore: number | null;
};

type HybridSearchData = {
  keyword: SearchResponse;
  semantic: SemanticSearchResponse | null;
  semanticError: string | null;
};

export function SearchPage({ onOpenCase }: { onOpenCase: (caseId: string, label?: string) => void }) {
  const [query, setQuery] = React.useState("");
  const [submittedQuery, setSubmittedQuery] = React.useState("");
  const [pageSize, setPageSize] = React.useState(15);
  const results = useAsyncData(
    () => submittedQuery
      ? loadHybridSearch(submittedQuery)
      : Promise.resolve<HybridSearchData | null>(null),
    [submittedQuery]
  );
  const hybridItems = React.useMemo(
    () => results.data ? mergeHybridResults(results.data.keyword.items, results.data.semantic?.items ?? [], pageSize) : [],
    [pageSize, results.data]
  );
  const semanticCaseCount = React.useMemo(
    () => new Set((results.data?.semantic?.items ?? []).map((item) => item.case_id)).size,
    [results.data?.semantic?.items]
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
                  ? `關鍵字 ${results.data.keyword.total.toLocaleString("zh-TW")} 件，語意候選 ${semanticCaseCount.toLocaleString("zh-TW")} 件`
                  : "查詢中"}
              </span>
            </div>
            <label className="result-size-control">
              <span>顯示筆數</span>
              <select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}>
                {PAGE_SIZE_OPTIONS.map((value) => (
                  <option key={value} value={value}>{value} 筆</option>
                ))}
              </select>
            </label>
          </div>
          {results.data?.semanticError && (
            <div className="semantic-unavailable-note" title={results.data.semanticError}>
              語意補充目前無法使用，以下仍保留關鍵字搜尋結果。
            </div>
          )}
          <AsyncBlock loading={results.loading} error={results.error}>
            <div className="claims-search-results">
              {hybridItems.map((item) => (
                <button
                  key={item.case_id}
                  className="claims-search-row"
                  type="button"
                  onClick={() => onOpenCase(item.case_id, item.case_number)}
                >
                  <span className="search-row-heading">
                    <strong>{item.case_number}</strong>
                    <span className={`search-source-label ${item.hybridSource}`}>
                      {hybridSourceLabel(item.hybridSource)}
                    </span>
                  </span>
                  <span className="search-row-meta">
                    <span className="search-row-dispute">{item.dispute_type || "爭議類型未標示"}</span>
                    <span>{item.decision_date || "日期未標示"}</span>
                  </span>
                  <p>{item.snippet || "此案件沒有可顯示的命中片段。"}</p>
                </button>
              ))}
              {hybridItems.length === 0 && (
                <div className="state-box">目前沒有符合「{submittedQuery}」的案件，請嘗試較短的關鍵字。</div>
              )}
            </div>
          </AsyncBlock>
        </section>
      )}
    </section>
  );
}

async function loadHybridSearch(query: string): Promise<HybridSearchData> {
  const [keywordResult, semanticResult] = await Promise.allSettled([
    apiGet<SearchResponse>(apiPath("/search", { q: query, page_size: 20 })),
    apiGet<SemanticSearchResponse>(apiPath("/semantic-search", {
      q: query,
      limit: SEMANTIC_SEARCH_CANDIDATE_LIMIT,
      embedding_provider: LOCAL_BGE_PROVIDER,
      embedding_model: LOCAL_BGE_MODEL,
    })),
  ]);

  if (keywordResult.status === "rejected") throw keywordResult.reason;

  return {
    keyword: keywordResult.value,
    semantic: semanticResult.status === "fulfilled" ? semanticResult.value : null,
    semanticError: semanticResult.status === "rejected" ? errorMessage(semanticResult.reason) : null,
  };
}

function mergeHybridResults(
  keywordItems: SearchResult[],
  semanticItems: SemanticSearchResult[],
  limit: number
): HybridSearchItem[] {
  const bestSemanticByCase = new Map<string, SemanticSearchResult>();
  semanticItems.forEach((item) => {
    if (!bestSemanticByCase.has(item.case_id)) bestSemanticByCase.set(item.case_id, item);
  });

  const keywordCases = new Set(keywordItems.map((item) => item.case_id));
  const keywordQueue = keywordItems.map((item) => {
    const semantic = bestSemanticByCase.get(item.case_id);
    return {
      ...item,
      hybridSource: semantic ? "both" as const : "keyword" as const,
      semanticScore: semantic?.score ?? null,
    };
  });
  const semanticQueue = Array.from(bestSemanticByCase.values())
    .filter((item) => !keywordCases.has(item.case_id))
    .map((item) => ({
      case_id: item.case_id,
      case_number: item.case_number,
      decision_date: item.decision_date,
      dispute_type: item.dispute_type,
      snippet: item.chunk_text,
      match_source: "semantic_bge",
      hybridSource: "semantic" as const,
      semanticScore: item.score,
    }));

  const merged: HybridSearchItem[] = [];
  let keywordIndex = 0;
  let semanticIndex = 0;
  while (merged.length < limit && (keywordIndex < keywordQueue.length || semanticIndex < semanticQueue.length)) {
    if (keywordIndex < keywordQueue.length && merged.length < limit) {
      merged.push(keywordQueue[keywordIndex]);
      keywordIndex += 1;
    }
    if (semanticIndex < semanticQueue.length && merged.length < limit) {
      merged.push(semanticQueue[semanticIndex]);
      semanticIndex += 1;
    }
  }
  return merged;
}

function hybridSourceLabel(source: HybridSource) {
  if (source === "both") return "關鍵字與語意";
  if (source === "semantic") return "語意相關";
  return "關鍵字命中";
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
