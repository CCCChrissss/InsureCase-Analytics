# Chunk Embedding Pipeline

## 目標

在 `case_chunks` 基礎上建立可查詢的向量資料，讓系統可以先用 chunk 層級做語意搜尋，後續再聚合成案件層級的相似案件推薦。

目前版本是學校專題版 MVP：使用本機純 Python hashing vector，不依賴外部 API，也不需要 API key。

## 目前模型

```text
local_hashing_cjk_v1
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
py .\backend\scripts\build_chunk_embeddings.py --dims 384 --limit 100
```

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

範例：

```text
GET /api/semantic-search?q=癌症保險金&limit=3
```

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

- 建議改用正式 embedding model，例如 OpenAI embedding 或中文/多語 embedding model。
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

目前 `local_hashing_cjk_v1` 是本機 MVP。未來若要改成實際 AI embedding model，建議做法：

1. 在 `backend/app/services/embedding_service.py` 新增 provider 介面，例如 `embed_texts(texts) -> list[list[float]]`。
2. 保留目前 `local_hashing_cjk_v1` 作為 fallback provider。
3. 新增 AI provider，例如 OpenAI embedding 或其他中文/多語 embedding model。
4. 重跑 `backend/scripts/build_chunk_embeddings.py`，用新 `embedding_model` 名稱寫入 `chunk_embeddings`。
5. API query 可增加 `embedding_model` 參數，讓展示時能比較 local model 與 AI model。
6. 若資料量擴大，再將 SQLite BLOB 改成 PostgreSQL + pgvector 或其他 ANN index。

注意：不要把 API key 寫入程式碼或 commit 到 Git；應使用 `.env` / 環境變數，並只在 `.env.example` 說明變數名稱。

## 下一步

1. 抽樣評估目前 local model 的語意相似品質。
2. 決定要串接哪一個正式 AI embedding model。
3. 建立 provider 介面與環境變數設定。
