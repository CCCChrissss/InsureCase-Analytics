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

跨年度測試 DB 建立後，曾發現 ROC 114 一月資料中有 32 筆 metadata 與整理後路徑存在亂碼，集中在「必要性醫療」爭議類型。

根因：

- FOI ODS 結果頁明確回傳 `charset=utf-8`。
- `requests.Response.apparent_encoding` 對 ROC 114/1/16「必要性醫療」結果頁誤判為 `MacCyrillic`。
- 舊版爬蟲用 `apparent_encoding` 覆蓋 header charset，導致中文案號與爭議類型被解成 Cyrillic 亂碼。

已確認：

- ROC 114 metadata 總數仍為 112。
- trial DB 總數仍為 604。
- 修正爬蟲後，ROC 114 metadata 品質檢查 `issue_count` 為 0。
- ROC 114 `data/foi_ods/cases/roc114/` 內 `decision.pdf`、`raw_text.txt`、`normalized_text.txt`、`metadata.json` 均為 112 份。
- 跨年度 trial DB 品質檢查 `issue_count` 為 0。
- trial DB 年度分布仍為 ROC 114 = 112、ROC 115 = 492。
- ROC 114「必要性醫療」案件為 32 筆。

已新增 `backend/scripts/check_data_quality.py`，可檢查 metadata 與 SQLite DB 是否含異常 Cyrillic 或 replacement character。

## 建議下一步

資料品質問題已修正。後續建議：

1. 擴大 ROC 114 到完整年度前，先把 `check_data_quality.py` 納入每次 pipeline 驗證。
2. 重跑其他年度時，若品質檢查失敗，不要匯入正式 DB。
3. 再決定是否擴大 ROC 114 到完整年度。
4. 最後才考慮將正式展示 DB 切換為跨年度資料。

## 結論

ROC 114 一月小期間 metadata、PDF 下載、文字抽取、案件整理與跨年度 trial DB 匯入均已完成。

ROC 114 中 32 筆亂碼資料已修正，跨年度 trial DB 已重建並通過資料品質檢查。

正式展示 DB 仍未切換；下一步可以開始規劃擴大 ROC 114 完整年度，或先把資料品質檢查整合成固定 pipeline 步驟。
