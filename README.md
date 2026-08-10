# InsureCase Analytics

**InsureCase Analytics** 是一套保險評議案件搜尋與查找系統，目標是將金融消費評議中心 FOI ODS 的人壽保險評議決定書整理成可依案號、年度、爭議類型、全文關鍵字與語意相似度查找的案件資料庫。

本專案目前定位為學校專題版 MVP，以本機 SQLite、FastAPI、React + Vite 建立可展示的搜尋與案件閱讀系統；後續可延伸至正式 AI embedding、OCR fallback、Docker、CI 與 PostgreSQL / pgvector 架構。

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
- React + Vite 前端案件查找工作台
- 案件列表、彈出式案件 Dashboard、正式 PDF 連結
- 全文搜尋頁
- 搜尋結果不跳頁，保留原搜尋畫面並在上層開啟案件
- 瀏覽器式多案件分頁，可切換、關閉、最小化與重新整理還原
- 年度篩選
- 規則式案件摘要
- 規則式法源擷取，只呈現明確法規條文並排除保單、附約與契約條款
- 規則式相似案件推薦
- 分析驗證頁，展示摘要與相似案件品質檢查過程
- 案件文字 chunking pipeline，作為後續 embedding 與向量搜尋前置資料
- 本機 chunk embedding MVP 與語意搜尋 API
- 全文命中案件可依關鍵字相關性或全域語意相似度排序，排序完成後再分頁
- 「計算方法」頁公開全文搜尋、搜尋相似度、相關案件、評議結果與 Precision@5 計算流程
- 前端語意搜尋頁，展示 query、embedding 模型、命中 chunk、score、section hint 與案件來源
- 案件詳情頁語意相似案件區塊，展示案件層級語意相似與命中段落
- 語意搜尋 API 支援指定 `embedding_model` / `embedding_provider`
- 後端 pytest 測試
- 案件詳情、PDF、摘要、相似案件與語意相似案件 API 測試
- 正式 AI provider 實作前測試保護，包含 fake provider、輸出筆數、維度與非有限數值檢查
- 歷史 Hugging Face API 小批量試測報告保留作比較；可送出遠端 embedding request 的程式已移除
- Hugging Face BGE 1000 筆 trial embeddings 與 local hashing 離線比較報告
- Hugging Face BGE query-to-document 小樣本試測腳本與 1000 筆 candidates 查詢報告
- 前端語意搜尋頁已標示 Local MVP 與 Hugging Face BGE Trial 狀態，避免誤認正式 DB 已切換
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
├─ requirements-local-ai.txt
├─ requirements-local-ai-cuda.txt
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
GET /api/semantic-case-scores
GET /api/semantic-ranked-search
GET /api/cases/{case_id}/summary
GET /api/cases/{case_id}/similar
GET /api/cases/{case_id}/semantic-similar
GET /api/quality/roc114-summary-similarity
GET /api/statistics/overview
```

目前前端主軸是理賠人員使用的案件工作台、全文搜尋、計算方法與彈出式案件 Dashboard。計算方法頁公開所有與畫面分數有關的公式與限制；語意搜尋與分析驗證頁仍保留 direct route，供開發與專題驗證使用。統計總覽 API 保留供案件年度選單與資料狀態使用。

從案件清單、全文搜尋或相關案件開啟案件時，不會切換背景頁面。案件工作區可同時保留多個案件分頁，並以 `sessionStorage` 保存案件 ID 與標籤；同一瀏覽器分頁重新整理可還原，但這不是帳號層級或跨裝置保存。

### Search

關鍵字搜尋採用 SQLite FTS5，並加入 LIKE fallback：

```text
FTS5 有結果 → 回傳 FTS5 結果
FTS5 報錯 → LIKE fallback
FTS5 0 筆 → LIKE fallback
```

FTS5 與 LIKE fallback 的搜尋範圍皆包含：

- 案號 `case_number`
- 爭議類型 `dispute_type`
- 正規化全文 `normalized_text`

理賠人員使用的前端搜尋頁採「全文命中加語意評分」：

```text
FTS5 / LIKE 關鍵字結果
  +
本機 BAAI/bge-large-zh-v1.5 逐案評分
  ↓
關鍵字相關性排序，或先完成全體語意排序再分頁
```

前端搜尋頁會展示：

- 查詢文字、全部命中案件數、目前頁數與總頁數，每頁可選擇 10、15 或 20 筆。
- 排序方式可選擇「關鍵字相關性」或「相似度：高到低」。
- 每筆結果的案號、決定日期、爭議類型、命中文字片段、評議結果與「與搜尋內容相近 XX%」。
- 評議結果由摘要主文保守分類為有理由、部分有理由、無理由或不受理；無法可靠分類時顯示尚未整理。
- 「相似度怎麼看」以白話說明搜尋文字、案件內容與接近程度的關係，不在理賠人員主畫面呈現模型公式。
- 點擊案件後直接開啟彈出式案件 Dashboard，背景仍保留原查詢與結果。

案件 Dashboard 以 `GET /api/cases/{case_id}/document-sections` 回傳的完整原文為主要內容，依「主文、程序事項、申請人主張、相對人主張、不爭執事項、爭點、判斷理由、綜上所述、據上論結、附註」分段。各區塊保留完整文字與原始順序，不使用規則式摘要的字數上限；後端同時回傳來源字數、涵蓋字數與 `complete_coverage` 供核對。畫面預設只展開主文與本件爭點，也可全部展開／收合。逐字全文可切換 normalized text 與 raw text，正式頁碼、表格與排版仍以 PDF 為準。

關鍵字排序時，語意評分只針對目前頁面的 10 至 20 件案件；相似度排序時，`GET /api/semantic-ranked-search` 會先取得全部關鍵字命中案件，逐案取最高 chunk cosine similarity，完成全域排序後才分頁。後端以 DB 檔案身分、查詢、provider 與 model 作為 key，最多快取最近 16 組完整排名。查詢固定指定 `local_bge` 與 `BAAI/bge-large-zh-v1.5-local`，只讀取本機模型快取與目前後端連線 DB 的既有 embeddings，不呼叫 Hugging Face API；若全域排序失敗，前端會退回關鍵字排序。

案件 Dashboard 的相關案件使用不同公式：先將來源案件全部 chunks 向量相加並正規化，再與其他案件的每個 chunk 比較，候選案件取最高分。此計算具有方向性，且制式文字可能拉高分數，因此只能作為查找提示。完整公式、BM25、百分比換算、評議結果分類與 Precision@5 限制可由側邊欄「計算方法」查看。

`match_source` 與 FTS5 / LIKE fallback 技術資訊仍由 API 保留，但不放在理賠人員的主要畫面；需要驗證搜尋來源時可由 API response 或後端測試確認。

### Summaries

目前摘要方法為 `rule_based_v1`，欄位包含：

```text
holding
applicant_claim
reasoning
summary_method
created_at
```

另已完成本機生成式摘要五案 POC 與人工審核資料流。`backend/app/services/summary_generation_service.py` 只允許連線到本機 Ollama，拒絕 `:cloud` 模型；摘要採角色區塊約束、原文引文驗證、完整句擴展、表格過濾、規則式理由排序與正式法規過濾。驗證後的摘要版本存入 Trial DB 的 `case_ai_summaries`，不會覆蓋既有 `case_summaries`。案件 Dashboard 會顯示摘要、審核狀態與可展開的原文引用；公開 API 維持唯讀，核准或拒絕只能由本機 CLI 操作。完整結果見 `docs/local_llm_summary_trial.md`。

本機摘要設定：

```text
SUMMARY_PROVIDER=ollama_local
SUMMARY_MODEL=qwen3:4b
OLLAMA_BASE_URL=http://127.0.0.1:11434
SUMMARY_NUM_CTX=8192
SUMMARY_MAX_OUTPUT_TOKENS=2048
SUMMARY_SECTION_MAX_CHARS=2000
```

試跑不會寫入正式 DB，預設輸出到 `outputs/local_llm_summary_trial_qwen3_4b.json`：

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\run_summary_trial.py --limit 5 --dry-run
.\.venv\Scripts\python.exe .\backend\scripts\run_summary_trial.py --limit 5
.\.venv\Scripts\python.exe .\backend\scripts\validate_summary_trial.py `
  --report .\outputs\local_llm_summary_trial_qwen3_4b_final_v4.json
```

2026-08-06 實測 5 件、57 次本機請求全數完成；自動回查 47 段 evidence 與 11 筆法源均無違規。2026-08-10 再完成其餘四案的品質修正，處理未閉合引號、相對人具體理由、理由脈絡、當事人法條誤列、重複結論與背景重複；四案最新版本為 v7、v8、v9、v11，再次回查 37 段 evidence 與 8 筆法源均無違規。五案最新版本均已由使用者檢視並人工核准。Trial DB 共保留 11 筆版本紀錄：5 筆 approved、1 筆 rejected、5 筆 unreviewed；未審核項目都是保留供稽核的舊版本，不會覆寫正式 DB。

匯入五案至 Trial DB 並查看審核佇列：

```powershell
py .\backend\scripts\import_summary_trial.py
py .\backend\scripts\review_ai_summary.py --list
py .\backend\scripts\review_ai_summary.py --case-number "114年評字第004802號" --show
```

核對 Dashboard、完整原文與 PDF 後，才執行人工決定：

```powershell
py .\backend\scripts\review_ai_summary.py `
  --case-number "114年評字第004802號" `
  --status approved `
  --reviewer "reviewer-id" `
  --note "已核對雙方主張、爭點、理由與主文"
```

`approved` 會成為 Dashboard 優先版本；`rejected` 不會出現在 Dashboard；再次匯入同一版本不會清除既有人工審核結果。兩個寫入腳本預設拒絕操作正式 `insurance_cases.db`。

### Similar Cases

後端仍保留規則式相似案件 baseline，依據包含：

```text
相同爭議類型
相同評議結果
相同決定類別
摘要文字中的保險關鍵詞重疊
```

此規則式 endpoint 供既有測試與比較使用；理賠人員的案件 Dashboard 已改用本機 BGE 案件層級語意相似 API。畫面顯示的相似度百分比是 cosine similarity 轉成百分比後的易讀表示，不是相關機率、理賠正確率或法律判斷。

### Semantic Search

目前提供本機 embedding MVP：

```text
GET /api/semantic-search?q=癌症保險金&limit=10
```

語意搜尋 API 可指定模型：

```text
GET /api/semantic-search?q=癌症保險金&embedding_provider=local&embedding_model=local_hashing_cjk_v1
GET /api/semantic-search?q=癌症保險金&embedding_provider=local_bge&embedding_model=BAAI/bge-large-zh-v1.5-local
```

`local_bge` 在本機執行 BGE，不需要 token，且固定使用 `local_files_only=True`。可送出 Hugging Face embedding request 的實作已移除；`huggingface` / `hf` 只保留為拒絕 aliases，API 會直接回傳 400。若 query provider 輸出維度與 DB stored embeddings 維度不一致，API 同樣會回傳 400。

目前模型：

```text
local_hashing_cjk_v1
```

這是純 Python 的 CJK n-gram hashing vector，優點是可離線、可重跑、無需 API key；限制是語意品質不等同於 OpenAI embedding、BGE 或其他正式語意模型。

前端語意搜尋頁會展示：

- 查詢文字、embedding 模型、候選 chunk 數、顯示結果筆數。
- 查詢文字轉向量、候選 chunk 比對、cosine similarity 排序的流程。
- 每筆結果的 score、score bar、section hint、chunk index、命中段落與案件來源。
- 明確提示目前是本機 MVP，尚未串接正式 AI embedding model。

案件層級語意相似 API：

```text
GET /api/cases/{case_id}/semantic-similar?limit=5
```

案件層級語意相似主要讀取已存在 embeddings，可指定：

```text
GET /api/cases/{case_id}/semantic-similar?embedding_provider=local_bge&embedding_model=BAAI/bge-large-zh-v1.5-local
```

目前做法是將來源案件的 chunk embeddings 聚合成案件向量，再與候選案件 chunk 比對，回傳相似案件與命中段落。

未來若要串接實際 AI 語意分析模型，主要替換 `backend/app/services/embedding_service.py` 的向量產生流程與 `chunk_embeddings` 重建腳本，API 與前端展示可以大致沿用。

目前已加入 embedding provider 設定：

```text
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=local_hashing_cjk_v1
EMBEDDING_DIMS=384
```

`local` 是正式 DB 目前使用的 hashing baseline；`local_bge` 是目前唯一啟用的正式語意模型 provider。`huggingface` / `hf` 遠端 API 與 `openai` / `ai` 均不可在目前程式中執行。

已支援本機 BGE provider：

```text
EMBEDDING_PROVIDER=local_bge
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5-local
EMBEDDING_DIMS=1024
LOCAL_BGE_DEVICE=auto
LOCAL_BGE_BATCH_SIZE=4
```

本機 BGE 使用 `BAAI/bge-large-zh-v1.5` 權重，不需要 API token。選用套件與 CPU / CUDA 安裝方式記錄於 `docs/local_bge_provider.md`。

Hugging Face Inference API 執行實作已移除：

```text
embedding_provider=huggingface -> HTTP 400
embedding_provider=hf          -> HTTP 400
```

後端不再讀取 `EMBEDDING_API_KEY` 或 `HF_TOKEN`。舊的 Hugging Face 1000 筆 trial DB 與報告只作為歷史比較資料，不會觸發新的外部 API 請求。

正式 AI provider 接入前的工程規格已整理在 `docs/ai_embedding_provider_plan.md`。

目前也已補上實作前測試保護：provider 回傳 embeddings 時會檢查筆數、向量維度、`token_count`、`norm` 與非有限數值；測試使用 fake provider，不會呼叫外部 API。

若設定 `EMBEDDING_PROVIDER=openai` 或 `EMBEDDING_PROVIDER=ai`，目前後端會明確拋出 `EmbeddingProviderError`，避免誤以為已經串接 OpenAI 類 provider。未來要替換成其他正式 AI embedding model 時，建議流程是：

```text
1. 在 backend/app/services/embedding_service.py 實作新的 provider。
2. 通過安全與費用審查後，才新增明確的 opt-in 開關與 secret 管理。
3. 使用新的 EMBEDDING_PROVIDER / EMBEDDING_MODEL 重建 chunk_embeddings。
4. 執行 pytest 與 verify_case_db，確認 API 與資料完整性。
```

重建 embeddings 範例：

```powershell
py .\backend\scripts\build_chunk_embeddings.py --provider local --model local_hashing_cjk_v1 --dims 384
```

本機 BGE 小批量試跑範例：

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements-local-ai-cuda.txt
$env:HF_HUB_OFFLINE="1"
$env:LOCAL_BGE_DEVICE="cuda"
.\.venv\Scripts\python.exe .\backend\scripts\build_chunk_embeddings.py --db .\backend\data\insurance_cases_local_bge_trial.db --provider local_bge --model BAAI/bge-large-zh-v1.5-local --dims 1024 --limit 20
```

本機 BGE query-to-document trial 查詢範例：

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\run_semantic_query_trial.py --db .\backend\data\insurance_cases_local_bge_trial.db --provider local_bge --model BAAI/bge-large-zh-v1.5-local --query 除外責任
```

這個查詢只讀取本機模型快取與 trial DB，不會呼叫 Hugging Face Inference API。

15 詞 benchmark v1：

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\run_semantic_query_trial.py `
  --db .\backend\data\insurance_cases_local_bge_trial.db `
  --provider local_bge `
  --model BAAI/bge-large-zh-v1.5-local `
  --query-set benchmark-v1 `
  --limit 5 `
  --include-text `
  --json-out .\outputs\local_bge_semantic_benchmark_v1_results.json `
  --out .\outputs\local_bge_semantic_benchmark_v1_results.md
```

這個固定查詢集會產生 15 個 queries、共 75 筆 Top 5 結果。標註規則、模板建立與 Precision@5 計算方式請看 `docs/hf_semantic_benchmark_v1_protocol.md`。

本機 BGE 1000-candidate 結果的人工標註工具：

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\annotate_semantic_benchmark.py
```

工具會顯示查詢詞、排名、分數、案件資訊、命中 chunk 與前後相鄰 chunk。每完成一筆就會以 UTF-8 原子寫入方式儲存，下次執行會從第一筆未完成項目繼續；過程不會呼叫任何外部 API。

操作鍵：

- `r`：相關（`relevant`）
- `p`：部分相關（`partially_relevant`）
- `n`：不相關（`not_relevant`）
- `s`：本次先略過
- `q`：儲存既有進度並結束

只標註單一查詢詞或重新檢查指定筆數：

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\annotate_semantic_benchmark.py --query 除外責任
.\.venv\Scripts\python.exe .\backend\scripts\annotate_semantic_benchmark.py --index 1
```

標註工作檔為 `outputs/local_bge_semantic_benchmark_v1_1000_annotations.json`，不提交 Git。75 筆全部完成後，執行以下指令驗證完整性並產生 Precision@5 報告：

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\evaluate_semantic_benchmark.py `
  --results .\outputs\local_bge_semantic_benchmark_v1_1000.json `
  --annotations .\outputs\local_bge_semantic_benchmark_v1_1000_annotations.json `
  --out .\outputs\local_bge_semantic_benchmark_v1_1000_evaluation.md
```

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
/api
```

本機 Vite 會將 `/api` 代理到 `http://127.0.0.1:8000`。若後端使用其他位址，可設定：

```text
VITE_DEV_API_PROXY_TARGET
```

只有前後端無法使用同源代理時，才需要以 `VITE_API_BASE_URL` 覆寫瀏覽器實際呼叫的 API 位址。

設定範例位於：

```text
frontend/.env.example
```

### Temporary public preview with Cloudflare Tunnel

Quick Tunnel 僅適合短時間專題展示。公開網址沒有本系統層級的登入驗證，持有網址的人可以搜尋案件、閱讀案件內容並開啟系統提供的 PDF；展示結束後必須停止 tunnel。

後端若使用 Local BGE trial API `http://127.0.0.1:8001`，在 `frontend/` 啟動一個同源代理前端：

```powershell
$env:VITE_API_BASE_URL="/api"
$env:VITE_DEV_API_PROXY_TARGET="http://127.0.0.1:8001"
pnpm dev --port 5174
```

另開終端機建立臨時公開網址：

```powershell
cloudflared tunnel --url http://127.0.0.1:5174
```

成功後終端機會顯示 `https://<random>.trycloudflare.com`。按 `Ctrl+C` 或停止 `cloudflared` process 即可關閉公開入口；每次重新建立 Quick Tunnel 時網址可能改變。

## Testing

### Backend syntax check

```powershell
py -m py_compile .\foi_ods_life_mvp_crawler.py
py -m py_compile .\foi_ods_pdf_text_pipeline.py
py -m py_compile .\foi_ods_case_organizer.py
py -m py_compile .\backend\scripts\import_cases_to_db.py
py -m py_compile .\backend\scripts\build_case_chunks.py
py -m py_compile .\backend\scripts\build_chunk_embeddings.py
py -m py_compile .\backend\scripts\compare_embedding_models.py
py -m py_compile .\backend\scripts\run_semantic_query_trial.py
py -m py_compile .\backend\scripts\evaluate_semantic_benchmark.py
py -m py_compile .\backend\scripts\verify_case_db.py
py -m py_compile .\backend\scripts\extract_case_summaries.py
py -m py_compile .\backend\app\services\search_service.py
py -m py_compile .\backend\app\services\embedding_service.py
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
- 全域語意排序、排序後分頁與 bounded cache
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

法源過濾與完整案件文字可使用 Node 內建測試，不需新增前端測試套件：

```powershell
node --test .\frontend\tests\caseText.test.ts .\frontend\tests\legalReferences.test.ts
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
- `docs/ai_embedding_provider_plan.md`：正式 AI embedding provider 接入規格，包含本機執行、重建、費用控制與測試策略
- `docs/local_bge_provider.md`：本機 BGE provider、CPU / CUDA 安裝、離線模型快取、1000 chunks trial 與正式切換條件
- `docs/local_llm_summary_trial.md`：Qwen3 4B + Ollama 本機案件摘要 POC、證據驗證、唯讀試跑與費用邊界
- `docs/local_bge_semantic_query_trial_100.md`：本機 BGE 100 candidates、15 詞 Top 5 結果、20/100 涵蓋比較與限制
- `docs/local_bge_semantic_query_trial_1000.md`：本機 BGE 1000 candidates、15 詞 Top 5 結果、100/1000 排名穩定性與限制
- `docs/hf_embedding_trial_comparison.md`：Hugging Face BGE trial embeddings、local hashing 離線 anchor-based 比較與 query-to-document 小樣本試測報告
- `docs/hf_semantic_query_trial_1000.md`：Hugging Face BGE 1000 筆 candidates 的 query-to-document 詳細查詢結果
- `docs/hf_semantic_relevance_check_1000.md`：Hugging Face BGE 1000 筆 trial Top 25 人工 relevance check，含 7 筆較不明確結果的 chunk 原文證據核對
- `docs/hf_semantic_benchmark_v1_protocol.md`：15 詞、75 筆結果的固定 benchmark、人工標註規則與 Precision@5 驗證流程
- `docs/hf_semantic_benchmark_v1_results.md`：benchmark v1 的 15 詞、75 筆 Hugging Face BGE Top 5 查詢結果
- `docs/hf_semantic_benchmark_v1_annotations.json`：75 筆 Codex-assisted 第一輪標註與逐筆原文證據摘要
- `docs/hf_semantic_benchmark_v1_evaluation.md`：第一輪 strict / lenient、macro / micro Precision@5 與逐查詢評測報告
- 第二位標註者空白模板：`outputs/hf_semantic_benchmark_v1_second_annotations.json`，此本機工作檔不提交 Git

## Current Limitations

目前尚未完成：

- 正式 DB 尚未切換為實務級 embedding 模型
- Hugging Face BGE 目前只完成 trial DB 1000 筆小樣本驗證，尚未全量重建正式 DB
- 本機 BGE 已完成 RTX 4050 CUDA 1000 chunks、15 詞／75 結果的離線 benchmark；尚未完成獨立人工 relevance 標註、歷史 API BGE 排名比較與正式 DB 全量重建
- 前端目前展示 Local BGE trial 摘要，不會直接查詢 trial DB 或呼叫外部 embedding API
- 15 詞 benchmark v1 已完成 75 筆第一輪 Codex-assisted 原文標註：Strict Precision@5 為 0.8133、Lenient Precision@5 為 0.9333
- 第二位標註者空白模板與一致性比較工具已完成；第二位獨立標註、實際一致率計算與爭議標記仲裁尚未完成
- ANN 向量索引
- OCR fallback
- Docker
- CI
- 部署設定
- 前端自動化測試
- 規則式摘要與法源擷取不是 LLM 法律判斷，可能有截段或漏抓，正式使用必須回查原文與官方 PDF
- 本機 Qwen3 摘要目前仍是五案 POC；已接入 Trial API 與 Dashboard，但尚未寫入正式 DB、完成全資料建置或逐案人工核准
- 案件分頁目前只用 `sessionStorage` 保存，不支援帳號同步、跨裝置或永久工作清單
- PostgreSQL / pgvector 實務版

## Recommended Next Steps

建議後續開發順序：

```text
1. 第二位標註者在不查看第一輪答案的情況下，完成 75 筆 `label` 與 `evidence_summary`
2. 執行標註一致性比較，檢查原始一致率、Cohen's Kappa、混淆矩陣並仲裁所有衝突
3. 依既有標註規則人工判讀本機 BGE 1000-candidate 的 75 筆結果，並與歷史 API BGE 排名比較
4. 針對人工驗證後的低品質查詢調整 query 或加入 reranking
5. 依 1000 chunks CUDA 實測估算全量重建時間，再決定是否替換正式 DB
6. 試跑 ROC 116 小期間資料
7. 導入 Docker / CI / 部署設定
```

## Project Positioning

本專案目前可定位為：

> A local MVP for insurance dispute case search, case lookup, summarization, and similarity exploration.

中文定位：

> 一套以金融消費評議中心人壽保險評議決定書為資料來源的保險評議案件搜尋與查找系統，提供案件查找、全文搜尋、語意搜尋、規則式摘要與相似案件推薦功能。
