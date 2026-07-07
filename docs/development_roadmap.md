# 開發路線

## 第 0 階段：專案基礎整理

目標：建立專案文件與開發基準。

完成項目：

- 確認 Git 狀態。
- 建立 `README.md`。
- 建立 `docs/project_plan.md`。
- 建立 `docs/development_roadmap.md`。
- 建立 `docs/pipeline.md`。

驗證方式：

- `README.md` 能說明專案目標、目前資料狀態與後續方向。
- `docs/` 內有完整計畫、開發路線與 pipeline 說明。
- Git 狀態已被確認並記錄。

目前狀態：

- `.git` 目錄存在但內容為空，`git status` 回報不是有效 repository。
- 文件可先建立，Git 修正需另行處理。

## 第 1 階段：SQLite 資料庫匯入

目標：將 492 筆案件匯入 SQLite，建立查詢與搜尋基礎。

完成項目：

- 建立 SQLite schema。
- 匯入 `cases`。
- 匯入 `case_texts`。
- 建立 `case_search` FTS5 index。
- 建立資料匯入腳本。

新增檔案：

- `backend/scripts/import_cases_to_db.py`
- `backend/scripts/verify_case_db.py`
- `backend/app/database.py`
- `backend/schema.sql`

驗證方式：

```powershell
py .\backend\scripts\import_cases_to_db.py --recreate
py .\backend\scripts\verify_case_db.py
```

成功標準：

- `cases` 筆數 = 492。
- `case_texts` 筆數 = 492。
- `case_search` 可搜尋「必要性醫療」、「癌症」、「除外責任」。
- 每筆案件都能查到 PDF 路徑與 normalized text。

## 第 2 階段：FastAPI 後端

目標：提供案件查詢、搜尋與統計 API。

完成項目：

- 建立 FastAPI app。
- 案件列表 API。
- 案件詳情 API。
- 全文搜尋 API。
- 統計 API。
- PDF 檔案讀取 API。

新增檔案：

- `backend/app/main.py`
- `backend/app/routers/cases.py`
- `backend/app/routers/search.py`
- `backend/app/routers/statistics.py`
- `backend/app/schemas.py`
- `backend/app/services/case_service.py`
- `backend/app/services/search_service.py`
- `backend/app/services/statistics_service.py`

驗證方式：

- `/api/health` 回傳正常。
- `/docs` 可開啟。
- `/api/cases` 回傳分頁資料。
- `/api/search?q=癌症` 有搜尋結果。
- `/api/statistics/dispute-types` 數量總和 = 492。

## 第 3 階段：React 前端 MVP

目標：建立可展示的前端介面。

完成項目：

- Dashboard。
- 案件列表頁。
- 搜尋頁。
- 案件詳情頁。
- 統計頁。

新增檔案：

- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/src/main.tsx`
- `frontend/src/styles.css`

驗證方式：

- 首頁能顯示案件總數 492。
- 可依爭議類型篩選案件。
- 可用關鍵字搜尋。
- 可點進案件詳情。
- PDF 連結可用。
- 統計圖表數量與 API 一致。

## 第 4 階段：規則式摘要

目標：從 normalized text 擷取案件重點。

完成項目：

- 擷取主文。
- 擷取申請人主張。
- 擷取評議理由。
- 儲存至 `case_summaries`。
- 案件詳情頁顯示摘要。

新增檔案：

- `backend/scripts/extract_case_summaries.py`
- `backend/app/routers/summaries.py`
- `backend/app/services/summary_service.py`
- `backend/tests/test_summary_service.py`

修改檔案：

- `backend/app/main.py`
- `backend/app/schemas.py`
- `frontend/src/main.tsx`
- `frontend/src/styles.css`

驗證方式：

- `py .\backend\scripts\extract_case_summaries.py`
- `py -m pytest`
- `pnpm build`
- 抽樣案件人工檢查。
- 大多數案件能抽出主文、申請人主張與判斷理由。
- 摘要內容可回溯原文。
- 沒有產生原文不存在的結論。

## 第 5 階段：相似案件搜尋

目標：讓使用者可從單一案件找到相似案例。

完成項目：

- 規則式相似度計分。
- 相似案件 API。
- 詳情頁顯示 top 5 相似案件。

相似度依據：

- 相同爭議類型。
- 相同評議結果。
- 相同決定類別。
- 摘要文字中的保險關鍵詞重疊。

新增檔案：

- `backend/app/routers/similar_cases.py`
- `backend/app/services/similar_case_service.py`
- `backend/tests/test_similar_case_service.py`

後續再做：

- normalized text chunking。
- embedding 建立。
- 相似案件 API。
- 向量搜尋。

驗證方式：

- 任一案件可回傳 top 5 相似案件。
- 相似案件多數落在相近爭議類型。
- 回傳結果顯示分數與命中原因。

## 第 6 階段：前端結構整理

目標：降低前端單檔維護成本，讓後續 embedding、跨年度與部署功能更容易擴充。

完成項目：

- 將 `frontend/src/main.tsx` 縮小為 app 掛載入口。
- 新增 `frontend/src/App.tsx` 作為主版面與 route state 管理。
- 新增 `frontend/src/api/client.ts` 管理 API base 與 fetch helper。
- 新增 `frontend/src/types.ts` 集中 API response 型別。
- 新增 `frontend/src/hooks/useAsyncData.ts`。
- 新增 `frontend/src/components/` 放共用 UI 與案件詳情元件。
- 新增 `frontend/src/pages/` 放 Dashboard、案件、搜尋、統計頁。
- 使用 URL query 同步目前頁面與選中案件，例如 `?view=cases&case_id=<case_id>`。

驗證方式：

- `pnpm build` 成功。
- 既有頁面與 API 行為不變。
- 案件詳情 URL 可分享，重新整理後可回到同一案件。

## 第 7 階段：跨年度擴充

目標：支援更多年度與後續資料更新。

目前進度：

- 已完成匯入腳本前置能力，可指定多個 `--metadata` 或使用 `--metadata-dir` 匯入多個 `*_metadata.json`。
- 已完成統計 API 的 `roc_year` 篩選。
- 已完成 Dashboard、案件管理與統計分析頁的年度篩選 UI。
- 已完成跨年度 readiness 檢查報告。
- 已修正爬蟲、PDF 文字 pipeline、案件整理 pipeline 的跨年度預設輸出檔名。
- 已完成 ROC 114 一月小期間試跑，metadata、PDF 文字抽取與案件整理均成功 112 筆。
- 已完成 ROC 114 一月跨年度 trial DB 試跑，當時為 ROC 114 一月 112 筆加 ROC 115 492 筆，共 604 筆。
- 已修正 ROC 114 一月資料中 32 筆案號、爭議類型與整理後路徑亂碼問題。
- 已新增資料品質檢查腳本，可檢查 metadata 與 SQLite DB 是否含 mojibake 類異常字元。
- 已完成 ROC 114 全年度試跑，metadata、PDF 文字抽取與案件整理均成功 2500 筆。
- 已重建跨年度 trial DB：ROC 114 全年度 2500 筆加 ROC 115 492 筆，共 2992 筆。
- 已在 trial DB 產生 2992 筆規則式摘要。
- 跨年度 trial DB 資料品質檢查 `issue_count` 為 0。
- 已確認正式展示 DB 仍維持 ROC 115 共 492 筆，尚未切換為跨年度資料。
- 尚未蒐集 ROC 116 資料。

預計完成：

- 支援匯入 ROC 114、ROC 115、ROC 116。
- 決定是否將正式展示 DB 切換為跨年度 trial DB。
- 實際匯入更多年度資料。
- 抽樣驗證跨年度統計。
- pipeline 可重跑且不覆蓋舊資料。
- 增加跨年度資料品質檢查，至少偵測案號與爭議類型是否含異常字元。

驗證方式：

- 新年度資料匯入不覆蓋舊資料。
- 跨年度案件數正確。
- 年度篩選正常。
- trial DB 年度分布為 ROC 114 = 2500、ROC 115 = 492，且異常字元檢查為 0。

## 建議執行順序

1. 完成第 0 階段文件與 Git 狀態處理。
2. 實作 SQLite 匯入。
3. 實作 FastAPI。
4. 實作 React 前端。
5. 加入規則式摘要。
6. 加入相似案件搜尋。
7. 整理前端結構。
8. 擴充跨年度資料。
9. 將資料品質檢查納入固定 pipeline。
10. 視需求導入 embedding 相似案件搜尋。
