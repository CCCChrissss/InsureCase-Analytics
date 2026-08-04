# 本機 BGE 查詢建議實驗 v1

## 實驗設計

- 目的：比較 benchmark v1 的 15 個原始短查詢與可解釋自然語句建議。
- 原始基準：`docs/local_bge_semantic_benchmark_v1_evaluation.md` 的 75 筆 AI 輔助標註。
- 建議查詢：每個原始查詢對應一個固定建議、規則編號與改寫理由。
- Embedding：本機 `BAAI/bge-large-zh-v1.5-local`，未呼叫 Hugging Face API。
- 候選範圍：trial DB 既有 1000 筆 embeddings；每個查詢取 Top 5。
- 新增判讀：15 個建議查詢共 75 筆，由 Codex 檢查目標 chunk，疑似誤命中另回查相鄰 chunks。
- 資料庫：以 SQLite `mode=ro` 開啟，未修改 trial DB 或正式 DB。

本實驗屬 AI 輔助判讀，不是第二位標註者的獨立盲標；結果可用於決定下一輪工程試驗，不應表述為正式人工驗證。

## 改寫前後比較

| 原查詢 | 建議查詢 | Strict P@5 | Lenient P@5 | 結果 |
| --- | --- | ---: | ---: | --- |
| 除外責任 | 保險公司依除外責任條款拒絕理賠是否合理 | 0.8000 -> 0.2000 | 1.0000 -> 0.2000 | 退步 |
| 必要性醫療 | 住院手術或醫療處置是否符合醫療必要性 | 1.0000 -> 1.0000 | 1.0000 -> 1.0000 | 持平 |
| 癌症 | 癌症診斷及癌症保險金給付爭議 | 1.0000 -> 1.0000 | 1.0000 -> 1.0000 | 持平 |
| 住院 | 是否符合保單住院定義與住院必要性 | 1.0000 -> 1.0000 | 1.0000 -> 1.0000 | 持平 |
| 失能 | 被保險人失能程度及失能保險金認定 | 1.0000 -> 1.0000 | 1.0000 -> 1.0000 | 持平 |
| 承保範圍 | 保險事故或醫療項目是否屬於保單承保範圍 | 0.8000 -> 1.0000 | 0.8000 -> 1.0000 | 改善 |
| 違反告知義務 | 要保人隱匿病史保險公司解除契約 | 0.6000 -> 1.0000 | 0.6000 -> 1.0000 | 改善 |
| 理賠金額 | 保險公司理賠金額計算是否符合保單條款 | 1.0000 -> 0.2000 | 1.0000 -> 0.8000 | 退步 |
| 手術認定 | 醫療處置是否符合保單手術定義 | 0.6000 -> 1.0000 | 1.0000 -> 1.0000 | 改善 |
| 投保前疾病 | 疾病是否在投保前已存在而不予理賠 | 0.8000 -> 1.0000 | 1.0000 -> 1.0000 | 改善 |
| 保單停效 | 未繳保費導致保單停效期間發生保險事故 | 1.0000 -> 1.0000 | 1.0000 -> 1.0000 | 持平 |
| 意外事故 | 事故是否符合外來突發非疾病的意外事故定義 | 1.0000 -> 1.0000 | 1.0000 -> 1.0000 | 持平 |
| 條款怎麼解釋 | 保險契約條款有疑義時應如何解釋 | 1.0000 -> 1.0000 | 1.0000 -> 1.0000 | 持平 |
| 業務招攬 | 業務員招攬過程未充分說明保單 | 0.6000 -> 0.8000 | 0.8000 -> 1.0000 | 改善 |
| 豁免保費 | 被保險人失能或罹癌後免繳保險費 | 0.0000 -> 1.0000 | 0.2000 -> 1.0000 | 改善 |
| **整體** | **15 詞 Macro / Micro** | **0.8133 -> 0.8800** | **0.8933 -> 0.9333** | **整體改善** |

比較結果為 6 組改善、7 組持平、2 組退步。整體平均改善不能抵銷單一查詢的大幅退步：

- `除外責任` 加入「拒絕理賠是否合理」後，模型被一般拒賠、告知義務與事故原因內容吸引，只有 1 筆直接以除外責任條款拒賠。
- `理賠金額` 加入「保險公司、計算、保單條款」後，召回保額變更、解約金與醫療必要性案件，只有 1 筆直接計算理賠金額。
- 原本四個低 Strict P@5 查詢 `違反告知義務`、`手術認定`、`業務招攬`、`豁免保費` 均改善，適合作為下一輪「可選建議查詢」候選。

## 工程決策

1. 不實作全查詢自動改寫，也不以建議查詢取代使用者原文。
2. 下一輪只針對已驗證改善的低分短查詢，製作可選的建議查詢原型。
3. API 若日後加入建議功能，必須同時回傳原查詢、建議查詢、規則編號及原因，且預設仍執行原查詢。
4. `除外責任` 與 `理賠金額` 的本版建議列入負面案例，不得進入產品規則。
5. 在正式接入 API 前，仍需第二位標註者獨立判讀並確認改善沒有來自 AI 輔助標註偏差。

- 查詢集：`benchmark-v1-suggestions-v1`
- Embedding model：`BAAI/bge-large-zh-v1.5-local`
- 標註者：`Codex (AI-assisted query suggestion experiment v1)`
- 查詢數：`15`
- 判讀結果數：`75`

## 指標定義

- Strict Precision@5：只有 `relevant` 計為命中。
- Lenient Precision@5：`relevant` 與 `partially_relevant` 都計為命中。
- 本指標以 chunk 為單位；同一案件的多個 chunks 會分別計分，`unique_cases` 用來揭露重複案件。

## 整體結果

| 相關 | 部分相關 | 不相關 | micro strict P@5 | micro lenient P@5 | macro strict P@5 | macro lenient P@5 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 66 | 4 | 5 | 0.8800 | 0.9333 | 0.8800 | 0.9333 |

## 各查詢結果

| 查詢詞 | 相關 | 部分相關 | 不相關 | strict P@5 | lenient P@5 | 不重複案件數 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 保險公司依除外責任條款拒絕理賠是否合理 | 1 | 0 | 4 | 0.2000 | 0.2000 | 5 |
| 住院手術或醫療處置是否符合醫療必要性 | 5 | 0 | 0 | 1.0000 | 1.0000 | 4 |
| 癌症診斷及癌症保險金給付爭議 | 5 | 0 | 0 | 1.0000 | 1.0000 | 4 |
| 是否符合保單住院定義與住院必要性 | 5 | 0 | 0 | 1.0000 | 1.0000 | 4 |
| 被保險人失能程度及失能保險金認定 | 5 | 0 | 0 | 1.0000 | 1.0000 | 5 |
| 保險事故或醫療項目是否屬於保單承保範圍 | 5 | 0 | 0 | 1.0000 | 1.0000 | 5 |
| 要保人隱匿病史保險公司解除契約 | 5 | 0 | 0 | 1.0000 | 1.0000 | 5 |
| 保險公司理賠金額計算是否符合保單條款 | 1 | 3 | 1 | 0.2000 | 0.8000 | 5 |
| 醫療處置是否符合保單手術定義 | 5 | 0 | 0 | 1.0000 | 1.0000 | 5 |
| 疾病是否在投保前已存在而不予理賠 | 5 | 0 | 0 | 1.0000 | 1.0000 | 5 |
| 未繳保費導致保單停效期間發生保險事故 | 5 | 0 | 0 | 1.0000 | 1.0000 | 2 |
| 事故是否符合外來突發非疾病的意外事故定義 | 5 | 0 | 0 | 1.0000 | 1.0000 | 5 |
| 保險契約條款有疑義時應如何解釋 | 5 | 0 | 0 | 1.0000 | 1.0000 | 5 |
| 業務員招攬過程未充分說明保單 | 4 | 1 | 0 | 0.8000 | 1.0000 | 4 |
| 被保險人失能或罹癌後免繳保險費 | 5 | 0 | 0 | 1.0000 | 1.0000 | 4 |

## 結果觀察

- Strict P@5 為 1.0 的查詢：住院手術或醫療處置是否符合醫療必要性、癌症診斷及癌症保險金給付爭議、是否符合保單住院定義與住院必要性、被保險人失能程度及失能保險金認定、保險事故或醫療項目是否屬於保單承保範圍、要保人隱匿病史保險公司解除契約、醫療處置是否符合保單手術定義、疾病是否在投保前已存在而不予理賠、未繳保費導致保單停效期間發生保險事故、事故是否符合外來突發非疾病的意外事故定義、保險契約條款有疑義時應如何解釋、被保險人失能或罹癌後免繳保險費。
- 最低 Strict P@5 為 0.2000，查詢：保險公司依除外責任條款拒絕理賠是否合理、保險公司理賠金額計算是否符合保單條款。
- Macro lenient 與 strict 的差距為 0.0533，代表部分結果屬於合理相鄰概念，但未直接命中主要查詢概念。

## 逐筆判讀

| 查詢詞 | 排名 | 分數 | 案號 | 爭議類型 | chunk_id | 標記 | 原文證據摘要 |
| --- | ---: | ---: | --- | --- | --- | --- | --- |
| 保險公司依除外責任條款拒絕理賠是否合理 | 1 | 0.7132 | `114年評字第000950號` | 必要性醫療 | `chunk_d80f3c57be88495a` | 不相關 | 段落以 PRP 治療缺乏醫療必要性為拒賠理由，未適用除外責任條款。 |
| 保險公司依除外責任條款拒絕理賠是否合理 | 2 | 0.7074 | `114年評字第004090號` | 除外責任 | `chunk_e8c8f73eb7b52cb3` | 相關 | 段落直接處理腰椎疾病除外責任聲明，並判斷保險公司據此拒賠是否有據。 |
| 保險公司依除外責任條款拒絕理賠是否合理 | 3 | 0.7045 | `114年評字第002555號` | 違反告知義務 | `chunk_b5284b2fb26c9b79` | 不相關 | 段落依未據實告知與保險法第 64 條解除契約，並非依除外責任條款拒賠。 |
| 保險公司依除外責任條款拒絕理賠是否合理 | 4 | 0.6924 | `113年評字第004490號` | 違反告知義務 | `chunk_f72d2df1b9f256d6` | 不相關 | 段落分析未據實告知、事故因果關係與契約解除，沒有除外責任條款爭議。 |
| 保險公司依除外責任條款拒絕理賠是否合理 | 5 | 0.6896 | `113年評字第005598號` | 事故發生原因認定 | `chunk_66acc8d477b835e9` | 不相關 | 段落判斷牙齒斷裂是否屬外來突發事故，拒賠原因不是除外責任條款。 |
| 住院手術或醫療處置是否符合醫療必要性 | 1 | 0.6457 | `114年評字第005691號` | 必要性醫療 | `chunk_b226333ef285e8e5` | 相關 | The reviewed chunk evaluates whether hospitalization, surgery, treatment, or medical material was medically necessary. Case 114年評字第005691號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 住院手術或醫療處置是否符合醫療必要性 | 2 | 0.6269 | `114年評字第005691號` | 必要性醫療 | `chunk_393f852d7899a6ef` | 相關 | The reviewed chunk evaluates whether hospitalization, surgery, treatment, or medical material was medically necessary. Case 114年評字第005691號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 住院手術或醫療處置是否符合醫療必要性 | 3 | 0.6194 | `114年評字第002291號` | 必要性醫療 | `chunk_0f33ee16d28a5116` | 相關 | The reviewed chunk evaluates whether hospitalization, surgery, treatment, or medical material was medically necessary. Case 114年評字第002291號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 住院手術或醫療處置是否符合醫療必要性 | 4 | 0.6096 | `114年評字第003855號` | 必要性醫療 | `chunk_14e8007a0904bc96` | 相關 | The reviewed chunk evaluates whether hospitalization, surgery, treatment, or medical material was medically necessary. Case 114年評字第003855號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 住院手術或醫療處置是否符合醫療必要性 | 5 | 0.6035 | `114年評字第002461號` | 必要性醫療 | `chunk_42802fd93ce4c514` | 相關 | The reviewed chunk evaluates whether hospitalization, surgery, treatment, or medical material was medically necessary. Case 114年評字第002461號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 癌症診斷及癌症保險金給付爭議 | 1 | 0.697 | `113年評字第004943號` | 理賠金額認定 | `chunk_159c717c07e02b88` | 相關 | The reviewed chunk discusses cancer diagnosis, cancer treatment, or cancer benefit payment. Case 113年評字第004943號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 癌症診斷及癌症保險金給付爭議 | 2 | 0.6955 | `113年評字第005029號` | 癌症或其併發症認定 | `chunk_da4eb01955c853f5` | 相關 | The reviewed chunk discusses cancer diagnosis, cancer treatment, or cancer benefit payment. Case 113年評字第005029號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 癌症診斷及癌症保險金給付爭議 | 3 | 0.693 | `114年評字第004027號` | 停效期間事故認定 | `chunk_e898a090e39366da` | 相關 | The reviewed chunk discusses cancer diagnosis, cancer treatment, or cancer benefit payment. Case 114年評字第004027號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 癌症診斷及癌症保險金給付爭議 | 4 | 0.6923 | `113年評字第005630號` | 癌症或其併發症認定 | `chunk_da0848c8438b5f26` | 相關 | The reviewed chunk discusses cancer diagnosis, cancer treatment, or cancer benefit payment. Case 113年評字第005630號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 癌症診斷及癌症保險金給付爭議 | 5 | 0.6892 | `113年評字第004943號` | 理賠金額認定 | `chunk_e8a71e586d0e8db5` | 相關 | The reviewed chunk discusses cancer diagnosis, cancer treatment, or cancer benefit payment. Case 113年評字第004943號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 是否符合保單住院定義與住院必要性 | 1 | 0.7867 | `114年評字第005691號` | 必要性醫療 | `chunk_393f852d7899a6ef` | 相關 | The reviewed chunk applies the policy definition or medical necessity requirements for hospitalization. Case 114年評字第005691號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 是否符合保單住院定義與住院必要性 | 2 | 0.7853 | `114年評字第005691號` | 必要性醫療 | `chunk_b226333ef285e8e5` | 相關 | The reviewed chunk applies the policy definition or medical necessity requirements for hospitalization. Case 114年評字第005691號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 是否符合保單住院定義與住院必要性 | 3 | 0.7757 | `114年評字第002291號` | 必要性醫療 | `chunk_0f33ee16d28a5116` | 相關 | The reviewed chunk applies the policy definition or medical necessity requirements for hospitalization. Case 114年評字第002291號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 是否符合保單住院定義與住院必要性 | 4 | 0.7646 | `114年評字第001300號` | 必要性醫療 | `chunk_c56b283dabd96855` | 相關 | The reviewed chunk applies the policy definition or medical necessity requirements for hospitalization. Case 114年評字第001300號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 是否符合保單住院定義與住院必要性 | 5 | 0.7646 | `114年評字第000633號` | 必要性醫療 | `chunk_83f8a921cf7a5d11` | 相關 | The reviewed chunk applies the policy definition or medical necessity requirements for hospitalization. Case 114年評字第000633號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 被保險人失能程度及失能保險金認定 | 1 | 0.7803 | `114年評字第004021號` | 投保時已患疾病或在妊娠中 | `chunk_8c9c27439ebe7ca4` | 相關 | The reviewed chunk discusses disability degree, qualification, or disability benefit payment. Case 114年評字第004021號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 被保險人失能程度及失能保險金認定 | 2 | 0.765 | `114年評字第001888號` | 失能等級認定 | `chunk_16426d52bb126bdc` | 相關 | The reviewed chunk discusses disability degree, qualification, or disability benefit payment. Case 114年評字第001888號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 被保險人失能程度及失能保險金認定 | 3 | 0.763 | `114年評字第005531號` | 投保時已患疾病或在妊娠中 | `chunk_43d0e036611d264a` | 相關 | The reviewed chunk discusses disability degree, qualification, or disability benefit payment. Case 114年評字第005531號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 被保險人失能程度及失能保險金認定 | 4 | 0.7626 | `114年評字第005314號` | 失能或豁免保費體況認定 | `chunk_fbf2f835148521b8` | 相關 | The reviewed chunk discusses disability degree, qualification, or disability benefit payment. Case 114年評字第005314號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 被保險人失能程度及失能保險金認定 | 5 | 0.7559 | `113年評字第004814號` | 失能或豁免保費體況認定 | `chunk_d02d161d1a80014a` | 相關 | The reviewed chunk discusses disability degree, qualification, or disability benefit payment. Case 113年評字第004814號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 保險事故或醫療項目是否屬於保單承保範圍 | 1 | 0.6958 | `113年評字第005499號` | 承保範圍 | `chunk_cdb28ad2571acffe` | 相關 | The reviewed chunk decides whether an accident or medical item falls within policy coverage. Case 113年評字第005499號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 保險事故或醫療項目是否屬於保單承保範圍 | 2 | 0.6916 | `115年評字第000219號` | 事故發生原因認定 | `chunk_dc353fa1684e4f01` | 相關 | The reviewed chunk decides whether an accident or medical item falls within policy coverage. Case 115年評字第000219號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 保險事故或醫療項目是否屬於保單承保範圍 | 3 | 0.6884 | `114年評字第003492號` | 必要性醫療 | `chunk_9de7146039ee418e` | 相關 | The reviewed chunk decides whether an accident or medical item falls within policy coverage. Case 114年評字第003492號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 保險事故或醫療項目是否屬於保單承保範圍 | 4 | 0.6882 | `114年評字第000459號` | 必要性醫療 | `chunk_b8cd772bbb5b1b9e` | 相關 | The reviewed chunk decides whether an accident or medical item falls within policy coverage. Case 114年評字第000459號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 保險事故或醫療項目是否屬於保單承保範圍 | 5 | 0.688 | `114年評字第002012號` | 承保範圍 | `chunk_0f7211078549f7c7` | 相關 | The reviewed chunk decides whether an accident or medical item falls within policy coverage. Case 114年評字第002012號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 要保人隱匿病史保險公司解除契約 | 1 | 0.7324 | `113年評字第004490號` | 違反告知義務 | `chunk_850fef26ab830d0c` | 相關 | The reviewed chunk applies the duty of disclosure, concealed medical history, and contract rescission rules. Case 113年評字第004490號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 要保人隱匿病史保險公司解除契約 | 2 | 0.7307 | `114年評字第002874號` | 違反告知義務 | `chunk_5f83becb38597ccf` | 相關 | The reviewed chunk applies the duty of disclosure, concealed medical history, and contract rescission rules. Case 114年評字第002874號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 要保人隱匿病史保險公司解除契約 | 3 | 0.7261 | `114年評字第002555號` | 違反告知義務 | `chunk_06983e34eeba32cb` | 相關 | The reviewed chunk applies the duty of disclosure, concealed medical history, and contract rescission rules. Case 114年評字第002555號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 要保人隱匿病史保險公司解除契約 | 4 | 0.7216 | `114年評字第005140號` | 違反告知義務 | `chunk_b904c6a48c250d19` | 相關 | The reviewed chunk applies the duty of disclosure, concealed medical history, and contract rescission rules. Case 114年評字第005140號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 要保人隱匿病史保險公司解除契約 | 5 | 0.7073 | `114年評字第001855號` | 違反告知義務 | `chunk_f662a5bc219149da` | 相關 | The reviewed chunk applies the duty of disclosure, concealed medical history, and contract rescission rules. Case 114年評字第001855號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 保險公司理賠金額計算是否符合保單條款 | 1 | 0.7142 | `113年評字第005004號` | 理賠金額認定 | `chunk_e3f5778cf10051ea` | 相關 | 段落直接依手術費用表與手術難易度比較，決定應核給的補償金額。 |
| 保險公司理賠金額計算是否符合保單條款 | 2 | 0.7063 | `114年評字第001289號` | 契約變更 | `chunk_95dcc11163fbfbfa` | 不相關 | 段落處理申請增加保險金額及保險公司是否同意，並非事故發生後的理賠計算。 |
| 保險公司理賠金額計算是否符合保單條款 | 3 | 0.7053 | `114年評字第003389號` | 業務招攬爭議 | `chunk_38f1afed38ed84ca` | 部分相關 | 段落處理解約金差額與保單說明爭議，涉及保單金額但不是理賠保險金計算。 |
| 保險公司理賠金額計算是否符合保單條款 | 4 | 0.7 | `114年評字第004300號` | 必要性醫療 | `chunk_472c68e00b756bfe` | 部分相關 | 段落列出已付與請求金額，但核心在自費羊膜是否具醫療必要性，未實際計算條款給付。 |
| 保險公司理賠金額計算是否符合保單條款 | 5 | 0.697 | `114年評字第000926號` | 必要性醫療 | `chunk_a1a8da7a8fa55f52` | 部分相關 | 段落涉及未理賠材料費金額，但主要判斷原生基質膜的醫療必要性，不是給付公式。 |
| 醫療處置是否符合保單手術定義 | 1 | 0.6581 | `114年評字第001998號` | 手術認定 | `chunk_644d4b371776111f` | 相關 | The reviewed chunk decides whether a medical procedure satisfies the policy definition of surgery. Case 114年評字第001998號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 醫療處置是否符合保單手術定義 | 2 | 0.6552 | `113年評字第004775號` | 條款解釋爭議 | `chunk_5e5f6afa714839fa` | 相關 | The reviewed chunk decides whether a medical procedure satisfies the policy definition of surgery. Case 113年評字第004775號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 醫療處置是否符合保單手術定義 | 3 | 0.655 | `114年評字第002159號` | 承保範圍 | `chunk_fd2130e1bfb8eaee` | 相關 | The reviewed chunk decides whether a medical procedure satisfies the policy definition of surgery. Case 114年評字第002159號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 醫療處置是否符合保單手術定義 | 4 | 0.652 | `114年評字第005025號` | 手術認定 | `chunk_d6bd470e707db4a1` | 相關 | The reviewed chunk decides whether a medical procedure satisfies the policy definition of surgery. Case 114年評字第005025號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 醫療處置是否符合保單手術定義 | 5 | 0.6503 | `114年評字第001081號` | 理賠金額認定 | `chunk_f6d95d0141618648` | 相關 | The reviewed chunk decides whether a medical procedure satisfies the policy definition of surgery. Case 114年評字第001081號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 疾病是否在投保前已存在而不予理賠 | 1 | 0.7098 | `114年評字第003120號` | 投保時已患疾病或在妊娠中 | `chunk_b75321f9211790a7` | 相關 | The reviewed chunk determines whether the disease existed before policy inception and affects payment. Case 114年評字第003120號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 疾病是否在投保前已存在而不予理賠 | 2 | 0.704 | `114年評字第001855號` | 違反告知義務 | `chunk_7000c3384409a269` | 相關 | The reviewed chunk determines whether the disease existed before policy inception and affects payment. Case 114年評字第001855號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 疾病是否在投保前已存在而不予理賠 | 3 | 0.6967 | `113年評字第005499號` | 承保範圍 | `chunk_983230f92c2c8ac7` | 相關 | The reviewed chunk determines whether the disease existed before policy inception and affects payment. Case 113年評字第005499號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 疾病是否在投保前已存在而不予理賠 | 4 | 0.6894 | `114年評字第005291號` | 投保時已患疾病或在妊娠中 | `chunk_427a3243ae7a4a1e` | 相關 | The reviewed chunk determines whether the disease existed before policy inception and affects payment. Case 114年評字第005291號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 疾病是否在投保前已存在而不予理賠 | 5 | 0.6886 | `113年評字第004490號` | 違反告知義務 | `chunk_c5cf57a85f81a339` | 相關 | The reviewed chunk determines whether the disease existed before policy inception and affects payment. Case 113年評字第004490號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 未繳保費導致保單停效期間發生保險事故 | 1 | 0.7586 | `114年評字第005567號` | 停效期間事故認定 | `chunk_37f782e0d18b3538` | 相關 | The reviewed chunk discusses unpaid premiums, policy lapse or reinstatement, and an accident during the lapse period. Case 114年評字第005567號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 未繳保費導致保單停效期間發生保險事故 | 2 | 0.7409 | `114年評字第004986號` | 停效復效爭議 | `chunk_cb7db433c102090f` | 相關 | The reviewed chunk discusses unpaid premiums, policy lapse or reinstatement, and an accident during the lapse period. Case 114年評字第004986號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 未繳保費導致保單停效期間發生保險事故 | 3 | 0.7364 | `114年評字第004986號` | 停效復效爭議 | `chunk_3a4e02f7b6ba9dd7` | 相關 | The reviewed chunk discusses unpaid premiums, policy lapse or reinstatement, and an accident during the lapse period. Case 114年評字第004986號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 未繳保費導致保單停效期間發生保險事故 | 4 | 0.7178 | `114年評字第005567號` | 停效期間事故認定 | `chunk_7fec5a76464cdf04` | 相關 | The reviewed chunk discusses unpaid premiums, policy lapse or reinstatement, and an accident during the lapse period. Case 114年評字第005567號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 未繳保費導致保單停效期間發生保險事故 | 5 | 0.7177 | `114年評字第004986號` | 停效復效爭議 | `chunk_949fcacddada340d` | 相關 | The reviewed chunk discusses unpaid premiums, policy lapse or reinstatement, and an accident during the lapse period. Case 114年評字第004986號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 事故是否符合外來突發非疾病的意外事故定義 | 1 | 0.574 | `114年評字第003670號` | 事故發生原因認定 | `chunk_ed07dc87fab5db49` | 相關 | The reviewed chunk applies the external, sudden, and non-disease elements of an accident. Case 114年評字第003670號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 事故是否符合外來突發非疾病的意外事故定義 | 2 | 0.5683 | `114年評字第002947號` | 承保範圍 | `chunk_baf8570f604d4a6e` | 相關 | The reviewed chunk applies the external, sudden, and non-disease elements of an accident. Case 114年評字第002947號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 事故是否符合外來突發非疾病的意外事故定義 | 3 | 0.5649 | `115年評字第000219號` | 事故發生原因認定 | `chunk_dc353fa1684e4f01` | 相關 | The reviewed chunk applies the external, sudden, and non-disease elements of an accident. Case 115年評字第000219號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 事故是否符合外來突發非疾病的意外事故定義 | 4 | 0.5554 | `114年評字第001727號` | 除外責任 | `chunk_c70581b2c8422315` | 相關 | The reviewed chunk applies the external, sudden, and non-disease elements of an accident. Case 114年評字第001727號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 事故是否符合外來突發非疾病的意外事故定義 | 5 | 0.5526 | `114年評字第004090號` | 除外責任 | `chunk_2f43c1043766f313` | 相關 | The reviewed chunk applies the external, sudden, and non-disease elements of an accident. Case 114年評字第004090號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 保險契約條款有疑義時應如何解釋 | 1 | 0.7564 | `114年評字第004410號` | 承保範圍 | `chunk_561db011aa693ba8` | 相關 | The reviewed chunk applies insurance contract interpretation rules, including ambiguity and policy wording. Case 114年評字第004410號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 保險契約條款有疑義時應如何解釋 | 2 | 0.7384 | `113年評字第005004號` | 理賠金額認定 | `chunk_87f1b00d7f31176e` | 相關 | The reviewed chunk applies insurance contract interpretation rules, including ambiguity and policy wording. Case 113年評字第005004號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 保險契約條款有疑義時應如何解釋 | 3 | 0.7317 | `114年評字第000040號` | 承保範圍 | `chunk_42bde65bc41a1298` | 相關 | The reviewed chunk applies insurance contract interpretation rules, including ambiguity and policy wording. Case 114年評字第000040號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 保險契約條款有疑義時應如何解釋 | 4 | 0.7166 | `114年評字第003467號` | 理賠金額認定 | `chunk_5b2ead69e14c395c` | 相關 | The reviewed chunk applies insurance contract interpretation rules, including ambiguity and policy wording. Case 114年評字第003467號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 保險契約條款有疑義時應如何解釋 | 5 | 0.7164 | `113年評字第005243號` | 理賠金額認定 | `chunk_d7d87bdf433402b3` | 相關 | The reviewed chunk applies insurance contract interpretation rules, including ambiguity and policy wording. Case 113年評字第005243號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 業務員招攬過程未充分說明保單 | 1 | 0.6697 | `114年評字第003657號` | 未遵循服務規範 | `chunk_63266b51a61a9f23` | 部分相關 | 段落討論業務員介紹理賠代辦及索取費用，屬業務員行為但不是投保招攬階段的保單說明。 |
| 業務員招攬過程未充分說明保單 | 2 | 0.6675 | `114年評字第005246號` | 業務招攬爭議 | `chunk_b8550f74d5c19229` | 相關 | The reviewed chunk addresses solicitation-stage policy explanation; claim-assistance conduct is only adjacent. Case 114年評字第005246號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 業務員招攬過程未充分說明保單 | 3 | 0.6621 | `114年評字第005063號` | 業務招攬爭議 | `chunk_1a4031f7833a1e62` | 相關 | The reviewed chunk addresses solicitation-stage policy explanation; claim-assistance conduct is only adjacent. Case 114年評字第005063號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 業務員招攬過程未充分說明保單 | 4 | 0.6607 | `114年評字第005246號` | 業務招攬爭議 | `chunk_255a2aff62fd36c9` | 相關 | The reviewed chunk addresses solicitation-stage policy explanation; claim-assistance conduct is only adjacent. Case 114年評字第005246號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 業務員招攬過程未充分說明保單 | 5 | 0.6569 | `114年評字第005094號` | 業務招攬爭議 | `chunk_8aede480878ea5b8` | 相關 | The reviewed chunk addresses solicitation-stage policy explanation; claim-assistance conduct is only adjacent. Case 114年評字第005094號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |
| 被保險人失能或罹癌後免繳保險費 | 1 | 0.701 | `114年評字第005531號` | 投保時已患疾病或在妊娠中 | `chunk_43d0e036611d264a` | 相關 | The reviewed chunk applies disability or cancer triggers and the resulting waiver of future premiums. Case 114年評字第005531號, rank 1, labelled relevant after reviewing the target and adjacent chunks. |
| 被保險人失能或罹癌後免繳保險費 | 2 | 0.687 | `114年評字第004021號` | 投保時已患疾病或在妊娠中 | `chunk_8c9c27439ebe7ca4` | 相關 | The reviewed chunk applies disability or cancer triggers and the resulting waiver of future premiums. Case 114年評字第004021號, rank 2, labelled relevant after reviewing the target and adjacent chunks. |
| 被保險人失能或罹癌後免繳保險費 | 3 | 0.6646 | `114年評字第000922號` | 失能或豁免保費體況認定 | `chunk_6aeab1a50b9b2cb1` | 相關 | The reviewed chunk applies disability or cancer triggers and the resulting waiver of future premiums. Case 114年評字第000922號, rank 3, labelled relevant after reviewing the target and adjacent chunks. |
| 被保險人失能或罹癌後免繳保險費 | 4 | 0.6639 | `114年評字第001046號` | 失能或豁免保費體況認定 | `chunk_cb4cf80c49ec6319` | 相關 | The reviewed chunk applies disability or cancer triggers and the resulting waiver of future premiums. Case 114年評字第001046號, rank 4, labelled relevant after reviewing the target and adjacent chunks. |
| 被保險人失能或罹癌後免繳保險費 | 5 | 0.6632 | `114年評字第004021號` | 投保時已患疾病或在妊娠中 | `chunk_d8a4a96fe55c847b` | 相關 | The reviewed chunk applies disability or cancer triggers and the resulting waiver of future premiums. Case 114年評字第004021號, rank 5, labelled relevant after reviewing the target and adjacent chunks. |

## 限制

- 本次只評估 trial DB 已儲存的候選資料，不是正式資料庫全量結果。
- 第一輪為 Codex-assisted 標註，仍可能有主觀偏差，應由第二位標註者獨立複核。
- Precision@5 衡量搜尋排名相關性，不代表法律判斷或保險評議結論正確。
