# Hugging Face Semantic Query Trial

- Created at: `2026-08-03T02:38:17.353895+00:00`
- Database: `D:\Projects\保險評議分析系統\backend\data\insurance_cases_hf_trial.db`
- Embedding provider: `huggingface`
- Embedding model: `BAAI/bge-large-zh-v1.5`

This report uses Hugging Face to generate a query embedding, then compares it with stored trial chunk embeddings.
It consumes API quota and does not modify the source database.

## Query: `除外責任`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6207 | `113年評字第004957號` | 除外責任 | `chunk_c3d1a2f73e93c32f` | 兩造不爭執之事實 | 3 |
| 2 | 0.6205 | `114年評字第004090號` | 除外責任 | `chunk_2f43c1043766f313` | 相對人主張 | 3 |
| 3 | 0.6001 | `114年評字第002947號` | 承保範圍 | `chunk_baf8570f604d4a6e` | 判斷理由 | 2 |
| 4 | 0.5976 | `114年評字第001727號` | 除外責任 | `chunk_8cd73331844e38b0` | 相對人主張 | 2 |
| 5 | 0.5971 | `114年評字第004090號` | 除外責任 | `chunk_e8c8f73eb7b52cb3` | 申請人主張 | 1 |

## Query: `必要性醫療`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.5469 | `114年評字第002461號` | 必要性醫療 | `chunk_42802fd93ce4c514` | 判斷理由 | 3 |
| 2 | 0.545 | `114年評字第005691號` | 必要性醫療 | `chunk_b226333ef285e8e5` | 申請人主張 | 2 |
| 3 | 0.5381 | `114年評字第005691號` | 必要性醫療 | `chunk_393f852d7899a6ef` | 判斷理由 | 6 |
| 4 | 0.5368 | `114年評字第002291號` | 必要性醫療 | `chunk_0f33ee16d28a5116` | 判斷理由 | 3 |
| 5 | 0.5365 | `114年評字第001504號` | 必要性醫療 | `chunk_bd7d984272c355f0` | 判斷理由 | 3 |

## Query: `癌症`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.5232 | `114年評字第004027號` | 停效期間事故認定 | `chunk_f346f0851368873d` | 判斷理由 | 3 |
| 2 | 0.5226 | `113年評字第005630號` | 癌症或其併發症認定 | `chunk_40166aac122d74b0` | 判斷理由 | 3 |
| 3 | 0.5115 | `113年評字第005630號` | 癌症或其併發症認定 | `chunk_da0848c8438b5f26` | 申請人主張 | 1 |
| 4 | 0.4978 | `114年評字第001080號` | 停效期間事故認定 | `chunk_26b1e4c2eb606fb9` | 判斷理由 | 5 |
| 5 | 0.4974 | `113年評字第004943號` | 理賠金額認定 | `chunk_d699fe801808be6d` | 判斷理由 | 7 |

## Query: `住院`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6179 | `114年評字第005691號` | 必要性醫療 | `chunk_b226333ef285e8e5` | 申請人主張 | 2 |
| 2 | 0.6096 | `114年評字第001300號` | 必要性醫療 | `chunk_c56b283dabd96855` | 相對人主張 | 5 |
| 3 | 0.6045 | `114年評字第005691號` | 必要性醫療 | `chunk_393f852d7899a6ef` | 判斷理由 | 6 |
| 4 | 0.604 | `114年評字第003942號` | 承保範圍 | `chunk_8532466a84e5bbcc` | 相對人主張 | 2 |
| 5 | 0.6022 | `114年評字第005016號` | 必要性醫療 | `chunk_94eb305c76d7cabc` | 判斷理由 | 3 |

## Query: `失能`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6086 | `114年評字第005531號` | 投保時已患疾病或在妊娠中 | `chunk_04d0d6b184cb96c7` | 判斷理由 | 4 |
| 2 | 0.598 | `113年評字第004994號` | 失能或豁免保費體況認定 | `chunk_d55cc4219b1d0200` | 申請人主張 | 1 |
| 3 | 0.5945 | `114年評字第001443號` | 因果關係認定 | `chunk_11d51cd1ba4466af` | 判斷理由 | 3 |
| 4 | 0.5846 | `115年評字第000060號` | 失能等級認定 | `chunk_a3a79c72ea2db929` | 判斷理由 | 5 |
| 5 | 0.5835 | `115年評字第000060號` | 失能等級認定 | `chunk_48aefbe7c270fc1e` | 相對人主張 | 2 |
