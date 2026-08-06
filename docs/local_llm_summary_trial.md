# 本機 LLM 案件摘要 POC

## 目的與邊界

本階段在既有 `rule_based_v1` 摘要旁建立生成式摘要試驗，確認本機小型語言模型能否把評議決定書整理成理賠人員可讀、且能回查原文的結構化摘要。

目前仍是 POC：

- 不修改 `case_summaries`、既有摘要 API 或前端。
- SQLite 以 `mode=ro` 唯讀開啟，結果只寫入 Git 忽略的 `outputs/`。
- 每筆結果固定為 `review_status = unreviewed`，不得直接作為理賠或法律結論。
- 摘要採證據優先的抽取式策略；可讀性低於自由生成，但能降低錯誤改寫風險。

## 本機模型與費用邊界

- Runtime：Ollama Windows `0.32.6`。
- Provider：`ollama_local`。
- Model：`qwen3:4b`，Qwen3 4B Q4_K_M GGUF，約 2.5 GB。
- API：`http://127.0.0.1:11434`。
- Windows 使用者設定：`OLLAMA_NO_CLOUD=1`、`OLLAMA_HOST=127.0.0.1:11434`。
- 模型目錄：`D:\Models\Ollama`。

GGUF 來源為 `Qwen/Qwen3-4B-GGUF`，下載檔 SHA-256 已驗證為：

```text
7485FE6F11AF29433BC51CAB58009521F205840F5B4AE3A32FA7F92E8534FDF5
```

模型下載需要網路，但摘要推論只呼叫 loopback API；程式不接受遠端 Ollama URL、不帶 `Authorization` header、拒絕 `:cloud` 模型，也不使用 Hugging Face Inference API 或 token。

參考：[Ollama FAQ](https://docs.ollama.com/faq)、[Ollama Windows](https://docs.ollama.com/windows)、[Qwen3 GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF)。

## 摘要資料流

1. 從 `case_texts.normalized_text` 讀取案件；缺少時才使用 raw text。
2. 沿用 `document_section_service.py` 分出主文、雙方主張、不爭執事項、爭點、判斷理由、綜上所述與據上論結。
3. 長區塊以真正句界切成最多 2,000 字的 packet；PDF 排版換行不視為句界。
4. Qwen3 每個 packet 最多擷取 2 個陳述與 2 個法源候選，回覆最多 2,048 tokens。
5. 區塊類型強制決定角色，避免申請人或相對人主張被誤作評議理由。
6. 引文必須存在於原文；程式會移除頁碼與模型外加引號，並把片段擴展到完整原句。表格密集列與不完整句會被排除。
7. `local_llm_summary_v5` 會保守移除句首屬於前一段法條引文的 `…」`；移除後的句子仍必須逐字存在原文。
8. `local_llm_summary_v6` 只在摘要顯示層移除已知的章節標題與編號；evidence 仍保留包含 `主文`、`本件爭點`、`據上論結` 的逐字原文。
9. 模型改寫無法逐字核對時，顯示已驗證原文引文；短區塊漏抓時才使用可標示的原文補位。
10. 評議理由另從完整理由區塊擷取含 `從而`、`足認`、`難認`、`有據` 等訊號的完整句，按本案套用訊號排序。
11. 法源同時接受模型驗證與規則擷取，但只保留原文中的正式法規名稱與條號；保單、附約與契約條款不列為法源。
12. 最終 JSON 保留 model、prompt version、source hash、原文 offset、拒絕／補位／失敗數與本機推論耗時。

## 摘要欄位

```text
background
applicant_position
respondent_position
core_issues[]
reasoning_points[]
decision_result
legal_references[]
evidence[]
```

## 環境設定

```powershell
$env:SUMMARY_PROVIDER="ollama_local"
$env:SUMMARY_MODEL="qwen3:4b"
$env:OLLAMA_BASE_URL="http://127.0.0.1:11434"
$env:SUMMARY_REQUEST_TIMEOUT_SECONDS="240"
$env:SUMMARY_NUM_CTX="8192"
$env:SUMMARY_MAX_OUTPUT_TOKENS="2048"
$env:SUMMARY_SECTION_MAX_CHARS="2000"
```

## 執行與驗證

在專案根目錄執行：

```powershell
# 只確認代表案件，不呼叫模型
py .\backend\scripts\run_summary_trial.py --limit 5 --dry-run

# 執行五案本機摘要
py .\backend\scripts\run_summary_trial.py `
  --db .\backend\data\insurance_cases_local_bge_trial.db `
  --limit 5 `
  --output .\outputs\local_llm_summary_trial_qwen3_4b_final_v4.json

# 逐筆回查原文、角色與法源
py .\backend\scripts\validate_summary_trial.py `
  --report .\outputs\local_llm_summary_trial_qwen3_4b_final_v4.json
```

另外可用 `ollama ps` 確認 `qwen3:4b` 為 `100% GPU` 與 `8192` context。

## 2026-08-06 實測結果

- 代表案件：5 件、5 種爭議類型，原文字數 2,082 至 23,669。
- 本機請求：57 次，失敗 0；最終合併 fallback 0。
- 必要欄位：5 件皆有背景、雙方主張、爭點、理由與結果。
- 自動回查：47 段摘要證據、11 筆法源，`violations = []`。
- 原文補位：4 次，均在輸出中標示；規則式理由候選共 10 段。
- 推論耗時合計約 517.5 秒；最長案 20 次請求約 230.9 秒。
- RTX 4050 Laptop GPU 實測約使用 4.3 至 4.5 GB / 6 GB VRAM，Ollama 顯示 `100% GPU`。
- 試跑前後 DB 大小與最後修改時間完全一致：336,064,512 bytes，`2026-08-05T01:03:40.3062243Z`。

## 結論與限制

POC 已證明 `qwen3:4b` 可在目前硬體上離線完成有來源證據的案件摘要，且不消耗 Hugging Face 推論額度。這不代表可直接上線：

- 五案樣本不足以代表 2,992 件資料，正式建置前仍需擴大抽樣與人工標註。
- 長主張可能以完整原文補位，文字仍偏長；表格與正式排版應回看 PDF。
- 規則式理由訊號需隨年度與文件格式持續校正。
- 五案已匯入 Trial DB 的獨立版本表並接入案件 Dashboard；目前可用版本仍全部為 `unreviewed`，不會冒充正式人工判斷。
- 第一案 v4 因判斷理由句首殘留 `…」` 而標記 rejected；v5 修正引文尾端，v6 再清理摘要顯示中的章節標題。v5 與 v6 都保留為 unreviewed，舊版本不覆寫，供後續稽核與比較。
- 五案樣本與審核介面仍屬 POC；正式全量建置前需要擴大抽樣、逐案人工核准及登入權限設計。

## 人工審核流程

AI 摘要使用獨立的 `case_ai_summaries` 表，不會覆蓋既有規則式 `case_summaries`。API 只有 GET；人工狀態寫入只能在本機 CLI 執行，避免 Cloudflare Tunnel 公開時讓未登入使用者修改資料。

```powershell
# 匯入已通過 validate_summary_trial.py 的五案報告
py .\backend\scripts\import_summary_trial.py

# 查看全部待審案件
py .\backend\scripts\review_ai_summary.py --list

# 查看一案完整摘要、法源與 evidence
py .\backend\scripts\review_ai_summary.py `
  --case-number "114年評字第004802號" `
  --show

# 核對 Dashboard、完整原文與正式 PDF 後核准
py .\backend\scripts\review_ai_summary.py `
  --case-number "114年評字第004802號" `
  --status approved `
  --reviewer "reviewer-id" `
  --note "已核對雙方主張、爭點、理由與主文"
```

審核狀態：

- `unreviewed`：Dashboard 顯示黃色警示，只能作為閱讀方向。
- `approved`：Dashboard 顯示「已人工確認」，且同案有多個版本時優先採用。
- `rejected`：API 不回傳該版本；若同案沒有其他可用版本，Dashboard 顯示尚無摘要。

匯入與審核腳本預設只操作 `insurance_cases_local_bge_trial.db`，並拒絕正式 `insurance_cases.db`。同一個 case、model、prompt 與 source hash 重複匯入時會更新生成內容，但保留 reviewer、note 與 review status。
