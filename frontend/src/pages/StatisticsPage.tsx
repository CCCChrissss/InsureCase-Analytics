import React from "react";

import { apiGet, apiPath } from "../api/client";
import { AsyncBlock, PageHeader, PanelHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { CountItem, DateCountItem, OverviewStatistics } from "../types";

export function StatisticsPage() {
  const [rocYear, setRocYear] = React.useState("");
  const overview = useAsyncData(() => apiGet<OverviewStatistics>("/statistics/overview"), []);
  const disputeTypes = useAsyncData(() => apiGet<CountItem[]>(apiPath("/statistics/dispute-types", { roc_year: rocYear })), [rocYear]);
  const dates = useAsyncData(() => apiGet<DateCountItem[]>(apiPath("/statistics/decision-dates", { roc_year: rocYear })), [rocYear]);
  const total = disputeTypes.data?.reduce((sum, item) => sum + item.count, 0) ?? 0;
  const years = overview.data?.roc_years ?? [];

  return (
    <section className="page">
      <PageHeader
        title="統計分析"
        description="檢視案件在爭議類型與決定日期上的分布。"
        action={
          <label className="compact-field">
            年度
            <select value={rocYear} onChange={(event) => setRocYear(event.target.value)}>
              <option value="">全部年度</option>
              {years.map((year) => (
                <option key={year} value={year}>ROC {year}</option>
              ))}
            </select>
          </label>
        }
      />
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
