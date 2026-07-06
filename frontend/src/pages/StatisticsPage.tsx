import { apiGet } from "../api/client";
import { AsyncBlock, PageHeader, PanelHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { CountItem, DateCountItem } from "../types";

export function StatisticsPage() {
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
