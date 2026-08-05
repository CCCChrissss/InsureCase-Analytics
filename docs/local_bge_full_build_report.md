# Local BGE Full Build Report

## 1. 結論

2026-08-05 已在獨立 trial DB 完成本機 `BAAI/bge-large-zh-v1.5` 全量向量建置：

- Trial DB：`backend/data/insurance_cases_local_bge_trial.db`
- Provider：`local_bge`
- Stored model：`BAAI/bge-large-zh-v1.5-local`
- Device：`cuda`
- Embedding dimensions：`1024`
- `case_chunks`：`17254`
- BGE embeddings：`17254`
- Local hashing embeddings：`17254`
- 缺漏、空向量、非有限數值：`0`

這次全程使用本機模型快取與 RTX 4050，不呼叫 Hugging Face Inference API，也不需要 API token。正式 DB `backend/data/insurance_cases.db` 沒有切換，仍只使用 `local_hashing_cjk_v1`。

## 2. 建置方式

從既有 `1100` 筆 BGE embeddings 續建剩餘 `16154` 筆：

```powershell
$env:HF_HUB_OFFLINE="1"
$env:TRANSFORMERS_OFFLINE="1"
$env:LOCAL_BGE_DEVICE="cuda"
$env:LOCAL_BGE_BATCH_SIZE="4"

.\.venv\Scripts\python.exe .\backend\scripts\build_chunk_embeddings.py `
  --db .\backend\data\insurance_cases_local_bge_trial.db `
  --provider local_bge `
  --model BAAI/bge-large-zh-v1.5-local `
  --dims 1024 `
  --resume `
  --write-batch-size 100
```

實測結果：

- Existing embeddings before：`1100`
- Selected / processed / embedded：`16154 / 16154 / 16154`
- Write batches：`162`，最後一批 `54` 筆
- Total embeddings after：`17254`
- Remaining chunks：`0`
- Empty chunks：`0`
- Wall time：`1732.1` 秒，約 `28 分 52 秒`
- Trial DB size：`336064512` bytes，約 `320.5 MiB`

## 3. 完整性驗證

建置完成後另以唯讀 SQLite 連線與 Python 數值檢查交叉驗證：

| 檢查 | 結果 |
| --- | ---: |
| SQLite `integrity_check` | `ok` |
| BGE embeddings | `17254` |
| 維度為 1024 | `17254` |
| 每個 blob 為 4096 bytes | `17254` |
| chunks without BGE embedding | `0` |
| 空 blob | `0` |
| 缺漏或非正數 norm | `0` |
| 非有限向量值或 norm | `0` |
| 建置前備份中的 1000 筆是否未變 | `True` |

正式 DB 交叉檢查：

- SQLite `integrity_check`：`ok`
- `case_chunks`：`17254`
- `BAAI/bge-large-zh-v1.5-local`：`0`
- `local_hashing_cjk_v1`：`17254`

## 4. 全量 Benchmark

固定 `benchmark-v1` 的 15 個查詢均以全量 `17254` candidates 重跑 Top 5：

- JSON：`outputs/local_bge_semantic_benchmark_v1_full.json`
- 可讀報告：`docs/local_bge_semantic_query_trial_full.md`
- Query count：`15`
- Results：`75`
- Top 5 合集涵蓋案件：`73`
- Top 5 合集涵蓋爭議類型：`21`
- 平均 Top 1 cosine score：`0.6503`
- 第一輪標註：`69` 相關、`4` 部分相關、`2` 不相關
- 第一輪 Strict / Lenient Precision@5：`0.9200 / 0.9733`
- 標註快照：`docs/local_bge_semantic_benchmark_v1_full_annotations.json`
- 評測報告：`docs/local_bge_semantic_benchmark_v1_full_evaluation.md`

與先前 1000-candidate 結果比較：

- Top 1 相同 chunk：`1 / 15`
- Top 1 相同案件：`1 / 15`
- 平均 Top 5 chunk overlap：`0.2 / 5`
- 1000-candidate 平均 Top 1 score：`0.6148`
- 17254-candidate 平均 Top 1 score：`0.6503`

候選範圍擴大後排名明顯改變，證明前 1000 筆只適合驗證流程，不可代表全資料搜尋品質。舊的 75 筆標註沒有直接沿用；全量結果已另做 75 筆 Codex-assisted 第一輪原文判讀。

## 5. 可下的結論與限制

目前可以確定：

- 全量本機 BGE 建置流程可在 RTX 4050 穩定完成。
- 17254 個 chunks 都有合法的 1024 維 BGE embedding。
- 全程可離線執行，不消耗 Hugging Face Inference API 額度。
- 全量查詢流程可重跑，且結果可追溯到 chunk、案件與段落。

目前不能宣稱：

- 全量搜尋已通過獨立人工品質驗證。
- BGE 分數等同法律相似度或評議結論。
- 正式 API 與前端已切換到 BGE。
- 既有 1000-candidate Precision@5 可代表全量結果。

## 6. 下一步

1. 由未接觸第一輪答案的第二位標註者，使用空白模板獨立判讀 75 筆結果。
2. 執行一致率、Cohen's Kappa 與爭議標記比較，必要時另行仲裁。
3. 確認前端與 API 的 trial DB 切換方式、首次模型載入時間與記憶體需求。
4. 品質通過且使用者明確確認後，再規劃正式 DB 備份與 BGE 切換；本報告不包含正式切換。
