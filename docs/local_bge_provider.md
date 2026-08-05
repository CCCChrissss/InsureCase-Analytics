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

已實際在 GPU 建立 tensor 並執行矩陣運算，`torch.cuda.is_available()` 為 `True`；本機 BGE 全量 17254 chunks trial 也已使用 RTX 4050 完成。

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
- `BAAI/bge-large-zh-v1.5-local`：17254 筆、1024 維

## 5.1 可續跑批次建置

2026-08-04 起，`build_chunk_embeddings.py` 支援只處理缺漏 chunks：

```powershell
$env:HF_HUB_OFFLINE="1"
$env:LOCAL_BGE_DEVICE="cuda"
$env:LOCAL_BGE_BATCH_SIZE="4"

.\.venv\Scripts\python.exe .\backend\scripts\build_chunk_embeddings.py `
  --db .\backend\data\insurance_cases_local_bge_trial.db `
  --provider local_bge `
  --model BAAI/bge-large-zh-v1.5-local `
  --dims 1024 `
  --resume `
  --limit 100 `
  --write-batch-size 25
```

- `--resume`：跳過已存在 `BAAI/bge-large-zh-v1.5-local` 的 chunks。
- `--limit 100`：在 resume 模式下最多新增 100 筆，不是重算前 100 筆。
- `--write-batch-size 25`：每 25 筆 commit 一次；中斷後已完成批次仍保留。
- `LOCAL_BGE_BATCH_SIZE=4`：模型內部 GPU 推論 batch，與 SQLite write batch 不同。

100 筆 resume smoke test 實測：

- existing embeddings：`1000`
- selected / processed / embedded：`100 / 100 / 100`
- completed write batches：`4`
- total embeddings：`1100`
- remaining chunks：`16154`
- empty embeddings：`0`
- device：`cuda`
- wall time：約 `23.6` 秒，包含模型載入
- 原有 1000 筆 embedding、norm、`created_at` 逐筆比較變更數：`0`

## 5.2 全量建置

2026-08-05 使用同一個 trial DB 以 `--resume --write-batch-size 100` 完成剩餘 16154 筆：

- existing embeddings：`1100`
- selected / processed / embedded：`16154 / 16154 / 16154`
- completed write batches：`162`
- total embeddings：`17254`
- remaining chunks：`0`
- empty embeddings：`0`
- device：`cuda`
- wall time：約 `28 分 52 秒`
- dimensions / blob length：`1024 / 4096 bytes`
- missing、空向量、非正數 norm、非有限數值：皆為 `0`
- 建置前備份中的 1000 筆 embedding、norm、`created_at`：逐筆完全未變
- trial DB `integrity_check`：`ok`

正式 DB 同期驗證仍只有 `local_hashing_cjk_v1` 17254 筆，BGE 為 0 筆。完整證據與限制記錄於 `docs/local_bge_full_build_report.md`。

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
  --json-out .\outputs\local_bge_semantic_benchmark_v1_full.json `
  --out .\docs\local_bge_semantic_query_trial_full.md
```

15 個查詢均已在全量 17254 筆 candidates 上完成 Top 5 排序，共 75 筆結果。Top 5 合集涵蓋 73 個案件與 21 種爭議類型，完整結果記錄於 `docs/local_bge_semantic_query_trial_full.md`。

1000 與 17254 candidates 的 15 組查詢中，只有 1 組維持相同 Top 1，平均 Top 5 chunk overlap 為 `0.2 / 5`。這表示 1000 筆候選不足以代表全資料排名，不應作為全量品質基準。舊標註沒有直接套用；全量結果已另做 Codex-assisted 第一輪判讀，Strict / Lenient Precision@5 為 `0.9200 / 0.9733`。

## 7. 人工標註

第一輪 75 筆已完成，追蹤版快照與評測報告為：

- `docs/local_bge_semantic_benchmark_v1_full_annotations.json`
- `docs/local_bge_semantic_benchmark_v1_full_evaluation.md`

POC 混合式第二輪也已完成：第 1 至 9 題由使用者先行判讀，第 10 至 75 題為 Codex-assisted consolidation。追蹤版快照、評測及比較報告為：

- `docs/local_bge_semantic_benchmark_v1_poc_second_annotations.json`
- `docs/local_bge_semantic_benchmark_v1_poc_second_evaluation.md`
- `docs/local_bge_semantic_benchmark_v1_poc_comparison.md`

POC 第二輪不是獨立盲標，一致率與 Kappa 即使為 `1.0000` 也不能當作正式信度證據。未來若要補正式第二位獨立標註，必須建立另一個全新空白檔，且標註者不可查看第一輪與 POC 答案：

正式獨立標註可使用 `docs/local_bge_semantic_benchmark_v1_independent_guide.md` 的共同標準；不得使用歷史 `docs/local_bge_semantic_benchmark_v1_1000_assisted_guide.md`，因其題目對應舊的 1000-candidate 結果且包含逐題提示。

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\evaluate_semantic_benchmark.py `
  --results .\outputs\local_bge_semantic_benchmark_v1_full.json `
  --template-out .\outputs\local_bge_semantic_benchmark_v1_formal_independent_annotations.json

.\.venv\Scripts\python.exe .\backend\scripts\annotate_semantic_benchmark.py `
  --annotations .\outputs\local_bge_semantic_benchmark_v1_formal_independent_annotations.json
```

未指定 `--annotations` 時，預設仍會開啟歷史 1000-candidate 工作檔；正式全量標註必須明確指定上述新路徑。工具會逐筆顯示：

- 查詢詞、排名與 cosine score。
- 案號、爭議類型與段落提示。
- 命中 chunk 原文及前後相鄰 chunk。

標註快捷鍵：`r` 相關、`p` 部分相關、`n` 不相關、`s` 暫時略過、`q` 結束。選擇 relevance label 後，還必須填寫原文證據摘要；完成一筆就會立即安全寫入 JSON，重新執行時會從未完成項目續作。

只處理單一查詢詞：

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\annotate_semantic_benchmark.py `
  --annotations .\outputs\local_bge_semantic_benchmark_v1_formal_independent_annotations.json `
  --query 除外責任
```

重新檢查或修改第 1 筆：

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\annotate_semantic_benchmark.py `
  --annotations .\outputs\local_bge_semantic_benchmark_v1_formal_independent_annotations.json `
  --index 1
```

標註工具只讀 trial DB，且不載入模型、不呼叫 Hugging Face 或其他外部 API。

正式第二輪 75 筆全部完成後，先產生評測，再比較兩位獨立標註者：

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\evaluate_semantic_benchmark.py `
  --results .\outputs\local_bge_semantic_benchmark_v1_full.json `
  --annotations .\outputs\local_bge_semantic_benchmark_v1_formal_independent_annotations.json `
  --out .\outputs\local_bge_semantic_benchmark_v1_formal_independent_evaluation.md

.\.venv\Scripts\python.exe .\backend\scripts\compare_semantic_annotations.py `
  --results .\outputs\local_bge_semantic_benchmark_v1_full.json `
  --annotations-a .\docs\local_bge_semantic_benchmark_v1_full_annotations.json `
  --annotations-b .\outputs\local_bge_semantic_benchmark_v1_formal_independent_annotations.json `
  --out .\outputs\local_bge_semantic_benchmark_v1_formal_independent_agreement.md
```

## 8. 正式切換條件

在以下條件全部完成前，不切換正式 DB：

1. 本機 BGE 至少完成 1000 筆 trial。（已完成）
2. 固定 15 詞 benchmark 可重跑。（已完成）
3. 與 Hugging Face API BGE 的排名差異有紀錄。
4. CPU 或 GPU 的全量重建時間可接受。（GPU 全量約 28 分 52 秒，已完成）
5. 17254 筆 embeddings 全數建立且資料庫驗證通過。（已完成）
6. 全量第一輪與 POC 混合式第二輪已完成；正式第二位獨立標註與有效信度估計尚未完成。
7. 前端與 API 明確顯示實際 provider、model 與 device。
