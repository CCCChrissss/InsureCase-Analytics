# 保險評議分析系統專案計畫

## 1. 專案目標

建立一個保險評議分析系統，將 FOI ODS 人壽保險評議決定書從 PDF 與文字檔，整理成可查詢、可統計、可閱讀、可比對相似案件的分析平台。

系統目標分為三層：

1. 資料管理：管理案件 metadata、PDF、raw text、normalized text。
2. 查詢分析：依年度、爭議類型、案號、關鍵字搜尋案件。
3. 智慧輔助：提供案件摘要與相似案件搜尋，輔助使用者理解爭議脈絡。

## 2. 使用情境

主要使用者：

- 學生：展示資料蒐集、資料整理、搜尋與分析成果。
- 開發者：建立可維護的資料處理與查詢系統。
- 研究者或一般使用者：查找特定爭議類型或相似評議案件。

典型流程：

1. 使用者進入 Dashboard，看目前資料量與爭議類型分布。
2. 使用者依爭議類型篩選案件，例如「必要性醫療」。
3. 使用者輸入關鍵字，例如「癌症」、「手術」、「除外責任」。
4. 使用者點進案件詳情，看 metadata、主文、全文與 PDF。
5. 系統顯示摘要與相似案件，協助比較案例。

## 3. MVP 範圍

MVP 必須完成：

- 案件資料匯入 SQLite。
- 案件列表。
- 年度、爭議類型、案號查詢。
- 關鍵字全文搜尋。
- 案件詳情頁。
- PDF 連結或下載。
- 爭議類型統計。
- 決定日期統計。
- 規則式案件摘要。

MVP 暫不納入：

- OCR。
- LLM 自動摘要。
- 向量資料庫。
- 使用者登入。
- 跨年度資料整併。
- 複雜權限管理。

原因：第一版應先完成可展示、可驗證、可維護的查詢系統，不宜過早導入過重架構。

## 4. 建議技術架構

學校專題版：

```text
Python scripts
  ↓
SQLite + FTS5
  ↓
FastAPI
  ↓
React + Vite
  ↓
Dashboard / Search / Case Detail
```

實務版：

```text
Pipeline jobs
  ↓
PostgreSQL + Full Text Search + pgvector
  ↓
FastAPI
  ↓
React / Next.js
  ↓
Docker / CI / deployment
```

建議先做學校專題版，但資料表、API 與 pipeline 不要寫死單一年份。

## 5. 資料庫設計

MVP 使用 SQLite。

### cases

```sql
CREATE TABLE cases (
  case_id TEXT PRIMARY KEY,
  case_number TEXT NOT NULL UNIQUE,
  roc_year INTEGER NOT NULL,
  decision_date TEXT,
  decision_category TEXT,
  decision_result TEXT,
  industry TEXT,
  industry_subcategory TEXT,
  dispute_type TEXT,
  source_pdf_url TEXT,
  case_directory TEXT,
  pdf_path TEXT,
  raw_text_path TEXT,
  normalized_text_path TEXT,
  metadata_path TEXT,
  created_at TEXT,
  updated_at TEXT
);
```

### case_texts

```sql
CREATE TABLE case_texts (
  case_id TEXT PRIMARY KEY,
  raw_text TEXT,
  normalized_text TEXT,
  raw_text_chars INTEGER,
  normalized_text_chars INTEGER,
  page_count INTEGER,
  extraction_method TEXT,
  FOREIGN KEY(case_id) REFERENCES cases(case_id)
);
```

### case_summaries

```sql
CREATE TABLE case_summaries (
  case_id TEXT PRIMARY KEY,
  holding TEXT,
  applicant_claim TEXT,
  reasoning TEXT,
  summary_method TEXT,
  created_at TEXT,
  FOREIGN KEY(case_id) REFERENCES cases(case_id)
);
```

### case_search

```sql
CREATE VIRTUAL TABLE case_search USING fts5(
  case_id UNINDEXED,
  case_number,
  dispute_type,
  normalized_text
);
```

SQLite FTS5 是 SQLite 官方提供的 full-text search virtual table module，適合 MVP 階段做本機全文搜尋。

## 6. 搜尋設計

MVP 搜尋分三層：

1. 結構化搜尋：年度、爭議類型、案號、決定日期。
2. 全文搜尋：使用 SQLite FTS5 查詢 `normalized_text`。
3. 中文 fallback 搜尋：保留 `LIKE` 查詢，避免中文斷詞造成找不到結果。

搜尋結果至少回傳：

```json
{
  "case_id": "...",
  "case_number": "114年評字第005xxx號",
  "decision_date": "115.03.20",
  "dispute_type": "必要性醫療",
  "snippet": "...命中的文字片段..."
}
```

## 7. 向量搜尋設計

向量搜尋放在第三階段，不放入 MVP。

流程：

1. 將每份 `normalized_text.txt` 切成 chunk。
2. 每個 chunk 約 500 到 1,000 中文字。
3. 為每個 chunk 產生 embedding。
4. 查詢時將使用者問題轉成 embedding。
5. 計算 cosine similarity。
6. 回傳相似案件 top 5 或 top 10。

MVP 延伸版可先用 SQLite 或 JSON 儲存 embedding。實務版改用 PostgreSQL + pgvector。

## 8. 後端 API 規劃

MVP API：

```text
GET /api/health
GET /api/cases
GET /api/cases/{case_id}
GET /api/dispute-types
GET /api/search
GET /api/statistics/overview
GET /api/statistics/dispute-types
GET /api/statistics/decision-dates
GET /api/files/{case_id}/pdf
```

後續 API：

```text
GET /api/cases/{case_id}/summary
GET /api/cases/{case_id}/similar
POST /api/admin/reindex
POST /api/admin/import
```

FastAPI 適合本專案，因為它支援 OpenAPI，並可提供互動式 API 文件，方便專題展示與前後端協作。

## 9. 前端頁面規劃

MVP 頁面：

1. Dashboard：總案件數、爭議類型數、前十大爭議類型、日期分布。
2. 案件列表頁：年度、爭議類型、案號搜尋、分頁。
3. 全文搜尋頁：關鍵字搜尋、命中片段、點擊進入詳情。
4. 案件詳情頁：案號、決定日期、爭議類型、評議結果、摘要、全文、PDF。
5. 統計頁：爭議類型長條圖、日期趨勢圖、案件數統計表。

第二階段再加：

- 相似案件區塊。
- 案件摘要卡片。
- 案件比較頁。

## 10. 學校專題版與實務版差異

學校專題版可接受：

- SQLite。
- 本機資料夾。
- FastAPI + React。
- 規則式摘要。
- 簡單全文搜尋。
- 本機 demo。

實務版應要求：

- PostgreSQL。
- migration 管理。
- Docker。
- CI 測試。
- pipeline 可重跑。
- PostgreSQL Full Text Search。
- pgvector 向量搜尋。
- OCR fallback。
- log 與錯誤監控。

## 11. 主要風險

1. Git 狀態異常：目前 `.git` 目錄存在但內容為空，`git status` 仍回報不是有效 repository。
2. 中文搜尋品質：SQLite FTS5 對中文斷詞有限，MVP 需搭配 `LIKE` fallback。
3. 摘要可靠性：評議書屬金融法律文件，摘要需可回溯原文。
4. OCR 缺口：目前資料可抽文字，但未來掃描 PDF 需要 OCR。
5. 資料期間說明：查詢期間與實際取得案件決定日期範圍要分開說明。

## 12. 參考依據

- SQLite FTS5 官方文件：https://www.sqlite.org/fts5.html
- FastAPI 官方文件：https://fastapi.tiangolo.com/
- PostgreSQL Full Text Search 官方文件：https://www.postgresql.org/docs/current/textsearch.html
- pgvector 官方專案：https://github.com/pgvector/pgvector
