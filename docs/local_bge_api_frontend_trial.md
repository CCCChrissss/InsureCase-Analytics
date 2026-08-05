# Local BGE API / Frontend Trial

## 1. 範圍

- 日期：2026-08-05
- Trial DB：`backend/data/insurance_cases_local_bge_trial.db`
- API：FastAPI `GET /api/embedding-status`、`GET /api/semantic-search`
- 前端：React `SemanticSearchPage`
- Provider：`local_bge`
- Stored model：`BAAI/bge-large-zh-v1.5-local`
- 裝置：NVIDIA GeForce RTX 4050 Laptop GPU / CUDA
- 外部 embedding API：未使用

本次只驗證獨立 trial DB，不切換或修改正式 DB。

## 2. 啟動條件

Local BGE 必須使用專案 `.venv` 啟動。系統 `py` launcher 目前指向 CPU-only PyTorch，強制 `LOCAL_BGE_DEVICE=cuda` 時會正確回傳 HTTP 400；專案 `.venv` 則為 CUDA build，`torch.cuda.is_available()` 為 `True`。

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

前端另以 `VITE_API_BASE_URL=http://127.0.0.1:8001/api` 啟動於 `5174`。

## 3. Embedding 庫存

`GET /api/embedding-status` 實測：

| Stored model | Provider | 維度 | 筆數 |
| --- | --- | ---: | ---: |
| `local_hashing_cjk_v1` | `local` | 384 | 17,254 |
| `BAAI/bge-large-zh-v1.5-local` | `local_bge` | 1,024 | 17,254 |

搜尋前會先檢查 stored model 是否存在、維度是否唯一，以及 provider / model 是否相容。沒有 stored embeddings 時會在載入本機模型前回傳 HTTP 400。

## 4. 查詢效能

查詢詞皆在 17,254 個 chunk candidates 上做 cosine similarity 全量掃描。

| 情境 | 查詢詞 | API 耗時 | 結果 |
| --- | --- | ---: | --- |
| 冷啟動 | 除外責任 | 66,652.54 ms | 成功，CUDA，Top 1 score 0.6555 |
| 暖機 | 除外責任 | 2,484.76 ms | 成功 |
| 暖機 3 次平均 | 必要性醫療 | 2,499.95 ms | wall time 平均 2,589.13 ms |
| 前端實測 | 除外責任 | 2,832.35 ms | 成功顯示 10 筆 |

結論：暖機後已可作為本機 POC 展示；冷啟動約 66.65 秒，不符合一般互動式搜尋期待。API 應維持常駐，後續需增加啟動 warmup 或背景預載，並評估把 SQLite 全量向量掃描改為記憶體快取或 ANN index。

## 5. GPU 觀察限制

Windows WDDM 下 `nvidia-smi` 無法提供此 Python process 的可歸屬 VRAM 數字。模型載入後曾觀察整張 GPU 使用量為 2,045 MiB，但該值包含其他圖形與系統程序，不能宣稱為 API 或 BGE 模型的獨占記憶體。

## 6. 錯誤處理驗證

- 選到 DB 中不存在的 stored model：HTTP 400，明確指出 DB 名稱與缺少的模型。
- `huggingface` / `hf` provider：HTTP 400，明確說明遠端 provider 已移除，不送出外部 request。
- `local` provider 搭配 BGE model：HTTP 400，避免以 hashing 演算法冒充 BGE。
- 系統 Python 強制 CUDA 但 PyTorch 為 CPU build：HTTP 400，提示改用 CPU 或安裝 CUDA build。

## 7. 前端驗證

- Local Hashing 與 Local BGE 均會實際呼叫目前 API，不再只展示靜態 trial 摘要。
- 顯示 API DB、stored embedding 筆數、provider、model、device、維度、API elapsed、候選數與結果數。
- Local Hashing 在後端全域設定為 BGE 1024 維時，仍依 DB 庫存正確使用 384 維。
- Local BGE 暖機查詢顯示 `local_bge / cuda / 1024 / 17,254` 與實際命中 chunk。
- 桌面 viewport 沒有水平溢位，browser console 無 warning 或 error。
- 400 response 會顯示後端 `detail`，不再只顯示一般化的 request failure。

## 8. 判定

- 功能 POC：通過。
- 完全離線本機推論：通過。
- 暖機互動時間：通過目前小於 5 秒的 POC 目標。
- 冷啟動互動時間：未通過，列為正式切換前技術債。
- 正式 DB 切換：未執行。
- 獨立第二位人工標註：未完成。
