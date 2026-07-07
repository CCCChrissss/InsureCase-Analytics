# ROC 114 一月跨年度試跑報告

本文件記錄 ROC 114/1/1 到 ROC 114/1/31 的跨年度小期間試跑結果。

執行日期：2026-07-07

## 目標

本次試跑目標是確認跨年度 pipeline 是否可在不影響現有 ROC 115 SQLite 展示資料的前提下，正確新增 ROC 114 資料產物。

原始試跑沒有執行：

- SQLite 匯入。
- 摘要重建。
- 後端 API 資料切換。
- 前端資料展示切換。
- Git 提交 `data/` 產物。

後續已補做跨年度測試 SQLite DB 匯入與摘要重建；正式展示 DB 仍維持 ROC 115 版本。

## 執行範圍

查詢條件：

- 年度：ROC 114
- 期間：ROC 114/1/1 到 ROC 114/1/31
- 產業：保險業
- 保險類別：人壽保險
- 文件類型：評議決定書

## 執行指令

### 1. Metadata 爬蟲

```powershell
py .\foi_ods_life_mvp_crawler.py --roc-year 114 --start-month 1 --start-day 1 --end-month 1 --end-day 31
```

輸出：

```text
data/foi_ods/metadata/foi_ods_life_roc114_metadata.json
```

結果：

- records：112
- batches：53
- duplicate case number count：0
- required field error count：0
- 實際 `decision_date` 範圍：`114.01.16` 到 `114.01.16`
- planned path 均指向 `roc114`

### 2. PDF 下載與文字抽取

```powershell
py .\foi_ods_pdf_text_pipeline.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json
```

輸出：

```text
data/foi_ods/metadata/foi_ods_life_roc114_pdf_text_report.json
```

結果：

- record count：112
- success count：112
- failure count：0
- file validation error count：0

### 3. 案件資料夾整理

```powershell
py .\foi_ods_case_organizer.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json
```

輸出：

```text
data/foi_ods/metadata/foi_ods_life_roc114_case_organize_report.json
data/foi_ods/cases/roc114/
```

結果：

- record count：112
- success count：112
- failure count：0
- validation error count：0
- year counts：ROC 114 = 112

整理後檔案數：

- `decision.pdf`：112
- `raw_text.txt`：112
- `normalized_text.txt`：112
- `metadata.json`：112

## 觀察

### 已驗證成功

- 爬蟲預設 metadata 檔名會依 `--roc-year 114` 輸出到 ROC 114 檔名。
- planned PDF/text path 會使用 `roc114`。
- PDF/text pipeline 的 report 檔名會依 ROC 114 metadata 自動推導。
- case organizer 的 report 檔名會依 ROC 114 metadata 自動推導。
- case organizer 會整理到 `data/foi_ods/cases/roc114/`。
- `data/` 產物未進入 Git tracked changes。

### 執行環境注意事項

在受限 sandbox 下，直接執行網路請求會被代理到 `127.0.0.1:9` 並造成 `ProxyError`。本次爬蟲與 PDF 下載在升權網路環境下執行成功。

這是執行環境限制，不是 FOI ODS 或 pipeline 邏輯錯誤。

## 尚未做的事

本次仍未把 ROC 114 資料匯入正式 SQLite DB。

原因：

- 目前 `backend/data/insurance_cases.db` 是 ROC 115 展示用資料庫。
- 直接 `--recreate` 會改變目前展示資料。
- 跨年度匯入前應先決定是否要建立備份或產生另一個測試 DB。

## 跨年度測試 DB 結果

已建立跨年度測試 DB，沒有覆蓋目前展示用 DB。

```text
backend/data/insurance_cases_cross_year_trial.db
```

匯入指令：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json --metadata .\data\foi_ods\metadata\foi_ods_life_roc115_metadata.json --db .\backend\data\insurance_cases_cross_year_trial.db --recreate
```

驗證指令：

```powershell
py .\backend\scripts\verify_case_db.py --db .\backend\data\insurance_cases_cross_year_trial.db --expected-count 604
```

驗證結果：

- ROC 115 目前為 492 筆。
- ROC 114 一月試跑為 112 筆。
- 跨年度測試 DB 總數為 604 筆。
- `cases`：604。
- `case_texts`：604。
- `case_search`：604。
- `path_error_count`：0。
- `passed`：true。

年度分布：

- ROC 114：112。
- ROC 115：492。

正式展示 DB 驗證結果：

- `backend/data/insurance_cases.db` 仍為 492 筆。
- `case_summaries` 仍為 492 筆。
- `passed`：true。

### 摘要重建結果

```powershell
py .\backend\scripts\extract_case_summaries.py --db .\backend\data\insurance_cases_cross_year_trial.db
```

結果：

- `processed_count`：604。
- `total_summaries`：604。
- `holding`：604。
- `applicant_claim`：604。
- `reasoning`：604。
- `empty_case_count`：0。

## 資料品質注意事項

跨年度測試 DB 建立成功，但 ROC 114 一月資料中發現 32 筆 metadata 與整理後路徑存在亂碼，集中在同一個爭議類型。

已確認：

- ROC 114 metadata 總數仍為 112。
- trial DB 總數仍為 604。
- 亂碼資料列的 PDF/text/metadata 檔案路徑存在，`path_error_count` 為 0。
- 問題影響案號與爭議類型文字品質，不是 SQLite 匯入筆數失敗。

下一步不建議直接把 trial DB 切成正式展示 DB，應先處理 ROC 114 亂碼資料來源或補做資料清理驗證。

## 建議下一步

建議先處理資料品質，再擴大抓取：

1. 追查 ROC 114 亂碼來源，優先確認爬蟲回應編碼、批次查詢結果與 case organizer 輸出。
2. 修正或重跑受影響的 32 筆資料。
3. 重建 `backend/data/insurance_cases_cross_year_trial.db` 並重新驗證 604 筆。
4. 驗證無亂碼後，再決定是否擴大 ROC 114 到完整年度。
5. 最後才考慮將正式展示 DB 切換為跨年度資料。

## 結論

ROC 114 一月小期間 metadata、PDF 下載、文字抽取、案件整理與跨年度 trial DB 匯入均已完成。

目前不建議直接覆蓋現有展示 DB。下一步應先修正 ROC 114 中 32 筆亂碼資料，再擴大年度資料量。
