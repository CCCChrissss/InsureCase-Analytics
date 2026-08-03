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

已實際在 GPU 建立 tensor 並執行矩陣運算，`torch.cuda.is_available()` 為 `True`；本機 BGE 三筆中文 embedding 與 20 chunks trial 也已使用 RTX 4050 完成。

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

第一次載入會從 Hugging Face Hub 下載約 1.3 GB 模型權重。這是公開模型下載，不是 Inference API 呼叫，不會消耗 Inference Providers credits。

目前 Windows 未啟用 symlink，Hugging Face Hub 會使用降級快取模式，可能占用較多磁碟空間。下載完成後可設定：

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

建立 20 筆 embeddings：

```powershell
$env:HF_HUB_OFFLINE="1"
$env:LOCAL_BGE_DEVICE="cuda"
$env:LOCAL_BGE_BATCH_SIZE="2"

.\.venv\Scripts\python.exe .\backend\scripts\build_chunk_embeddings.py `
  --db .\backend\data\insurance_cases_local_bge_trial.db `
  --provider local_bge `
  --model BAAI/bge-large-zh-v1.5-local `
  --dims 1024 `
  --limit 20
```

2026-08-03 實測結果：

- processed chunks：`20`
- embedded chunks：`20`
- empty chunks：`0`
- dimensions：`1024`
- verified devices：`cpu`、`cuda`
- CPU 兩次執行時間：約 `41.1` 至 `50.8` 秒，包含模型載入
- RTX 4050 CUDA 執行時間：約 `27.1` 秒，包含模型載入

trial DB 同時保留：

- `local_hashing_cjk_v1`：17254 筆、384 維
- `BAAI/bge-large-zh-v1.5-local`：20 筆、1024 維

## 6. 本機查詢 trial

```powershell
$env:HF_HUB_OFFLINE="1"
$env:LOCAL_BGE_DEVICE="cuda"

.\.venv\Scripts\python.exe .\backend\scripts\run_semantic_query_trial.py `
  --db .\backend\data\insurance_cases_local_bge_trial.db `
  --provider local_bge `
  --model BAAI/bge-large-zh-v1.5-local `
  --query 癌症 `
  --query 住院 `
  --query 除外責任 `
  --limit 3
```

三個查詢均已在 20 筆 candidates 上完成排序，證明 query embedding 與 stored embeddings 可以完全離線配對。

20 筆 candidates 太少，只能證明流程可用，不能用來宣稱搜尋品質。下一步應擴充到 100 或 1000 筆本機 embeddings，再用固定 benchmark v1 比較排名品質。

## 7. 正式切換條件

在以下條件全部完成前，不切換正式 DB：

1. 本機 BGE 至少完成 1000 筆 trial。
2. 固定 15 詞 benchmark 可重跑。
3. 與 Hugging Face API BGE 的排名差異有紀錄。
4. CPU 或 GPU 的全量重建時間可接受。
5. 17254 筆 embeddings 全數建立且資料庫驗證通過。
6. 前端與 API 明確顯示實際 provider、model 與 device。
