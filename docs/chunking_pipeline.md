# 案件文字 Chunking Pipeline

## 目標

將每筆案件的 `normalized_text` 切成較小、可追溯的文字段落，作為後續 embedding、語意搜尋與相似案件分析的前置資料。

這一步先不產生 embedding，只負責建立穩定的文字切片資料。

## 設計原則

- 保留原案件關聯：每個 chunk 都有 `case_id`。
- 保留順序：每個 chunk 都有 `chunk_index`。
- 保留原文定位：每個 chunk 都有 `char_start` 與 `char_end`。
- 保留段落提示：盡量標示 `section_hint`，例如主文、申請人主張、相對人主張、判斷理由。
- 可重跑：同一案件重建 chunk 時，會先刪除該案件舊 chunk 再寫入新 chunk。

## 資料表

```sql
CREATE TABLE IF NOT EXISTS case_chunks (
  chunk_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  section_hint TEXT,
  chunk_text TEXT NOT NULL,
  char_start INTEGER NOT NULL,
  char_end INTEGER NOT NULL,
  chunk_chars INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(case_id, chunk_index)
);
```

索引：

```sql
CREATE INDEX IF NOT EXISTS idx_case_chunks_case_id ON case_chunks(case_id);
```

## 預設參數

- `target_chars`：1000
- `overlap_chars`：180
- `MIN_CHUNK_CHARS`：250

重疊區間的目的，是避免重要語意剛好落在兩個 chunk 的切點而遺失。

## 執行方式

在專案根目錄執行：

```powershell
py .\backend\scripts\build_case_chunks.py --db .\backend\data\insurance_cases.db
```

可選參數：

```powershell
py .\backend\scripts\build_case_chunks.py --target-chars 1000 --overlap-chars 180 --limit 10
```

## 驗證方式

```powershell
py -m py_compile .\backend\scripts\build_case_chunks.py .\backend\scripts\verify_case_db.py .\backend\scripts\import_cases_to_db.py
py -m pytest
py .\backend\scripts\verify_case_db.py --expected-count 2992 --require-chunks
```

目前正式 DB 驗證結果：

- `cases`：2992
- `case_chunks`：17254
- `cases_without_chunks`：0
- `min_chunk_chars`：189
- `empty_case_count`：0
- `min_chunks_per_case`：3
- `max_chunks_per_case`：30

## 後續工作

下一步可以在 `case_chunks` 基礎上建立 embedding：

1. 新增 `chunk_embeddings` 或外部向量索引。
2. 對每個 `chunk_text` 產生 embedding。
3. 查詢時先比對 chunk，再聚合回案件層級。
4. 在前端案件詳情頁展示命中的相似段落與分數依據。
