# AI Embedding Provider 接入規格

## 1. 目標

本文件規劃如何將目前的本機 `local_hashing_cjk_v1` 語意搜尋 MVP，升級成可串接正式 AI embedding model 的工程架構。

目前已完成 Hugging Face API provider 與本機 BGE provider 的小批量接入口。目標不是立即替換正式展示 DB，而是先定義並落實清楚：

- provider 介面如何擴充。
- API key 與敏感資訊如何管理。
- embeddings 如何重建。
- model version 如何記錄。
- 如何控制費用、批次、錯誤與中斷續跑。
- 如何驗證正式模型比本機 MVP 更適合案件查找。

## 2. 目前狀態

目前已完成：

- `backend/app/services/embedding_service.py` 已有 provider factory。
- `local` provider 已實作，可離線建立 `local_hashing_cjk_v1` embeddings。
- `local_bge` provider 已實作，可透過 Sentence Transformers 在本機執行 `BAAI/bge-large-zh-v1.5`，不需要 API token；CPU 與 RTX 4050 CUDA 20 chunks trial 均已通過。
- `huggingface` / `hf` provider 已實作，可透過 Hugging Face Inference API Feature Extraction 取得 embeddings。
- Hugging Face provider 預設模型為 `BAAI/bge-large-zh-v1.5`，預設維度 1024。
- Hugging Face provider 支援：
  - `EMBEDDING_API_KEY` 或 `HF_TOKEN`
  - `EMBEDDING_BATCH_SIZE`
  - `EMBEDDING_MAX_RETRIES`
  - `EMBEDDING_RETRY_BACKOFF_SECONDS`
  - `EMBEDDING_TIMEOUT_SECONDS`
  - `HUGGINGFACE_API_BASE_URL`
- `openai` / `ai` provider 名稱已保留，但目前會明確拋出 `EmbeddingProviderError`。
- `backend/scripts/build_chunk_embeddings.py` 已支援：
  - `--provider`
  - `--model`
  - `--dims`
  - `--limit`
- provider 輸出已加入防呆檢查：
  - 回傳筆數必須等於輸入文字筆數。
  - 向量維度必須等於 provider dims。
  - `token_count` 不可為負數。
  - `norm` 必須是有限且非負數。
  - vector 不可包含 NaN 或 Infinity。
- `backend/tests/test_embedding_service.py` 已加入 fake provider 與 fake Hugging Face HTTP client 測試，不需要呼叫外部 API 即可驗證寫入、回應解析、重試與異常輸出。
- `chunk_embeddings` 已用 `(chunk_id, embedding_model)` 作為主鍵，可同時保留不同模型的 embeddings。
- 語意搜尋 API 與案件層級語意相似 API 目前會依 `embedding_model` 查詢向量。
- `GET /api/semantic-search` 與 `GET /api/cases/{case_id}/semantic-similar` 已支援 `embedding_model` / `embedding_provider` query 參數。
- Hugging Face trial DB 已完成 `--limit 20` 與 `--limit 100` 試跑。
- `docs/hf_embedding_trial_comparison.md` 已記錄 100 筆 trial embeddings 與 local hashing 的離線 anchor-based 比較。

目前正式 DB 狀態：

- `case_chunks`：17254
- `chunk_embeddings`：17254
- `embedding_model`：`local_hashing_cjk_v1`
- `embedding_dims`：384

目前 Hugging Face trial DB 狀態：

- Trial DB：`backend/data/insurance_cases_hf_trial.db`
- BGE embeddings：100 筆
- `embedding_model`：`BAAI/bge-large-zh-v1.5`
- `embedding_dims`：1024

## 3. 目前暫不執行範圍

這一階段不做：

- 不提交任何 API key。
- pytest 不呼叫外部 AI API。
- 不重建正式 DB 的 embeddings。
- 不改前端畫面。
- 不改 `data/` 或 `backend/data/`。
- 不導入 PostgreSQL / pgvector。

原因：正式 AI provider 會影響費用、模型版本、向量維度、重建時間與展示結果。程式已具備小批量接入口，但正式展示 DB 是否切換需要先試跑與抽樣驗證。

## 4. Provider 設計

目前 provider 介面：

```python
class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    dims: int

    def embed_texts(self, texts: list[str]) -> list[EmbeddedText]:
        pass
```

正式 AI provider 應遵守：

- 輸入：`list[str]`
- 輸出：與輸入長度相同的 `list[EmbeddedText]`
- 每筆輸出包含：
  - `vector`
  - `norm`
  - `token_count`
- 不可在 provider 內靜默 fallback 到 `local`。
- 失敗時應拋出明確錯誤，讓建置腳本停止或進入重試流程。

Hugging Face 範例：

```text
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5
EMBEDDING_DIMS=1024
EMBEDDING_API_KEY=<only in shell env or deployment secret>
```

其他 provider 建議命名：

```text
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=<official-model-name>
EMBEDDING_DIMS=<model-dimensions>
```

注意：`EMBEDDING_MODEL` 必須寫入 `chunk_embeddings.embedding_model`，因為 API 會依 model name 查詢 embeddings。

## 5. 環境變數設計

目前已有：

```text
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=local_hashing_cjk_v1
EMBEDDING_DIMS=384
```

外部 AI provider 支援：

```text
EMBEDDING_API_KEY=<only in .env or deployment secret>
HF_TOKEN=<Hugging Face token alias>
HUGGINGFACE_API_BASE_URL=https://router.huggingface.co/hf-inference/models
EMBEDDING_BATCH_SIZE=16
EMBEDDING_MAX_RETRIES=3
EMBEDDING_RETRY_BACKOFF_SECONDS=2
EMBEDDING_TIMEOUT_SECONDS=60
```

規則：

- `.env.example` 只能列變數名稱與範例格式，不可放真實 key。
- `.env` 不可提交 Git。
- provider 讀不到必要 API key 時，應明確報錯。
- 不要在程式碼、README、測試或 commit history 中硬編碼 key。

目前 `.env.example` 已列出上述外部 provider 變數名稱與 Hugging Face 範例；所有 token 欄位都只能放假值或空值。

## 6. Model 選擇原則

正式模型選擇時應評估：

- 是否支援中文與繁體中文語境。
- 是否適合長文本切片後的語意檢索。
- 向量維度與儲存成本。
- API 成本與 rate limit。
- 是否能穩定批次處理 17254 個 chunks。
- 未來是否容易擴充到更多年度。

本專案目前第一個外部 provider 選用 `BAAI/bge-large-zh-v1.5` 作為預設 Hugging Face model，原因是它是中文 embedding model、模型頁標示 MIT license、維度為 1024，且可透過 Hugging Face Feature Extraction 介面試跑。

其他候選模型仍可透過 `--model` 與 `--dims` 指定，但必須先確認模型授權、維度、API 可用性與成本。

## 7. Batch 策略

正式 provider 不應一筆一筆送 API。

建議流程：

1. 從 `case_chunks` 讀取尚未建立指定 `embedding_model` 的 chunks。
2. 依 `EMBEDDING_BATCH_SIZE` 分批。
3. 每批呼叫 provider。
4. 成功後立即寫入 `chunk_embeddings`。
5. 失敗時保留已完成批次，方便續跑。

建議 script 行為：

```text
py .\backend\scripts\build_chunk_embeddings.py --provider huggingface --model BAAI/bge-large-zh-v1.5 --dims 1024
```

試跑時先用：

```text
py .\backend\scripts\build_chunk_embeddings.py --provider huggingface --model BAAI/bge-large-zh-v1.5 --dims 1024 --limit 100
```

## 8. Retry 與 Rate Limit

正式 provider 應處理：

- timeout
- rate limit
- 暫時性 5xx
- network error
- 單筆文字過長

建議策略：

- 預設最多重試 3 次。
- 使用遞增等待時間。
- 對不可重試錯誤直接停止。
- 錯誤訊息應包含 provider、model、batch index，但不可包含 API key。
- 建置報告應列出失敗 chunk 數與前幾個 chunk_id。

## 9. 費用控制

正式串接前必須先做小批量試跑。

建議順序：

1. `--limit 20`
2. `--limit 100`
3. `--limit 1000`
4. 全量 17254 chunks

每次都應記錄：

- provider
- model
- dims
- processed_chunks
- embedded_chunks
- failed_chunks
- started_at
- finished_at
- estimated or actual cost

若 provider API 無法直接回傳費用，至少應記錄 token 或輸入字元統計，方便後續估算。

## 10. DB 與 Model Version 管理

目前 `chunk_embeddings` schema 已可用同一 chunk 保留多個模型：

```sql
PRIMARY KEY(chunk_id, embedding_model)
```

因此正式模型建議使用新的 model name 寫入，不要覆蓋 `local_hashing_cjk_v1`。

範例：

```text
local_hashing_cjk_v1
official_ai_model_v1
```

未來若同一 provider 更換維度或前處理規則，也應更換 `embedding_model` 名稱，避免新舊向量混在一起。

後續可考慮新增 `embedding_runs` 表，記錄每次重建：

```sql
run_id
provider
embedding_model
embedding_dims
chunk_count
success_count
failed_count
started_at
finished_at
status
notes
```

## 11. API 設計影響

短期可沿用目前 API：

```text
GET /api/semantic-search
GET /api/cases/{case_id}/semantic-similar
```

中期建議增加可選參數：

```text
embedding_model=<model-name>
embedding_provider=<provider-name>
```

用途：

- 比較 local MVP 與正式 AI model。
- 展示不同模型的搜尋結果差異。
- 避免後端只依環境變數選模型，導致展示結果不易追蹤。

目前已完成：

```text
GET /api/semantic-search?q=癌症保險金&embedding_provider=huggingface&embedding_model=BAAI/bge-large-zh-v1.5
GET /api/cases/{case_id}/semantic-similar?embedding_model=BAAI/bge-large-zh-v1.5
```

注意：`/api/semantic-search` 需要產生 query embedding，因此 BGE 查詢需要 Hugging Face token，且會消耗額度。若 selected model 的 stored embeddings 維度與 query provider 輸出維度不一致，API 會回傳 400。

## 12. 測試策略

不需要在 pytest 中呼叫真實 AI API。

建議測試：

- `local` provider 正常。
- `huggingface` provider 在缺 API key 時明確報錯。
- `huggingface` provider 可用 fake HTTP client 驗證 batch payload、Authorization header、常見回應格式解析、空字串略過、retryable HTTP status 重試與 non-retryable HTTP status 報錯。
- `openai` / `ai` provider 仍明確標示預留未實作。
- fake provider 可模擬固定向量回傳。此項目前已完成。
- batch 寫入不會破壞既有 embeddings。
- 同一 chunk 可保留不同 `embedding_model`。
- `dims <= 0` 會報錯。此項目前已完成。
- provider 回傳數量與輸入數量不一致時會報錯。此項目前已完成。
- provider 回傳維度錯誤或非有限數值時會報錯。此項目前已完成。
- API 查詢指定不存在的 `embedding_model` 時應回傳空結果或明確錯誤。
- API 查詢指定 model / provider 維度不一致時應回傳 400，避免錯誤相似度。

## 13. 驗證流程

正式 provider 實作後，建議驗證指令：

```powershell
py -m pytest .\backend\tests\test_embedding_service.py
py -m pytest
py -m py_compile .\backend\app\services\embedding_service.py .\backend\scripts\build_chunk_embeddings.py
py .\backend\scripts\build_chunk_embeddings.py --provider huggingface --model BAAI/bge-large-zh-v1.5 --dims 1024 --limit 100
py .\backend\scripts\verify_case_db.py --expected-count 2992 --require-chunks --require-embeddings
```

若執行全量重建，完成後應確認：

- `chunk_embeddings` 中新 model 的筆數等於 `case_chunks`。
- `chunks_without_embeddings = 0`。
- 語意搜尋 API 可回傳新 model 結果。
- 案件層級語意相似仍可回傳 `matched_chunks`。

## 14. 專題展示說法

目前可說：

```text
系統目前正式 DB 使用本機 CJK hashing vector 完成語意搜尋 MVP，
已建立 provider 邊界，並完成 Hugging Face API 與本機 BGE 小批量接入口。
本機 BGE 已在 CPU 完成 20 chunks 離線 trial，不需要 API token；
正式展示 DB 若要切換，仍需擴大 benchmark 並重建 chunk_embeddings，
案件搜尋 API 與前端展示流程可大致沿用。
```

不要說：

```text
目前已經串接 OpenAI。
目前正式展示 DB 已經使用 Hugging Face embeddings。
目前語意分數等同法律相似度。
目前模型已可取代專業判斷。
```

## 15. 建議實作順序

1. 將本機 BGE trial 從 20 擴大到 100、1000 筆，與既有 API BGE benchmark 比較。
2. 驗證 CUDA PyTorch，記錄 CPU / GPU 建置時間與記憶體使用。
3. 在前端展示實際 provider、model 與 device。
4. 品質與效能可接受後，再考慮全量重建正式 DB。
5. 後續如需 OpenAI 或其他 provider，再在 `embedding_service.py` 新增 provider。
