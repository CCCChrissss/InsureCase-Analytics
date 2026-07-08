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

- 實務級 embedding model。
- ANN 向量索引。

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
- 已將正式展示 DB 切換為 ROC 114 全年度 2500 筆加 ROC 115 492 筆，共 2992 筆。
- 已備份原 ROC 115 正式 DB 至 `backend/data/insurance_cases_roc115_backup_20260707_163248.db`。
- 已用正式 DB 通過 `verify_case_db.py --expected-count 2992`、`py -m pytest` 與 `pnpm build`。
- 尚未蒐集 ROC 116 資料。

預計完成：

- 支援匯入 ROC 114、ROC 115、ROC 116。
- 實際匯入更多年度資料。
- 抽樣驗證跨年度統計。
- pipeline 可重跑且不覆蓋舊資料。
- 增加跨年度資料品質檢查，至少偵測案號與爭議類型是否含異常字元。

驗證方式：

- 新年度資料匯入不覆蓋舊資料。
- 跨年度案件數正確。
- 年度篩選正常。
- 正式 DB 年度分布為 ROC 114 = 2500、ROC 115 = 492，且異常字元檢查為 0。

## 第 7.5 階段：Embedding 前置 chunking

目標：先把長篇 normalized text 切成可追溯、可重跑、可驗證的文字 chunk，避免後續 embedding 直接吃整篇決定書而失去段落定位能力。

完成項目：

- 新增 `case_chunks` SQLite table。
- 新增 `backend/scripts/build_case_chunks.py`。
- chunk 欄位包含 `chunk_id`、`case_id`、`chunk_index`、`section_hint`、`chunk_text`、`char_start`、`char_end`、`chunk_chars`、`created_at`。
- 預設切片參數為 `target_chars=1000`、`overlap_chars=180`。
- 可辨識常見段落提示，例如主文、申請人主張、相對人主張、判斷理由與結論。
- 新增 `backend/tests/test_build_case_chunks.py`。
- `verify_case_db.py` 新增 `--require-chunks`，可驗證每筆案件都有 chunk。
- 正式 DB 已產生 17254 段 chunk，2992 筆案件皆有 chunk。

驗證方式：

```powershell
py -m py_compile .\backend\scripts\build_case_chunks.py .\backend\scripts\verify_case_db.py .\backend\scripts\import_cases_to_db.py
py -m pytest
py .\backend\scripts\build_case_chunks.py --db .\backend\data\insurance_cases.db
py .\backend\scripts\verify_case_db.py --expected-count 2992 --require-chunks
```

## 第 7.6 階段：本機 chunk embedding MVP

目標：先建立可離線、可重跑的 chunk embedding 資料流，讓後續前端可以展示語意搜尋與向量比對過程。

完成項目：

- 新增 `chunk_embeddings` SQLite table。
- 新增 `backend/app/services/embedding_service.py`。
- 新增 `backend/scripts/build_chunk_embeddings.py`。
- 新增 `backend/app/routers/semantic_search.py`。
- 新增 `GET /api/semantic-search`。
- 新增 `backend/tests/test_embedding_service.py`。
- `verify_case_db.py` 新增 `--require-embeddings`。
- 正式 DB 已產生 17254 筆 embedding，與 `case_chunks` 數量一致。

目前方法：

- 模型名稱：`local_hashing_cjk_v1`。
- 維度：384。
- 方法：CJK 2-gram / 3-gram + hashing vector + cosine similarity。
- 定位：學校專題版 MVP，不等同於 OpenAI embedding、BGE 或其他正式語意模型。

驗證方式：

```powershell
py -m py_compile .\backend\app\services\embedding_service.py .\backend\scripts\build_chunk_embeddings.py .\backend\scripts\verify_case_db.py .\backend\app\routers\semantic_search.py .\backend\app\main.py
py -m pytest
py .\backend\scripts\build_chunk_embeddings.py --db .\backend\data\insurance_cases.db
py .\backend\scripts\verify_case_db.py --expected-count 2992 --require-chunks --require-embeddings
```

## 第 7.7 階段：前端語意搜尋展示

目標：讓使用者能在網頁上看到語意搜尋的分析過程與結果，不只聽到後端已有 embedding。

完成項目：

- 新增 `frontend/src/pages/SemanticSearchPage.tsx`。
- `frontend/src/types.ts` 新增 `SemanticSearchResponse` 與 `SemanticSearchResult`。
- `frontend/src/App.tsx` 新增 `semantic` route 與側邊欄導覽。
- `frontend/src/styles.css` 新增語意搜尋表單、分析流程與結果卡片樣式。
- 頁面展示 query、embedding 模型、候選 chunk 數、命中 chunk、score、section hint 與案件來源。

驗證方式：

```powershell
py -m pytest
cd frontend
pnpm build
```

目前已驗證：

- 後端 pytest：32 passed。
- 前端 build 成功。
- Vite chunk size warning 仍存在，但不影響 build。

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
10. 建立 chunking 與本機 embedding pipeline。
11. 將語意搜尋與向量分析細節接到前端。
12. 將 chunk 層級語意結果聚合為案件層級相似案件。
13. 視需求升級為實務級 embedding model 與 ANN 向量索引。
