import React from "react";
import { BriefcaseBusiness, Calculator, Files, FileSearch, LayoutDashboard } from "lucide-react";

import { apiGet } from "./api/client";
import { CaseWorkspaceModal } from "./components/CaseWorkspaceModal";
import { useAsyncData } from "./hooks/useAsyncData";
import { useOpenCases } from "./hooks/useOpenCases";
import { CasesPage } from "./pages/CasesPage";
import { CalculationMethodPage } from "./pages/CalculationMethodPage";
import { QualityPage } from "./pages/QualityPage";
import { SearchPage } from "./pages/SearchPage";
import { SemanticSearchPage } from "./pages/SemanticSearchPage";
import type { HealthResponse, Route } from "./types";

// methodology 是面向使用者的公開說明頁；semantic 與 quality 保留為內部驗證路由。
const ROUTES: Route[] = ["dashboard", "cases", "search", "methodology", "semantic", "quality"];

function parseRoute(value: string | null): Route | null {
  return ROUTES.includes(value as Route) ? (value as Route) : null;
}

function readUrlState(): { route: Route; caseId: string | null } {
  const params = new URLSearchParams(window.location.search);
  const parsedRoute = parseRoute(params.get("view"));
  return {
    route: parsedRoute === "cases" ? "dashboard" : parsedRoute ?? "dashboard",
    caseId: params.get("case_id"),
  };
}

function writeUrlState(route: Route) {
  const params = new URLSearchParams();
  if (route !== "dashboard") params.set("view", route);

  const query = params.toString();
  const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
  const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (nextUrl !== currentUrl) window.history.pushState({}, "", nextUrl);
}

export function App() {
  const initialUrlState = React.useMemo(readUrlState, []);
  const [route, setRoute] = React.useState<Route>(initialUrlState.route);
  const health = useAsyncData(() => apiGet<HealthResponse>("/health"), []);
  const caseWorkspace = useOpenCases();

  React.useEffect(() => {
    if (initialUrlState.caseId) caseWorkspace.openCase(initialUrlState.caseId);
  }, [caseWorkspace.openCase, initialUrlState.caseId]);

  React.useEffect(() => {
    const handlePopState = () => {
      const nextState = readUrlState();
      setRoute(nextState.route);
      if (nextState.caseId) caseWorkspace.openCase(nextState.caseId);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [caseWorkspace.openCase]);

  const navigate = React.useCallback((nextRoute: Route) => {
    setRoute(nextRoute);
    writeUrlState(nextRoute);
  }, []);

  const navItems: Array<{ route: Route; label: string; icon: React.ReactNode }> = [
    { route: "dashboard", label: "案件工作台", icon: <LayoutDashboard size={18} /> },
    { route: "search", label: "全文搜尋", icon: <FileSearch size={18} /> },
    { route: "methodology", label: "計算方法", icon: <Calculator size={18} /> },
  ];

  return (
    <>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <BriefcaseBusiness size={24} />
            <div>
              <h1>理賠案件查詢</h1>
              <p>金融消費評議案例</p>
            </div>
          </div>
          <nav className="nav-list" aria-label="主要導覽">
            {navItems.map((item) => (
              <button
                key={item.route}
                className={route === item.route ? "nav-button active" : "nav-button"}
                type="button"
                onClick={() => navigate(item.route)}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
          {caseWorkspace.tabs.length > 0 && (
            <button className="open-cases-dock" type="button" onClick={caseWorkspace.restore}>
              <Files size={17} />
              <span>已開啟案件</span>
              <strong>{caseWorkspace.tabs.length}</strong>
            </button>
          )}
          <div className="sidebar-status">
            <span className={health.data?.database_ready ? "status-dot ok" : "status-dot"} />
            <span>{health.loading ? "API 檢查中" : health.data?.database_ready ? "資料庫已連線" : "資料庫未就緒"}</span>
          </div>
        </aside>

        <main className="main-content">
          {(route === "dashboard" || route === "cases") && (
            <CasesPage
              onOpenCase={caseWorkspace.openCase}
              onOpenSearch={() => navigate("search")}
            />
          )}
          {route === "search" && <SearchPage onOpenCase={caseWorkspace.openCase} />}
          {route === "methodology" && <CalculationMethodPage />}
          {route === "semantic" && <SemanticSearchPage onOpenCase={caseWorkspace.openCase} />}
          {route === "quality" && <QualityPage />}
        </main>
      </div>

      {caseWorkspace.activeCaseId && (
        <CaseWorkspaceModal
          tabs={caseWorkspace.tabs}
          activeCaseId={caseWorkspace.activeCaseId}
          onSelect={caseWorkspace.selectCase}
          onClose={caseWorkspace.closeCase}
          onMinimize={caseWorkspace.minimize}
          onRename={caseWorkspace.renameCase}
          onOpenCase={caseWorkspace.openCase}
        />
      )}
    </>
  );
}
