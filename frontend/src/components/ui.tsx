import type React from "react";

export function PageHeader({
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

export function PanelHeader({ title }: { title: string }) {
  return (
    <div className="panel-header">
      <h3>{title}</h3>
    </div>
  );
}

export function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function AsyncBlock({ loading, error, children }: { loading: boolean; error: string | null; children: React.ReactNode }) {
  if (loading) return <div className="state-box">載入中</div>;
  if (error) return <div className="state-box error">錯誤：{error}</div>;
  return <>{children}</>;
}

export function EmptyState({ text }: { text: string }) {
  return <div className="state-box">{text}</div>;
}
