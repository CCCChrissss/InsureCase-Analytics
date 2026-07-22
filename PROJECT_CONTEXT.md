# 保險評議分析系統 PROJECT_CONTEXT

本文件整理目前專案狀態，供後續開發、交接、專題展示與維護使用。

掃描範圍排除：

- `.env`
- `node_modules/`
- `.venv/`
- `data/`
- `outputs/`
- `dist/`
- `build/`

因此，本文件不直接引用上述目錄內的內容；資料量與資料路徑資訊主要根據 README、docs、schema 與程式碼整理。

## 1. 專案目標

本專案目標是建立「保險評議分析系統」，將金融消費評議中心 FOI ODS 的人壽保險評議決定書整理成可查詢、可統計、可閱讀，並可逐步擴充摘要與相似案件搜尋的分析平台。

目前系統定位：

- 學校專題版：以本機 SQLite、FastAPI、React + Vite 完成可展示 MVP。
- 實務延伸版：未來可擴充 PostgreSQL、pgvector、OCR、Docker、CI、跨年度匯入與部署。

目前已處理資料範圍：

- 正式展示 DB 年度：ROC 114 + ROC 115
- 產業：保險業
- 保險類別：人壽保險
- 文件類型：評議決定書
- ROC 114 查詢期間：ROC 114/1/1 到 ROC 114/12/31
- ROC 115 查詢期間：ROC 115/1/1 到 ROC 115/7/1
- metadata records：2992 筆
- PDF / raw text / normalized text / 單案 metadata：各 2992 份
- 爭議類型：41 種
- 正式 DB：`backend/data/insurance_cases.db`
- 正式 DB 年度分布：ROC 114 = 2500，ROC 115 = 492
- 跨年度 trial DB：ROC 114 全年度 2500 筆 + ROC 115 492 筆，共 2992 筆
- trial DB 路徑：`backend/data/insurance_cases_cross_year_trial.db`
- trial DB 資料品質檢查：`issue_count = 0`
- trial DB 規則式摘要：2992 筆，`holding`、`applicant_claim`、`reasoning` 均已補齊到 2992 筆

注意：ROC 115 查詢期間是 ROC 115/1/1 到 ROC 115/7/1，但目前文件記錄的實際 `decision_date` 範圍是 `115.01.09` 到 `115.03.20`。ROC 114 全年度實際 `decision_date` 範圍是 `114.01.16` 到 `114.12.26`。

## 2. 目前資料夾結構

以下為本次掃描到的主要結構，已排除指定不讀取的目錄。

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
│  ├─ cross_year_trial_run_roc114_january.md
│  ├─ cross_year_trial_run_roc114_full_year.md
│  ├─ roc114_summary_similarity_quality_check.md
│  └─ embedding_pipeline.md
├─ backend/
│  ├─ schema.sql
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ config.py
│  │  ├─ main.py
│  │  ├─ database.py
│  │  ├─ schemas.py
│  │  ├─ routers/
│  │  │  ├─ __init__.py
│  │  │  ├─ health.py
│  │  │  ├─ cases.py
│  │  │  ├─ quality.py
│  │  │  ├─ search.py
│  │  │  ├─ semantic_search.py
│  │  │  ├─ similar_cases.py
│  │  │  ├─ statistics.py
│  │  │  └─ summaries.py
│  │  └─ services/
│  │     ├─ __init__.py
│  │     ├─ case_service.py
│  │     ├─ embedding_service.py
│  │     ├─ quality_service.py
│  │     ├─ search_service.py
│  │     ├─ similar_case_service.py
│  │     ├─ statistics_service.py
│  │     └─ summary_service.py
│  ├─ scripts/
│  │  ├─ build_chunk_embeddings.py
│  │  ├─ build_case_chunks.py
│  │  ├─ extract_case_summaries.py
│  │  ├─ import_cases_to_db.py
│  │  └─ verify_case_db.py
│  └─ tests/
│     ├─ test_api.py
│     ├─ test_build_case_chunks.py
│     ├─ test_cross_year_pipeline_defaults.py
│     ├─ test_data_quality.py
│     ├─ test_embedding_service.py
│     ├─ test_import_cases_to_db.py
│     ├─ test_search_service.py
│     ├─ test_similar_case_service.py
│     └─ test_summary_service.py
└─ frontend/
   ├─ index.html
   ├─ .env.example
   ├─ package.json
   ├─ pnpm-lock.yaml
   ├─ pnpm-workspace.yaml
   ├─ tsconfig.json
   ├─ tsconfig.node.json
   ├─ vite.config.ts
   └─ src/
      ├─ App.tsx
      ├─ main.tsx
      ├─ styles.css
      ├─ types.ts
      ├─ vite-env.d.ts
      ├─ api/
      │  └─ client.ts
      ├─ components/
      │  ├─ CaseDetailView.tsx
      │  └─ ui.tsx
      ├─ hooks/
      │  └─ useAsyncData.ts
      └─ pages/
         ├─ CasesPage.tsx
         ├─ Dashboard.tsx
         ├─ QualityPage.tsx
         ├─ SearchPage.tsx
         ├─ SemanticSearchPage.tsx
         └─ StatisticsPage.tsx
```

未掃描但專案會使用的產物目錄：

```text
data/
backend/data/
frontend/node_modules/
frontend/dist/
```

說明：

- `data/`：原始 PDF、文字、metadata 等資料產物。本次依要求未讀取。
- `backend/data/insurance_cases.db`：SQLite 匯入產物。本次依排除規則未讀取資料內容。
- `frontend/node_modules/`：前端相依套件，不提交 Git。
- `frontend/dist/`：前端 build 產物，不提交 Git。

## 3. 每個主要檔案的用途

### 根目錄

- `.gitignore`：忽略 Python cache、虛擬環境、`.env`、資料產物、SQLite DB、前端 dependencies、前端 build 產物與本機工具狀態。
- `.env.example`：根目錄環境變數範例，包含後端 DB path、CORS origins、embedding provider 設定與前端 API base URL。
- `README.md`：專案介紹、目前資料狀態、pipeline、後端與前端啟動方式。
- `requirements.txt`：Python 相依套件，包含 `beautifulsoup4`、`fastapi`、`httpx`、`pdfplumber`、`pypdf`、`pytest`、`requests`、`uvicorn`。
- `foi_ods_life_mvp_crawler.py`：FOI ODS metadata 與 PDF URL 爬蟲。
- `foi_ods_pdf_text_pipeline.py`：下載 PDF、抽取 raw text、產生 normalized text、回寫 metadata 與報表。
- `foi_ods_case_organizer.py`：將案件依年度、爭議類型、案號整理成單案資料夾。
- `PROJECT_CONTEXT.md`：本文件，整理目前專案上下文。

### docs

- `docs/project_plan.md`：完整專案計畫，包含目標、MVP 範圍、架構、資料庫、搜尋、API、前端與風險。
- `docs/development_roadmap.md`：階段式開發路線，目前已記錄到 embedding provider 介面與後續 AI provider 替換點。
- `docs/pipeline.md`：資料處理 pipeline 說明，包含爬蟲、PDF 文字抽取、案件整理、SQLite 匯入、API 與前端讀取流程。
- `docs/cross_year_readiness.md`：跨年度資料匯入前檢查報告，包含已支援項目、風險與正式匯入前 checklist。
- `docs/cross_year_trial_run_roc114_january.md`：ROC 114 一月小期間跨年度試跑報告，記錄 112 筆 metadata、PDF/text 與案件整理成功結果。
- `docs/cross_year_trial_run_roc114_full_year.md`：ROC 114 全年度跨年度試跑報告，記錄 2500 筆 metadata、PDF/text、案件整理與 trial DB 驗證結果。
- `docs/roc114_summary_similarity_quality_check.md`：ROC 114 摘要與相似案件抽樣品質檢查，記錄摘要覆蓋率、截段污染檢查、相似案件 top 5 檢查與已知例外。
- `docs/embedding_pipeline.md`：本機 chunk embedding MVP、語意搜尋 API 與後續升級路線。

### backend

- `backend/schema.sql`：SQLite schema，定義 `cases`、`case_texts`、`case_summaries`、`case_chunks`、`chunk_embeddings`、`case_search` 與索引。
- `backend/app/config.py`：後端集中設定，支援由環境變數覆蓋 DB path、CORS origins 與 embedding provider 設定。
- `backend/app/main.py`：FastAPI app 入口，設定 CORS 與註冊 routers。
- `backend/app/database.py`：SQLite 連線、預設 DB 路徑與 schema 初始化。
- `backend/app/schemas.py`：Pydantic response models。
- `backend/app/routers/health.py`：健康檢查 API。
- `backend/app/routers/cases.py`：案件列表、案件詳情、爭議類型、PDF 讀取 API。
- `backend/app/routers/quality.py`：分析驗證 API，回傳 ROC 114 摘要與相似案件品質檢查結果。
- `backend/app/routers/search.py`：全文搜尋 API。
- `backend/app/routers/semantic_search.py`：chunk embedding 語意搜尋 API。
- `backend/app/routers/similar_cases.py`：相似案件 API。
- `backend/app/routers/statistics.py`：統計 API，支援可選 `roc_year` 篩選。
- `backend/app/routers/summaries.py`：案件摘要 API。
- `backend/app/services/case_service.py`：案件查詢、篩選、分頁、PDF path resolver。
- `backend/app/services/embedding_service.py`：embedding provider 介面、本機 CJK hashing vector、chunk embedding 建置、chunk 語意搜尋與案件層級語意相似。
- `backend/app/services/quality_service.py`：ROC 114 分析驗證報告資料。
- `backend/app/services/search_service.py`：FTS5 搜尋、LIKE fallback、snippet 產生；FTS5 報錯或 0 筆時會進 LIKE fallback。
- `backend/app/services/similar_case_service.py`：規則式相似案件計分。
- `backend/app/services/statistics_service.py`：總覽、爭議類型、決定日期統計，支援可選年度條件。
- `backend/app/services/summary_service.py`：案件摘要查詢。
- `backend/scripts/extract_case_summaries.py`：從 normalized text 產生規則式摘要並寫入 `case_summaries`；已支援「二、申請人主張」與非固定序號的「判斷理由」標題。
- `backend/scripts/build_case_chunks.py`：將 `case_texts.normalized_text` 切成可重跑的 `case_chunks`，保留 section hint、字元起訖位置與 chunk 長度，作為後續 embedding 前置資料。
- `backend/scripts/build_chunk_embeddings.py`：為 `case_chunks` 建立 embedding，支援 `--provider`，目前可用 provider 為 `local`。
- `backend/scripts/import_cases_to_db.py`：讀取單一或多個 metadata 與文字檔，匯入 SQLite。
- `backend/scripts/verify_case_db.py`：驗證 SQLite 筆數、搜尋、路徑與 sample case；可用 `--require-chunks` 與 `--require-embeddings` 檢查 chunk 與 embedding 完整性。
- `backend/scripts/check_data_quality.py`：檢查 metadata 與 SQLite DB 是否含 mojibake 類異常字元。
- `backend/tests/test_api.py`：API smoke tests。
- `backend/tests/test_build_case_chunks.py`：chunking 邏輯、section hint 與 SQLite 寫入測試。
- `backend/tests/test_cross_year_pipeline_defaults.py`：跨年度 pipeline 預設輸出路徑測試。
- `backend/tests/test_data_quality.py`：資料品質檢查測試。
- `backend/tests/test_embedding_service.py`：本機 embedding、provider factory、embedding 寫入、語意搜尋排序與案件層級語意相似測試。
- `backend/tests/test_import_cases_to_db.py`：SQLite 匯入腳本測試，包含多 metadata 匯入與 metadata 目錄解析。
- `backend/tests/test_search_service.py`：搜尋 fallback 單元測試。
- `backend/tests/test_similar_case_service.py`：相似案件 service 單元測試。
- `backend/tests/test_summary_service.py`：摘要擷取與 summary service 測試，包含 FOI 標題格式變異的 regression tests。

### frontend

- `frontend/package.json`：React + Vite 前端專案設定與 scripts。
- `frontend/.env.example`：前端環境變數範例，主要設定 `VITE_API_BASE_URL`。
- `frontend/pnpm-lock.yaml`：pnpm lockfile，鎖定前端相依版本。
- `frontend/pnpm-workspace.yaml`：pnpm build approval 設定，目前允許 `esbuild`。
- `frontend/index.html`：Vite HTML 入口。
- `frontend/vite.config.ts`：Vite 設定，使用 React plugin，dev server 固定 `127.0.0.1:5173`。
- `frontend/tsconfig.json`：前端 TypeScript 設定。
- `frontend/tsconfig.node.json`：Vite config 使用的 TypeScript 設定。
- `frontend/src/main.tsx`：React app 掛載入口。
- `frontend/src/App.tsx`：主版面、側邊欄導覽與 route state 管理。
- `frontend/src/api/client.ts`：API base URL、`apiGet`、`apiGetOptional`。
- `frontend/src/types.ts`：前端 API response 型別。
- `frontend/src/hooks/useAsyncData.ts`：共用非同步資料載入 hook。
- `frontend/src/components/CaseDetailView.tsx`：案件詳情、摘要、相似案件區塊。
- `frontend/src/components/ui.tsx`：PageHeader、PanelHeader、Metric、AsyncBlock、EmptyState。
- `frontend/src/pages/`：Dashboard、案件管理、全文搜尋、語意搜尋、統計分析、分析驗證頁。
- `frontend/src/styles.css`：前端全域樣式與 responsive layout。
- `frontend/src/vite-env.d.ts`：Vite TypeScript 型別宣告。

## 4. 後端架構

目前後端為 FastAPI + SQLite 的唯讀查詢 API。

架構分層：

```text
FastAPI app
  ├─ routers
  │  ├─ health
  │  ├─ cases
  │  ├─ quality
  │  ├─ search
  │  ├─ semantic_search
  │  ├─ similar_cases
  │  ├─ summaries
  │  └─ statistics
  ├─ services
  │  ├─ case_service
  │  ├─ embedding_service
  │  ├─ quality_service
  │  ├─ search_service
  │  ├─ similar_case_service
  │  ├─ summary_service
  │  └─ statistics_service
  ├─ schemas
  ├─ config
  └─ database
      ↓
SQLite database
```

資料流：

```text
backend/data/insurance_cases.db
  ↓ sqlite3
services
  ↓ dict / Pydantic response model
routers
  ↓ JSON / FileResponse
frontend
```

主要設計：

- API prefix 以 `/api` 為主。
- 統計 API 使用 `/api/statistics`。
- CORS 預設允許：
  - `http://localhost:5173`
  - `http://127.0.0.1:5173`
- CORS 可用 `BACKEND_CORS_ORIGINS` 以逗號分隔覆蓋。
- DB path 預設為 `backend/data/insurance_cases.db`，可用 `INSURANCE_CASES_DB_PATH` 覆蓋。
- HTTP method 目前只允許 GET。
- DB 連線使用 Python 標準庫 `sqlite3`。
- 每次 service function 以 context manager 建立連線。
- 查詢結果透過 `sqlite3.Row` 轉 dict。

## 5. 前端架構

目前前端為 React + Vite + TypeScript 的單頁應用。

技術：

- React 19
- Vite 7
- TypeScript
- Recharts
- lucide-react
- pnpm

主要資料流：

```text
React component
  ↓ useAsyncData
fetch(API_BASE + path)
  ↓
FastAPI /api/*
```

`API_BASE` 設定：

```text
VITE_API_BASE_URL 若存在則使用該值
否則預設 http://127.0.0.1:8000/api
```

前端設定範例位於 `frontend/.env.example`。

目前頁面以 React state 切換，並同步基本 URL query：

- `dashboard`
- `cases`
- `search`
- `statistics`
- `quality`

案件詳情可分享：

```text
?view=cases&case_id=<case_id>
```

重新整理或使用瀏覽器上一頁/下一頁時，會依 URL 還原頁面與選中案件。

主要 UI：

- 側邊欄導覽：總覽、案件、搜尋、統計。
- Dashboard：年度篩選、案件數、爭議類型數、年度、決定日期、前十大爭議類型圖、日期分布圖。
- 案件管理：年度、爭議類型、案號 filter，案件列表，案件詳情。
- 全文搜尋：關鍵字輸入，搜尋結果，snippet，點擊進入案件詳情。
- 統計分析：年度篩選、爭議類型分布與決定日期分布。
- 分析驗證：展示 ROC 114 摘要覆蓋率、截段污染檢查、相似度計分規則、抽樣案件、已知例外與限制。

目前前端已拆分為：

```text
frontend/src/
├─ api/
├─ components/
├─ hooks/
├─ pages/
├─ App.tsx
├─ main.tsx
├─ styles.css
└─ types.ts
```

樣式仍集中於 `frontend/src/styles.css`。

## 6. 資料庫 schema

資料庫：SQLite。

schema 來源：`backend/schema.sql`。

### `cases`

案件 metadata 主表。

```sql
case_id TEXT PRIMARY KEY
case_number TEXT NOT NULL UNIQUE
roc_year INTEGER NOT NULL
decision_date TEXT
decision_category TEXT
decision_result TEXT
industry TEXT
industry_subcategory TEXT
dispute_type TEXT
source_pdf_url TEXT
case_directory TEXT
pdf_path TEXT
raw_text_path TEXT
normalized_text_path TEXT
metadata_path TEXT
created_at TEXT NOT NULL
updated_at TEXT NOT NULL
```

索引：

```sql
idx_cases_roc_year
idx_cases_decision_date
idx_cases_dispute_type
idx_cases_case_number
```

### `case_texts`

案件文字主表。

```sql
case_id TEXT PRIMARY KEY
raw_text TEXT
normalized_text TEXT
raw_text_chars INTEGER
normalized_text_chars INTEGER
page_count INTEGER
extraction_method TEXT
FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
```

### `case_summaries`

摘要表，目前由 `backend/scripts/extract_case_summaries.py` 寫入；目前正式 DB 已產生 2992 筆 `rule_based_v1` 摘要。

```sql
case_id TEXT PRIMARY KEY
holding TEXT
applicant_claim TEXT
reasoning TEXT
summary_method TEXT
created_at TEXT
FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
```

### `case_chunks`

案件文字切片表，目前由 `backend/scripts/build_case_chunks.py` 寫入；正式 DB 已產生 17254 段，2992 筆案件皆至少有一段 chunk。

```sql
chunk_id TEXT PRIMARY KEY
case_id TEXT NOT NULL
chunk_index INTEGER NOT NULL
section_hint TEXT
chunk_text TEXT NOT NULL
char_start INTEGER NOT NULL
char_end INTEGER NOT NULL
chunk_chars INTEGER NOT NULL
created_at TEXT NOT NULL
FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
UNIQUE(case_id, chunk_index)
```

索引：

```sql
idx_case_chunks_case_id
```

### `chunk_embeddings`

chunk embedding 表，目前由 `backend/scripts/build_chunk_embeddings.py` 寫入；正式 DB 已產生 17254 筆，與 `case_chunks` 數量一致。

```sql
chunk_id TEXT NOT NULL
embedding_model TEXT NOT NULL
embedding_dims INTEGER NOT NULL
embedding BLOB NOT NULL
embedding_norm REAL NOT NULL
created_at TEXT NOT NULL
FOREIGN KEY(chunk_id) REFERENCES case_chunks(chunk_id) ON DELETE CASCADE
PRIMARY KEY(chunk_id, embedding_model)
```

目前模型：

```text
local_hashing_cjk_v1
```

注意：這是學校專題版的本機 hashing vector MVP，不等同於正式語意 embedding model。

### `case_search`

SQLite FTS5 full-text search virtual table。

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS case_search USING fts5(
  case_id UNINDEXED,
  case_number,
  dispute_type,
  normalized_text
);
```

用途：

- 搜尋案號
- 搜尋爭議類型
- 搜尋 normalized text

## 7. API endpoint 清單

### Health

```text
GET /api/health
```

用途：確認 API 狀態與 SQLite DB 是否存在。

回傳：

```json
{
  "status": "ok",
  "database_ready": true
}
```

### Cases

```text
GET /api/cases
```

用途：案件列表與篩選。

Query parameters：

- `page`：預設 1，最小 1。
- `page_size`：預設 20，最大 100。
- `roc_year`：可選。
- `dispute_type`：可選。
- `case_number`：可選，使用 `LIKE` 模糊查詢。

```text
GET /api/cases/{case_id}
```

用途：取得單一案件詳情，包含 metadata、raw text、normalized text 與文字統計。

```text
GET /api/dispute-types
```

用途：取得爭議類型清單與數量，供前端 filter 使用。

```text
GET /api/files/{case_id}/pdf
```

用途：依案件 ID 回傳 PDF 檔案。

### Search

```text
GET /api/search
```

用途：全文搜尋。

Query parameters：

- `q`：必填，最小長度 1。
- `page`：預設 1。
- `page_size`：預設 20，最大 100。

搜尋方式：

- 優先使用 SQLite FTS5 `MATCH`。
- 若 FTS5 query 產生 `sqlite3.OperationalError`，fallback 到 `LIKE`。
- 若 FTS5 沒報錯但回傳 0 筆，也會 fallback 到 `LIKE`。
- 回傳 snippet 與 `match_source`。

### Semantic Search

```text
GET /api/semantic-search
```

用途：使用 `chunk_embeddings` 做 chunk 層級語意搜尋。

Query parameters：

- `q`：必填，最小長度 1。
- `limit`：預設 10，最大 50。
- `min_score`：最低分數，預設 0。

目前方法：

- 使用 `local_hashing_cjk_v1`。
- 回傳命中的 `chunk_text`、`section_hint`、`score` 與案件基本資料。
- 這是本機 MVP，尚不是正式語意模型。

### Summaries

```text
GET /api/cases/{case_id}/summary
```

用途：取得單一案件規則式摘要。

回傳：

- `holding`
- `applicant_claim`
- `reasoning`
- `summary_method`
- `created_at`

### Similar Cases

```text
GET /api/cases/{case_id}/similar?limit=5
```

用途：取得規則式相似案件。

目前相似度依據：

- 相同爭議類型。
- 相同評議結果。
- 相同決定類別。
- 摘要文字中的保險關鍵詞重疊。

回傳：

- `score`
- `matched_reasons`
- top N 相似案件基本資料。

### Quality

```text
GET /api/quality/roc114-summary-similarity
```

用途：取得 ROC 114 摘要與相似案件品質檢查結果，供前端「分析驗證」頁展示。

回傳內容包含：

- 分析範圍。
- 前十大爭議類型。
- 摘要欄位覆蓋率與長度統計。
- 截段污染檢查。
- 相似案件計分規則。
- 抽樣案件檢查結果。
- 整體 Top 1 / Top 5 同爭議類型率。
- 已知低信心例外。
- 方法限制與下一步。

### Statistics

```text
GET /api/statistics/overview
```

用途：總案件數、爭議類型數、年度清單、最早與最晚決定日期。

Query parameters：

- `roc_year`：可選；指定後只統計該年度案件。

```text
GET /api/statistics/dispute-types
```

用途：依爭議類型統計案件數。

Query parameters：

- `roc_year`：可選；指定後只統計該年度案件。

```text
GET /api/statistics/decision-dates
```

用途：依決定日期統計案件數。

Query parameters：

- `roc_year`：可選；指定後只統計該年度案件。

## 8. 目前已完成功能

### 資料處理

- FOI ODS metadata 與 PDF URL 爬取。
- 避免網站單次查詢 100 筆上限的月份、週、爭議類型切分。
- PDF 下載。
- `pdfplumber` 文字抽取。
- `pypdf` fallback。
- raw text 與 normalized text 產生。
- 依年度、爭議類型、案號整理案件資料夾。
- metadata 回寫本地檔案路徑。
- ROC 114 全年度 metadata / PDF text / case organizer 均完成 2500 筆。

### SQLite

- 建立 `cases`。
- 建立 `case_texts`。
- 建立 `case_summaries`。
- 建立 `case_chunks`。
- 建立 `chunk_embeddings`。
- 建立 `case_search` FTS5 virtual table。
- 匯入 2992 筆案件。
- 匯入 2992 筆文字。
- 匯入腳本支援多個 `--metadata` 與 `--metadata-dir`。
- 建立全文搜尋索引。
- 已寫入 2992 筆規則式摘要。
- 已建立 17254 段案件文字 chunk，2992 筆案件皆有 chunk。
- 已建立 17254 筆 chunk embedding，模型為 `local_hashing_cjk_v1`，維度 384。
- 提供資料庫驗證腳本。
- 已建立跨年度 trial DB：`backend/data/insurance_cases_cross_year_trial.db`，匯入 ROC 114 全年度 2500 筆與 ROC 115 492 筆，共 2992 筆。
- trial DB 已重建規則式摘要，共 2992 筆；`holding`、`applicant_claim`、`reasoning` 均為 2992 筆。
- 正式展示 DB `backend/data/insurance_cases.db` 已切換為 ROC 114 + ROC 115 共 2992 筆；原 ROC 115 DB 已備份為 `backend/data/insurance_cases_roc115_backup_20260707_163248.db`。

### 後端

- FastAPI app。
- CORS 設定，支援環境變數覆蓋。
- DB path 設定，支援環境變數覆蓋。
- 健康檢查。
- 案件列表 API。
- 案件詳情 API。
- 爭議類型 API。
- PDF 回傳 API。
- 全文搜尋 API。
- 語意搜尋 API。
- 案件層級語意相似 API。
- 摘要 API。
- 規則式相似案件 API。
- 分析驗證 API。
- 統計 API，支援年度篩選。
- 後端 pytest 測試。
- OpenAPI docs 可由 FastAPI 自動產生。

### 前端

- React + Vite 專案。
- Dashboard 年度篩選。
- 案件管理頁年度篩選。
- 案件詳情區。
- 全文搜尋頁。
- 語意搜尋頁，展示 query、embedding 模型、候選 chunk 數、命中 chunk、score、section hint 與案件來源。
- 案件詳情頁語意相似案件區塊，展示相似案件、分數與實際命中 chunk。
- 統計分析頁年度篩選。
- 分析驗證頁。
- 案件摘要區塊。
- 相似案件區塊。
- PDF 連結。
- Responsive layout。
- API 連線狀態顯示。
- 基本 URL 狀態同步，可分享案件詳情。

### Git

- 專案目前已是有效 Git repository。
- 目前已建立至少三個階段 commit：
  - 專案文件與 pipeline 腳本。
  - SQLite 匯入流程。
  - FastAPI 後端 API。
  - React 前端 MVP。
  - 搜尋 fallback 與後端測試。
  - 規則式摘要。
  - chunking pipeline。
  - 本機 embedding pipeline 與語意搜尋 API。
  - 案件層級語意相似展示。
  - embedding provider 介面。

## 9. 尚未完成項目

- 實務級 embedding model。
- ANN 向量索引。
- OCR fallback。
- ROC 116 或更多年度資料蒐集。
- 後台管理 API，例如重新匯入、重建索引。
- Docker。
- CI。
- 部署設定。
- API 錯誤回應格式統一。
- 正式 React Router。
- 前端自動化測試。
- 正式 AI embedding provider 與向量重建流程。
- 實務級向量資料庫或 ANN index。

## 10. 目前可能的 bug 或技術債

### 規則式相似度不是語意相似

目前相似案件是 baseline，依爭議類型、評議結果與保險關鍵詞重疊計分。
系統也已新增案件層級語意相似，但目前語意向量仍是本機 `local_hashing_cjk_v1`，不是正式 AI embedding model。

影響：

- 分數可解釋，但不等同語意相似度或法律判斷。
- 本機語意相似可展示分析流程與命中段落，但語意品質不能等同 OpenAI embedding、BGE 或其他正式模型。

建議：

- 後續實作正式 AI embedding provider，重建 `chunk_embeddings`，再視資料量導入 pgvector 或其他向量索引。

### ROC 114 一月亂碼問題已修正

跨年度 trial DB 第一次建立時，ROC 114 一月資料中有 32 筆案號、爭議類型與整理後路徑出現亂碼。根因是 FOI ODS 結果頁已宣告 `charset=utf-8`，但爬蟲用 `response.apparent_encoding` 覆蓋 header charset，而該批結果頁被誤判為 `MacCyrillic`。

已修正：

- `foi_ods_life_mvp_crawler.py` 改為優先使用 response header 宣告的 charset。
- 爬蟲 validation 會偵測案號與爭議類型是否含異常 Cyrillic 字元。
- 新增 `backend/scripts/check_data_quality.py`，可檢查 metadata 與 SQLite DB。
- 已重跑 ROC 114 一月 metadata、PDF/text pipeline、case organizer。
- 已刪除舊的 ROC 114 亂碼資料夾殘留。
- 後續已擴大到 ROC 114 全年度，並重建跨年度 trial DB 與 2992 筆摘要。

驗證結果：

- ROC 114 metadata 品質檢查 `issue_count` = 0。
- ROC 114 一月修正當時，cases 資料夾中 `decision.pdf`、`raw_text.txt`、`normalized_text.txt`、`metadata.json` 均為 112 份。
- 跨年度 trial DB 品質檢查 `issue_count` = 0。
- 目前 trial DB 年度分布為 ROC 114 = 2500、ROC 115 = 492。

### 前端尚未使用正式 router

前端已支援 `view` 與 `case_id` query 同步，但尚未使用 React Router 這類正式 router。

影響：

- 基本案件詳情分享已可用。
- 若未來頁面狀態變多，例如篩選條件、搜尋字串、分頁，手寫 History API 會變得難維護。

建議：

- 後續在功能複雜後加入 React Router 或等價 routing。

### 案件詳情一次回傳全文

`GET /api/cases/{case_id}` 會回傳 `raw_text` 與 `normalized_text`。

影響：

- 2992 筆本機 MVP 可接受。
- 未來跨年度或文字更長時，API payload 可能偏大。

建議：

- 保留案件 metadata endpoint。
- 另開 `/api/cases/{case_id}/text` 或支援 lazy loading。

### API 設定已可覆蓋，但尚未導入完整設定管理

目前 DB path、CORS、frontend API base 已提供本機預設值與 `.env.example`，並可透過環境變數覆蓋。

影響：

- 本機展示方便。
- 部署或多人協作時已可調整設定，但專案目前不會自動載入 `.env` 檔。

建議：

- 若後續要正式部署，可評估加入部署平台環境變數、Docker env 或 settings class。
- 若希望本機自動讀 `.env`，需要再評估是否加入 `python-dotenv` 或等價方案。

### 前端尚無自動化測試

後端已有 pytest；前端目前仍主要依靠 `pnpm build` 與人工瀏覽器檢查。

建議：

- 後續加入前端 smoke tests。

### Vite build bundle 偏大

目前前端 production build 曾出現 chunk 超過 500 kB 的 warning，主要可能來自 Recharts。

影響：

- 本機展示可接受。
- 實際部署時首屏 JS 可能偏大。

建議：

- 後續可做 dynamic import 或 manual chunks。

### 摘要與相似案件規則需要持續抽樣校正

目前摘要與相似案件都採規則式方法，已可展示，但遇到新年度或格式變異時仍可能需要調整規則。

已知已修正格式變異：

- 「二、申請人主張」缺少「之」時，仍可抽取 `applicant_claim`。
- 「判斷理由」不固定為第六段時，例如「四、判斷理由」，仍可抽取 `reasoning`。

建議：

- 跨年度前先建立抽樣驗證流程。

## 11. 執行方式

### Python 後端相依套件

在專案根目錄執行：

```powershell
py -m pip install -r requirements.txt
```

### 環境變數設定

根目錄提供 `.env.example`，前端目錄提供 `frontend/.env.example`。

後端支援：

```text
INSURANCE_CASES_DB_PATH=backend/data/insurance_cases.db
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

前端支援：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

注意：目前後端沒有新增自動讀取 `.env` 的套件。若要套用設定，請在啟動指令前於 shell 或部署平台設定環境變數。

### 建立 SQLite DB

前提：

- `data/` 內已存在整理完成的 metadata、PDF、raw text、normalized text。

執行：

```powershell
py .\backend\scripts\import_cases_to_db.py --recreate
```

預設輸入：

```text
data/foi_ods/metadata/foi_ods_life_roc115_metadata.json
```

多 metadata 匯入：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json --metadata .\data\foi_ods\metadata\foi_ods_life_roc115_metadata.json --recreate
```

metadata 目錄匯入：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata-dir .\data\foi_ods\metadata --recreate
```

說明：

- `--metadata` 可重複指定。
- `--metadata-dir` 只讀取目錄下的 `*_metadata.json`。
- 目前正式展示資料已是 ROC 114 + ROC 115 共 2992 筆；多 metadata 匯入仍可用於後續新增年度。

預設輸出：

```text
backend/data/insurance_cases.db
```

### 驗證 SQLite DB

```powershell
py .\backend\scripts\verify_case_db.py
```

成功標準：

- `cases` = 2992
- `case_texts` = 2992
- `case_search` = 2992
- `case_summaries` = 2992
- `case_chunks` = 17254
- `chunk_embeddings` = 17254
- `cases_without_chunks` = 0
- `chunks_without_embeddings` = 0
- path errors = 0
- 關鍵字查詢有結果

### 產生規則式摘要

```powershell
py .\backend\scripts\extract_case_summaries.py
```

目前成功標準：

- `processed_count` = 2992
- `total_summaries` = 2992
- `holding` = 2992
- `applicant_claim` = 2992
- `reasoning` = 2992

### 建立案件文字 chunks

```powershell
py .\backend\scripts\build_case_chunks.py --db .\backend\data\insurance_cases.db
```

目前正式 DB 驗證結果：

- `processed_cases` = 2992
- `total_chunks_in_table` = 17254
- `empty_case_count` = 0
- `min_chunks_per_case` = 3
- `max_chunks_per_case` = 30

### 建立 chunk embeddings

```powershell
py .\backend\scripts\build_chunk_embeddings.py --db .\backend\data\insurance_cases.db
```

目前正式 DB 驗證結果：

- `processed_chunks` = 17254
- `embedded_chunks` = 17254
- `total_embeddings_in_table` = 17254
- `empty_chunk_count` = 0
- `embedding_model` = `local_hashing_cjk_v1`
- `embedding_dims` = 384

### 啟動後端 API

在專案根目錄執行：

```powershell
py -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

開啟：

```text
http://127.0.0.1:8000/docs
```

### 啟動前端

在 `frontend/` 目錄執行：

```powershell
pnpm install
pnpm dev
```

開啟：

```text
http://127.0.0.1:5173
```

前端預設呼叫：

```text
http://127.0.0.1:8000/api
```

若要改 API 位址，可設定：

```text
VITE_API_BASE_URL
```

設定範例在 `frontend/.env.example`。

## 12. 測試方式

目前後端已有 pytest 測試，前端目前以 build 與人工檢查為主。

### 後端語法檢查

```powershell
py -m py_compile .\foi_ods_life_mvp_crawler.py
py -m py_compile .\foi_ods_pdf_text_pipeline.py
py -m py_compile .\foi_ods_case_organizer.py
py -m py_compile .\backend\scripts\import_cases_to_db.py
py -m py_compile .\backend\scripts\build_case_chunks.py
py -m py_compile .\backend\scripts\build_chunk_embeddings.py
py -m py_compile .\backend\scripts\verify_case_db.py
py -m py_compile .\backend\scripts\extract_case_summaries.py
```

### 後端 pytest

```powershell
py -m pytest
```

目前覆蓋：

- API smoke tests。
- 分析驗證 API tests。
- 統計 API 年度篩選 tests。
- 搜尋 fallback service test。
- chunking pipeline tests。
- embedding service tests。
- 摘要擷取與 summary service tests，包含「申請人主張」標題缺少「之」與「判斷理由」非第六段的 regression tests。
- 相似案件 service tests。
- 匯入腳本多 metadata tests。

### SQLite 匯入驗證

```powershell
py .\backend\scripts\verify_case_db.py --expected-count 2992 --require-chunks --require-embeddings
```

### API smoke test

後端啟動後檢查：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/health -UseBasicParsing
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/statistics/overview -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/statistics/overview?roc_year=115" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/search?q=癌症" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/semantic-search?q=癌症保險金&limit=5" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/cases/{case_id}/summary" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/cases/{case_id}/similar" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/cases/{case_id}/semantic-similar?limit=5" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/quality/roc114-summary-similarity" -UseBasicParsing
```

預期：

- `/api/health` 回傳 `status: ok` 且 `database_ready: true`。
- `/api/statistics/overview` 的 `case_count` 應為 2992。
- `/api/statistics/overview?roc_year=115` 應可回傳年度篩選後的統計。
- `/api/search?q=癌症` 應有搜尋結果。
- `/api/semantic-search?q=癌症保險金` 應回傳 embedding 模型、候選 chunk 數、score 與命中段落。
- `/api/cases/{case_id}/summary` 應回傳 `rule_based_v1` 摘要。
- `/api/cases/{case_id}/similar` 應回傳相似案件與命中原因。
- `/api/cases/{case_id}/semantic-similar` 應回傳案件層級語意相似案件與命中 chunk。
- `/api/quality/roc114-summary-similarity` 應回傳 ROC 114 品質檢查報告。

### 前端 build 驗證

在 `frontend/` 執行：

```powershell
pnpm build
```

預期：

- TypeScript build 成功。
- Vite build 成功。
- 若出現 chunk size warning，代表 bundle 偏大，但不等於 build 失敗。

### 前端人工驗證

後端與前端都啟動後，開啟：

```text
http://127.0.0.1:5173
```

檢查：

- Dashboard 顯示 2992 案件。
- Dashboard 年度下拉可選全部年度、ROC 114 或 ROC 115。
- 案件頁可篩選、分頁、點選案件。
- 案件頁可依年度篩選。
- 案件詳情可看到 metadata、全文與 PDF 連結。
- 案件詳情可看到案件摘要。
- 案件詳情可看到相似案件。
- 搜尋頁可查「癌症」。
- 語意搜尋頁可查「癌症保險金」，並顯示 embedding 模型、候選 chunk、score、section hint 與命中段落。
- 統計頁可看到爭議類型與日期分布。
- 統計頁可依年度篩選。
- 分析驗證頁可看到摘要品質、相似度規則、抽樣案件與已知例外。
- 瀏覽器 console 無 error。

### 最近一次本機穩定檢查

2026-07-22 已完成以下檢查：

- `py -m pytest`：36 passed。
- `py .\backend\scripts\verify_case_db.py --expected-count 2992 --require-chunks --require-embeddings`：passed，`cases = 2992`、`case_chunks = 17254`、`chunk_embeddings = 17254`。
- `pnpm build`：TypeScript 與 Vite build 成功；僅有 chunk size warning。
- `py -m py_compile`：後端主要設定、service 與 router 檔案通過語法檢查。
- 本機後端 `http://127.0.0.1:8000/api/health` 回傳 `status = ok`、`database_ready = true`。
- 本機前端 `http://127.0.0.1:5173/` 可回傳首頁 HTML。
- 瀏覽器人工檢查 Dashboard、案件、全文搜尋、語意搜尋、統計、分析驗證頁皆可載入，console 無 error。

注意：語意搜尋頁第一次載入會計算 17254 筆 chunk embedding 相似度，可能短暫顯示「載入中」；等待數秒後會顯示結果。

## 13. 建議下一步開發順序

### 已完成：規則式摘要與規則式相似案件

目前已完成：

- 規則式摘要 pipeline。
- Summary API。
- 前端案件摘要。
- 搜尋 fallback 修正。
- 後端 pytest。
- 規則式相似案件 API。
- 前端相似案件區塊。
- 分析驗證 API 與前端頁面。
- 前端結構拆分。
- 環境設定集中化與 `.env.example`。
- SQLite 匯入腳本支援多 metadata。
- 統計 API 與前端年度篩選。
- 跨年度 pipeline 預設檔名修正與 readiness 報告。
- ROC 114 一月資料小期間試跑，metadata / PDF text / case organizer 均成功 112 筆。
- ROC 114 全年度資料試跑，metadata / PDF text / case organizer 均成功 2500 筆。
- 已建立跨年度 trial DB，ROC 114 全年度 2500 筆加 ROC 115 492 筆共 2992 筆，並已產生 2992 筆規則式摘要；`holding`、`applicant_claim`、`reasoning` 欄位均已補齊；正式 DB 已切換。
- 已修正 ROC 114 一月 32 筆亂碼資料，並新增資料品質檢查腳本。
- 已完成 ROC 114 摘要與相似案件品質檢查：摘要三欄覆蓋率 2500/2500，Top 1 同爭議類型率 99.92%，已知 2 筆稀有爭議類型因無同類候選而只能回傳低信心相似案件。
- 已在前端相似案件區塊加入低信心提示，當 Top 5 沒有同爭議類型或最高分偏低時會提示結果僅供參考。
- 已建立案件文字 chunking pipeline，正式 DB 目前有 17254 段 chunk，且 2992 筆案件皆有 chunk。
- 已建立本機 chunk embedding pipeline，正式 DB 目前有 17254 筆 `local_hashing_cjk_v1` embedding，且每個 chunk 皆有 embedding。
- 已新增前端語意搜尋頁，可展示 query、embedding 模型、候選 chunk、命中 chunk、score、section hint 與案件來源。
- 已新增案件層級語意相似 API 與案件詳情頁區塊，可展示相似案件、分數與實際命中 chunk。
- 已建立 embedding provider 介面，目前可用 provider 為 `local`，`openai` / `ai` 會明確提示尚未實作。

### 下一步：串接實際 AI embedding model 或擴大跨年度資料

優先原因：

- 規則式摘要與相似案件 baseline 已完成。
- chunking、本機 embedding、前端語意搜尋展示與案件層級語意相似展示已完成。
- 前端結構已整理，後續可以承接更複雜功能。
- 跨年度 trial DB 已建立並通過資料品質檢查，正式 DB 也已切換為跨年度資料。

建議工作：

1. 若要強化語意品質：實作 OpenAI 或其他正式 AI embedding provider，並以新 `embedding_model` 重建 `chunk_embeddings`。
2. 若要強化資料範圍：試跑 ROC 116 小期間。

### 第 8 階段：跨年度擴充

優先原因：

- 需要先確認現有 ROC 115 pipeline、DB、API、前端流程穩定。

建議工作：

1. 實際新增其他年度資料並匯入。
2. 檢查 `case_id` 是否能跨年度穩定唯一。
3. 抽樣驗證跨年度統計結果。
4. 視資料量調整前端統計呈現。

### 第 9 階段：部署與實務化

建議工作：

1. Dockerfile。
2. docker-compose。
3. CI。
4. PostgreSQL migration 評估。
5. pgvector 評估。
6. OCR fallback 評估。
