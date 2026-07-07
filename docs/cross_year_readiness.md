# 跨年度資料匯入前檢查報告

本文件檢查目前專案是否已準備好擴充 ROC 114、ROC 116 或其他年度資料。

檢查範圍只包含程式碼與文件：

- `foi_ods_life_mvp_crawler.py`
- `foi_ods_pdf_text_pipeline.py`
- `foi_ods_case_organizer.py`
- `backend/schema.sql`
- `backend/scripts/import_cases_to_db.py`
- 後端 API 與前端年度篩選相關程式

本次沒有讀取或修改 `data/`、`outputs/`、PDF、raw text、normalized text，也沒有執行爬蟲或重建 DB。

## 結論

目前專案已具備跨年度擴充的主要前置能力，但還不等於已完成跨年度資料整合。

已可支援：

- 爬蟲可用 `--roc-year`、起訖月日查詢不同年度。
- PDF、raw text、normalized text 的 planned path 會依 `roc{year}` 分年度。
- 案件整理會依 metadata 內的年度輸出到 `data/foi_ods/cases/roc<year>/...`。
- SQLite 匯入腳本支援多個 `--metadata` 與 `--metadata-dir`。
- DB schema 有 `roc_year` 欄位與索引。
- 案件列表 API 已支援 `roc_year`。
- 統計 API 已支援 `roc_year`。
- 前端 Dashboard、案件管理、統計分析頁已支援年度篩選。

尚未完成：

- 尚未實際蒐集 ROC 114、ROC 116 或其他年度資料。
- 尚未做多年度資料匯入後的抽樣核對。
- 尚未驗證跨年度後的摘要擷取命中率。
- 尚未驗證跨年度後的規則式相似案件品質。

## 本次已修正

原本三個 pipeline 腳本的預設輸出仍偏 ROC 115，容易在跨年度操作時寫錯檔名。

已修正：

- `foi_ods_life_mvp_crawler.py`
  - `--output` 未指定時，會依 `--roc-year` 自動輸出：
    - `data/foi_ods/metadata/foi_ods_life_roc<year>_metadata.json`
- `foi_ods_pdf_text_pipeline.py`
  - `--report` 未指定時，會依 `--metadata` 檔名自動輸出：
    - `*_pdf_text_report.json`
- `foi_ods_case_organizer.py`
  - `--report` 未指定時，會依 `--metadata` 檔名自動輸出：
    - `*_case_organize_report.json`

新增測試：

- `backend/tests/test_cross_year_pipeline_defaults.py`

## case_id 與案號風險

目前 `backend/scripts/import_cases_to_db.py` 的 `case_id` 是由 `case_number` 做 SHA-1 hash 產生。

目前判斷：

- 在「人壽保險、評議決定書」這個資料範圍內，`case_number` 通常可視為案件唯一識別。
- DB schema 也有 `case_number TEXT NOT NULL UNIQUE`，重複案號會被視為同一案件更新。
- 如果同一案件在不同年度 metadata 中重複出現，現有 upsert 行為會避免重複統計。

風險：

- 若未來擴充到不同產業、不同文件類型或不同資料來源，單靠 `case_number` 可能不足以代表全域唯一。
- 若 FOI ODS 對不同文件類型重用相同案號，現有 schema 會把它們視為同一案件。

建議：

- 目前跨 ROC 114/115/116 的人壽保險評議決定書，可先維持現有 `case_id`。
- 真正擴充到其他產業或文件類型前，應評估將唯一鍵升級為：
  - `source + document_type + industry_subcategory + case_number`
  - 或新增外部來源唯一鍵欄位。

## Pipeline 檢查結果

### 爬蟲

已支援：

- `--roc-year`
- `--start-month`
- `--start-day`
- `--end-month`
- `--end-day`
- `--output`

注意：

- 預設查詢仍是 `--roc-year 115 --start-month 1 --start-day 1 --end-month 7 --end-day 1`。
- 若要抓完整年度，必須明確指定到 12/31。
- 目前文件已知 ROC 115 查詢期間到 115/7/1，但實際取得案件決定日期只到 115.03.20；跨年度展示時要區分「查詢期間」與「實際取得決定日期範圍」。

### PDF 文字 pipeline

已支援：

- 指定任意 metadata：

```powershell
py .\foi_ods_pdf_text_pipeline.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json
```

注意：

- 會回寫 metadata。
- 執行前應確認 metadata 是正確年度，且 planned path 指向 `roc<year>`。

### 案件整理

已支援：

- 指定任意 metadata。
- 依 `crawl_batch.roc_year` 或 metadata query fallback 建立 `roc<year>` 目錄。

注意：

- 會回寫 metadata。
- 執行前應確認 PDF/text pipeline 已完成。

### SQLite 匯入

已支援：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata-dir .\data\foi_ods\metadata --recreate
```

注意：

- `--metadata-dir` 只會讀取 `*_metadata.json`。
- 匯入前應先確認每個年度的 PDF/text/organized metadata 都完成。
- 匯入後需要重新產生摘要：

```powershell
py .\backend\scripts\extract_case_summaries.py
```

## 建議執行順序

### 1. 先選一個年度試跑

建議先用 ROC 114 或 ROC 116 的小期間試跑，例如 1 個月，而不是直接整年。

```powershell
py .\foi_ods_life_mvp_crawler.py --roc-year 114 --start-month 1 --start-day 1 --end-month 1 --end-day 31
```

### 2. 檢查 metadata

人工確認：

- `query.roc_year` 正確。
- `records` 不為 0。
- `validation.required_field_errors` 為空。
- `storage.metadata_path` 指向正確年度檔名。
- planned PDF/text path 都包含 `roc114` 或對應年度。

### 3. 下載 PDF 並抽文字

```powershell
py .\foi_ods_pdf_text_pipeline.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json
```

成功標準：

- `failure_count = 0`
- `file_validation_errors = []`

### 4. 整理案件資料夾

```powershell
py .\foi_ods_case_organizer.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json
```

成功標準：

- `failure_count = 0`
- `validation_error_count = 0`
- 輸出目錄為 `data/foi_ods/cases/roc114/...`

### 5. 匯入 SQLite

先備份現有 DB 或確認可重建後，再執行：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata-dir .\data\foi_ods\metadata --recreate
```

### 6. 驗證 DB

跨年度後要調整 expected count：

```powershell
py .\backend\scripts\verify_case_db.py --expected-count <跨年度總案件數>
```

### 7. 重建摘要

```powershell
py .\backend\scripts\extract_case_summaries.py
```

### 8. 前後端驗證

確認：

- Dashboard 年度下拉出現多個年度。
- 案件管理年度篩選正確。
- 統計頁年度篩選正確。
- `/api/statistics/overview?roc_year=<year>` 的數字與 DB 查詢一致。

## 開始跨年度前 Checklist

- [ ] 決定要先抓哪個年度與期間。
- [ ] 明確記錄查詢期間。
- [ ] 執行爬蟲後確認 metadata 檔名與 `query.roc_year` 一致。
- [ ] 確認 planned path 都包含正確 `roc<year>`。
- [ ] PDF/text pipeline 成功且失敗數為 0。
- [ ] case organizer 成功且輸出到正確年度資料夾。
- [ ] 匯入 DB 前確認 metadata 目錄只包含要匯入的正式 `*_metadata.json`。
- [ ] 匯入 DB 後用年度 filter 抽樣檢查。
- [ ] 重建摘要。
- [ ] 抽樣檢查摘要與相似案件品質。

## 不建議現在做的事

- 不建議還沒試跑小期間就直接抓整年。
- 不建議先改 DB schema，除非確認 `case_number` 在新範圍內不夠唯一。
- 不建議直接引入 PostgreSQL / pgvector；目前跨年度前置仍可用 SQLite 驗證。
- 不建議在未完成跨年度抽樣驗證前，把展示資料說成完整年度資料。
