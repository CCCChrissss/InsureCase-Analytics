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

## 下一步

1. 在前端新增語意搜尋頁或分析驗證區塊。
2. 展示 query 向量化、命中 chunk、score、section hint 與案件來源。
3. 將 chunk 層級結果聚合成案件層級相似案件。
4. 評估是否替換為正式 embedding model。
