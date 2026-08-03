# Local BGE Provider

## 1. 目標

本功能讓 `BAAI/bge-large-zh-v1.5` 在本機執行，不呼叫 Hugging Face Inference API，也不需要 `EMBEDDING_API_KEY` 或 `HF_TOKEN`。

正式 DB 目前仍維持 `local_hashing_cjk_v1`。本機 BGE 先使用獨立 trial DB 與獨立儲存模型名稱驗證：

```text
provider: local_bge
source model: BAAI/bge-large-zh-v1.5
stored model: BAAI/bge-large-zh-v1.5-local
dims: 1024
```

使用不同 stored model 名稱，是為了避免與 Hugging Face API 產生的 `BAAI/bge-large-zh-v1.5` embeddings 混用或互相覆寫。

## 2. 安裝

先建立專案隔離環境並安裝基礎套件：

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
```

CPU 版本：

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements-local-ai.txt
```

NVIDIA CUDA 13.0 版本：

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\requirements-local-ai-cuda.txt
```

驗證環境：

```powershell
.\.venv\Scripts\python.exe -c "import torch, sentence_transformers; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), sentence_transformers.__version__)"
```

目前已驗證環境為：

- Python `3.14.5`
- torch `2.13.0+cu130`
- compiled CUDA `13.0`
- sentence-transformers `5.6.1`
- device `cuda:0`
- GPU `NVIDIA GeForce RTX 4050 Laptop GPU`，約 6 GB VRAM
- 專案 `.venv` 約 3.27 GB

已實際在 GPU 建立 tensor 並執行矩陣運算，`torch.cuda.is_available()` 為 `True`；本機 BGE 1000 chunks trial 也已使用 RTX 4050 完成。

## 3. 設定

```text
EMBEDDING_PROVIDER=local_bge
EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5-local
EMBEDDING_DIMS=1024
LOCAL_BGE_DEVICE=auto
LOCAL_BGE_BATCH_SIZE=4
```

`LOCAL_BGE_DEVICE` 可用值：

- `auto`：CUDA 可用時使用 GPU，否則使用 CPU。
- `cuda`：強制使用 CUDA；不可用時明確報錯。
- `cpu`：強制使用 CPU。

若發生記憶體不足，可先將 `LOCAL_BGE_BATCH_SIZE` 降為 `2`，仍不足時改用 `cpu`。

## 4. 模型下載與離線執行

模型權重已預先下載到本機 Hugging Face cache。Production loader 固定傳入 `local_files_only=True`，執行期間只讀本機檔案；若模型不存在會直接報錯，不會自動連線下載。

可送出 Hugging Face Inference API request 的 provider 實作已從 production code 移除。`huggingface` / `hf` 只保留為拒絕 aliases；即使 shell 中殘留 `EMBEDDING_API_KEY` 或 `HF_TOKEN`，後端也不會讀取 Token，且沒有遠端 embedding request 程式可執行。

目前 Windows 未啟用 symlink，Hugging Face Hub 會使用降級快取模式，可能占用較多磁碟空間。仍建議設定以下環境變數作為第二層離線保護：

```powershell
$env:HF_HUB_OFFLINE="1"
```

此設定可強制只從本機快取載入，用來確認執行期間沒有外部模型請求。

官方來源：

- BGE 模型與 Sentence Transformers 用法：https://huggingface.co/BAAI/bge-large-zh-v1.5
- Sentence Transformers 安裝：https://www.sbert.net/docs/installation.html
- PyTorch Windows / CUDA 安裝：https://pytorch.org/get-started/locally/

## 5. 小批量 trial

先複製正式 DB，禁止直接重建正式 DB：

```powershell
Copy-Item `
  .\backend\data\insurance_cases.db `
  .\backend\data\insurance_cases_local_bge_trial.db
```

建立 1000 筆 embeddings：

```powershell
$env:HF_HUB_OFFLINE="1"
$env:LOCAL_BGE_DEVICE="cuda"
$env:LOCAL_BGE_BATCH_SIZE="2"

.\.venv\Scripts\python.exe .\backend\scripts\build_chunk_embeddings.py `
  --db .\backend\data\insurance_cases_local_bge_trial.db `
  --provider local_bge `
  --model BAAI/bge-large-zh-v1.5-local `
  --dims 1024 `
  --limit 1000
```

2026-08-03 實測結果：

- processed chunks：`1000`
- embedded chunks：`1000`
- empty chunks：`0`
- dimensions：`1024`
- verified device：`cuda`
- RTX 4050 CUDA 執行時間：約 `85.12` 秒，包含模型載入
- 先前 100 chunks CUDA 基準：約 `25.86` 秒，包含模型載入
- 先前 20 chunks CPU 基準：約 `41.1` 至 `50.8` 秒；20 chunks CUDA 基準約 `27.1` 秒

trial DB 同時保留：

- `local_hashing_cjk_v1`：17254 筆、384 維
- `BAAI/bge-large-zh-v1.5-local`：1000 筆、1024 維

## 6. 本機查詢 trial

```powershell
$env:HF_HUB_OFFLINE="1"
$env:LOCAL_BGE_DEVICE="cuda"

.\.venv\Scripts\python.exe .\backend\scripts\run_semantic_query_trial.py `
  --db .\backend\data\insurance_cases_local_bge_trial.db `
  --provider local_bge `
  --model BAAI/bge-large-zh-v1.5-local `
  --query-set benchmark-v1 `
  --limit 5 `
  --include-text `
  --json-out .\outputs\local_bge_semantic_benchmark_v1_1000.json `
  --out .\docs\local_bge_semantic_query_trial_1000.md
```

15 個查詢均已在 1000 筆 candidates 上完成 Top 5 排序，共 75 筆結果。候選範圍涵蓋 167 個案件與 25 種爭議類型；Top 5 合集涵蓋 53 個案件與 19 種爭議類型，完整結果與限制記錄於 `docs/local_bge_semantic_query_trial_1000.md`。

100 與 1000 candidates 的 15 組查詢中，只有 1 組維持相同 Top 1，平均 Top 5 chunk overlap 為 `0.53 / 5`。這表示前 100 筆候選不足以代表資料範圍，不應作為品質基準。1000 筆仍是依案件與 chunk 順序取樣，也尚未完成 75 筆獨立人工 relevance 標註，因此不能宣稱搜尋品質已通過；下一步應沿用固定 benchmark v1 標註規則，並與歷史 API BGE 結果比較。

## 7. 正式切換條件

在以下條件全部完成前，不切換正式 DB：

1. 本機 BGE 至少完成 1000 筆 trial。（已完成）
2. 固定 15 詞 benchmark 可重跑。（已完成）
3. 與 Hugging Face API BGE 的排名差異有紀錄。
4. CPU 或 GPU 的全量重建時間可接受。
5. 17254 筆 embeddings 全數建立且資料庫驗證通過。
6. 前端與 API 明確顯示實際 provider、model 與 device。
