# Semantic Query Trial

- Created at: `2026-08-03T08:00:30.131450+00:00`
- Database: `D:\Projects\保險評議分析系統\backend\data\insurance_cases_local_bge_trial.db`
- Embedding provider: `local_bge`
- Embedding model: `BAAI/bge-large-zh-v1.5-local`
- Query set: `benchmark-v1`

This report generated query embeddings from the local BGE model cache.
It does not call an external inference API and does not modify the source database.

## Validation Summary

- Embedding build: `1000 / 1000` chunks completed, `0` empty chunks, `1024` dimensions.
- Runtime: RTX 4050 Laptop GPU (`cuda`), about `85.12` seconds including model loading.
- Benchmark: `15` queries, `75` Top 5 results, `1000` candidates per query.
- Candidate coverage: `167` cases, `25` dispute types, decision dates from `114.01.16` to `115.03.20`.
- Top 5 union: `72` unique chunks, `53` cases, `19` dispute types.
- Score range: `0.4463` to `0.7493`.
- Compared with the 100-candidate run, only `1 / 15` queries kept the same Top 1 chunk and case. Mean Top 5 overlap was `0.53 / 5` for both chunks and cases.

The low overlap shows that the first 100 chunks were too narrow to represent the available cases. Adding 900 candidates introduced many higher-scoring results, so the 100-candidate ranking must not be treated as a quality baseline. This report still uses the first 1000 chunks ordered by case and chunk index rather than a stratified sample, and the 75 results have not yet received independent human relevance labels. Scores are relative retrieval signals, not legal conclusions.

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

## Query: `承保範圍`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6588 | `113年評字第004576號` | 未遵循服務規範 | `chunk_04658cda5091e103` | 判斷理由 | 15 |
| 2 | 0.6543 | `114年評字第003367號` | 除外責任 | `chunk_aecc581fabb986e2` | 判斷理由 | 4 |
| 3 | 0.6528 | `114年評字第004445號` | 必要性醫療 | `chunk_ee42bf1c3404a46f` | 判斷理由 | 4 |
| 4 | 0.6516 | `114年評字第002501號` | 承保範圍 | `chunk_8c912fc58ab22cb7` | 判斷理由 | 2 |
| 5 | 0.6498 | `114年評字第003582號` | 必要性醫療 | `chunk_75157a74de69e574` | 判斷理由 | 2 |

## Query: `違反告知義務`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6195 | `114年評字第000107號` | 契約變更 | `chunk_b397036b3fed6fbf` | 判斷理由 | 3 |
| 2 | 0.6116 | `114年評字第004784號` | 違反告知義務 | `chunk_0ffdefb366285451` | 判斷理由 | 4 |
| 3 | 0.6035 | `114年評字第001855號` | 違反告知義務 | `chunk_f662a5bc219149da` | 判斷理由 | 3 |
| 4 | 0.6012 | `113年評字第004576號` | 未遵循服務規範 | `chunk_e0b17ab192476cb8` | 判斷理由 | 21 |
| 5 | 0.6003 | `114年評字第002874號` | 違反告知義務 | `chunk_8b836fc359fe620a` | 相對人主張 | 4 |

## Query: `理賠金額`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6535 | `113年評字第005502號` | 理賠金額認定 | `chunk_465eb1132048ca58` | 申請人主張 | 1 |
| 2 | 0.6501 | `114年評字第001881號` | 承保範圍 | `chunk_3e8624809b05f1eb` | 相對人主張 | 2 |
| 3 | 0.65 | `114年評字第006123號` | 必要性醫療 | `chunk_bdaaea97c9fd0f40` | 申請人主張 | 1 |
| 4 | 0.6474 | `114年評字第001080號` | 停效期間事故認定 | `chunk_af4d58ee9c190353` | 判斷理由 | 10 |
| 5 | 0.6404 | `114年評字第003703號` | 條款解釋爭議 | `chunk_ac0f07ae446d367e` | 申請人主張 | 1 |

## Query: `手術認定`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6294 | `114年評字第001447號` | 除外責任 | `chunk_cfea82e8412f9564` | 判斷理由 | 7 |
| 2 | 0.5927 | `114年評字第001457號` | 必要性醫療 | `chunk_82c4bc85734497ef` | 判斷理由 | 4 |
| 3 | 0.584 | `114年評字第003582號` | 必要性醫療 | `chunk_e26e05dbcbf90871` | 申請人主張 | 1 |
| 4 | 0.5784 | `114年評字第005025號` | 手術認定 | `chunk_d6bd470e707db4a1` | 申請人主張 | 1 |
| 5 | 0.5726 | `114年評字第003283號` | 手術認定 | `chunk_83d6e2e0b1a35380` | 判斷理由 | 4 |

## Query: `投保前疾病`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6905 | `114年評字第005291號` | 投保時已患疾病或在妊娠中 | `chunk_427a3243ae7a4a1e` | 判斷理由 | 4 |
| 2 | 0.6788 | `114年評字第003120號` | 投保時已患疾病或在妊娠中 | `chunk_b75321f9211790a7` | 本件爭點 | 2 |
| 3 | 0.6761 | `114年評字第005531號` | 投保時已患疾病或在妊娠中 | `chunk_007807aa380a3ad3` | 相對人主張 | 2 |
| 4 | 0.6731 | `114年評字第003774號` | 違反告知義務 | `chunk_fbd5afbf2d5bd045` | 判斷理由 | 3 |
| 5 | 0.6714 | `113年評字第004490號` | 違反告知義務 | `chunk_a9bc0c4204ad23fa` | 判斷理由 | 9 |

## Query: `保單停效`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.7493 | `114年評字第004986號` | 停效復效爭議 | `chunk_3a4e02f7b6ba9dd7` | 相對人主張 | 2 |
| 2 | 0.7443 | `114年評字第005567號` | 停效期間事故認定 | `chunk_5e30ef319186a18d` | 相對人主張 | 2 |
| 3 | 0.7418 | `114年評字第004986號` | 停效復效爭議 | `chunk_949fcacddada340d` | 申請人主張 | 1 |
| 4 | 0.7371 | `114年評字第005567號` | 停效期間事故認定 | `chunk_37f782e0d18b3538` | 相對人主張 | 3 |
| 5 | 0.7272 | `114年評字第004986號` | 停效復效爭議 | `chunk_faed3bd7df97c2c1` | 判斷理由 | 5 |

## Query: `意外事故`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.597 | `115年評字第000219號` | 事故發生原因認定 | `chunk_dc353fa1684e4f01` | 判斷理由 | 2 |
| 2 | 0.5962 | `114年評字第003670號` | 事故發生原因認定 | `chunk_ed07dc87fab5db49` | 判斷理由 | 3 |
| 3 | 0.5962 | `114年評字第002947號` | 承保範圍 | `chunk_baf8570f604d4a6e` | 判斷理由 | 2 |
| 4 | 0.5838 | `114年評字第001727號` | 除外責任 | `chunk_c70581b2c8422315` | 判斷理由 | 3 |
| 5 | 0.5716 | `114年評字第003670號` | 事故發生原因認定 | `chunk_074895a28282a5b7` | 申請人主張 | 1 |

## Query: `條款怎麼解釋`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6343 | `114年評字第004410號` | 承保範圍 | `chunk_561db011aa693ba8` | 判斷理由 | 3 |
| 2 | 0.6235 | `114年評字第000040號` | 承保範圍 | `chunk_42bde65bc41a1298` | 判斷理由 | 2 |
| 3 | 0.6186 | `114年評字第003467號` | 理賠金額認定 | `chunk_5b2ead69e14c395c` | 判斷理由 | 4 |
| 4 | 0.6177 | `113年評字第005004號` | 理賠金額認定 | `chunk_87f1b00d7f31176e` | 判斷理由 | 6 |
| 5 | 0.6088 | `114年評字第005025號` | 手術認定 | `chunk_f8055b4ee7b9969a` | 判斷理由 | 3 |

## Query: `業務招攬`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.4681 | `114年評字第003657號` | 未遵循服務規範 | `chunk_63266b51a61a9f23` | 申請人主張 | 2 |
| 2 | 0.4615 | `114年評字第005063號` | 業務招攬爭議 | `chunk_1a4031f7833a1e62` | 判斷理由 | 3 |
| 3 | 0.4559 | `114年評字第005246號` | 業務招攬爭議 | `chunk_4460f5d00256c6c0` | 判斷理由 | 9 |
| 4 | 0.4501 | `114年評字第005246號` | 業務招攬爭議 | `chunk_b8550f74d5c19229` | 判斷理由 | 8 |
| 5 | 0.4463 | `114年評字第001863號` | 拒保或加費承保爭議 | `chunk_2750370a637766dd` | 主文 | 0 |

## Query: `豁免保費`

- Total candidates: `1000`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6036 | `114年評字第002114號` | 業務招攬爭議 | `chunk_1db92ffee03e3bfd` | 判斷理由 | 2 |
| 2 | 0.5978 | `114年評字第001881號` | 承保範圍 | `chunk_1b80b1d8acfcadf1` | 申請人主張 | 1 |
| 3 | 0.5917 | `114年評字第004784號` | 違反告知義務 | `chunk_e3bde04c0a48e329` | 主文 | 0 |
| 4 | 0.5852 | `114年評字第005567號` | 停效期間事故認定 | `chunk_cc1a1d72b7ab5942` | 判斷理由 | 7 |
| 5 | 0.5851 | `114年評字第004784號` | 違反告知義務 | `chunk_57cd9369f48a7c9b` | 申請人主張 | 1 |
