# Semantic Query Trial

- Created at: `2026-08-05T01:06:40.952168+00:00`
- Database: `D:\Projects\保險評議分析系統\backend\data\insurance_cases_local_bge_trial.db`
- Embedding provider: `local_bge`
- Embedding model: `BAAI/bge-large-zh-v1.5-local`
- Query set: `benchmark-v1`

This report generated query embeddings from the local BGE model cache.
It does not call an external inference API and does not modify the source database.

## Full-build scope

- Candidates per query: `17254`
- Query count: `15`
- Top results per query: `5`
- Total ranked results: `75`
- Trial DB BGE embeddings: `17254 / 17254`
- Formal DB switched to BGE: `no`

Compared with the earlier 1000-candidate run, only `1 / 15` queries kept the
same Top 1 chunk and the average Top 5 chunk overlap was `0.2 / 5`. The old
annotations therefore cannot be reused as full-candidate quality labels. This
report records retrieval output only. The separate Codex-assisted first-pass
evaluation is available at
`docs/local_bge_semantic_benchmark_v1_full_evaluation.md`; its Precision@5
results are not independent human validation and do not establish legal
correctness.

## Query: `除外責任`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6555 | `114年評字第003675號` | 承保範圍 | `chunk_1dd72152e821e99e` | 判斷理由 | 3 |
| 2 | 0.6456 | `114年評字第003277號` | 除外責任 | `chunk_d8265adb7b4c6d63` | 判斷理由 | 4 |
| 3 | 0.6428 | `114年評字第004621號` | 除外責任 | `chunk_3b2d1f044cb29842` | 兩造不爭執之事實 | 3 |
| 4 | 0.6407 | `114年評字第000527號` | 除外責任 | `chunk_63f1e2b66faabe36` | 申請人主張 | 1 |
| 5 | 0.6352 | `114年評字第003447號` | 除外責任 | `chunk_84083b342a4cd08a` | 判斷理由 | 3 |

## Query: `必要性醫療`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6003 | `113年評字第004951號` | 承保範圍 | `chunk_a6338d9edbb4e362` | 判斷理由 | 3 |
| 2 | 0.5878 | `114年評字第003248號` | 必要性醫療 | `chunk_e13ff5c4c917b87a` | 判斷理由 | 3 |
| 3 | 0.5717 | `114年評字第003659號` | 必要性醫療 | `chunk_39cb49bebb669b61` | 申請人主張 | 1 |
| 4 | 0.5631 | `114年評字第002372號` | 必要性醫療 | `chunk_973e286f2819d22f` | 判斷理由 | 3 |
| 5 | 0.5625 | `114年評字第004935號` | 醫療單據認定 | `chunk_92e1302f763848c4` | 本件爭點 | 2 |

## Query: `癌症`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.5797 | `114年評字第002198號` | 遲延給付 | `chunk_02a0e697222976d0` | 本件爭點 | 2 |
| 2 | 0.5758 | `114年評字第002225號` | 必要性醫療 | `chunk_407510bb1178121f` | 判斷理由 | 3 |
| 3 | 0.5635 | `114年評字第005178號` | 癌症或其併發症認定 | `chunk_191cc7844ce5c92a` | 判斷理由 | 2 |
| 4 | 0.5629 | `114年評字第004135號` | 承保範圍 | `chunk_df03293a93fca4ad` | 相對人主張 | 2 |
| 5 | 0.5622 | `113年評字第005005號` | 癌症或其併發症認定 | `chunk_512f2802708bb1e3` | 相對人主張 | 2 |

## Query: `住院`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6445 | `114年評字第000752號` | 必要性醫療 | `chunk_c41e23ae2cc35e36` | 本件爭點 | 2 |
| 2 | 0.6425 | `114年評字第004347號` | 必要性醫療 | `chunk_63685c388c2e105d` | 本件爭點 | 2 |
| 3 | 0.6277 | `114年評字第001103號` | 必要性醫療 | `chunk_18ce86607cf413c8` | 申請人主張 | 1 |
| 4 | 0.6264 | `114年評字第004010號` | 必要性醫療 | `chunk_e28a57184a9e6cca` | 申請人主張 | 1 |
| 5 | 0.6263 | `114年評字第004086號` | 必要性醫療 | `chunk_e3013f6f246b58f6` | 申請人主張 | 1 |

## Query: `失能`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.634 | `113年評字第005022號` | 失能或豁免保費體況認定 | `chunk_df814fa644af6d99` | 相對人主張 | 2 |
| 2 | 0.6335 | `114年評字第003350號` | 失能或豁免保費體況認定 | `chunk_390203f4bb6e267c` | 相對人主張 | 2 |
| 3 | 0.6256 | `114年評字第005683號` | 失能等級認定 | `chunk_296499100b17b564` | 相對人主張 | 3 |
| 4 | 0.6214 | `114年評字第001196號` | 失能或豁免保費體況認定 | `chunk_f7f923c20051e7a4` | 判斷理由 | 4 |
| 5 | 0.6154 | `114年評字第003727號` | 失能或豁免保費體況認定 | `chunk_abbeb2a8b3282d03` | 判斷理由 | 3 |

## Query: `承保範圍`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6844 | `114年評字第005628號` | 除外責任 | `chunk_4ac61924e71c3383` | 判斷理由 | 3 |
| 2 | 0.6835 | `114年評字第004519號` | 續保爭議 | `chunk_f97ba21eb6e09d6f` | 判斷理由 | 3 |
| 3 | 0.6795 | `114年評字第004167號` | 事故發生原因認定 | `chunk_c2804a2c14fa9d46` | 判斷理由 | 8 |
| 4 | 0.6757 | `114年評字第001997號` | 必要性醫療 | `chunk_f30699ee8dd3dbdd` | 判斷理由 | 2 |
| 5 | 0.6746 | `114年評字第003832號` | 投保時已患疾病或在妊娠中 | `chunk_945e806a07f39807` | 申請人主張 | 1 |

## Query: `違反告知義務`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6601 | `114年評字第004040號` | 解約爭議 | `chunk_b728bef83e2574b6` | 判斷理由 | 4 |
| 2 | 0.6364 | `114年評字第003133號` | 違反告知義務 | `chunk_8b29ba17233e886c` | 判斷理由 | 2 |
| 3 | 0.6347 | `113年評字第004415號` | 業務招攬爭議 | `chunk_88d968075930b408` | 判斷理由 | 4 |
| 4 | 0.6326 | `114年評字第004099號` | 停效復效爭議 | `chunk_708fe90791fff02c` | 判斷理由 | 3 |
| 5 | 0.6293 | `114年評字第002357號` | 停效復效爭議 | `chunk_fce2ff7636543b71` | 申請人主張 | 1 |

## Query: `理賠金額`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6936 | `114年評字第001525號` | 理賠金額認定 | `chunk_0865e2be07cdd844` | 申請人主張 | 1 |
| 2 | 0.6866 | `114年評字第002295號` | 必要性醫療 | `chunk_1676fdbf65a80483` | 申請人主張 | 1 |
| 3 | 0.6692 | `113年評字第005191號` | 理賠金額認定 | `chunk_d198cbba590d2148` | 相對人主張 | 2 |
| 4 | 0.6644 | `113年評字第005155號` | 理賠金額認定 | `chunk_f1ae59a7bac6821d` | 申請人主張 | 1 |
| 5 | 0.6634 | `114年評字第001243號` | 必要性醫療 | `chunk_5aaf14b200b4d274` | 判斷理由 | 5 |

## Query: `手術認定`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6294 | `114年評字第001447號` | 除外責任 | `chunk_cfea82e8412f9564` | 判斷理由 | 7 |
| 2 | 0.6123 | `114年評字第001555號` | 承保範圍 | `chunk_0c4c416c3543ace9` | 判斷理由 | 5 |
| 3 | 0.6116 | `113年評字第005479號` | 手術認定 | `chunk_9379f65d891e67bb` | 判斷理由 | 4 |
| 4 | 0.6057 | `114年評字第000812號` | 手術認定 | `chunk_e9fdbc23e5cbbd84` | 申請人主張 | 1 |
| 5 | 0.6042 | `114年評字第005506號` | 事故發生原因認定 | `chunk_61574fcc64bf05fc` | 判斷理由 | 4 |

## Query: `投保前疾病`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6959 | `114年評字第003262號` | 違反告知義務 | `chunk_e6f4c8150dbbc287` | 相對人主張 | 2 |
| 2 | 0.6909 | `114年評字第000103號` | 投保時已患疾病或在妊娠中 | `chunk_33cc72fa09ec305c` | 判斷理由 | 4 |
| 3 | 0.6905 | `114年評字第005291號` | 投保時已患疾病或在妊娠中 | `chunk_427a3243ae7a4a1e` | 判斷理由 | 4 |
| 4 | 0.6904 | `113年評字第004905號` | 違反告知義務 | `chunk_987413e8ece4d93b` | 判斷理由 | 8 |
| 5 | 0.6889 | `113年評字第005372號` | 違反告知義務 | `chunk_4a2de7e702884537` | 相對人主張 | 3 |

## Query: `保單停效`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.7619 | `114年評字第001499號` | 停效期間事故認定 | `chunk_f360034c70392a03` | 申請人主張 | 1 |
| 2 | 0.7603 | `114年評字第000508號` | 停效復效爭議 | `chunk_b240a55342fe1ce7` | 申請人主張 | 1 |
| 3 | 0.7552 | `114年評字第001957號` | 停效復效爭議 | `chunk_065ea6bacc06b5e3` | 相對人主張 | 2 |
| 4 | 0.7541 | `114年評字第004890號` | 停效復效爭議 | `chunk_cf02cbf0bdbf3b1e` | 相對人主張 | 2 |
| 5 | 0.7498 | `114年評字第001776號` | 停效復效爭議 | `chunk_1fd8059f159f6e02` | 相對人主張 | 1 |

## Query: `意外事故`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6451 | `114年評字第000055號` | 事故發生原因認定 | `chunk_7978dc55e880da38` | 申請人主張 | 1 |
| 2 | 0.6234 | `114年評字第005613號` | 事故發生原因認定 | `chunk_56d7403131d3e27e` | 判斷理由 | 3 |
| 3 | 0.6221 | `114年評字第006020號` | 事故發生原因認定 | `chunk_fb31f1e4c16b1d52` | 判斷理由 | 3 |
| 4 | 0.6189 | `114年評字第004690號` | 事故發生原因認定 | `chunk_44287520417d4061` | 判斷理由 | 3 |
| 5 | 0.6174 | `114年評字第004891號` | 失能等級認定 | `chunk_4ff233401326de67` | 判斷理由 | 3 |

## Query: `條款怎麼解釋`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6433 | `114年評字第001646號` | 保費之交付 | `chunk_fe277b5b515e301f` | 判斷理由 | 3 |
| 2 | 0.6407 | `113年評字第005597號` | 未遵循服務規範 | `chunk_6aa17b2ebbe29499` | 判斷理由 | 3 |
| 3 | 0.6394 | `114年評字第000336號` | 理賠金額認定 | `chunk_9310ccb4730f30c4` | 判斷理由 | 6 |
| 4 | 0.6366 | `114年評字第003357號` | 承保範圍 | `chunk_6283425f2509af84` | 判斷理由 | 3 |
| 5 | 0.6343 | `114年評字第004410號` | 承保範圍 | `chunk_561db011aa693ba8` | 判斷理由 | 3 |

## Query: `業務招攬`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.5548 | `114年評字第000721號` | 年金/滿期金給付 | `chunk_a16b96a081fcf381` | 判斷理由 | 5 |
| 2 | 0.5331 | `114年評字第002459號` | 業務招攬爭議 | `chunk_5aee56308b8e6f17` | 相對人主張 | 2 |
| 3 | 0.533 | `114年評字第001167號` | 業務招攬爭議 | `chunk_06d11ea433f936e3` | 判斷理由 | 7 |
| 4 | 0.5251 | `114年評字第000069號` | 業務招攬爭議 | `chunk_e1b86580c782d366` | 判斷理由 | 7 |
| 5 | 0.5194 | `113年評字第004840號` | 投保時已患疾病或在妊娠中 | `chunk_038eb7c949a620a0` | 判斷理由 | 7 |

## Query: `豁免保費`

- Total candidates: `17254`

| rank | score | case_number | dispute_type | chunk_id | section | chunk_index |
| ---: | ---: | --- | --- | --- | --- | ---: |
| 1 | 0.6713 | `114年評字第000263號` | 承保範圍 | `chunk_2152a2731d72c3b9` | 申請人主張 | 1 |
| 2 | 0.6661 | `114年評字第001047號` | 失能或豁免保費體況認定 | `chunk_3bdfc9378b890ebd` | 申請人主張 | 1 |
| 3 | 0.6605 | `114年評字第002307號` | 失能或豁免保費體況認定 | `chunk_69e687c0d71f790d` | 申請人主張 | 2 |
| 4 | 0.6451 | `114年評字第001047號` | 失能或豁免保費體況認定 | `chunk_7c5de0f6d49cdca8` | 兩造不爭執之事實 | 2 |
| 5 | 0.6444 | `114年評字第002307號` | 失能或豁免保費體況認定 | `chunk_bee2cfc2ca0d2f95` | 判斷理由 | 5 |
