import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { apiGet } from "../api/client";
import { AsyncBlock, Metric, PageHeader, PanelHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { CountItem, DateCountItem, OverviewStatistics } from "../types";

export function Dashboard({ onOpenCases }: { onOpenCases: () => void }) {
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
