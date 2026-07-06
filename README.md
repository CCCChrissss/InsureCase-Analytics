# 保險評議分析系統

本專案目標是將金融消費評議中心 FOI ODS 的人壽保險評議決定書，整理成可查詢、可統計、可閱讀、後續可做相似案件搜尋的分析系統。

目前專案已完成第一階段資料蒐集與整理，後續開發重點會從資料管理、全文搜尋、案件詳情頁與統計儀表板開始，再逐步擴充摘要與相似案件搜尋。

## 目前資料狀態

資料來源：

- https://ods.foi.org.tw/

已完成查詢條件：

- 年度：ROC 115
- 產業：保險業
- 保險類別：人壽保險
- 文件類型：評議決定書
- 查詢期間：ROC 115/1/1 到 ROC 115/7/1

目前本地資料狀態：

- metadata records：492 筆
- PDF：492 份
- raw text：492 份
- normalized text：492 份
- 單案 metadata：492 份
- 爭議類型：35 種
- PDF 文字抽取失敗筆數：0
- 案件整理失敗筆數：0

注意：查詢期間是 ROC 115/1/1 到 ROC 115/7/1，但目前 metadata records 內的 `decision_date` 實際範圍是 `115.01.09` 到 `115.03.20`。展示與文件中應區分「查詢期間」與「實際取得案件決定日期範圍」。

## 目前資料結構

```text
data/
  foi_ods/
    cases/
      roc115/
        <爭議類型>/
          <案號>/
            decision.pdf
            raw_text.txt
            normalized_text.txt
            metadata.json

    metadata/
      foi_ods_life_roc115_metadata.json
      foi_ods_life_roc115_pdf_text_report.json
      foi_ods_life_roc115_case_organize_report.json
```

## 目前程式

```text
foi_ods_life_mvp_crawler.py
```

負責查詢 FOI ODS、取得案件 metadata 與 PDF URL，並支援月份、週、爭議類型切分，避免超過網站單次查詢 100 筆上限。

```text
foi_ods_pdf_text_pipeline.py
```

負責下載 PDF、使用 `pdfplumber` 抽取文字、產生 raw text 與 normalized text，並回寫 metadata。

```text
foi_ods_case_organizer.py
```

負責依照「年度 → 爭議類型 → 案件」整理資料夾，產生每案 `metadata.json`，並更新總 metadata 的本地檔案路徑。

## 後續開發方向

MVP 優先完成：

1. SQLite 資料庫匯入。
2. SQLite FTS5 全文搜尋。
3. FastAPI 後端 API。
4. React 前端 Dashboard、案件列表、搜尋頁、案件詳情頁。
5. 規則式案件摘要。

後續再擴充：

1. 相似案件搜尋。
2. 向量搜尋。
3. 跨年度資料整合。
4. OCR fallback。
5. PostgreSQL + pgvector 實務版架構。

## 文件

- [完整專案計畫](docs/project_plan.md)
- [開發路線](docs/development_roadmap.md)
- [資料處理 Pipeline](docs/pipeline.md)

## SQLite 匯入

第 1 階段新增 SQLite 匯入流程，預設會讀取：

```text
data/foi_ods/metadata/foi_ods_life_roc115_metadata.json
```

並建立：

```text
backend/data/insurance_cases.db
```

匯入指令：

```powershell
py .\backend\scripts\import_cases_to_db.py --recreate
```

驗證指令：

```powershell
py .\backend\scripts\verify_case_db.py
```

成功標準：

- `cases` = 492
- `case_texts` = 492
- `case_search` = 492
- `data/` 內原始案件資料不會被修改
- `backend/data/insurance_cases.db` 是本機產物，不提交 Git

## FastAPI 後端

第 2 階段新增唯讀 API，啟動前請先安裝相依套件：

```powershell
py -m pip install -r requirements.txt
```

啟動 API：

```powershell
py -m uvicorn backend.app.main:app --reload
```

啟動後可開啟：

```text
http://127.0.0.1:8000/docs
```

目前主要 endpoint：

```text
GET /api/health
GET /api/cases
GET /api/cases/{case_id}
GET /api/dispute-types
GET /api/search?q=癌症
GET /api/statistics/overview
GET /api/statistics/dispute-types
GET /api/statistics/decision-dates
GET /api/files/{case_id}/pdf
```

## React 前端

第 3 階段新增 React + Vite 前端 MVP。

前端目錄：

```text
frontend/
```

安裝相依套件：

```powershell
cd frontend
pnpm install
```

啟動前端：

```powershell
pnpm dev
```

預設網址：

```text
http://127.0.0.1:5173
```

前端會呼叫：

```text
http://127.0.0.1:8000/api
```

目前頁面：

- Dashboard：案件數、爭議類型、日期分布。
- 案件管理：篩選、分頁、案件詳情、PDF 連結。
- 全文搜尋：關鍵字搜尋與命中片段。
- 統計分析：爭議類型與決定日期統計。

## 目前待處理事項

- 尚未建立自動化測試。
