# Hugging Face Semantic Benchmark v1 Protocol

## 1. 目標

本評測將 Hugging Face `BAAI/bge-large-zh-v1.5` 的 query-to-document 試測，從 5 個查詢詞擴充為 15 個查詢詞。每個查詢保留 Top 5，共 75 筆 chunk-level 結果。

目標是建立可重跑、可人工標註、可計算 Precision@5 的評測流程，不是宣稱模型已在正式資料庫上線或已證明法律判斷正確。

## 2. 評測範圍

- Trial DB：`backend/data/insurance_cases_hf_trial.db`
- Embedding provider：`huggingface`
- Embedding model：`BAAI/bge-large-zh-v1.5`
- Stored BGE candidates：`1000` chunks
- Query 數量：`15`
- 每個 query：Top `5`
- 人工判讀總量：`75` results

1000 筆候選資料涵蓋 25 種爭議類型。查詢集同時包含正式爭議類型名稱與一般使用者可能輸入的自然語句，避免只測 metadata 名稱是否相同。

## 3. 固定查詢集

| 類型 | 查詢詞 | 設計目的 |
| --- | --- | --- |
| 既有基準 | `除外責任` | 延續原 1000 candidates 試測，可比較版本差異。 |
| 既有基準 | `必要性醫療` | 測試既有表現最穩定的查詢。 |
| 自然查詢 | `癌症` | 測試疾病概念能否跨法律爭議類型命中。 |
| 自然查詢 | `住院` | 測試住院定義、必要性與給付範圍。 |
| 自然查詢 | `失能` | 測試失能等級、體況與因果關係。 |
| 類型名稱 | `承保範圍` | 測試保單給付範圍爭議。 |
| 類型名稱 | `違反告知義務` | 測試投保告知與解除契約爭議。 |
| 自然查詢 | `理賠金額` | 測試保險金計算與金額認定。 |
| 類型名稱 | `手術認定` | 測試手術定義與給付項目。 |
| 自然查詢 | `投保前疾病` | 測試「投保時已患疾病」的同義表達。 |
| 自然查詢 | `保單停效` | 測試停效、復效與事故時點。 |
| 自然查詢 | `意外事故` | 測試事故原因、外來性與因果關係。 |
| 問句形式 | `條款怎麼解釋` | 測試口語查詢能否對應條款解釋爭議。 |
| 類型名稱 | `業務招攬` | 測試銷售說明與招攬爭議。 |
| 自然查詢 | `豁免保費` | 測試失能體況與保費豁免給付。 |

## 4. 標註規則

| label | 中文 | 判斷標準 |
| --- | --- | --- |
| `relevant` | 相關 | chunk 原文直接回答或討論查詢概念。 |
| `partially_relevant` | 部分相關 | 原文與查詢概念有實質關聯，但不是主要爭點或只涵蓋部分概念。 |
| `not_relevant` | 不相關 | 原文沒有足以支持查詢概念的內容。 |

每筆標註必須填寫 `evidence_summary`，不能只依分數或 `dispute_type` 判斷。若單一 chunk 上下文不足，應回看同案件前後 chunk，再摘要判斷依據。

## 5. 指標定義

- Strict Precision@5：只有 `relevant` 計為命中。
- Lenient Precision@5：`relevant` 與 `partially_relevant` 都計為命中。
- Macro Precision@5：先計算每個查詢的 Precision@5，再對 15 個查詢取平均。
- Micro Precision@5：直接以 75 筆結果的標記總數計算。

本評測以 chunk 為排名單位，同一案件的多個 chunks 會分別計分。報告另外顯示 Top 5 的 unique case 數量，避免忽略同案件重複命中的情形。

## 6. 執行方式

在已設定 Hugging Face token 的 PowerShell、專案根目錄執行：

```powershell
py .\backend\scripts\run_semantic_query_trial.py `
  --db .\backend\data\insurance_cases_hf_trial.db `
  --query-set benchmark-v1 `
  --limit 5 `
  --include-text `
  --json-out .\outputs\hf_semantic_benchmark_v1_results.json `
  --out .\docs\hf_semantic_benchmark_v1_results.md
```

成功時應產生 15 個 queries、每個 5 筆結果。這一步會呼叫 Hugging Face API，但不會修改 trial DB。

建立 75 筆空白標註模板：

```powershell
py .\backend\scripts\evaluate_semantic_benchmark.py `
  --results .\outputs\hf_semantic_benchmark_v1_results.json `
  --template-out .\outputs\hf_semantic_benchmark_v1_annotations.json
```

完成所有 `label` 與 `evidence_summary` 後產生評測報告：

```powershell
py .\backend\scripts\evaluate_semantic_benchmark.py `
  --results .\outputs\hf_semantic_benchmark_v1_results.json `
  --annotations .\outputs\hf_semantic_benchmark_v1_annotations.json `
  --out .\docs\hf_semantic_benchmark_v1_evaluation.md
```

## 7. 驗證條件

- 查詢詞必須剛好 15 個且不可重複。
- 每個查詢必須剛好有 5 筆結果。
- 75 筆結果都必須有合法 label 與非空白 `evidence_summary`。
- annotations 不可缺少或多出結果。
- 報告必須同時提供 strict、lenient、macro、micro Precision@5。

## 8. 限制

- candidates 只有 trial DB 中的 1000 筆 BGE embeddings，不是正式 DB 全量 17254 chunks。
- 第一輪人工標註仍可能有單人主觀偏差，正式報告建議由第二位標註者獨立複核。
- Precision@5 只能衡量搜尋結果與查詢的相關性，不能代表保險評議結論或法律判斷正確。
