# InsureCase Analytics

**InsureCase Analytics** 是一套保險評議案件搜尋與分析系統，目標是將金融消費評議中心 FOI ODS 的人壽保險評議決定書整理成可查詢、可統計、可閱讀，並可進一步進行規則式摘要與相似案件推薦的分析平台。

本專案目前定位為學校專題版 MVP，以本機 SQLite、FastAPI、React + Vite 建立可展示系統；後續可延伸至跨年度資料整合、embedding 相似案件、OCR fallback、Docker、CI 與 PostgreSQL / pgvector 架構。

## Features

目前已完成：

- FOI ODS 人壽保險評議決定書 metadata 與 PDF URL 爬取
- PDF 下載與文字抽取
- raw text 與 normalized text 產生
- 案件依年度、爭議類型、案號整理
- SQLite 資料庫匯入
- SQLite FTS5 全文搜尋
- 中文搜尋 LIKE fallback
- FastAPI 後端 API
- React + Vite 前端 Dashboard
- 案件列表、案件詳情、PDF 連結
- 全文搜尋頁
- 統計分析頁
- 年度篩選
- 規則式案件摘要
- 規則式相似案件推薦
- 後端 pytest 測試
- 前端基本 build 驗證
- 跨年度匯入前置支援
- ROC 114 一月小期間跨年度試跑文件

## Data Scope

目前主要資料範圍：

- 年度：ROC 115
- 產業：保險業
- 保險類別：人壽保險
- 文件類型：評議決定書
- 查詢期間：ROC 115/1/1 到 ROC 115/7/1
- metadata records：492 筆
- PDF：492 份
- raw text：492 份
- normalized text：492 份
- 單案 metadata：492 份
- 爭議類型：35 種

注意：查詢期間是 ROC 115/1/1 到 ROC 115/7/1，但目前 metadata records 內的實際 `decision_date` 範圍是 `115.01.09` 到 `115.03.20`。展示與文件中應區分「查詢期間」與「實際取得案件決定日期範圍」。

## Tech Stack

### Backend

- Python
- FastAPI
- SQLite
- SQLite FTS5
- Pydantic
- pytest

### Frontend

- React
- Vite
- TypeScript
- Recharts
- lucide-react
- pnpm

### Data Processing

- requests
- beautifulsoup4
- pdfplumber
- pypdf

## Project Structure

```text
.
├─ .gitignore
├─ .env.example
├─ PROJECT_CONTEXT.md
├─ README.md
├─ requirements.txt
├─ foi_ods_life_mvp_crawler.py
├─ foi_ods_pdf_text_pipeline.py
├─ foi_ods_case_organizer.py
├─ docs/
│  ├─ project_plan.md
│  ├─ development_roadmap.md
│  ├─ pipeline.md
│  ├─ cross_year_readiness.md
│  └─ cross_year_trial_run_roc114_january.md
├─ backend/
│  ├─ schema.sql
│  ├─ app/
│  │  ├─ config.py
│  │  ├─ main.py
│  │  ├─ database.py
│  │  ├─ schemas.py
│  │  ├─ routers/
│  │  └─ services/
│  ├─ scripts/
│  └─ tests/
└─ frontend/
   ├─ index.html
   ├─ .env.example
   ├─ package.json
   ├─ vite.config.ts
   └─ src/
      ├─ App.tsx
      ├─ main.tsx
      ├─ api/
      ├─ components/
      ├─ hooks/
      └─ pages/
```

## Data Pipeline

```text
FOI ODS
  ↓
foi_ods_life_mvp_crawler.py
  ↓
metadata + PDF URL
  ↓
foi_ods_pdf_text_pipeline.py
  ↓
PDF / raw text / normalized text
  ↓
foi_ods_case_organizer.py
  ↓
年度 / 爭議類型 / 案號整理
  ↓
backend/scripts/import_cases_to_db.py
  ↓
SQLite + FTS5
  ↓
FastAPI
  ↓
React frontend
```

## Backend API

主要 API：

```text
GET /api/health
GET /api/cases
GET /api/cases/{case_id}
GET /api/dispute-types
GET /api/files/{case_id}/pdf
GET /api/search
GET /api/cases/{case_id}/summary
GET /api/cases/{case_id}/similar
GET /api/statistics/overview
GET /api/statistics/dispute-types
GET /api/statistics/decision-dates
```

### Search

全文搜尋採用 SQLite FTS5，並加入 LIKE fallback：

```text
FTS5 有結果 → 回傳 FTS5 結果
FTS5 報錯 → LIKE fallback
FTS5 0 筆 → LIKE fallback
```

### Summaries

目前摘要方法為 `rule_based_v1`，欄位包含：

```text
holding
applicant_claim
reasoning
summary_method
created_at
```

### Similar Cases

目前相似案件推薦為規則式 baseline，依據包含：

```text
相同爭議類型
相同評議結果
相同決定類別
摘要文字中的保險關鍵詞重疊
```

此方法具可解釋性，但尚不等同於語意相似度或法律判斷。後續可升級為 embedding / pgvector。

## Setup

### 1. Install Python dependencies

在專案根目錄執行：

```powershell
py -m pip install -r requirements.txt
```

### 2. Backend environment variables

根目錄提供 `.env.example`。

後端支援：

```text
INSURANCE_CASES_DB_PATH=backend/data/insurance_cases.db
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

目前後端不會自動讀取 `.env` 檔。若要套用設定，請在 shell 或部署平台設定環境變數。

### 3. Build SQLite database

前提：`data/` 內已存在整理完成的 metadata、PDF、raw text、normalized text。

```powershell
py .\backend\scripts\import_cases_to_db.py --recreate
```

多 metadata 匯入：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json --metadata .\data\foi_ods\metadata\foi_ods_life_roc115_metadata.json --recreate
```

metadata 目錄匯入：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata-dir .\data\foi_ods\metadata --recreate
```

### 4. Extract rule-based summaries

```powershell
py .\backend\scripts\extract_case_summaries.py
```

### 5. Verify database

```powershell
py .\backend\scripts\verify_case_db.py
```

### 6. Start backend

```powershell
py -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

### 7. Start frontend

```powershell
cd frontend
pnpm install
pnpm dev
```

Open:

```text
http://127.0.0.1:5173
```

前端預設 API：

```text
http://127.0.0.1:8000/api
```

若要改 API 位址，可設定：

```text
VITE_API_BASE_URL
```

設定範例位於：

```text
frontend/.env.example
```

## Testing

### Backend syntax check

```powershell
py -m py_compile .\foi_ods_life_mvp_crawler.py
py -m py_compile .\foi_ods_pdf_text_pipeline.py
py -m py_compile .\foi_ods_case_organizer.py
py -m py_compile .\backend\scripts\import_cases_to_db.py
py -m py_compile .\backend\scripts\verify_case_db.py
py -m py_compile .\backend\scripts\extract_case_summaries.py
```

### Backend pytest

```powershell
py -m pytest
```

目前測試涵蓋：

- API smoke tests
- 統計 API 年度篩選
- 搜尋 fallback
- 摘要擷取與 summary service
- 相似案件 service
- SQLite 匯入腳本
- 跨年度 pipeline 預設路徑
- 資料品質檢查

### Frontend build

```powershell
cd frontend
pnpm build
```

若出現 Vite chunk size warning，代表 bundle 偏大，但不等於 build 失敗。

## Documentation

- `PROJECT_CONTEXT.md`：目前專案狀態總覽
- `docs/project_plan.md`：專案計畫
- `docs/development_roadmap.md`：開發路線
- `docs/pipeline.md`：資料處理 pipeline
- `docs/cross_year_readiness.md`：跨年度匯入前檢查
- `docs/cross_year_trial_run_roc114_january.md`：ROC 114 一月試跑報告

## Current Limitations

目前尚未完成：

- embedding 建立
- 向量索引
- OCR fallback
- 正式跨年度完整資料匯入
- Docker
- CI
- 部署設定
- 前端自動化測試
- PostgreSQL / pgvector 實務版

## Recommended Next Steps

建議後續開發順序：

```text
1. 驗證摘要與相似案件品質
2. 根據抽樣結果修正規則
3. 完成跨年度資料匯入
4. 更新跨年度統計與搜尋驗證
5. 規劃 embedding 相似案件
6. 導入 Docker / CI / 部署設定
```

## Project Positioning

本專案目前可定位為：

> A local MVP for insurance dispute case search, summarization, and analysis.

中文定位：

> 一套以金融消費評議中心人壽保險評議決定書為資料來源的保險評議案件搜尋與分析系統，提供全文搜尋、統計儀表板、規則式摘要與相似案件推薦功能。
