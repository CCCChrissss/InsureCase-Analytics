# 保險評議分析系統 PROJECT_CONTEXT

本文件整理目前專案狀態，供後續開發、交接、專題展示與維護使用。

掃描範圍排除：

- `.env`
- `node_modules/`
- `.venv/`
- `data/`
- `outputs/`
- `dist/`
- `build/`

因此，本文件不直接引用上述目錄內的內容；資料量與資料路徑資訊主要根據 README、docs、schema 與程式碼整理。

## 1. 專案目標

本專案目標是建立「保險評議分析系統」，將金融消費評議中心 FOI ODS 的人壽保險評議決定書整理成可依年度、爭議類型、案號、全文關鍵字與語意相似度查找的案件資料庫。

目前系統定位：

- 學校專題版：以本機 SQLite、FastAPI、React + Vite 完成可展示的搜尋與案件閱讀 MVP。
- 實務延伸版：未來可擴充 PostgreSQL、pgvector、OCR、Docker、CI、跨年度匯入與部署。

目前已處理資料範圍：

- 正式展示 DB 年度：ROC 114 + ROC 115
- 產業：保險業
- 保險類別：人壽保險
- 文件類型：評議決定書
- ROC 114 查詢期間：ROC 114/1/1 到 ROC 114/12/31
- ROC 115 查詢期間：ROC 115/1/1 到 ROC 115/7/1
- metadata records：2992 筆
- PDF / raw text / normalized text / 單案 metadata：各 2992 份
- 爭議類型：41 種
- 正式 DB：`backend/data/insurance_cases.db`
- 正式 DB 年度分布：ROC 114 = 2500，ROC 115 = 492
- 跨年度 trial DB：ROC 114 全年度 2500 筆 + ROC 115 492 筆，共 2992 筆
- trial DB 路徑：`backend/data/insurance_cases_cross_year_trial.db`
- trial DB 資料品質檢查：`issue_count = 0`
- trial DB 規則式摘要：2992 筆，`holding`、`applicant_claim`、`reasoning` 均已補齊到 2992 筆

注意：ROC 115 查詢期間是 ROC 115/1/1 到 ROC 115/7/1，但目前文件記錄的實際 `decision_date` 範圍是 `115.01.09` 到 `115.03.20`。ROC 114 全年度實際 `decision_date` 範圍是 `114.01.16` 到 `114.12.26`。

## 2. 目前資料夾結構

以下為本次掃描到的主要結構，已排除指定不讀取的目錄。

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
│  ├─ roc114_summary_similarity_quality_check.md
│  ├─ embedding_pipeline.md
│  ├─ ai_embedding_provider_plan.md
│  ├─ local_bge_provider.md
│  ├─ local_bge_api_frontend_trial.md
│  ├─ local_bge_semantic_query_trial_100.md
│  ├─ local_bge_semantic_query_trial_1000.md
│  ├─ local_bge_semantic_benchmark_v1_1000_assisted_guide.md
│  ├─ local_bge_semantic_benchmark_v1_independent_guide.md
│  ├─ local_bge_semantic_benchmark_v1_poc_second_annotations.json
│  ├─ local_bge_semantic_benchmark_v1_poc_second_evaluation.md
│  ├─ local_bge_semantic_benchmark_v1_poc_comparison.md
│  ├─ local_bge_semantic_benchmark_v1_annotations.json
│  ├─ local_bge_semantic_benchmark_v1_evaluation.md
│  ├─ local_bge_low_precision_query_analysis.md
│  ├─ local_bge_query_suggestion_experiment_v1.md
│  ├─ hf_embedding_trial_comparison.md
│  ├─ hf_semantic_query_trial_1000.md
│  ├─ hf_semantic_relevance_check_1000.md
│  ├─ hf_semantic_benchmark_v1_protocol.md
│  ├─ hf_semantic_benchmark_v1_results.md
│  ├─ hf_semantic_benchmark_v1_annotations.json
│  └─ hf_semantic_benchmark_v1_evaluation.md
├─ backend/
│  ├─ schema.sql
│  ├─ app/
│  │  ├─ __init__.py
│  │  ├─ config.py
│  │  ├─ main.py
│  │  ├─ database.py
│  │  ├─ schemas.py
│  │  ├─ routers/
│  │  │  ├─ __init__.py
│  │  │  ├─ health.py
│  │  │  ├─ cases.py
│  │  │  ├─ quality.py
│  │  │  ├─ query_suggestions.py
│  │  │  ├─ search.py
│  │  │  ├─ semantic_search.py
│  │  │  ├─ similar_cases.py
│  │  │  ├─ statistics.py
│  │  │  └─ summaries.py
│  │  └─ services/
│  │     ├─ __init__.py
│  │     ├─ case_service.py
│  │     ├─ embedding_service.py
│  │     ├─ quality_service.py
│  │     ├─ query_suggestion_service.py
│  │     ├─ search_service.py
│  │     ├─ similar_case_service.py
│  │     ├─ statistics_service.py
│  │     └─ summary_service.py
│  ├─ scripts/
│  │  ├─ annotate_semantic_benchmark.py
│  │  ├─ build_chunk_embeddings.py
│  │  ├─ build_case_chunks.py
│  │  ├─ compare_semantic_annotations.py
│  │  ├─ compare_embedding_models.py
│  │  ├─ extract_case_summaries.py
│  │  ├─ evaluate_semantic_benchmark.py
│  │  ├─ import_cases_to_db.py
│  │  ├─ run_semantic_query_suggestion_trial.py
│  │  ├─ run_semantic_query_trial.py
│  │  └─ verify_case_db.py
│  └─ tests/
│     ├─ test_semantic_annotation_cli.py
│     ├─ test_api.py
│     ├─ test_build_chunk_embeddings.py
│     ├─ test_build_case_chunks.py
│     ├─ test_cross_year_pipeline_defaults.py
│     ├─ test_data_quality.py
│     ├─ test_embedding_service.py
│     ├─ test_import_cases_to_db.py
│     ├─ test_query_suggestion_service.py
│     ├─ test_search_service.py
│     ├─ test_semantic_annotation_agreement.py
│     ├─ test_semantic_benchmark.py
│     ├─ test_semantic_query_suggestions.py
│     ├─ test_similar_case_service.py
│     └─ test_summary_service.py
└─ frontend/
   ├─ index.html
   ├─ .env.example
   ├─ package.json
   ├─ pnpm-lock.yaml
   ├─ pnpm-workspace.yaml
   ├─ tsconfig.json
   ├─ tsconfig.node.json
   ├─ vite.config.ts
   └─ src/
      ├─ App.tsx
      ├─ main.tsx
      ├─ styles.css
      ├─ types.ts
      ├─ vite-env.d.ts
      ├─ api/
      │  └─ client.ts
      ├─ components/
      │  ├─ CaseDetailView.tsx
      │  ├─ CaseWorkspaceModal.tsx
      │  └─ ui.tsx
      ├─ config/
      │  └─ semantic.ts
      ├─ hooks/
      │  ├─ useAsyncData.ts
      │  └─ useOpenCases.ts
      ├─ pages/
         ├─ CasesPage.tsx
         ├─ QualityPage.tsx
         ├─ SearchPage.tsx
         └─ SemanticSearchPage.tsx
      └─ utils/
         └─ legalReferences.ts
```

未掃描但專案會使用的產物目錄：

```text
data/
backend/data/
frontend/node_modules/
frontend/dist/
```

說明：

- `data/`：原始 PDF、文字、metadata 等資料產物。本次依要求未讀取。
- `backend/data/insurance_cases.db`：SQLite 匯入產物。本次依排除規則未讀取資料內容。
- `frontend/node_modules/`：前端相依套件，不提交 Git。
- `frontend/dist/`：前端 build 產物，不提交 Git。

## 3. 每個主要檔案的用途

### 根目錄

- `.gitignore`：忽略 Python cache、虛擬環境、`.env`、資料產物、SQLite DB、前端 dependencies、前端 build 產物與本機工具狀態。
- `.env.example`：根目錄環境變數範例，包含後端 DB path、CORS origins、本機 BGE 與前端 API base URL；不再提供外部 API Token 設定，`openai` / `ai` 仍為預留名稱。
- `README.md`：專案介紹、目前資料狀態、pipeline、後端與前端啟動方式。
- `requirements.txt`：Python 相依套件，包含 `beautifulsoup4`、`fastapi`、`httpx`、`pdfplumber`、`pypdf`、`pytest`、`requests`、`uvicorn`。
- `requirements-local-ai.txt`：本機 BGE CPU 選用相依，固定 `torch 2.13.0` 與 `sentence-transformers 5.6.1`。
- `requirements-local-ai-cuda.txt`：本機 BGE NVIDIA CUDA 13.0 選用相依；已在專案 `.venv` 驗證 `torch 2.13.0+cu130` 與 RTX 4050 GPU 推論。
- `foi_ods_life_mvp_crawler.py`：FOI ODS metadata 與 PDF URL 爬蟲。
- `foi_ods_pdf_text_pipeline.py`：下載 PDF、抽取 raw text、產生 normalized text、回寫 metadata 與報表。
- `foi_ods_case_organizer.py`：將案件依年度、爭議類型、案號整理成單案資料夾。
- `PROJECT_CONTEXT.md`：本文件，整理目前專案上下文。

### docs

- `docs/project_plan.md`：完整專案計畫，包含目標、MVP 範圍、架構、資料庫、搜尋、API、前端與風險。
- `docs/development_roadmap.md`：階段式開發路線，目前已記錄到 embedding provider 介面與後續 AI provider 替換點。
- `docs/pipeline.md`：資料處理 pipeline 說明，包含爬蟲、PDF 文字抽取、案件整理、SQLite 匯入、API 與前端讀取流程。
- `docs/cross_year_readiness.md`：跨年度資料匯入前檢查報告，包含已支援項目、風險與正式匯入前 checklist。
- `docs/cross_year_trial_run_roc114_january.md`：ROC 114 一月小期間跨年度試跑報告，記錄 112 筆 metadata、PDF/text 與案件整理成功結果。
- `docs/cross_year_trial_run_roc114_full_year.md`：ROC 114 全年度跨年度試跑報告，記錄 2500 筆 metadata、PDF/text、案件整理與 trial DB 驗證結果。
- `docs/roc114_summary_similarity_quality_check.md`：ROC 114 摘要與相似案件抽樣品質檢查，記錄摘要覆蓋率、截段污染檢查、相似案件 top 5 檢查與已知例外。
- `docs/embedding_pipeline.md`：本機 chunk embedding MVP、語意搜尋 API、provider 狀態與後續正式 AI provider 升級路線。
- `docs/ai_embedding_provider_plan.md`：正式 AI embedding provider 接入規格與本機 BGE 狀態，包含 provider 介面、環境變數、模型重建、費用控制、DB model version、測試與展示說法。
- `docs/local_bge_provider.md`：本機 BGE provider、CPU / CUDA 安裝、離線模型快取、17254 chunks 全量實測結果、查詢 trial 與正式切換條件。
- `docs/local_bge_api_frontend_trial.md`：Local BGE trial DB 的 API / 前端實際切換、模型庫存、冷暖查詢耗時、GPU 觀察限制、錯誤處理與瀏覽器驗證報告。
- `docs/local_bge_semantic_query_trial_100.md`：本機 BGE 100 candidates 的 15 詞 Top 5 結果、20/100 候選涵蓋比較、執行證據與限制。
- `docs/local_bge_semantic_query_trial_1000.md`：本機 BGE 1000 candidates 的 15 詞 Top 5 結果、100/1000 排名穩定性、執行證據與限制。
- `docs/local_bge_semantic_query_trial_full.md`：本機 BGE 全量 17254 candidates 的 15 詞 Top 5 結果與適用限制。
- `docs/local_bge_full_build_report.md`：本機 BGE 全量建置參數、耗時、資料庫完整性證據、1000/17254 排名差異與正式切換邊界。
- `docs/local_bge_semantic_benchmark_v1_full_annotations.json`：全量 17254-candidate Top 5 的 75 筆 Codex-assisted 第一輪標註快照，包含每筆原文證據摘要。
- `docs/local_bge_semantic_benchmark_v1_full_evaluation.md`：全量 75 筆第一輪評測報告，Strict / Lenient Precision@5 為 `0.9200 / 0.9733`，並記錄限制與低分查詢。
- `docs/local_bge_semantic_benchmark_v1_1000_assisted_guide.md`：歷史 1000-candidate 的 75 題 AI 輔助指南，包含逐題提示；不適用全量結果或第二位獨立標註者。
- `docs/local_bge_semantic_benchmark_v1_independent_guide.md`：全量第二輪獨立標註規範，只包含標籤定義、15 詞概念邊界、流程與證據規則，不含個別案件提示或第一輪答案。
- `docs/local_bge_semantic_benchmark_v1_poc_second_annotations.json`：POC 混合式第二輪快照；第 1 至 9 題由使用者先行判讀，第 10 至 75 題為 Codex-assisted consolidation，明確標記 `independent = false`。
- `docs/local_bge_semantic_benchmark_v1_poc_second_evaluation.md`：POC 第二輪 Precision@5 報告，結果為 Strict `0.9200`、Lenient `0.9733`，不得當作獨立人工評測。
- `docs/local_bge_semantic_benchmark_v1_poc_comparison.md`：第一輪與 POC 第二輪的比較流程報告；一致率與 Kappa 均為 `1.0000`，但因來源不獨立，只能證明比較流程可運作。
- `docs/local_bge_semantic_benchmark_v1_annotations.json`：本機 BGE 75 筆完成版 AI 輔助標註快照，包含共同標註方法、label 與 evidence summary；來源工作檔位於 Git 忽略的 `outputs/`。
- `docs/local_bge_semantic_benchmark_v1_evaluation.md`：本機 BGE 15 詞、75 筆 AI 輔助標註的完整評測報告，包含逐查詢與逐筆判讀結果。
- `docs/local_bge_low_precision_query_analysis.md`：針對四個低 Strict P@5 查詢執行 12 組、60 筆本機 BGE 對照試驗，記錄 query 改寫、逐筆 AI 輔助判讀、Precision@5 與實作建議。
- `docs/local_bge_query_suggestion_experiment_v1.md`：15 個 benchmark 查詢的離線建議試驗，包含改寫規則、75 筆 AI 輔助判讀、逐查詢 Precision@5、退步案例與工程決策。
- `docs/hf_embedding_trial_comparison.md`：Hugging Face `BAAI/bge-large-zh-v1.5` trial embeddings、`local_hashing_cjk_v1` 離線 anchor-based 比較與 query-to-document 試測摘要。
- `docs/hf_semantic_query_trial_1000.md`：Hugging Face BGE 1000 筆 candidates 的 query-to-document 詳細查詢結果，包含 `除外責任`、`必要性醫療`、`癌症`、`住院`、`失能`。
- `docs/hf_semantic_relevance_check_1000.md`：Hugging Face BGE 1000 筆 trial Top 25 人工 relevance check，並對 7 筆較不明確結果保留 chunk 原文證據摘要與最終標記。
- `docs/hf_semantic_benchmark_v1_protocol.md`：將 BGE trial 擴充為 15 詞、75 筆 Top 5 結果的固定 benchmark，定義人工標註規則、strict / lenient Precision@5、執行方式與限制。
- `docs/hf_semantic_benchmark_v1_results.md`：15 個固定查詢詞對 1000 筆 BGE candidates 執行 Top 5 搜尋的 75 筆結果。
- `docs/hf_semantic_benchmark_v1_annotations.json`：75 筆 Codex-assisted 第一輪 relevance 標註與原文證據摘要，可由評測器驗證完整性。
- `docs/hf_semantic_benchmark_v1_evaluation.md`：第一輪評測報告；61 筆相關、9 筆部分相關、5 筆不相關，Strict P@5 0.8133、Lenient P@5 0.9333。

### backend

- `backend/schema.sql`：SQLite schema，定義 `cases`、`case_texts`、`case_summaries`、`case_chunks`、`chunk_embeddings`、`case_search` 與索引。
- `backend/app/config.py`：後端集中設定，支援由環境變數覆蓋 DB path、CORS origins 與 embedding provider 設定。
- `backend/app/main.py`：FastAPI app 入口，設定 CORS 與註冊 routers。
- `backend/app/database.py`：SQLite 連線與預設 DB 路徑。
- `backend/app/schemas.py`：Pydantic response models。
- `backend/app/routers/health.py`：健康檢查 API。
- `backend/app/routers/cases.py`：案件列表、案件詳情、爭議類型、PDF 讀取 API。
- `backend/app/routers/quality.py`：分析驗證 API，回傳 ROC 114 摘要與相似案件品質檢查結果。
- `backend/app/routers/query_suggestions.py`：唯讀查詢建議 API；區分有建議與無建議，拒絕空白輸入，且不會自動執行建議查詢。
- `backend/app/routers/search.py`：全文搜尋 API。
- `backend/app/routers/semantic_search.py`：chunk embedding 語意搜尋與 embedding 庫存狀態 API，支援 `embedding_model` / `embedding_provider` 可選參數。
- `backend/app/routers/similar_cases.py`：相似案件 API；案件層級語意相似 API 支援 `embedding_model` / `embedding_provider` 可選參數。
- `backend/app/routers/statistics.py`：首頁與案件篩選使用的輕量總覽 API，支援可選 `roc_year`。
- `backend/app/routers/summaries.py`：案件摘要 API。
- `backend/app/services/case_service.py`：案件查詢、篩選、分頁、PDF path resolver。
- `backend/app/services/embedding_service.py`：embedding provider 介面、本機 CJK hashing、本機 Sentence Transformers BGE、可續跑分批 chunk embedding 建置、模型庫存、chunk 語意搜尋與案件層級語意相似；搜尋前依 DB stored model 驗證維度及 provider 相容性，目前只啟用 `local` 與 `local_bge`，遠端 Hugging Face HTTP 實作已移除，本機 BGE 強制只讀本機模型快取。
- `backend/app/services/quality_service.py`：ROC 114 分析驗證報告資料。
- `backend/app/services/query_suggestion_service.py`：選擇性查詢建議服務；目前只收錄 4 個已在離線實驗改善的短查詢，以精確詞彙觸發，回傳原查詢、建議查詢、規則編號與理由，並固定標示不自動套用。
- `backend/app/services/search_service.py`：FTS5 搜尋、LIKE fallback、snippet 產生；FTS5 報錯或 0 筆時會進 LIKE fallback，且 fallback 會查案號、爭議類型與 normalized text。
- `backend/app/services/similar_case_service.py`：規則式相似案件計分。
- `backend/app/services/statistics_service.py`：案件總數、爭議類型數、年度與日期範圍總覽，支援可選年度條件。
- `backend/app/services/summary_service.py`：案件摘要查詢。
- `backend/scripts/extract_case_summaries.py`：從 normalized text 產生規則式摘要並寫入 `case_summaries`；已支援「二、申請人主張」與非固定序號的「判斷理由」標題。
- `backend/scripts/annotate_semantic_benchmark.py`：本機互動式人工標註工具，逐筆顯示 benchmark 命中內容與相鄰 chunks，支援相關／部分相關／不相關、略過、離開、指定查詢與指定序號；每筆完成後即原子寫入 UTF-8 JSON，不呼叫外部 API。
- `backend/scripts/build_case_chunks.py`：將 `case_texts.normalized_text` 切成可重跑的 `case_chunks`，保留 section hint、字元起訖位置與 chunk 長度，作為後續 embedding 前置資料。
- `backend/scripts/build_chunk_embeddings.py`：為 `case_chunks` 建立 embedding，支援 `--provider`、`--model`、`--dims`、`--limit`、`--resume` 與 `--write-batch-size`；resume 模式只處理指定模型的缺漏 chunks，每批 commit 並輸出進度，目前啟用 provider 為 `local` 與 `local_bge`。
- `backend/scripts/compare_embedding_models.py`：比較同一批共同 chunks 在 local hashing 與候選 embedding model 下的相似度排序，預設使用本機 BGE trial DB 並輸出至 `outputs/`，不會呼叫外部 API。
- `backend/scripts/compare_semantic_annotations.py`：驗證並比較兩份完整 benchmark 標註，計算原始一致率、Cohen's Kappa、混淆矩陣與各查詢一致率，並輸出待仲裁衝突清單。
- `backend/scripts/run_semantic_query_trial.py`：在指定 SQLite trial DB 上執行 query-to-document 語意搜尋試測，預設使用本機 BGE，支援重複 `--query`、固定 `benchmark-v1`、JSON 與 Markdown 輸出；查詢不修改 DB，也不使用外部 API。
- `backend/scripts/run_semantic_query_suggestion_trial.py`：為 benchmark v1 的 15 個短查詢執行固定、可解釋的離線建議試驗；只使用本機 BGE、以唯讀模式開啟 trial DB，輸出原查詢、建議查詢、規則編號、原因與 Top 5。
- `backend/scripts/evaluate_semantic_benchmark.py`：由 query trial JSON 產生人工標註模板，驗證每筆 label 與 evidence summary 完整性，並輸出 strict / lenient、macro / micro Precision@5 與逐筆證據報告。
- `backend/scripts/import_cases_to_db.py`：讀取單一或多個 metadata 與文字檔，匯入 SQLite。
- `backend/scripts/verify_case_db.py`：驗證 SQLite 筆數、搜尋、路徑與 sample case；可用 `--require-chunks` 與 `--require-embeddings` 檢查 chunk 與 embedding 完整性。
- `backend/scripts/check_data_quality.py`：檢查 metadata 與 SQLite DB 是否含 mojibake 類異常字元。
- `backend/tests/test_api.py`：API smoke tests，覆蓋 health、statistics、cases、case detail、PDF、search、summary、similar、semantic-similar、semantic model params 與 quality。
- `backend/tests/test_build_case_chunks.py`：chunking 邏輯、section hint 與 SQLite 寫入測試。
- `backend/tests/test_build_chunk_embeddings.py`：embedding build CLI 測試，覆蓋 resume / write batch 參數與 stderr 批次進度輸出。
- `backend/tests/test_cross_year_pipeline_defaults.py`：跨年度 pipeline 預設輸出路徑測試。
- `backend/tests/test_data_quality.py`：資料品質檢查測試。
- `backend/tests/test_embedding_service.py`：本機 hashing、本機 BGE fake model、provider factory、遠端 aliases 拒絕、維度與記憶體錯誤、embedding 寫入、搜尋排序及案件層級語意相似測試。
- `backend/tests/test_import_cases_to_db.py`：SQLite 匯入腳本測試，包含多 metadata 匯入與 metadata 目錄解析。
- `backend/tests/test_query_suggestion_service.py`：選擇性查詢建議服務測試，覆蓋 4 個核准詞、實驗規則一致性、未核准詞拒絕與前後空白處理。
- `backend/tests/test_search_service.py`：搜尋 fallback 單元測試，覆蓋 normalized text、案號與爭議類型 fallback。
- `backend/tests/test_semantic_annotation_cli.py`：人工標註 CLI 單元測試，覆蓋快捷鍵、續作篩選、標註驗證、原子儲存、SQLite 唯讀脈絡查詢與互動流程。
- `backend/tests/test_semantic_annotation_agreement.py`：雙標註一致性測試，覆蓋完全一致、部分衝突、標註者名稱重複、結果鍵值不符與 Kappa 無法定義情境。
- `backend/tests/test_semantic_benchmark.py`：固定 15 詞查詢集、參數互斥、標註模板、Precision@5 計算與證據必填驗證。
- `backend/tests/test_semantic_query_suggestions.py`：查詢建議 15 詞覆蓋與順序、規則完整性、SQLite 唯讀連線及本機 BGE provider/model 固定行為測試。
- `backend/tests/test_similar_case_service.py`：相似案件 service 單元測試。
- `backend/tests/test_summary_service.py`：摘要擷取與 summary service 測試，包含 FOI 標題格式變異的 regression tests。

### frontend

- `frontend/package.json`：React + Vite 前端專案設定與 scripts。
- `frontend/.env.example`：前端環境變數範例，主要設定 `VITE_API_BASE_URL`。
- `frontend/pnpm-lock.yaml`：pnpm lockfile，鎖定前端相依版本。
- `frontend/pnpm-workspace.yaml`：pnpm build approval 設定，目前允許 `esbuild`。
- `frontend/index.html`：Vite HTML 入口。
- `frontend/vite.config.ts`：Vite 設定，使用 React plugin，dev server 固定 `127.0.0.1:5173`。
- `frontend/tsconfig.json`：前端 TypeScript 設定。
- `frontend/tsconfig.node.json`：Vite config 使用的 TypeScript 設定。
- `frontend/src/main.tsx`：React app 掛載入口。
- `frontend/src/App.tsx`：主版面、側邊欄導覽、背景頁面 route 與全域案件工作區整合。
- `frontend/src/api/client.ts`：API base URL、`apiGet`、`apiGetOptional`。
- `frontend/src/config/semantic.ts`：理賠人員主搜尋與案件 Dashboard 共用的本機 BGE provider、模型名稱與語意候選上限。
- `frontend/src/types.ts`：前端 API response 型別，包含查詢建議回應。
- `frontend/src/hooks/useAsyncData.ts`：共用非同步資料載入 hook。
- `frontend/src/hooks/useOpenCases.ts`：已開啟案件分頁、切換、關閉、最小化與 `sessionStorage` 狀態保存。
- `frontend/src/components/CaseDetailView.tsx`：理賠人員導向的案件摘要、判斷理由、法源、相關案件及原文閱讀區。
- `frontend/src/components/CaseWorkspaceModal.tsx`：不離開搜尋背景頁的彈出式案件 Dashboard 與瀏覽器式案件分頁。
- `frontend/src/components/ui.tsx`：PageHeader、PanelHeader、Metric、AsyncBlock、EmptyState。
- `frontend/src/pages/`：案件工作台、全文搜尋、語意搜尋與分析驗證頁；主要導覽只顯示案件工作台與全文搜尋，技術頁保留 direct route。
- `frontend/src/utils/legalReferences.ts`：從案件原文規則式擷取法規與保單條款名稱、條號及來源段落。
- `frontend/src/styles.css`：前端全域樣式與 responsive layout。
- `frontend/src/vite-env.d.ts`：Vite TypeScript 型別宣告。

## 4. 後端架構

目前後端為 FastAPI + SQLite 的唯讀查詢 API。

架構分層：

```text
FastAPI app
  ├─ routers
  │  ├─ health
  │  ├─ cases
  │  ├─ quality
  │  ├─ search
  │  ├─ semantic_search
  │  ├─ similar_cases
  │  ├─ summaries
  │  └─ statistics
  ├─ services
  │  ├─ case_service
  │  ├─ embedding_service
  │  ├─ quality_service
  │  ├─ search_service
  │  ├─ similar_case_service
  │  ├─ summary_service
  │  └─ statistics_service
  ├─ schemas
  ├─ config
  └─ database
      ↓
SQLite database
```

資料流：

```text
backend/data/insurance_cases.db
  ↓ sqlite3
services
  ↓ dict / Pydantic response model
routers
  ↓ JSON / FileResponse
frontend
```

主要設計：

- API prefix 以 `/api` 為主。
- 統計 API 使用 `/api/statistics`。
- CORS 預設允許：
  - `http://localhost:5173`
  - `http://127.0.0.1:5173`
- CORS 可用 `BACKEND_CORS_ORIGINS` 以逗號分隔覆蓋。
- DB path 預設為 `backend/data/insurance_cases.db`，可用 `INSURANCE_CASES_DB_PATH` 覆蓋。
- HTTP method 目前只允許 GET。
- DB 連線使用 Python 標準庫 `sqlite3`。
- 每次 service function 以 context manager 建立連線。
- 查詢結果透過 `sqlite3.Row` 轉 dict。

## 5. 前端架構

目前前端為 React + Vite + TypeScript 的單頁應用。

技術：

- React 19
- Vite 7
- TypeScript
- Recharts
- lucide-react
- pnpm

主要資料流：

```text
React component
  ↓ useAsyncData
fetch(API_BASE + path)
  ↓
FastAPI /api/*
```

`API_BASE` 設定：

```text
VITE_API_BASE_URL 若存在則使用該值
否則預設 http://127.0.0.1:8000/api
```

前端設定範例位於 `frontend/.env.example`。

目前背景頁面以 React state 切換，並同步基本 URL query：

- `dashboard`
- `cases`
- `search`
- `semantic`
- `quality`

舊版案件連結仍可向下相容：

```text
?view=cases&case_id=<case_id>
```

一般操作不再把案件 ID 寫回 URL。開啟案件時會保留目前背景頁面，例如從全文搜尋開啟案件後仍停留在 `?view=search`，案件內容由全域彈出式工作區顯示。

已開啟案件分頁只保存 `case_id` 與顯示標籤於 `sessionStorage`；同一瀏覽器分頁重新整理可還原，關閉瀏覽器分頁後不保證保留。詳細資料、摘要與相關案件只在目前作用中的案件分頁載入。

主要 UI：

- 側邊欄主要導覽：案件工作台、全文搜尋；另有已開啟案件數量與還原按鈕。
- 案件工作台：年度、爭議類型、案號篩選與案件列表，可選擇每頁顯示 10、15 或 20 筆。
- 全文搜尋：同時執行 FTS5 / LIKE 關鍵字搜尋與本機 BGE 語意搜尋，將案件去重後交錯顯示，標示關鍵字、語意或兩者皆命中；可選擇顯示 10、15 或 20 筆。語意服務失敗時仍保留關鍵字結果。
- 案件工作區：瀏覽器式案件分頁、關閉、切換、最小化、摘要、評議結論、申請人主張、判斷理由、法源與契約條款、本機 BGE 語意相似案件與相似度、查看原文及正式 PDF。相似度為 cosine similarity 的百分比表示，不是相關機率或理賠正確率。
- 語意搜尋：輸入查詢文字，展示 embedding 模型、候選 chunk、cosine similarity、score bar、段落提示、命中段落與案件來源。
- 統計分析：目前保留 direct route 與後端 API 作為輔助檢查，不放在主要導覽。
- 分析驗證：展示 ROC 114 摘要覆蓋率、截段污染檢查、相似度計分規則、抽樣案件、已知例外與限制。

目前前端已拆分為：

```text
frontend/src/
├─ api/
├─ components/
├─ hooks/
├─ pages/
├─ App.tsx
├─ main.tsx
├─ styles.css
└─ types.ts
```

樣式仍集中於 `frontend/src/styles.css`。

## 6. 資料庫 schema

資料庫：SQLite。

schema 來源：`backend/schema.sql`。

### `cases`

案件 metadata 主表。

```sql
case_id TEXT PRIMARY KEY
case_number TEXT NOT NULL UNIQUE
roc_year INTEGER NOT NULL
decision_date TEXT
decision_category TEXT
decision_result TEXT
industry TEXT
industry_subcategory TEXT
dispute_type TEXT
source_pdf_url TEXT
case_directory TEXT
pdf_path TEXT
raw_text_path TEXT
normalized_text_path TEXT
metadata_path TEXT
created_at TEXT NOT NULL
updated_at TEXT NOT NULL
```

索引：

```sql
idx_cases_roc_year
idx_cases_decision_date
idx_cases_dispute_type
idx_cases_case_number
```

### `case_texts`

案件文字主表。

```sql
case_id TEXT PRIMARY KEY
raw_text TEXT
normalized_text TEXT
raw_text_chars INTEGER
normalized_text_chars INTEGER
page_count INTEGER
extraction_method TEXT
FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
```

### `case_summaries`

摘要表，目前由 `backend/scripts/extract_case_summaries.py` 寫入；目前正式 DB 已產生 2992 筆 `rule_based_v1` 摘要。

```sql
case_id TEXT PRIMARY KEY
holding TEXT
applicant_claim TEXT
reasoning TEXT
summary_method TEXT
created_at TEXT
FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
```

### `case_chunks`

案件文字切片表，目前由 `backend/scripts/build_case_chunks.py` 寫入；正式 DB 已產生 17254 段，2992 筆案件皆至少有一段 chunk。

```sql
chunk_id TEXT PRIMARY KEY
case_id TEXT NOT NULL
chunk_index INTEGER NOT NULL
section_hint TEXT
chunk_text TEXT NOT NULL
char_start INTEGER NOT NULL
char_end INTEGER NOT NULL
chunk_chars INTEGER NOT NULL
created_at TEXT NOT NULL
FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
UNIQUE(case_id, chunk_index)
```

索引：

```sql
idx_case_chunks_case_id
```

### `chunk_embeddings`

chunk embedding 表，目前由 `backend/scripts/build_chunk_embeddings.py` 寫入；正式 DB 已產生 17254 筆，與 `case_chunks` 數量一致。

```sql
chunk_id TEXT NOT NULL
embedding_model TEXT NOT NULL
embedding_dims INTEGER NOT NULL
embedding BLOB NOT NULL
embedding_norm REAL NOT NULL
created_at TEXT NOT NULL
FOREIGN KEY(chunk_id) REFERENCES case_chunks(chunk_id) ON DELETE CASCADE
PRIMARY KEY(chunk_id, embedding_model)
```

目前模型：

```text
local_hashing_cjk_v1
```

目前 provider 狀態：

- `local`：正式展示 DB 目前使用的 provider，使用本機 CJK hashing vector。
- `local_hashing`：`local` 的相容別名。
- `local_bge`：已實作本機 Sentence Transformers provider，來源模型為 `BAAI/bge-large-zh-v1.5`，DB 儲存名稱為 `BAAI/bge-large-zh-v1.5-local`、維度 1024，不需要 API token；RTX 4050 CUDA 17254 chunks 全量建置與 15 詞 benchmark 流程已通過。
- `huggingface` / `hf`：可送出遠端 embedding request 的實作已移除；aliases 會直接拋出 `EmbeddingProviderError`。
- `openai` / `ai`：預留給未來 OpenAI 類 provider，目前會明確拋出 `EmbeddingProviderError`。

注意：正式 DB 目前仍是學校專題版的本機 hashing vector MVP。本機 BGE 已在獨立 trial DB 完成 17254 chunks 全量建置與 Codex-assisted 第一輪評測，但尚未完成第二位標註者的獨立品質驗證；只改環境變數不會切換 DB，正式採用仍需另外備份、驗證與明確確認。

### `case_search`

SQLite FTS5 full-text search virtual table。

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS case_search USING fts5(
  case_id UNINDEXED,
  case_number,
  dispute_type,
  normalized_text
);
```

用途：

- 搜尋案號
- 搜尋爭議類型
- 搜尋 normalized text

## 7. API endpoint 清單

### Health

```text
GET /api/health
```

用途：確認 API 狀態與 SQLite DB 是否存在。

回傳：

```json
{
  "status": "ok",
  "database_ready": true
}
```

### Cases

```text
GET /api/cases
```

用途：案件列表與篩選。

Query parameters：

- `page`：預設 1，最小 1。
- `page_size`：預設 20，最大 100。
- `roc_year`：可選。
- `dispute_type`：可選。
- `case_number`：可選，使用 `LIKE` 模糊查詢。

```text
GET /api/cases/{case_id}
```

用途：取得單一案件詳情，包含 metadata、raw text、normalized text、文字統計與本地資料路徑。

```text
GET /api/dispute-types
```

用途：取得爭議類型清單與數量，供前端 filter 使用。

Query parameters：

- `roc_year`：可選；指定後只回傳該年度的爭議類型與數量。

```text
GET /api/files/{case_id}/pdf
```

用途：依案件 ID 回傳 PDF 檔案；後端測試會確認存在案件可回傳 `application/pdf`。

### Search

```text
GET /api/search
```

用途：全文搜尋。

Query parameters：

- `q`：必填，最小長度 1。
- `page`：預設 1。
- `page_size`：預設 20，最大 100。

搜尋方式：

- 優先使用 SQLite FTS5 `MATCH`。
- 若 FTS5 query 產生 `sqlite3.OperationalError`，fallback 到 `LIKE`。
- 若 FTS5 沒報錯但回傳 0 筆，也會 fallback 到 `LIKE`。
- FTS5 與 LIKE fallback 的查詢範圍皆包含案號、爭議類型與 normalized text。
- 回傳 snippet 與 `match_source`。

### Query Suggestions

```text
GET /api/query-suggestions
```

用途：查詢指定短詞是否有經離線實驗核准的可選改寫建議。

Query parameters：

- `q`：必填，不可為空字串或只有空白。

回傳行為：

- 命中 4 個核准詞時回傳 `available = true`、原查詢、建議查詢、規則編號與理由。
- 未命中時回傳 HTTP 200 與 `available = false`，建議相關欄位為 `null`。
- `auto_apply` 固定為 `false`，API 不執行全文搜尋或語意搜尋，也不取代原查詢。
- 空字串或只有空白時回傳 HTTP 422。

### Semantic Search

```text
GET /api/embedding-status
```

用途：回傳目前 API 連線的 DB 名稱、後端 configured provider / model / BGE device，以及 DB 內各 stored model 的維度、筆數與建議 provider。此 endpoint 不載入 BGE 模型。

```text
GET /api/semantic-search
```

用途：使用 `chunk_embeddings` 做 chunk 層級語意搜尋。

Query parameters：

- `q`：必填，最小長度 1。
- `limit`：預設 10，最大 50。
- `min_score`：最低分數，預設 0。
- `embedding_model`：可選，指定要查詢的 stored embedding model。
- `embedding_provider`：可選，指定 query 文字轉向量時使用的 provider。

目前方法：

- 正式 DB 預設使用 `local_hashing_cjk_v1`；獨立 trial DB 同時包含 Local Hashing 384 維與 Local BGE 1024 維各 17254 筆。
- 回傳實際 provider、model、device、維度、API 耗時、候選數，以及命中的 `chunk_text`、`section_hint`、`score` 與案件基本資料。
- 搜尋前先驗證 stored model 存在、維度一致及 provider / model 相容，不存在時不載入 BGE 模型。
- 若指定 `embedding_provider=huggingface` 或 `hf`，API 會回傳 400 且不送出外部 request；本機 BGE 必須搭配 `embedding_model=BAAI/bge-large-zh-v1.5-local`。

### Summaries

```text
GET /api/cases/{case_id}/summary
```

用途：取得單一案件規則式摘要。

回傳：

- `holding`
- `applicant_claim`
- `reasoning`
- `summary_method`
- `created_at`

### Similar Cases

```text
GET /api/cases/{case_id}/similar?limit=5
```

用途：取得規則式相似案件。

目前相似度依據：

- 相同爭議類型。
- 相同評議結果。
- 相同決定類別。
- 摘要文字中的保險關鍵詞重疊。

回傳：

- `score`
- `matched_reasons`
- top N 相似案件基本資料。

規則式 `/similar` endpoint 目前保留供 baseline 與測試比較；理賠人員案件 Dashboard 實際使用下列本機 BGE endpoint：

```text
GET /api/cases/{case_id}/semantic-similar?limit=5&chunks_per_case=1&embedding_provider=local_bge&embedding_model=BAAI/bge-large-zh-v1.5-local
```

前端將回傳 cosine similarity 轉為百分比顯示，並附上主要相近段落類型。該數字只表示向量內容相近程度，不代表理賠判斷正確率或法律結論一致率。

### Quality

```text
GET /api/quality/roc114-summary-similarity
```

用途：取得 ROC 114 摘要與相似案件品質檢查結果，供前端「分析驗證」頁展示。

回傳內容包含：

- 分析範圍。
- 前十大爭議類型。
- 摘要欄位覆蓋率與長度統計。
- 截段污染檢查。
- 相似案件計分規則。
- 抽樣案件檢查結果。
- 整體 Top 1 / Top 5 同爭議類型率。
- 已知低信心例外。
- 方法限制與下一步。

### Statistics

```text
GET /api/statistics/overview
```

用途：總案件數、爭議類型數、年度清單、最早與最晚決定日期。

Query parameters：

- `roc_year`：可選；指定後只統計該年度案件。

## 8. 目前已完成功能

### 資料處理

- FOI ODS metadata 與 PDF URL 爬取。
- 避免網站單次查詢 100 筆上限的月份、週、爭議類型切分。
- PDF 下載。
- `pdfplumber` 文字抽取。
- `pypdf` fallback。
- raw text 與 normalized text 產生。
- 依年度、爭議類型、案號整理案件資料夾。
- metadata 回寫本地檔案路徑。
- ROC 114 全年度 metadata / PDF text / case organizer 均完成 2500 筆。

### SQLite

- 建立 `cases`。
- 建立 `case_texts`。
- 建立 `case_summaries`。
- 建立 `case_chunks`。
- 建立 `chunk_embeddings`。
- 建立 `case_search` FTS5 virtual table。
- 匯入 2992 筆案件。
- 匯入 2992 筆文字。
- 匯入腳本支援多個 `--metadata` 與 `--metadata-dir`。
- 建立全文搜尋索引。
- 已寫入 2992 筆規則式摘要。
- 已建立 17254 段案件文字 chunk，2992 筆案件皆有 chunk。
- 已建立 17254 筆 chunk embedding，模型為 `local_hashing_cjk_v1`，維度 384。
- 提供資料庫驗證腳本。
- 已建立跨年度 trial DB：`backend/data/insurance_cases_cross_year_trial.db`，匯入 ROC 114 全年度 2500 筆與 ROC 115 492 筆，共 2992 筆。
- trial DB 已重建規則式摘要，共 2992 筆；`holding`、`applicant_claim`、`reasoning` 均為 2992 筆。
- 正式展示 DB `backend/data/insurance_cases.db` 已切換為 ROC 114 + ROC 115 共 2992 筆；原 ROC 115 DB 已備份為 `backend/data/insurance_cases_roc115_backup_20260707_163248.db`。

### 後端

- FastAPI app。
- CORS 設定，支援環境變數覆蓋。
- DB path 設定，支援環境變數覆蓋。
- 健康檢查。
- 案件列表 API。
- 案件詳情 API。
- 爭議類型 API。
- PDF 回傳 API。
- 全文搜尋 API。
- 語意搜尋 API。
- Embedding model inventory / status API。
- 案件層級語意相似 API。
- 摘要 API。
- 規則式相似案件 API。
- 分析驗證 API。
- 案件總覽與爭議類型 API，支援年度篩選。
- 4 個已驗證低分短查詢的選擇性建議 service 與唯讀 API；目前不自動套用，也尚未接前端。
- 後端 pytest 測試。
- 案件詳情展示鏈 API 測試，覆蓋詳情、PDF、摘要、規則式相似案件與語意相似案件。
- OpenAPI docs 可由 FastAPI 自動產生。

### 前端

- React + Vite 專案。
- 案件工作台已取代舊 Dashboard，首頁直接提供案件篩選與清單。
- 案件管理頁年度篩選。
- 案件詳情區。
- 全文搜尋頁。
- 全文搜尋頁以理賠人員可理解的案件資訊與命中片段為主，不顯示 FTS5、fallback 或模型等技術欄位。
- 語意搜尋頁可在 Local Hashing 與 Local BGE 間切換並實際呼叫 API，展示 DB、stored embedding 筆數、provider、model、device、維度、API 耗時、候選 chunk、分析流程、模型限制、命中 chunk、score、score bar、section hint 與案件來源。
- 語意搜尋頁已接入查詢建議 API；有核准建議時顯示原查詢、建議查詢、理由、規則編號與目前實際執行查詢，由使用者自行切換。
- 一般案件工作區顯示規則式相關案件與業務理由，不顯示相似度分數或模型參數；語意技術細節留在 direct route 的語意搜尋頁。
- 統計分析頁仍保留 direct route，但不作為主導覽項目。
- 分析驗證頁。
- 案件摘要區塊。
- 相似案件區塊。
- PDF 連結。
- Responsive layout。
- API 連線狀態顯示。
- 背景頁面 URL 狀態同步與舊案件 URL 向下相容。
- 彈出式案件 Dashboard 與多案件分頁，可切換、關閉、最小化及還原。
- 已開啟案件以 `sessionStorage` 保存，同一瀏覽器分頁重新整理後可還原。
- 案件整理內容與原文可在同一彈窗內切換，並保留正式 PDF 連結。
- 規則式法源與保單條款擷取，顯示可回查的原文段落並標示需人工核對。

### Git

- 專案目前已是有效 Git repository。
- 目前已建立至少三個階段 commit：
  - 專案文件與 pipeline 腳本。
  - SQLite 匯入流程。
  - FastAPI 後端 API。
  - React 前端 MVP。
  - 搜尋 fallback 與後端測試。
  - 規則式摘要。
  - chunking pipeline。
  - 本機 embedding pipeline 與語意搜尋 API。
  - 案件層級語意相似展示。
  - embedding provider 介面。

## 9. 尚未完成項目

- 正式展示 DB 尚未切換為實務級 embedding model。
- ANN 向量索引。
- OCR fallback。
- ROC 116 或更多年度資料蒐集。
- 後台管理 API，例如重新匯入、重建索引。
- Docker。
- CI。
- 部署設定。
- API 錯誤回應格式統一。
- 正式 React Router。
- 前端自動化測試。
- 規則式摘要與法源擷取仍可能截取過長或不完整段落；正式理賠判斷必須回查原文與 PDF，不可把前端整理內容當成法律結論。
- 案件工作區使用 `sessionStorage`，不是帳號層級或跨裝置保存；關閉瀏覽器分頁後不保證留存。
- 遠端 Hugging Face embeddings 不再建置；本機 BGE 已在獨立 trial DB 完成全量 17254 筆，正式 DB 仍未切換。
- 本機 BGE 已完成 RTX 4050 CUDA 17254 chunks 全量 embeddings，維度、blob 長度、缺漏、norm、非有限值與 SQLite integrity 均驗證通過；全量 15 詞／75 結果、第一輪評測及 POC 混合式第二輪均已完成，但尚未完成第二位獨立標註或正式 DB 切換。
- 選擇性查詢建議 service、response schema、API endpoint 與前端操作介面已完成；目前只支援 4 個核准短查詢，尚未擴充同義詞或模糊觸發。
- 前端語意搜尋頁已可透過 trial backend 實際查詢 Local BGE trial DB；是否使用 trial DB 由後端啟動環境決定，前端不直接開啟 SQLite，也不呼叫外部 embedding API。
- 15 詞 benchmark v1 已完成 75 筆 Codex-assisted 第一輪原文標註與 Precision@5 報告。
- 一致性比較工具與 POC 混合式第二輪已完成；正式第二位獨立標註與有效的跨標註者信度估計仍未完成。
- OpenAI 或其他外部 AI embedding provider 尚未實作。
- 實務級向量資料庫或 ANN index。

## 10. 目前可能的 bug 或技術債

### 規則式相似度不是語意相似

目前相似案件是 baseline，依爭議類型、評議結果與保險關鍵詞重疊計分。
系統也已新增案件層級語意相似，但正式 DB 目前仍使用 `local_hashing_cjk_v1`；本機 BGE 只存在獨立 trial DB。

影響：

- 分數可解釋，但不等同語意相似度或法律判斷。
- 本機語意相似可展示分析流程與命中段落，但語意品質不能等同 OpenAI embedding、BGE 或其他正式模型。

建議：

- 後續先完成本機 BGE 全量結果的第二位獨立標註與一致率比較；再確認 API 載入時間與 GPU 記憶體，最後決定是否替換正式 DB 或導入 pgvector。

### Local BGE 冷啟動與 Python 環境

Local BGE trial API 已可實際查詢 17254 個 candidates，暖機後 API 約 2.5 至 2.8 秒；第一次載入模型實測約 66.65 秒，未達互動式搜尋期待。SQLite 向量目前仍由 Python 全量解包與排序，尚未使用 ANN index。

另需注意系統 `py` launcher 目前安裝 CPU-only PyTorch；CUDA API 必須用 `.\.venv\Scripts\python.exe` 啟動。若誤用系統 Python 並指定 `LOCAL_BGE_DEVICE=cuda`，API 會回傳 HTTP 400，不會靜默改用 CPU。

建議：

- POC 展示期間保持 API 常駐，避免現場冷啟動。
- 下一階段增加 startup warmup 或背景模型預載，並讓前端顯示初始化狀態。
- 評估將 stored vectors 預載到記憶體，之後再比較 SQLite 全量掃描與 FAISS / pgvector ANN。
- Windows WDDM 無法由 `nvidia-smi` 準確歸屬單一 Python process 的 VRAM；目前整張 GPU 觀察值不可當作模型獨占記憶體。

### ROC 114 一月亂碼問題已修正

跨年度 trial DB 第一次建立時，ROC 114 一月資料中有 32 筆案號、爭議類型與整理後路徑出現亂碼。根因是 FOI ODS 結果頁已宣告 `charset=utf-8`，但爬蟲用 `response.apparent_encoding` 覆蓋 header charset，而該批結果頁被誤判為 `MacCyrillic`。

已修正：

- `foi_ods_life_mvp_crawler.py` 改為優先使用 response header 宣告的 charset。
- 爬蟲 validation 會偵測案號與爭議類型是否含異常 Cyrillic 字元。
- 新增 `backend/scripts/check_data_quality.py`，可檢查 metadata 與 SQLite DB。
- 已重跑 ROC 114 一月 metadata、PDF/text pipeline、case organizer。
- 已刪除舊的 ROC 114 亂碼資料夾殘留。
- 後續已擴大到 ROC 114 全年度，並重建跨年度 trial DB 與 2992 筆摘要。

驗證結果：

- ROC 114 metadata 品質檢查 `issue_count` = 0。
- ROC 114 一月修正當時，cases 資料夾中 `decision.pdf`、`raw_text.txt`、`normalized_text.txt`、`metadata.json` 均為 112 份。
- 跨年度 trial DB 品質檢查 `issue_count` = 0。
- 目前 trial DB 年度分布為 ROC 114 = 2500、ROC 115 = 492。

### 前端尚未使用正式 router

前端已支援 `view` 與 `case_id` query 同步，但尚未使用 React Router 這類正式 router。

影響：

- 基本案件詳情分享已可用。
- 若未來頁面狀態變多，例如篩選條件、搜尋字串、分頁，手寫 History API 會變得難維護。

建議：

- 後續在功能複雜後加入 React Router 或等價 routing。

### 案件詳情一次回傳全文

`GET /api/cases/{case_id}` 會回傳 `raw_text` 與 `normalized_text`。

影響：

- 2992 筆本機 MVP 可接受。
- 未來跨年度或文字更長時，API payload 可能偏大。

建議：

- 保留案件 metadata endpoint。
- 另開 `/api/cases/{case_id}/text` 或支援 lazy loading。

### API 設定已可覆蓋，但尚未導入完整設定管理

目前 DB path、CORS、frontend API base 已提供本機預設值與 `.env.example`，並可透過環境變數覆蓋。

影響：

- 本機展示方便。
- 部署或多人協作時已可調整設定，但專案目前不會自動載入 `.env` 檔。

建議：

- 若後續要正式部署，可評估加入部署平台環境變數、Docker env 或 settings class。
- 若希望本機自動讀 `.env`，需要再評估是否加入 `python-dotenv` 或等價方案。

### 前端尚無自動化測試

後端已有 pytest；前端目前仍主要依靠 `pnpm build` 與人工瀏覽器檢查。

建議：

- 後續加入前端 smoke tests。

### Vite build bundle 偏大

目前前端 production build 曾出現 chunk 超過 500 kB 的 warning，主要可能來自 Recharts。

影響：

- 本機展示可接受。
- 實際部署時首屏 JS 可能偏大。

建議：

- 後續可做 dynamic import 或 manual chunks。

### 摘要與相似案件規則需要持續抽樣校正

目前摘要與相似案件都採規則式方法，已可展示，但遇到新年度或格式變異時仍可能需要調整規則。

已知已修正格式變異：

- 「二、申請人主張」缺少「之」時，仍可抽取 `applicant_claim`。
- 「判斷理由」不固定為第六段時，例如「四、判斷理由」，仍可抽取 `reasoning`。

建議：

- 跨年度前先建立抽樣驗證流程。

## 11. 執行方式

### Python 後端相依套件

在專案根目錄執行：

```powershell
py -m pip install -r requirements.txt
```

本機 BGE 為選用大型相依，CPU 與 CUDA 分開安裝：

```powershell
py -m pip install -r requirements-local-ai.txt
# 或 NVIDIA CUDA 13.0：
py -m pip install -r requirements-local-ai-cuda.txt
```

### 環境變數設定

根目錄提供 `.env.example`，前端目錄提供 `frontend/.env.example`。

後端支援：

```text
INSURANCE_CASES_DB_PATH=backend/data/insurance_cases.db
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=local_hashing_cjk_v1
EMBEDDING_DIMS=384
LOCAL_BGE_DEVICE=auto
LOCAL_BGE_BATCH_SIZE=4
```

前端支援：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

注意：目前後端沒有新增自動讀取 `.env` 的套件。若要套用設定，請在啟動指令前於 shell 或部署平台設定環境變數。

### 建立 SQLite DB

前提：

- `data/` 內已存在整理完成的 metadata、PDF、raw text、normalized text。

執行：

```powershell
py .\backend\scripts\import_cases_to_db.py --recreate
```

預設輸入：

```text
data/foi_ods/metadata/foi_ods_life_roc115_metadata.json
```

多 metadata 匯入：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata .\data\foi_ods\metadata\foi_ods_life_roc114_metadata.json --metadata .\data\foi_ods\metadata\foi_ods_life_roc115_metadata.json --recreate
```

metadata 目錄匯入：

```powershell
py .\backend\scripts\import_cases_to_db.py --metadata-dir .\data\foi_ods\metadata --recreate
```

說明：

- `--metadata` 可重複指定。
- `--metadata-dir` 只讀取目錄下的 `*_metadata.json`。
- 目前正式展示資料已是 ROC 114 + ROC 115 共 2992 筆；多 metadata 匯入仍可用於後續新增年度。

預設輸出：

```text
backend/data/insurance_cases.db
```

### 驗證 SQLite DB

```powershell
py .\backend\scripts\verify_case_db.py
```

成功標準：

- `cases` = 2992
- `case_texts` = 2992
- `case_search` = 2992
- `case_summaries` = 2992
- `case_chunks` = 17254
- `chunk_embeddings` = 17254
- `cases_without_chunks` = 0
- `chunks_without_embeddings` = 0
- path errors = 0
- 關鍵字查詢有結果

### 產生規則式摘要

```powershell
py .\backend\scripts\extract_case_summaries.py
```

目前成功標準：

- `processed_count` = 2992
- `total_summaries` = 2992
- `holding` = 2992
- `applicant_claim` = 2992
- `reasoning` = 2992

### 建立案件文字 chunks

```powershell
py .\backend\scripts\build_case_chunks.py --db .\backend\data\insurance_cases.db
```

目前正式 DB 驗證結果：

- `processed_cases` = 2992
- `total_chunks_in_table` = 17254
- `empty_case_count` = 0
- `min_chunks_per_case` = 3
- `max_chunks_per_case` = 30

### 建立 chunk embeddings

```powershell
py .\backend\scripts\build_chunk_embeddings.py --db .\backend\data\insurance_cases.db
```

可指定 provider、model、dims 與小批量試跑：

```powershell
py .\backend\scripts\build_chunk_embeddings.py --provider local --model local_hashing_cjk_v1 --dims 384 --limit 100
```

目前正式 DB 驗證結果：

- `processed_chunks` = 17254
- `embedded_chunks` = 17254
- `total_embeddings_in_table` = 17254
- `empty_chunk_count` = 0
- `embedding_model` = `local_hashing_cjk_v1`
- `embedding_dims` = 384

### 啟動後端 API

在專案根目錄執行：

```powershell
py -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

開啟：

```text
http://127.0.0.1:8000/docs
```

### 啟動 Local BGE trial API

CUDA 版本必須從專案根目錄使用 `.venv`，不可改成系統 `py`：

```powershell
$env:INSURANCE_CASES_DB_PATH="backend/data/insurance_cases_local_bge_trial.db"
$env:EMBEDDING_PROVIDER="local_bge"
$env:EMBEDDING_MODEL="BAAI/bge-large-zh-v1.5-local"
$env:EMBEDDING_DIMS="1024"
$env:LOCAL_BGE_DEVICE="cuda"
$env:LOCAL_BGE_BATCH_SIZE="4"
$env:HF_HUB_OFFLINE="1"
$env:TRANSFORMERS_OFFLINE="1"
$env:BACKEND_CORS_ORIGINS="http://localhost:5174,http://127.0.0.1:5174"

.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001
```

另開前端 shell，設定 `VITE_API_BASE_URL=http://127.0.0.1:8001/api` 後啟動於 5174。可先以 `GET /api/embedding-status` 確認 API 連到 trial DB，再切換前端 Local BGE Trial。

### 本機 BGE POC 第二輪狀態

POC 混合式第二輪已完成，工作檔為 `outputs/local_bge_semantic_benchmark_v1_full_second_annotations.json`。第 1 至 9 題由使用者先行判讀，第 10 至 75 題為 Codex-assisted consolidation，因此不得再將此檔作為獨立標註模板。

若未來要補正式第二位獨立標註，必須另外建立全新空白檔，例如 `outputs/local_bge_semantic_benchmark_v1_formal_independent_annotations.json`，且標註者在完成前不可查看第一輪及 POC 報告。

在專案根目錄執行：

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\evaluate_semantic_benchmark.py `
  --results .\outputs\local_bge_semantic_benchmark_v1_full.json `
  --template-out .\outputs\local_bge_semantic_benchmark_v1_formal_independent_annotations.json

.\.venv\Scripts\python.exe .\backend\scripts\annotate_semantic_benchmark.py `
  --annotations .\outputs\local_bge_semantic_benchmark_v1_formal_independent_annotations.json
```

全量標註讀取：

- 標註檔：`outputs/local_bge_semantic_benchmark_v1_formal_independent_annotations.json`
- 脈絡資料庫：`backend/data/insurance_cases_local_bge_trial.db`（唯讀）

若省略 `--annotations`，工具仍會開啟歷史 1000-candidate 工作檔，因此處理全量結果時不可省略此參數。

每筆必須選擇 `r`、`p` 或 `n`，並輸入一段以原文為依據的判斷摘要。可用 `s` 暫時略過、`q` 結束；重新執行會從第一筆未完成項目繼續。

### 啟動前端

在 `frontend/` 目錄執行：

```powershell
pnpm install
pnpm dev
```

開啟：

```text
http://127.0.0.1:5173
```

前端預設呼叫：

```text
http://127.0.0.1:8000/api
```

若要改 API 位址，可設定：

```text
VITE_API_BASE_URL
```

設定範例在 `frontend/.env.example`。

## 12. 測試方式

目前後端已有 pytest 測試，前端目前以 build 與人工檢查為主。

### 後端語法檢查

```powershell
py -m py_compile .\foi_ods_life_mvp_crawler.py
py -m py_compile .\foi_ods_pdf_text_pipeline.py
py -m py_compile .\foi_ods_case_organizer.py
py -m py_compile .\backend\scripts\import_cases_to_db.py
py -m py_compile .\backend\scripts\build_case_chunks.py
py -m py_compile .\backend\scripts\build_chunk_embeddings.py
py -m py_compile .\backend\scripts\annotate_semantic_benchmark.py
py -m py_compile .\backend\scripts\compare_embedding_models.py
py -m py_compile .\backend\scripts\compare_semantic_annotations.py
py -m py_compile .\backend\scripts\run_semantic_query_trial.py
py -m py_compile .\backend\scripts\evaluate_semantic_benchmark.py
py -m py_compile .\backend\scripts\verify_case_db.py
py -m py_compile .\backend\scripts\extract_case_summaries.py
```

### 後端 pytest

```powershell
py -m pytest
```

目前覆蓋：

- API smoke tests。
- 分析驗證 API tests。
- 統計 API 年度篩選 tests。
- 搜尋 fallback service test，包含 normalized text、案號與爭議類型 fallback。
- chunking pipeline tests。
- embedding service tests。
- 摘要擷取與 summary service tests，包含「申請人主張」標題缺少「之」與「判斷理由」非第六段的 regression tests。
- 相似案件 service tests。
- 人工標註 CLI tests，包含續作、原子儲存與唯讀相鄰 chunk 查詢。
- 匯入腳本多 metadata tests。

### SQLite 匯入驗證

```powershell
py .\backend\scripts\verify_case_db.py --expected-count 2992 --require-chunks --require-embeddings
```

### API smoke test

後端啟動後檢查：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/health -UseBasicParsing
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/statistics/overview -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/statistics/overview?roc_year=115" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/search?q=癌症" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/semantic-search?q=癌症保險金&limit=5" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/cases/{case_id}/summary" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/cases/{case_id}/similar" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/cases/{case_id}/semantic-similar?limit=5" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/quality/roc114-summary-similarity" -UseBasicParsing
```

預期：

- `/api/health` 回傳 `status: ok` 且 `database_ready: true`。
- `/api/statistics/overview` 的 `case_count` 應為 2992。
- `/api/statistics/overview?roc_year=115` 應可回傳年度篩選後的統計。
- `/api/search?q=癌症` 應有搜尋結果。
- `/api/search?q=癌症` 的前端結果應顯示 `FTS5`、`LIKE 補查` 或 `LIKE fallback` 來源標籤。
- `/api/semantic-search?q=癌症保險金` 應回傳 embedding 模型、候選 chunk 數、score 與命中段落，前端應顯示 cosine 分數與模型限制。
- `/api/cases/{case_id}/summary` 應回傳 `rule_based_v1` 摘要。
- `/api/cases/{case_id}/similar` 應回傳相似案件與命中原因。
- `/api/cases/{case_id}/semantic-similar` 應回傳案件層級語意相似案件與命中 chunk。
- `/api/quality/roc114-summary-similarity` 應回傳 ROC 114 品質檢查報告。

### 前端 build 驗證

在 `frontend/` 執行：

```powershell
pnpm build
```

預期：

- TypeScript build 成功。
- Vite build 成功。
- 若出現 chunk size warning，代表 bundle 偏大，但不等於 build 失敗。

### 前端人工驗證

後端與前端都啟動後，開啟：

```text
http://127.0.0.1:5173
```

檢查：

- Dashboard 顯示案件查找、全文搜尋、語意搜尋入口。
- Dashboard 顯示目前可查案件數與資料整理狀態。
- 案件頁可篩選、分頁、點選案件。
- 案件頁可依年度篩選。
- 案件詳情可看到 metadata、全文與 PDF 連結。
- 案件詳情可看到案件摘要。
- 案件詳情可看到相似案件。
- 搜尋頁可查「癌症」，並顯示搜尋摘要、match source、fallback 說明與 snippet。
- 語意搜尋頁可查「癌症保險金」，並顯示 embedding 模型、候選 chunk、cosine score、score bar、section hint、命中段落與本機 MVP 限制。
- 語意搜尋頁查詢「豁免保費」時會顯示可選建議與理由；預設執行原查詢，選擇建議後結果區的實際查詢詞會同步更新。
- 側邊欄不再顯示統計主入口。
- 分析驗證頁可看到摘要品質、相似度規則、抽樣案件與已知例外。
- 瀏覽器 console 無 error。

### 最近一次本機穩定檢查

2026-08-04 已完成以下檢查：

- `.\.venv\Scripts\python.exe -m pytest`：111 passed。
- `py .\backend\scripts\verify_case_db.py --expected-count 2992 --require-chunks --require-embeddings`：passed，`cases = 2992`、`case_chunks = 17254`、`chunk_embeddings = 17254`。
- embedding、案件篩選、統計總覽與模型比較腳本的 `py_compile`：通過。
- `pnpm build`：TypeScript 與 Vite production build 通過。
- `compare_embedding_models.py --query 癌症 --top 1 --json`：預設使用本機 BGE trial DB，完成 1000 個共同 chunks 離線比較。
- 正式執行程式未包含 Hugging Face router URL、Bearer header、Token 讀取或遠端 embedding HTTP client。
- `build_chunk_embeddings.py --resume --limit 100 --write-batch-size 25`：本機 CUDA trial 從 1000 增至 1100 筆，4 batches 成功、空向量 0、剩餘 16154；原有 1000 筆 embedding、norm 與 `created_at` 逐筆變更數為 0。

2026-08-05 已完成以下全量檢查：

- `build_chunk_embeddings.py --resume --write-batch-size 100`：從 1100 新增 16154 筆，162 batches 成功，總計 17254，耗時約 28 分 52 秒，裝置為 CUDA，空向量 0。
- Trial DB：BGE 17254 筆、維度全為 1024、blob 長度全為 4096 bytes、缺漏 0、非正數 norm 0、非有限值 0、`integrity_check = ok`。
- 建置前備份中的 1000 筆 embedding、norm 與 `created_at` 逐筆比較完全未變。
- 正式 DB：BGE 0 筆、`local_hashing_cjk_v1` 17254 筆、`integrity_check = ok`，未切換。
- 全量 15 詞 benchmark：每詞 17254 candidates、共 75 筆；相較 1000-candidate 結果只有 1/15 Top 1 相同，平均 Top 5 overlap 為 0.2/5。
- 全量第一輪標註：69 筆相關、4 筆部分相關、2 筆不相關；Strict / Lenient Precision@5 為 `0.9200 / 0.9733`。
- 75 筆證據摘要全部非空且不重複，最短 23 個字；本輪為 Codex-assisted 判讀，不是第二位標註者的獨立盲標。
- POC 混合式第二輪：75/75 完成，Strict / Lenient Precision@5 同為 `0.9200 / 0.9733`；與第一輪一致率及 Kappa 均為 `1.0000`，但第 10 至 75 題不是獨立來源，數值只用於流程展示。
- `.\.venv\Scripts\python.exe -m pytest`：114 passed。
- embedding build、query trial、evaluation 與 annotation 相關模組的 `py_compile`：通過。
- `verify_case_db.py --expected-count 2992 --require-chunks --require-embeddings`：passed；正式 DB 仍為 2992 案、17254 chunks、17254 筆 local hashing embeddings。
- Trial API `/api/embedding-status`：同時辨識 Local Hashing 384 維與 Local BGE 1024 維各 17254 筆。
- Local BGE API：冷啟動約 66.65 秒；暖機約 2.5 至 2.8 秒，provider / model / device / dims 均正確回傳。
- 前端 production build 與瀏覽器功能檢查通過；Local BGE 顯示實際結果，桌面無水平溢位，console 無 error 或 warning。

注意：Local BGE 語意搜尋第一次載入模型實測約 66.65 秒；暖機後仍需約 2.5 至 2.8 秒計算 17254 筆 chunk similarity。POC 展示前應先暖機，正式切換前需處理 cold start。

## 13. 建議下一步開發順序

### 已完成：規則式摘要與規則式相似案件

目前已完成：

- 規則式摘要 pipeline。
- Summary API。
- 前端案件摘要。
- 搜尋 fallback 修正。
- 後端 pytest。
- 規則式相似案件 API。
- 前端相似案件區塊。
- 分析驗證 API 與前端頁面。
- 前端結構拆分。
- 環境設定集中化與 `.env.example`。
- SQLite 匯入腳本支援多 metadata。
- 案件總覽、爭議類型 API 與前端年度篩選。
- 跨年度 pipeline 預設檔名修正與 readiness 報告。
- ROC 114 一月資料小期間試跑，metadata / PDF text / case organizer 均成功 112 筆。
- ROC 114 全年度資料試跑，metadata / PDF text / case organizer 均成功 2500 筆。
- 已建立跨年度 trial DB，ROC 114 全年度 2500 筆加 ROC 115 492 筆共 2992 筆，並已產生 2992 筆規則式摘要；`holding`、`applicant_claim`、`reasoning` 欄位均已補齊；正式 DB 已切換。
- 已修正 ROC 114 一月 32 筆亂碼資料，並新增資料品質檢查腳本。
- 已完成 ROC 114 摘要與相似案件品質檢查：摘要三欄覆蓋率 2500/2500，Top 1 同爭議類型率 99.92%，已知 2 筆稀有爭議類型因無同類候選而只能回傳低信心相似案件。
- 已在前端相似案件區塊加入低信心提示，當 Top 5 沒有同爭議類型或最高分偏低時會提示結果僅供參考。
- 已建立案件文字 chunking pipeline，正式 DB 目前有 17254 段 chunk，且 2992 筆案件皆有 chunk。
- 已建立本機 chunk embedding pipeline，正式 DB 目前有 17254 筆 `local_hashing_cjk_v1` embedding，且每個 chunk 皆有 embedding。
- 已新增前端語意搜尋頁，可展示 query、embedding 模型、候選 chunk、命中 chunk、score、section hint 與案件來源。
- 已新增案件層級語意相似 API 與案件詳情頁區塊，可展示相似案件、分數與實際命中 chunk。
- 已讓語意搜尋 API 與案件層級語意相似 API 支援 `embedding_model` / `embedding_provider` 可選參數，並加入 provider/model 維度不一致防呆。
- 已建立 embedding provider 介面，目前只啟用 `local` 與 `local_bge`；`huggingface` / `hf`、`openai` / `ai` 均會明確拒絕執行。
- 已完成本機 `BAAI/bge-large-zh-v1.5` CUDA provider、模型快取、17254 chunks / 1024 維全量 trial 與 15 詞／75 結果的完全離線 benchmark；RTX 4050 GPU 長時間推論已驗證，正式 DB 未切換。
- 已將前端主流程改為理賠案件工作台與全文搜尋；案件以彈出式 Dashboard 開啟，不改變搜尋背景 route，並支援瀏覽器式多案件分頁、關閉、最小化、重新整理還原、原文切換與正式 PDF。
- 已將理賠人員主搜尋改為 FTS5 / LIKE 與本機 BGE 的混合式查找；結果依案件去重並標示命中來源，搜尋與案件清單皆可選擇顯示 10、15 或 20 筆。語意服務失敗時會降級保留關鍵字結果。
- 案件 Dashboard 的相關案件已切換為本機 BGE 案件層級語意相似 API，畫面顯示相似度百分比與主要相近內容；規則式 `/similar` endpoint 僅保留為 baseline 與測試用途。
- 已完成全量 17254-candidate 的 75 筆 Codex-assisted 第一輪標註與評測；69 筆相關、4 筆部分相關、2 筆不相關，Strict P@5 `0.9200`、Lenient P@5 `0.9733`。最低分查詢為 `違反告知義務`，Strict P@5 `0.2000`，主要混淆來自不同角色的說明／告知義務及保費催告內容。
- 曾完成 Hugging Face API provider 與小批量試測；目前遠端 HTTP provider、response parser、retry 與 Token 設定已從 production code 移除，歷史結果只保留在文件與 trial DB。
- 已完成 Hugging Face `BAAI/bge-large-zh-v1.5` 20 筆、100 筆與 1000 筆 trial DB 試跑，trial DB 中 BGE embeddings 為 1000 筆，正式 DB 未切換。
- 已新增 `backend/scripts/compare_embedding_models.py`，可在不呼叫 Hugging Face API 的情況下，比較共同 chunks 的 local / BGE anchor-based 相似度排序。
- 已更新 `backend/scripts/run_semantic_query_trial.py`，預設以本機 BGE 執行固定 `benchmark-v1` 的 15 個 queries，並分別輸出 JSON 與 Markdown。
- 已新增 `backend/scripts/evaluate_semantic_benchmark.py`，可建立 75 筆標註模板、驗證 label 與 evidence summary，並計算 strict / lenient、macro / micro Precision@5。
- 已新增 `backend/scripts/compare_semantic_annotations.py`，可比較兩位標註者的 75 筆結果，輸出一致率、Cohen's Kappa、混淆矩陣、各查詢一致率與待仲裁衝突。
- 已新增 `backend/scripts/annotate_semantic_benchmark.py`，可在終端機逐筆閱讀本機 BGE benchmark 命中內容與相鄰 chunks，並安全續作 75 筆人工標註。
- 歷史逐題指南已更名為 `docs/local_bge_semantic_benchmark_v1_1000_assisted_guide.md`，明確限制為 1000-candidate AI 輔助流程；全量第二輪改用不含逐題提示的 `docs/local_bge_semantic_benchmark_v1_independent_guide.md`。
- 已完成本機 BGE 75/75 AI 輔助標註，並建立 `docs/local_bge_semantic_benchmark_v1_annotations.json` 與 `docs/local_bge_semantic_benchmark_v1_evaluation.md`；第 1 至 23 題由使用者在 Codex 逐題解說後輸入，第 24 至 75 題由 Codex 批次補齊。結果為 61 筆相關、6 筆部分相關、8 筆不相關，Strict P@5 0.8133、Lenient P@5 0.8933，不得表述為獨立人工盲標。
- 已完成四個低分查詢的改寫對照試驗，共 12 個查詢版本、60 筆 Top 5 AI 輔助判讀。最佳改寫的 Strict P@5 為：違反告知義務 `0.6 -> 1.0`、手術認定 `0.6 -> 1.0`、業務招攬 `0.6 -> 0.8`、豁免保費 `0.0 -> 1.0`；同時確認並非所有加長查詢都有效，暫不將固定改寫硬編碼進 production API。
- 已將可解釋查詢建議擴充至 benchmark v1 全部 15 詞，完成 75 筆建議查詢 Top 5 AI 輔助判讀。整體 Strict P@5 `0.8133 -> 0.8800`、Lenient P@5 `0.8933 -> 0.9333`，共有 6 組改善、7 組持平、2 組退步；`除外責任` 與 `理賠金額` 的建議造成明顯退步，因此不採全自動改寫。
- 已新增 `docs/hf_embedding_trial_comparison.md`，記錄 trial 模型分布、比較方法、可比較查詢詞、略過原因、Top results、100 筆與 1000 筆 query-to-document 小樣本結果與限制。
- 已新增 `docs/hf_semantic_query_trial_1000.md`，記錄 1000 筆 BGE candidates 下 5 個查詢詞的詳細 Top 5 結果。
- 已更新 `docs/hf_semantic_relevance_check_1000.md`，針對 5 個查詢詞 Top 5、共 25 筆結果做人工 relevance check，並回查 7 筆較不明確結果的 chunk 原文；最終為 24 筆相關、1 筆部分相關、0 筆待確認。
- 已完成 `docs/hf_semantic_benchmark_v1_results.md`、`docs/hf_semantic_benchmark_v1_annotations.json` 與 `docs/hf_semantic_benchmark_v1_evaluation.md`；第一輪共 61 筆相關、9 筆部分相關、5 筆不相關，Strict P@5 0.8133、Lenient P@5 0.9333。
- 已新增 `docs/ai_embedding_provider_plan.md`，規劃正式 AI embedding provider 的環境變數、費用控制、DB model version、測試與 embeddings 重建流程，並記錄本機 BGE 與歷史 Hugging Face trial 狀態。
- 已補上正式 AI provider 實作前測試保護，包含 fake provider、provider 回傳筆數檢查、向量維度檢查、`token_count` / `norm` 檢查與非有限數值檢查。
- 已更新前端 `SemanticSearchPage`，提供 Local Hashing MVP 與 Local BGE Trial 模型切換；兩種模式均實際呼叫目前 API，顯示 DB、stored embedding 數、provider、model、device、維度、耗時與候選數。Local BGE 只有在後端以 trial DB 啟動時可查，正式 DB 尚未切換。
- 已完成迭代後 Code Review：移除舊遠端 Hugging Face HTTP provider、response parser、retry / timeout 設定與專用 fake HTTP 測試；移除隱藏統計頁、重複統計 endpoints、未使用的 `recharts` 與未引用的資料庫初始化函式。

### 已完成：低分短查詢的可選建議服務核心

優先原因：

- 規則式摘要與相似案件 baseline 已完成。
- chunking、本機 embedding、前端語意搜尋展示與案件層級語意相似展示已完成。
- 前端結構已整理，後續可以承接更複雜功能。
- 跨年度 trial DB 已建立並通過資料品質檢查，正式 DB 也已切換為跨年度資料。
- 本機 BGE 1000-candidate 的 75 筆 AI 輔助標註與評測已完成。
- 15 詞離線建議試驗已完成，確認全查詢自動改寫會讓 `除外責任` 與 `理賠金額` 明顯退步。
- 原本四個低分查詢 `違反告知義務`、`手術認定`、`業務招攬`、`豁免保費` 的建議均改善，已建立可選建議服務核心。
- 目前結果不是獨立人工盲標；若要作為專題的正式品質證據，仍需第二位未接觸既有答案的標註者獨立判讀。

已完成工作：

1. 將四個已驗證改善的低分短查詢整理成獨立建議規則，不包含兩個退步案例。
2. 以 service 單元測試驗證觸發、非觸發、原文保留、建議理由與 `auto_apply = false`，未接入正式搜尋 API。
3. 服務規則已由測試核對上一階段 15 詞離線實驗資料，避免核准內容漂移。

### 已完成：建立可選查詢建議 API

已完成工作：

1. 已在 Pydantic schema 定義可選建議回應，明確區分「有建議」與「無建議」。
2. 已新增唯讀 `GET /api/query-suggestions`，只呼叫現有 service，不執行搜尋，也不修改原查詢。
3. 已新增 API tests，覆蓋 4 個核准詞、未核准詞、兩個退步案例、空白輸入與 `auto_apply = false`。

### 已完成：前端加入可選查詢建議

已完成工作：

1. 語意搜尋送出原查詢後會同步讀取查詢建議 API。
2. 有建議時顯示原查詢、建議查詢、理由、規則編號與清楚的二選一控制。
3. 預設維持原查詢；只有使用者明確選擇後才以建議查詢重新搜尋。
4. 已以桌面 1440×900 與手機 390×844 實際驗證，沒有水平溢出、按鈕重疊或 console error。

### 已完成：本機 BGE trial DB 全量建置與驗證

已完成工作：

1. 以可續跑與分批 commit pipeline 從 1100 筆接續完成剩餘 16154 chunks，全程使用本機模型快取與 CUDA。
2. 驗證 BGE embedding 數量 17254、維度 1024、blob 長度 4096 bytes、缺漏 0、空向量 0、非有限值 0 與資料庫完整性。
3. 驗證建置前備份中的 1000 筆向量未被重算，正式 DB 仍維持 local hashing。
4. 重跑固定 15 詞 benchmark，完成全量 17254 candidates 的 75 筆 Top 5 結果與 1000-candidate 排名比較。

已完成本階段第一輪品質工作：

1. 全量 benchmark 75 筆已重新判讀，未沿用 1000-candidate 舊標籤。
2. 已建立可追溯標註快照與 Strict / Lenient Precision@5 報告。
3. 已完成 POC 混合式第二輪、評測與比較流程；限制已寫入報告，未宣稱獨立信度。

下一步工作：

1. API / 前端切換 trial DB、模型庫存、錯誤處理與暖查詢驗證已完成；下一步先處理約 66.65 秒的 BGE 冷啟動，加入 startup warmup 或背景預載。
2. 量測並優化 17254 個 SQLite vectors 的每次全量解包與排序成本，再決定使用記憶體快取、FAISS 或 pgvector ANN。
3. 正式研究品質階段再由未接觸既有答案的第二位標註者，使用全新空白檔完成 75 筆判讀。
4. 正式獨立標註完成後，再計算有效的一致率、Cohen's Kappa 與爭議項目仲裁。
5. 冷啟動、搜尋效能與品質條件通過後，再另行確認是否備份並切換正式 DB。

### 第 8 階段：跨年度擴充

優先原因：

- 需要先確認現有 ROC 115 pipeline、DB、API、前端流程穩定。

建議工作：

1. 實際新增其他年度資料並匯入。
2. 檢查 `case_id` 是否能跨年度穩定唯一。
3. 抽樣驗證跨年度查找、全文搜尋與語意搜尋結果。
4. 視資料量調整搜尋效能與案件詳情載入方式。

### 第 9 階段：部署與實務化

建議工作：

1. Dockerfile。
2. docker-compose。
3. CI。
4. PostgreSQL migration 評估。
5. pgvector 評估。
6. OCR fallback 評估。
