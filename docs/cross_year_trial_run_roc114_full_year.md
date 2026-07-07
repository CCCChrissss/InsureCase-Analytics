# ROC 114 全年度跨年度試跑報告

本文件記錄 ROC 114/1/1 到 ROC 114/12/31 的跨年度全年度資料試跑結果。

執行日期：2026-07-07

## 目標

本次目標是將 ROC 114 從一月小期間試跑擴大為全年度資料，並在不覆蓋正式展示 DB 的前提下，建立跨年度 trial DB。

正式展示 DB 仍維持：

```text
backend/data/insurance_cases.db
```

本次 trial DB：

```text
backend/data/insurance_cases_cross_year_trial.db
```

## 查詢條件

- 年度：ROC 114
- 期間：ROC 114/1/1 到 ROC 114/12/31
- 產業：保險業
- 保險類別：人壽保險
- 文件類型：評議決定書
- 評議結果：未指定，等同全部

## Metadata 爬蟲

執行指令：

```powershell
py .\foi_ods_life_mvp_crawler.py --roc-year 114 --start-month 1 --start-day 1 --end-month 12 --end-day 31
```

輸出：

```text
data/foi_ods/metadata/foi_ods_life_roc114_metadata.json
```

結果：

- records：2500
- batches：729
- duplicate case number count：0
- expected records from leaf batches：2500
- required field errors：0
- 實際 `decision_date` 範圍：`114.01.16` 到 `114.12.26`
- 爭議類型：41 種

前十大爭議類型：

| 爭議類型 | 筆數 |
| --- | ---: |
| 必要性醫療 | 786 |
| 理賠金額認定 | 203 |
| 手術認定 | 183 |
| 承保範圍 | 174 |
| 投保時已患疾病或在妊娠中 | 170 |
| 業務招攬爭議 | 148 |
| 事故發生原因認定 | 114 |
| 除外責任 | 101 |
| 失能或豁免保費體況認定 | 72 |
| 違反告知義務 | 66 |

## 資料品質檢查

執行指令：

```powershell
py .\backend\scripts\check_data_quality.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json
```

結果：

- `issue_count`：0
- `passed`：true

## PDF 下載與文字抽取

執行指令：

```powershell
py .\foi_ods_pdf_text_pipeline.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json
```

輸出：

```text
data/foi_ods/metadata/foi_ods_life_roc114_pdf_text_report.json
```

結果：

- record count：2500
- success count：2500
- failure count：0
- file validation error count：0

## 案件資料夾整理

執行指令：

```powershell
py .\foi_ods_case_organizer.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json
```

輸出：

```text
data/foi_ods/metadata/foi_ods_life_roc114_case_organize_report.json
data/foi_ods/cases/roc114/
```

結果：

- record count：2500
- success count：2500
- failure count：0
- validation error count：0

整理後檔案數：

- `decision.pdf`：2500
- `raw_text.txt`：2500
- `normalized_text.txt`：2500
- `metadata.json`：2500
- 異常路徑數：0

## 跨年度 Trial DB

匯入指令：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json --metadata .\data\foi_ods\metadata\foi_ods_life_roc115_metadata.json --db .\backend\data\insurance_cases_cross_year_trial.db --recreate
```

結果：

- ROC 114：2500
- ROC 115：492
- total：2992
- success count：2992
- failure count：0
- `cases`：2992
- `case_texts`：2992
- `case_search`：2992

摘要重建指令：

```powershell
py .\backend\scripts\extract_case_summaries.py --db .\backend\data\insurance_cases_cross_year_trial.db
```

摘要結果：

- `processed_count`：2992
- `total_summaries`：2992
- `holding`：2992
- `applicant_claim`：2992
- `reasoning`：2992
- `empty_case_count`：0

補充說明：

- 第一次重建時，8 筆 `違反告知義務` 案件的申請人主張欄位未命中，原因是原文標題為「二、申請人主張」，少了「之」。
- 第一次重建時，1 筆 `必要性醫療` 案件的判斷理由欄位未命中，原因是原文標題為「四、判斷理由」，不是原規則預期的「六、判斷理由」。
- 已修正 `backend/scripts/extract_case_summaries.py`，並重新抽取 trial DB 摘要；目前三個摘要欄位均為 2992/2992。
- 已新增 regression tests，避免上述兩種格式變異再次退化。

## 驗證結果

trial DB 驗證：

```powershell
py .\backend\scripts\verify_case_db.py --db .\backend\data\insurance_cases_cross_year_trial.db --expected-count 2992
```

結果：

- `cases`：2992
- `case_texts`：2992
- `case_search`：2992
- `case_summaries`：2992
- `path_error_count`：0
- `passed`：true

跨年度品質檢查：

```powershell
py .\backend\scripts\check_data_quality.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json --metadata .\data\foi_ods\metadata\foi_ods_life_roc115_metadata.json --db .\backend\data\insurance_cases_cross_year_trial.db
```

結果：

- `issue_count`：0
- `passed`：true

正式展示 DB 驗證：

```powershell
py .\backend\scripts\verify_case_db.py
```

結果：

- `backend/data/insurance_cases.db` 仍維持 ROC 115 共 492 筆。
- `case_summaries` 仍為 492 筆。
- `passed`：true。

## 結論

ROC 114 全年度資料已完成 metadata、PDF/text、case organizer、trial DB 匯入與摘要重建。

目前可確認：

- ROC 114 全年度資料可處理到 trial DB。
- 跨年度 trial DB 共 2992 筆。
- trial DB 規則式摘要三個欄位 `holding`、`applicant_claim`、`reasoning` 均已補齊到 2992 筆。
- 資料品質檢查通過，沒有 mojibake 類異常字元。
- 正式展示 DB 尚未切換，前端預設仍使用 ROC 115 的 492 筆。

建議下一步：

1. 抽樣檢查 ROC 114 摘要與相似案件品質。
2. 決定是否將正式展示 DB 切換為跨年度 trial DB。
3. 若切換正式 DB，需同步驗證前端年度篩選、統計頁與搜尋頁效能。
4. 再考慮試跑 ROC 116 小期間。
