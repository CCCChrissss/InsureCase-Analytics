import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { apiGet } from "../api/client";
import { AsyncBlock, Metric, PageHeader, PanelHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { QualityReport } from "../types";

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-TW").format(value);
}

function percent(value: number) {
  return `${value.toFixed(2)}%`;
}

export function QualityPage() {
  const report = useAsyncData(() => apiGet<QualityReport>("/quality/roc114-summary-similarity"), []);
  const data = report.data;

  return (
    <section className="page">
      <PageHeader
        title="分析驗證"
        description="展示摘要與相似案件分析的範圍、規則、抽樣結果、例外與限制。"
      />
      <AsyncBlock loading={report.loading} error={report.error}>
        {data && (
          <>
            <section className="panel">
              <PanelHeader title={`${data.report_title} · ${data.report_date}`} />
              <div className="quality-intro">
                <p>
                  本頁把後台品質檢查結果結構化展示，證明目前展示版的摘要與相似案件推薦有明確的分析範圍、
                  計分規則、抽樣紀錄與已知限制。
                </p>
                <dl className="quality-scope">
                  <div>
                    <dt>分析年度</dt>
                    <dd>ROC {data.scope.roc_year}</dd>
                  </div>
                  <div>
                    <dt>分析案件</dt>
                    <dd>{formatNumber(data.scope.case_count)} 筆</dd>
                  </div>
                  <div>
                    <dt>爭議類型</dt>
                    <dd>{data.scope.dispute_type_count} 種</dd>
                  </div>
                  <div>
                    <dt>正式 DB</dt>
                    <dd>{formatNumber(data.scope.formal_database_case_count)} 筆</dd>
                  </div>
                  <div>
                    <dt>方法版本</dt>
                    <dd>{data.method_version}</dd>
                  </div>
                </dl>
              </div>
            </section>

            <div className="metric-grid">
              <Metric label="摘要三欄覆蓋" value={`${formatNumber(data.summary_field_stats[0].non_empty)} / ${formatNumber(data.scope.case_count)}`} />
              <Metric label="Top 1 同類型率" value={percent(data.similar_stats.top1_same_dispute_type_rate)} />
              <Metric label="Top 5 同類型率" value={percent(data.similar_stats.top5_contains_same_dispute_type_rate)} />
              <Metric label="已知低信心例外" value={`${data.known_exceptions.length} 筆`} />
            </div>

            <div className="content-grid two-columns">
              <section className="panel">
                <PanelHeader title="摘要品質指標" />
                <div className="quality-table-wrapper">
                  <table className="quality-table">
                    <thead>
                      <tr>
                        <th>欄位</th>
                        <th>非空</th>
                        <th>最小</th>
                        <th>中位數</th>
                        <th>平均</th>
                        <th>最大</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.summary_field_stats.map((item) => (
                        <tr key={item.field}>
                          <td>{item.field}</td>
                          <td>{formatNumber(item.non_empty)}</td>
                          <td>{item.min_length}</td>
                          <td>{item.median_length}</td>
                          <td>{item.average_length}</td>
                          <td>{item.max_length}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              <section className="panel">
                <PanelHeader title="截段污染檢查" />
                <div className="quality-check-list">
                  {data.contamination_checks.map((item) => (
                    <div className="quality-check-row" key={item.name}>
                      <CheckCircle2 size={18} />
                      <span>{item.name}</span>
                      <strong>{item.issue_count}</strong>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            <section className="panel">
              <PanelHeader title="相似度計分規則" />
              <div className="scoring-grid">
                {data.scoring_rules.map((rule) => (
                  <article className="scoring-card" key={rule.name}>
                    <strong>+{rule.points}</strong>
                    <h4>{rule.name}</h4>
                    <p>{rule.description}</p>
                  </article>
                ))}
              </div>
            </section>

            <div className="content-grid two-columns">
              <section className="panel">
                <PanelHeader title="ROC 114 前十大爭議類型" />
                <div className="table-list">
                  {data.top_dispute_types.map((item) => (
                    <div className="table-row" key={item.name}>
                      <span>{item.name}</span>
                      <strong>{formatNumber(item.count)}</strong>
                    </div>
                  ))}
                </div>
              </section>

              <section className="panel">
                <PanelHeader title="相似案件整體結果" />
                <div className="quality-summary-list">
                  <div><span>評估案件數</span><strong>{formatNumber(data.similar_stats.evaluated_cases)}</strong></div>
                  <div><span>Top 1 為同爭議類型</span><strong>{formatNumber(data.similar_stats.top1_same_dispute_type)}</strong></div>
                  <div><span>Top 5 包含同爭議類型</span><strong>{formatNumber(data.similar_stats.top5_contains_same_dispute_type)}</strong></div>
                  <div><span>Top 5 平均同類型數</span><strong>{data.similar_stats.average_same_type_count_in_top5}</strong></div>
                  <div><span>Top 5 最少同類型數</span><strong>{data.similar_stats.min_same_type_count_in_top5}</strong></div>
                </div>
              </section>
            </div>

            <section className="panel">
              <PanelHeader title="抽樣案件檢查" />
              <div className="quality-table-wrapper">
                <table className="quality-table">
                  <thead>
                    <tr>
                      <th>案號</th>
                      <th>爭議類型</th>
                      <th>決定日期</th>
                      <th>主文長度</th>
                      <th>申請人主張長度</th>
                      <th>判斷理由長度</th>
                      <th>Top 5 同類型</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.sample_cases.map((item) => (
                      <tr key={item.case_number}>
                        <td>{item.case_number}</td>
                        <td>{item.dispute_type}</td>
                        <td>{item.decision_date}</td>
                        <td>{item.holding_length}</td>
                        <td>{item.applicant_claim_length}</td>
                        <td>{item.reasoning_length}</td>
                        <td>{item.top5_same_dispute_type_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="panel warning-panel">
              <PanelHeader title="已知低信心例外" />
              <div className="exception-list">
                {data.known_exceptions.map((item) => (
                  <article className="exception-card" key={item.case_number}>
                    <AlertTriangle size={20} />
                    <div>
                      <h4>{item.case_number} · {item.dispute_type}</h4>
                      <p>{item.decision_date}</p>
                      <p>{item.reason}</p>
                    </div>
                  </article>
                ))}
              </div>
            </section>

            <div className="content-grid two-columns">
              <section className="panel">
                <PanelHeader title="結論" />
                <div className="quality-conclusions">
                  {data.conclusions.map((group) => (
                    <article key={group.title}>
                      <h4>{group.title}</h4>
                      <ul>
                        {group.items.map((item) => <li key={item}>{item}</li>)}
                      </ul>
                    </article>
                  ))}
                </div>
              </section>

              <section className="panel">
                <PanelHeader title="限制與下一步" />
                <div className="quality-conclusions">
                  <article>
                    <h4>方法限制</h4>
                    <ul>
                      {data.limitations.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </article>
                  <article>
                    <h4>下一步</h4>
                    <ul>
                      {data.next_steps.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </article>
                </div>
              </section>
            </div>
          </>
        )}
      </AsyncBlock>
    </section>
  );
}
