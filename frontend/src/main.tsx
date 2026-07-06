import React from "react";
import { createRoot } from "react-dom/client";
import { Activity, BarChart3, FileSearch, LayoutDashboard, ListFilter } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Line, LineChart } from "recharts";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

type HealthResponse = {
  status: string;
  database_ready: boolean;
};

type OverviewStatistics = {
  case_count: number;
  dispute_type_count: number;
  roc_years: number[];
  first_decision_date: string | null;
  last_decision_date: string | null;
};

type CountItem = {
  name: string;
  count: number;
};

type DateCountItem = {
  decision_date: string;
  count: number;
};

type CaseSummary = {
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

type PaginatedCases = {
  items: CaseSummary[];
  total: number;
  page: number;
  page_size: number;
};

type CaseDetail = CaseSummary & {
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

type CaseSummaryDetail = {
  case_id: string;
  holding: string | null;
  applicant_claim: string | null;
  reasoning: string | null;
  summary_method: string | null;
  created_at: string | null;
};

type SimilarCase = {
  case_id: string;
  case_number: string;
  decision_date: string | null;
  dispute_type: string | null;
  decision_result: string | null;
  score: number;
  matched_reasons: string[];
};

type SimilarCasesResponse = {
  case_id: string;
  items: SimilarCase[];
  total_candidates: number;
};

type SearchResult = {
  case_id: string;
  case_number: string;
  decision_date: string | null;
  dispute_type: string | null;
  snippet: string | null;
  match_source: string;
};

type SearchResponse = {
  items: SearchResult[];
  total: number;
  query: string;
  page: number;
  page_size: number;
};

type Route = "dashboard" | "cases" | "search" | "statistics";

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

async function apiGetOptional<T>(path: string): Promise<T | null> {
  const response = await fetch(`${API_BASE}${path}`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

function useAsyncData<T>(loader: () => Promise<T>, deps: React.DependencyList): {
  data: T | null;
  error: string | null;
  loading: boolean;
} {
  const [data, setData] = React.useState<T | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    loader()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((err: unknown) => {
        if (active) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, deps);

  return { data, error, loading };
}

function App() {
  const [route, setRoute] = React.useState<Route>("dashboard");
  const [selectedCaseId, setSelectedCaseId] = React.useState<string | null>(null);
  const health = useAsyncData(() => apiGet<HealthResponse>("/health"), []);

  const navItems: Array<{ route: Route; label: string; icon: React.ReactNode }> = [
    { route: "dashboard", label: "總覽", icon: <LayoutDashboard size={18} /> },
    { route: "cases", label: "案件", icon: <ListFilter size={18} /> },
    { route: "search", label: "搜尋", icon: <FileSearch size={18} /> },
    { route: "statistics", label: "統計", icon: <BarChart3 size={18} /> }
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Activity size={24} />
          <div>
            <h1>保險評議分析系統</h1>
            <p>FOI ODS 人壽保險案件</p>
          </div>
        </div>
        <nav className="nav-list" aria-label="主要導覽">
          {navItems.map((item) => (
            <button
              key={item.route}
              className={route === item.route ? "nav-button active" : "nav-button"}
              type="button"
              onClick={() => setRoute(item.route)}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-status">
          <span className={health.data?.database_ready ? "status-dot ok" : "status-dot"} />
          <span>{health.loading ? "API 檢查中" : health.data?.database_ready ? "資料庫已連線" : "資料庫未就緒"}</span>
        </div>
      </aside>

      <main className="main-content">
        {route === "dashboard" && <Dashboard onOpenCases={() => setRoute("cases")} />}
        {route === "cases" && (
          <CasesPage
            selectedCaseId={selectedCaseId}
            onSelectCase={(caseId) => setSelectedCaseId(caseId)}
          />
        )}
        {route === "search" && (
          <SearchPage
            onOpenCase={(caseId) => {
              setSelectedCaseId(caseId);
              setRoute("cases");
            }}
          />
        )}
        {route === "statistics" && <StatisticsPage />}
      </main>
    </div>
  );
}

function Dashboard({ onOpenCases }: { onOpenCases: () => void }) {
  const overview = useAsyncData(() => apiGet<OverviewStatistics>("/statistics/overview"), []);
  const disputeTypes = useAsyncData(() => apiGet<CountItem[]>("/statistics/dispute-types"), []);
  const dates = useAsyncData(() => apiGet<DateCountItem[]>("/statistics/decision-dates"), []);

  const topDisputes = disputeTypes.data?.slice(0, 8) ?? [];

  return (
    <section className="page">
      <PageHeader
        title="資料總覽"
        description="目前已匯入 ROC 115 人壽保險評議案件，提供查詢、搜尋與統計。"
        action={<button className="primary-button" onClick={onOpenCases}>查看案件</button>}
      />
      <AsyncBlock loading={overview.loading} error={overview.error}>
        {overview.data && (
          <div className="metric-grid">
            <Metric label="案件數" value={overview.data.case_count.toLocaleString()} />
            <Metric label="爭議類型" value={overview.data.dispute_type_count.toLocaleString()} />
            <Metric label="年度" value={overview.data.roc_years.join(", ")} />
            <Metric label="決定日期" value={`${overview.data.first_decision_date} - ${overview.data.last_decision_date}`} />
          </div>
        )}
      </AsyncBlock>

      <div className="content-grid two-columns">
        <section className="panel">
          <PanelHeader title="前十大爭議類型" />
          <AsyncBlock loading={disputeTypes.loading} error={disputeTypes.error}>
            <div className="chart-box">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={topDisputes} layout="vertical" margin={{ left: 18, right: 18 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} />
                  <YAxis dataKey="name" type="category" width={110} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#2f6f73" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </AsyncBlock>
        </section>

        <section className="panel">
          <PanelHeader title="決定日期分布" />
          <AsyncBlock loading={dates.loading} error={dates.error}>
            <div className="chart-box">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={dates.data ?? []} margin={{ left: 12, right: 18 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="decision_date" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} />
                  <Tooltip />
                  <Line type="monotone" dataKey="count" stroke="#7a4f25" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </AsyncBlock>
        </section>
      </div>
    </section>
  );
}

function CasesPage({
  selectedCaseId,
  onSelectCase
}: {
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}) {
  const [page, setPage] = React.useState(1);
  const [caseNumber, setCaseNumber] = React.useState("");
  const [disputeType, setDisputeType] = React.useState("");
  const [rocYear, setRocYear] = React.useState("115");

  const query = new URLSearchParams({
    page: String(page),
    page_size: "12"
  });
  if (rocYear) query.set("roc_year", rocYear);
  if (disputeType) query.set("dispute_type", disputeType);
  if (caseNumber) query.set("case_number", caseNumber);

  const cases = useAsyncData(() => apiGet<PaginatedCases>(`/cases?${query.toString()}`), [
    page,
    caseNumber,
    disputeType,
    rocYear
  ]);
  const disputeTypes = useAsyncData(() => apiGet<CountItem[]>("/dispute-types"), []);
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

  const totalPages = Math.max(1, Math.ceil((cases.data?.total ?? 0) / (cases.data?.page_size ?? 12)));

  return (
    <section className="page">
      <PageHeader title="案件管理" description="依年度、爭議類型、案號查詢評議案件，並查看全文與 PDF。" />
      <div className="filters">
        <label>
          年度
          <input value={rocYear} onChange={(event) => { setPage(1); setRocYear(event.target.value); }} />
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

function SearchPage({ onOpenCase }: { onOpenCase: (caseId: string) => void }) {
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

function StatisticsPage() {
  const disputeTypes = useAsyncData(() => apiGet<CountItem[]>("/statistics/dispute-types"), []);
  const dates = useAsyncData(() => apiGet<DateCountItem[]>("/statistics/decision-dates"), []);
  const total = disputeTypes.data?.reduce((sum, item) => sum + item.count, 0) ?? 0;

  return (
    <section className="page">
      <PageHeader title="統計分析" description="檢視案件在爭議類型與決定日期上的分布。" />
      <div className="content-grid two-columns">
        <section className="panel">
          <PanelHeader title={`爭議類型分布 (${total})`} />
          <AsyncBlock loading={disputeTypes.loading} error={disputeTypes.error}>
            <div className="table-list">
              {(disputeTypes.data ?? []).map((item) => (
                <div className="table-row" key={item.name}>
                  <span>{item.name}</span>
                  <strong>{item.count}</strong>
                </div>
              ))}
            </div>
          </AsyncBlock>
        </section>
        <section className="panel">
          <PanelHeader title="決定日期分布" />
          <AsyncBlock loading={dates.loading} error={dates.error}>
            <div className="table-list">
              {(dates.data ?? []).map((item) => (
                <div className="table-row" key={item.decision_date}>
                  <span>{item.decision_date}</span>
                  <strong>{item.count}</strong>
                </div>
              ))}
            </div>
          </AsyncBlock>
        </section>
      </div>
    </section>
  );
}

function CaseDetailView({
  caseDetail,
  summary,
  summaryError,
  summaryLoading,
  similar,
  similarError,
  similarLoading,
  onOpenCase
}: {
  caseDetail: CaseDetail;
  summary: CaseSummaryDetail | null;
  summaryError: string | null;
  summaryLoading: boolean;
  similar: SimilarCasesResponse | null;
  similarError: string | null;
  similarLoading: boolean;
  onOpenCase: (caseId: string) => void;
}) {
  return (
    <div className="case-detail">
      <div className="detail-title">
        <h2>{caseDetail.case_number}</h2>
        <a className="secondary-button" href={`${API_BASE}/files/${caseDetail.case_id}/pdf`} target="_blank" rel="noreferrer">
          開啟 PDF
        </a>
      </div>
      <dl className="detail-grid">
        <div><dt>決定日期</dt><dd>{caseDetail.decision_date}</dd></div>
        <div><dt>爭議類型</dt><dd>{caseDetail.dispute_type}</dd></div>
        <div><dt>評議結果</dt><dd>{caseDetail.decision_result}</dd></div>
        <div><dt>頁數</dt><dd>{caseDetail.page_count}</dd></div>
      </dl>
      <section className="summary-section">
        <div className="summary-header">
          <h3>案件摘要</h3>
          {summary?.summary_method && <span>{summary.summary_method}</span>}
        </div>
        {summaryLoading && <div className="state-box compact">摘要載入中</div>}
        {!summaryLoading && summaryError && <div className="state-box error compact">摘要讀取失敗：{summaryError}</div>}
        {!summaryLoading && !summaryError && !summary && <div className="state-box compact">尚未產生摘要。</div>}
        {!summaryLoading && !summaryError && summary && (
          <div className="summary-grid">
            <SummaryBlock title="主文" text={summary.holding} />
            <SummaryBlock title="申請人主張" text={summary.applicant_claim} />
            <SummaryBlock title="判斷理由" text={summary.reasoning} />
          </div>
        )}
      </section>
      <section className="similar-section">
        <div className="summary-header">
          <h3>相似案件</h3>
          {similar && <span>{similar.total_candidates} 個候選</span>}
        </div>
        {similarLoading && <div className="state-box compact">相似案件載入中</div>}
        {!similarLoading && similarError && <div className="state-box error compact">相似案件讀取失敗：{similarError}</div>}
        {!similarLoading && !similarError && similar && similar.items.length === 0 && (
          <div className="state-box compact">目前沒有找到相似案件。</div>
        )}
        {!similarLoading && !similarError && similar && similar.items.length > 0 && (
          <div className="similar-list">
            {similar.items.map((item) => (
              <button key={item.case_id} className="similar-row" type="button" onClick={() => onOpenCase(item.case_id)}>
                <span className="case-number">{item.case_number}</span>
                <span className="case-meta">{item.decision_date} · {item.dispute_type} · 分數 {item.score}</span>
                <span className="reason-list">{item.matched_reasons.join(" / ")}</span>
              </button>
            ))}
          </div>
        )}
      </section>
      <div className="text-viewer">
        <pre>{caseDetail.normalized_text}</pre>
      </div>
    </div>
  );
}

function SummaryBlock({ title, text }: { title: string; text: string | null }) {
  return (
    <article className="summary-block">
      <h4>{title}</h4>
      <p>{text || "未擷取到對應段落。"}</p>
    </article>
  );
}

function PageHeader({
  title,
  description,
  action
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}

function PanelHeader({ title }: { title: string }) {
  return (
    <div className="panel-header">
      <h3>{title}</h3>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AsyncBlock({ loading, error, children }: { loading: boolean; error: string | null; children: React.ReactNode }) {
  if (loading) return <div className="state-box">載入中</div>;
  if (error) return <div className="state-box error">錯誤：{error}</div>;
  return <>{children}</>;
}

function EmptyState({ text }: { text: string }) {
  return <div className="state-box">{text}</div>;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
