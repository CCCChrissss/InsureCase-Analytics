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
- 分析驗證頁，展示摘要與相似案件品質檢查過程
- 案件文字 chunking pipeline，作為後續 embedding 與向量搜尋前置資料
- 本機 chunk embedding MVP 與語意搜尋 API
- 前端語意搜尋頁，展示 query、embedding 模型、命中 chunk、score、section hint 與案件來源
- 案件詳情頁語意相似案件區塊，展示案件層級語意相似與命中段落
- 後端 pytest 測試
- 前端基本 build 驗證
- 跨年度匯入前置支援
- ROC 114 一月小期間跨年度試跑文件
- ROC 114 全年度跨年度 trial DB 試跑文件
- 正式展示 DB 已切換為 ROC 114 + ROC 115 跨年度資料
- ROC 114 摘要與相似案件品質檢查文件

## Data Scope

目前正式展示資料範圍：

- 年度：ROC 114 + ROC 115
- 產業：保險業
- 保險類別：人壽保險
- 文件類型：評議決定書
- ROC 114 查詢期間：ROC 114/1/1 到 ROC 114/12/31
- ROC 115 查詢期間：ROC 115/1/1 到 ROC 115/7/1
- metadata records：2992 筆
- PDF：2992 份
- raw text：2992 份
- normalized text：2992 份
- 單案 metadata：2992 份
- case chunks：17254 段
- chunk embeddings：17254 筆，模型為 `local_hashing_cjk_v1`
- 爭議類型：41 種
- 正式 DB：`backend/data/insurance_cases.db`
- 正式 DB 年度分布：ROC 114 = 2500，ROC 115 = 492

注意：查詢期間是 ROC 115/1/1 到 ROC 115/7/1，但目前 metadata records 內的實際 `decision_date` 範圍是 `115.01.09` 到 `115.03.20`。展示與文件中應區分「查詢期間」與「實際取得案件決定日期範圍」。

跨年度 trial 資料範圍：

- ROC 114 全年度：2500 筆
- ROC 115：492 筆
- trial DB：2992 筆
- trial DB 路徑：`backend/data/insurance_cases_cross_year_trial.db`
- trial DB data quality `issue_count`：0

注意：trial DB 已驗收並複製為正式展示 DB。原 ROC 115 正式 DB 已備份在 `backend/data/`，檔名格式為 `insurance_cases_roc115_backup_*.db`。

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
│  ├─ cross_year_trial_run_roc114_january.md
│  ├─ cross_year_trial_run_roc114_full_year.md
│  └─ roc114_summary_similarity_quality_check.md
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
backend/scripts/build_case_chunks.py
  ↓
case_chunks
  ↓
backend/scripts/build_chunk_embeddings.py
  ↓
chunk_embeddings
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
GET /api/semantic-search
GET /api/cases/{case_id}/summary
GET /api/cases/{case_id}/similar
GET /api/quality/roc114-summary-similarity
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

### Semantic Search

目前提供本機 embedding MVP：

```text
GET /api/semantic-search?q=癌症保險金&limit=10
```

目前模型：

```text
local_hashing_cjk_v1
```

這是純 Python 的 CJK n-gram hashing vector，優點是可離線、可重跑、無需 API key；限制是語意品質不等同於 OpenAI embedding、BGE 或其他正式語意模型。

案件層級語意相似 API：

```text
GET /api/cases/{case_id}/semantic-similar?limit=5
```

目前做法是將來源案件的 chunk embeddings 聚合成案件向量，再與候選案件 chunk 比對，回傳相似案件與命中段落。

未來若要串接實際 AI 語意分析模型，主要替換 `backend/app/services/embedding_service.py` 的向量產生流程與 `chunk_embeddings` 重建腳本，API 與前端展示可以大致沿用。

目前已加入 embedding provider 設定：

```text
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=local_hashing_cjk_v1
EMBEDDING_DIMS=384
```

`local` 是目前可用 provider；`openai` / AI provider 介面已預留，但尚未實作外部 API 呼叫。

### Quality Report

分析驗證 API 回傳 ROC 114 摘要與相似案件品質檢查結果：

```text
GET /api/quality/roc114-summary-similarity
```

前端「分析驗證」頁會顯示分析範圍、摘要覆蓋率、截段污染檢查、相似度計分規則、抽樣案件、整體指標、已知例外與方法限制。

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

匯入前建議先檢查 metadata 是否有 mojibake 類異常字元：

```powershell
py .\backend\scripts\check_data_quality.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc115_metadata.json
```

跨年度匯入前可同時檢查多個 metadata：

```powershell
py .\backend\scripts\check_data_quality.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json --metadata .\data\foi_ods\metadata\foi_ods_life_roc115_metadata.json
```

匯入 DB 後建議再檢查一次：

```powershell
py .\backend\scripts\check_data_quality.py --db .\backend\data\insurance_cases.db
```

成功標準：

- `issue_count` = 0
- `passed` = true

### 4. Extract rule-based summaries

```powershell
py .\backend\scripts\extract_case_summaries.py
```

### 5. Build case chunks

```powershell
py .\backend\scripts\build_case_chunks.py --db .\backend\data\insurance_cases.db
```

目前正式 DB 驗證結果：

- `processed_cases` = 2992
- `total_chunks_in_table` = 17254
- `empty_case_count` = 0

### 6. Build chunk embeddings

```powershell
py .\backend\scripts\build_chunk_embeddings.py --db .\backend\data\insurance_cases.db
```

目前正式 DB 驗證結果：

- `processed_chunks` = 17254
- `embedded_chunks` = 17254
- `total_embeddings_in_table` = 17254
- `empty_chunk_count` = 0

### 7. Verify database

```powershell
py .\backend\scripts\verify_case_db.py --expected-count 2992 --require-chunks --require-embeddings
```

### 8. Start backend

```powershell
py -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

### 9. Start frontend

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
py -m py_compile .\backend\scripts\build_case_chunks.py
py -m py_compile .\backend\scripts\build_chunk_embeddings.py
py -m py_compile .\backend\scripts\verify_case_db.py
py -m py_compile .\backend\scripts\extract_case_summaries.py
```

### Backend pytest

```powershell
py -m pytest
```

目前測試涵蓋：

- API smoke tests
- 分析驗證 API
- 統計 API 年度篩選
- 搜尋 fallback
- 案件文字 chunking pipeline
- 本機 embedding service 與語意搜尋
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

若目前 shell 找不到 `node`，需先確認 Node.js 已在 PATH，或使用 Codex bundled Node runtime。

若出現 Vite chunk size warning，代表 bundle 偏大，但不等於 build 失敗。

## Documentation

- `PROJECT_CONTEXT.md`：目前專案狀態總覽
- `docs/project_plan.md`：專案計畫
- `docs/development_roadmap.md`：開發路線
- `docs/pipeline.md`：資料處理 pipeline
- `docs/cross_year_readiness.md`：跨年度匯入前檢查
- `docs/cross_year_trial_run_roc114_january.md`：ROC 114 一月試跑報告
- `docs/cross_year_trial_run_roc114_full_year.md`：ROC 114 全年度試跑報告
- `docs/roc114_summary_similarity_quality_check.md`：ROC 114 摘要與相似案件抽樣品質檢查
- `docs/chunking_pipeline.md`：案件文字 chunking 設計、欄位與正式 DB 驗證結果
- `docs/embedding_pipeline.md`：本機 embedding MVP、語意搜尋 API 與後續升級路線

## Current Limitations

目前尚未完成：

- 實務級 embedding 模型
- ANN 向量索引
- OCR fallback
- Docker
- CI
- 部署設定
- 前端自動化測試
- PostgreSQL / pgvector 實務版

## Recommended Next Steps

建議後續開發順序：

```text
1. 實作 OpenAI 或其他正式 AI embedding provider
2. 試跑 ROC 116 小期間資料
3. 導入 Docker / CI / 部署設定
```

## Project Positioning

本專案目前可定位為：

> A local MVP for insurance dispute case search, summarization, and analysis.

中文定位：

> 一套以金融消費評議中心人壽保險評議決定書為資料來源的保險評議案件搜尋與分析系統，提供全文搜尋、統計儀表板、規則式摘要與相似案件推薦功能。
