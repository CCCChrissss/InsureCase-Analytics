# Chunk Embedding Pipeline

## 目標

在 `case_chunks` 基礎上建立可查詢的向量資料，讓系統可以先用 chunk 層級做語意搜尋，後續再聚合成案件層級的相似案件推薦。

目前正式展示資料仍是學校專題版 MVP：使用本機純 Python hashing vector，不依賴外部 API，也不需要 API key。

程式已另外支援 Hugging Face embedding provider，可用於小批量試跑與後續正式 AI embedding 替換；但只改 provider 設定不會改變既有 DB 內容，必須重建 `chunk_embeddings`。

## 目前模型

```text
local_hashing_cjk_v1
```

目前 provider 設定：

```text
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=local_hashing_cjk_v1
EMBEDDING_DIMS=384
```

方法：

- 對中文文字抽取 CJK 2-gram 與 3-gram。
- 對英文與數字抽取基本 token。
- 使用 `blake2b` 將 token hash 到固定維度。
- 預設維度為 384。
- 對向量做 L2 normalize。
- 查詢時使用 cosine similarity，也就是 normalized vector dot product。

這不是正式語意模型。它的用途是先建立完整資料流、API 與可展示分析過程。

## 資料表

```sql
CREATE TABLE IF NOT EXISTS chunk_embeddings (
  chunk_id TEXT NOT NULL,
  embedding_model TEXT NOT NULL,
  embedding_dims INTEGER NOT NULL,
  embedding BLOB NOT NULL,
  embedding_norm REAL NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(chunk_id) REFERENCES case_chunks(chunk_id) ON DELETE CASCADE,
  PRIMARY KEY(chunk_id, embedding_model)
);
```

## 執行方式

在專案根目錄執行：

```powershell
py .\backend\scripts\build_chunk_embeddings.py --db .\backend\data\insurance_cases.db
```

可選參數：

```powershell
py .\backend\scripts\build_chunk_embeddings.py --provider local --model local_hashing_cjk_v1 --dims 384 --limit 100
```

provider 狀態：

- `local`：目前正式 DB 使用的 provider。
- `local_hashing`：`local` 的相容別名。
- `local_bge`：本機 Sentence Transformers BGE，stored model 為 `BAAI/bge-large-zh-v1.5-local`、1024 維，只讀本機模型快取。
- `huggingface` / `hf`：遠端 Inference API 已停用，指定時會在 HTTP request 前明確報錯。
- `openai` / `ai`：預留給未來正式 AI integration，目前會明確拋出錯誤，不會自動 fallback。

注意：`chunk_embeddings.embedding_model` 是 API 查詢時用來選向量的關鍵欄位。只改環境變數不會改變既有 DB 內的向量；換正式模型後必須重建 embeddings。

本機 BGE 小批量試跑：

```powershell
$env:LOCAL_BGE_DEVICE="cuda"
.\.venv\Scripts\python.exe .\backend\scripts\build_chunk_embeddings.py --db .\backend\data\insurance_cases_local_bge_trial.db --provider local_bge --model BAAI/bge-large-zh-v1.5-local --dims 1024 --limit 100
```

注意：上述指令會寫入指定 DB 的 `chunk_embeddings`。正式試跑前建議先複製 DB 或使用 trial DB，避免直接改正式展示資料。

目前已完成 trial DB 小樣本驗證：

- `--limit 20`：成功。
- `--limit 100`：成功。
- Trial DB：`backend/data/insurance_cases_local_bge_trial.db`。
- BGE embeddings：`BAAI/bge-large-zh-v1.5-local`，1024 維，100 筆。
- Local embeddings：`local_hashing_cjk_v1`，384 維，17254 筆仍保留。
- 離線 benchmark 報告：`docs/local_bge_semantic_query_trial_100.md`。

## 驗證方式

```powershell
py -m py_compile .\backend\app\services\embedding_service.py .\backend\scripts\build_chunk_embeddings.py .\backend\scripts\verify_case_db.py
py -m pytest
py .\backend\scripts\verify_case_db.py --expected-count 2992 --require-chunks --require-embeddings
```

目前正式 DB 驗證結果：

- `case_chunks`：17254
- `chunk_embeddings`：17254
- `chunks_without_embeddings`：0
- `embedding_model`：`local_hashing_cjk_v1`
- `embedding_dims`：384

## API

```text
GET /api/semantic-search
```

Query parameters：

- `q`：查詢文字。
- `limit`：回傳筆數，預設 10，上限 50。
- `min_score`：最低分數，預設 0。
- `embedding_model`：可選，指定要查詢的 `chunk_embeddings.embedding_model`。
- `embedding_provider`：可選，指定 query 文字要使用哪個 provider 轉向量。

範例：

```text
GET /api/semantic-search?q=癌症保險金&limit=3
```

指定本機 BGE 試驗模型的範例：

```text
GET /api/semantic-search?q=癌症保險金&embedding_provider=local_bge&embedding_model=BAAI/bge-large-zh-v1.5-local
```

注意：`/api/semantic-search` 需要把查詢文字也轉成向量；本機 BGE 會從本機快取載入模型。指定 `huggingface` / `hf` 時 API 會回傳 400，且不會呼叫外部服務。

回傳內容包含：

- `chunk_id`
- `case_id`
- `case_number`
- `dispute_type`
- `section_hint`
- `chunk_index`
- `score`
- `chunk_text`

案件層級語意相似：

```text
GET /api/cases/{case_id}/semantic-similar?limit=5
```

可選參數：

- `embedding_model`：指定要使用哪個 stored embedding model。
- `embedding_provider`：指定 provider；案件層級相似主要讀取已存在 embeddings，通常只指定 `embedding_model` 即可。

做法：

1. 讀取來源案件所有 chunk embeddings。
2. 平均並 normalize 成來源案件 centroid。
3. 比對候選案件的 chunk embeddings。
4. 依案件分組，取最高分與前幾個命中 chunk。
5. 回傳相似案件、分數與命中段落。

## 學校專題版與實務版差異

學校專題版：

- 使用本機 hashing vector。
- 不需要外部 API。
- 適合展示資料流、chunking、向量化、相似度計算與查詢結果。

實務版：

- 建議改用正式 embedding model，例如 Hugging Face BGE、OpenAI embedding 或其他中文/多語 embedding model。
- 建議使用 PostgreSQL + pgvector 或其他 ANN index。
- 需要記錄 model version、向量維度、重建時間與資料版本。
- 需要建立評估集，避免只憑主觀感覺判斷相似度品質。

## 前端展示

目前已新增前端語意搜尋頁：

```text
?view=semantic
```

頁面會展示：

- 查詢文字。
- embedding 模型。
- 候選 chunk 數。
- 命中 chunk。
- cosine similarity score。
- section hint。
- 案件來源。

案件詳情頁也已新增「語意相似案件」區塊，會展示：

- 案件層級語意相似分數。
- 候選案件基本資料。
- 實際命中的 chunk。
- chunk score、section hint 與段落文字。

## 串接實際 AI 模型的替換點

目前 `local_hashing_cjk_v1` 是本機 MVP。程式已先建立 provider factory：

- `local`：目前可用，使用本機 CJK hashing vector。
- `local_bge`：目前可用，在本機 CPU 或 CUDA 執行 BGE。
- `huggingface` / `hf`：遠端 API 已停用，避免外部費用。
- `openai` / `ai`：目前會明確回報尚未實作，避免誤以為已經串接 OpenAI 類 provider。

未來若要改成實際 AI embedding model，建議做法：

1. 先用 `local_bge` provider 進行 `--limit 20` / `--limit 100` / `--limit 1000` 小批量試跑。
2. 保留目前 `local` provider 作為可離線比較基準。
3. 重跑 `backend/scripts/build_chunk_embeddings.py`，以 `BAAI/bge-large-zh-v1.5-local` 寫入 trial DB。
4. 執行 `.venv` 內的 pytest 與 `verify_case_db.py --require-embeddings`。
5. API query 已支援 `embedding_model` / `embedding_provider` 參數，可比較 local hashing 與本機 BGE。
6. 若資料量擴大，再將 SQLite BLOB 改成 PostgreSQL + pgvector 或其他 ANN index。

目前程式不讀取 Hugging Face API Token，`.env.example` 也不再提供遠端 Token 欄位。

## 下一步

1. 在 trial DB 上以 `embedding_provider=local_bge` 進行 query-to-document 比較。
2. 將前端語意搜尋頁加上模型切換與模型限制提示。
3. 若品質與成本可接受，再擴大到 `--limit 1000` 或全量重建 trial DB。
