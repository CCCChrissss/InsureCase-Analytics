import { API_BASE } from "../api/client";
import type { CaseDetail, CaseSummaryDetail, SimilarCasesResponse } from "../types";

export function CaseDetailView({
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
