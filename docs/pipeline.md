# 資料處理 Pipeline

本文件記錄目前 FOI ODS 人壽保險評議資料處理流程。

## 目前資料來源

來源網站：

- https://ods.foi.org.tw/

已完成查詢條件：

- 年度：ROC 115
- 產業：保險業
- 保險類別：人壽保險
- 文件類型：評議決定書
- 查詢期間：ROC 115/1/1 到 ROC 115/7/1

目前產物：

- metadata records：492 筆
- PDF：492 份
- raw text：492 份
- normalized text：492 份
- 單案 metadata：492 份
- 失敗筆數：0

## Pipeline 步驟

### 1. 爬取 metadata 與 PDF URL

程式：

```text
foi_ods_life_mvp_crawler.py
```

功能：

- 查詢 FOI ODS。
- 取得案件 metadata。
- 取得官方 PDF URL。
- 支援月份、週、爭議類型切分。
- 避免超過網站 100 筆查詢上限。
- 輸出總 metadata JSON。

主要輸出：

```text
data/foi_ods/metadata/foi_ods_life_roc115_metadata.json
```

若指定其他 `--roc-year` 且未指定 `--output`，輸出檔名會自動改為：

```text
data/foi_ods/metadata/foi_ods_life_roc<year>_metadata.json
```

驗證重點：

- records 筆數正確。
- 無重複案號。
- 每筆都有 `case_number`、`decision_date`、`dispute_type`、`source.pdf_url`。
- required field errors 為 0。

### 2. PDF 下載與文字抽取

程式：

```text
foi_ods_pdf_text_pipeline.py
```

功能：

- 下載官方 PDF。
- 使用 `pdfplumber` 抽取文字。
- 若 `pdfplumber` 失敗，fallback 到 `pypdf`。
- 產生 raw text。
- 產生 normalized text。
- 回寫 metadata。
- 產生處理 report。

主要輸出：

```text
data/foi_ods/metadata/foi_ods_life_roc115_pdf_text_report.json
```

若指定其他年度 metadata 且未指定 `--report`，report 檔名會依 metadata 檔名自動推導為 `*_pdf_text_report.json`。

驗證重點：

- `success_count` = 492。
- `failure_count` = 0。
- `file_validation_errors` = 0。
- 每筆案件都有 PDF、raw text、normalized text。

### 3. 案件資料夾整理

程式：

```text
foi_ods_case_organizer.py
```

功能：

- 依照「年度 → 爭議類型 → 案件」整理資料。
- 每案建立獨立資料夾。
- 每案輸出：
  - `decision.pdf`
  - `raw_text.txt`
  - `normalized_text.txt`
  - `metadata.json`
- 更新總 metadata 的本地檔案路徑。
- 產生整理 report。

主要輸出：

```text
data/foi_ods/cases/roc115/<爭議類型>/<案號>/
data/foi_ods/metadata/foi_ods_life_roc115_case_organize_report.json
```

若指定其他年度 metadata 且未指定 `--report`，report 檔名會依 metadata 檔名自動推導為 `*_case_organize_report.json`。

驗證重點：

- `success_count` = 492。
- `failure_count` = 0。
- `validation_errors` = 0。
- 每案四個檔案完整存在。

## 後續新增 Pipeline

### 4. 資料品質檢查

程式：

```text
backend/scripts/check_data_quality.py
```

功能：

- 檢查 metadata 與 SQLite DB 是否含 mojibake 類異常字元。
- 目前會偵測 replacement character 與 Cyrillic 字元。
- 用來避免 FOI ODS 結果頁編碼誤判後，把亂碼案號或爭議類型匯入 DB。

metadata 匯入前檢查：

```powershell
py .\backend\scripts\check_data_quality.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc115_metadata.json
```

跨年度 metadata 檢查：

```powershell
py .\backend\scripts\check_data_quality.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json --metadata .\data\foi_ods\metadata\foi_ods_life_roc115_metadata.json
```

DB 匯入後檢查：

```powershell
py .\backend\scripts\check_data_quality.py --db .\backend\data\insurance_cases.db
```

驗證：

- `issue_count` = 0。
- `passed` = true。
- 若品質檢查失敗，不要匯入或切換正式展示 DB。

### 5. 匯入 SQLite

程式：

```text
backend/scripts/import_cases_to_db.py
```

功能：

- 讀取單一或多個總 metadata。
- 讀取每案 normalized text。
- 寫入 `cases`、`case_texts`。
- 建立或更新 `case_search`。

預設輸出：

```text
backend/data/insurance_cases.db
```

執行指令：

```powershell
py .\backend\scripts\import_cases_to_db.py --recreate
```

指定多個 metadata：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json --metadata .\data\foi_ods\metadata\foi_ods_life_roc115_metadata.json --recreate
```

指定 metadata 目錄：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata-dir .\data\foi_ods\metadata --recreate
```

目錄模式只會讀取 `*_metadata.json`，避免誤讀 PDF text report 或 case organize report。

驗證：

- `cases` 筆數 = 492。
- `case_texts` 筆數 = 492。
- `case_search` 可查詢關鍵字。
- 多 metadata 匯入時，輸出 report 的 `metadata_files` 與 `metadata_sources` 應列出每個來源檔案。
- 匯入後需再次執行 `check_data_quality.py --db <db_path>`。

### 6. 建立全文搜尋索引

目前全文搜尋索引已整合在 SQLite 匯入流程中，匯入時會同步更新 `case_search` FTS5 table。

驗證程式：

```text
backend/scripts/verify_case_db.py
```

執行指令：

```powershell
py .\backend\scripts\verify_case_db.py
```

驗證：

- 搜尋「必要性醫療」有結果。
- 搜尋「癌症」有結果。
- 搜尋結果可回到正確 case。

### 7. 規則式摘要

程式：

```text
backend/scripts/extract_case_summaries.py
```

功能：

- 從 normalized text 抽取主文。
- 抽取申請人主張。
- 抽取評議理由。
- 寫入 `case_summaries`。
- 使用 `summary_method = rule_based_v1`。

執行指令：

```powershell
py .\backend\scripts\extract_case_summaries.py
```

API：

```text
GET /api/cases/{case_id}/summary
```

驗證：

- `case_summaries` 筆數應等於已處理案件數。
- API 可回傳摘要。
- 前端案件詳情頁可顯示摘要。
- 抽樣人工檢查。
- 摘要內容可回溯原文。

### 8. 向量索引

規則式相似案件搜尋已先作為 baseline 完成。

目前 API：

```text
GET /api/cases/{case_id}/similar?limit=5
```

目前依據：

- 相同爭議類型。
- 相同評議結果。
- 相同決定類別。
- 摘要文字中的保險關鍵詞重疊。

後續再新增向量索引。

預計新增：

```text
backend/scripts/build_embeddings.py
```

功能：

- 將 normalized text 切成 chunks。
- 產生 embedding。
- 建立相似案件搜尋資料。

驗證：

- 任一案件可查 top 5 相似案件。
- 回傳結果附相似段落。

## Pipeline 注意事項

1. 不要直接覆蓋原始資料，除非明確指定。
2. 匯入資料庫時要設計成可重跑。
3. metadata 完成後先跑 `check_data_quality.py --metadata`。
4. SQLite 匯入後再跑 `check_data_quality.py --db`。
5. 每個階段都要產生 report 或可查驗的統計結果。
6. metadata 的檔案路徑更新要保持一致。
7. 未來跨年度時，資料夾與資料庫都不可寫死 `roc115`。
8. 目前匯入腳本已支援多 metadata，但不代表其他年度資料已經完成蒐集與匯入。

## API 讀取流程

第 2 階段 API 不直接讀取 PDF 或 JSON metadata 作為主要查詢來源，而是讀取第 1 階段建立的 SQLite DB。

```text
data/foi_ods/cases
  ↓ import_cases_to_db.py
backend/data/insurance_cases.db
  ↓ FastAPI services
GET /api/cases
GET /api/search
GET /api/statistics/*
```

啟動 API：

```powershell
py -m uvicorn backend.app.main:app --reload
```

API 驗證重點：

- `/api/health` 的 `database_ready` 應為 `true`。
- `/api/statistics/overview` 的 `case_count` 應為 492。
- `/api/search?q=癌症` 應有搜尋結果。

## 前端讀取流程

第 3 階段前端使用 React + Vite，透過 HTTP 呼叫 FastAPI。

```text
React frontend
  ↓ fetch
FastAPI /api/*
  ↓ sqlite3
backend/data/insurance_cases.db
```

啟動順序：

1. 確認 SQLite DB 已建立。
2. 啟動 FastAPI：`py -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`
3. 啟動前端：`pnpm dev`
4. 開啟 `http://127.0.0.1:5173`
