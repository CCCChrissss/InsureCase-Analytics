import type React from "react";
import { BookOpenCheck, Calculator, Database, SearchCheck, ShieldCheck } from "lucide-react";

import { apiGet } from "../api/client";
import { PageHeader } from "../components/ui";
import { useAsyncData } from "../hooks/useAsyncData";
import type { EmbeddingStatusResponse } from "../types";

const SQLITE_FTS5_DOCS = "https://www.sqlite.org/fts5.html#the_bm25_function";

export function CalculationMethodPage() {
  // 顯示目前 API 實際連線的模型設定，避免說明頁與執行環境不一致。
  const embeddingStatus = useAsyncData(() => apiGet<EmbeddingStatusResponse>("/embedding-status"), []);
  const configuredModel = embeddingStatus.data?.configured_model ?? "讀取中";
  const configuredProvider = embeddingStatus.data?.configured_provider ?? "讀取中";

  return (
    <section className="page methodology-page">
      <PageHeader
        title="相似度與搜尋計算方法"
        description="說明搜尋排序、相關案件與畫面分數的來源，讓結果可以被核對，而不是只看到一個百分比。"
      />

      <div className="method-status-strip" aria-label="目前計算環境">
        {/* 完整名稱保留在 title，畫面欄位不足時則以省略號避免單字斷裂。 */}
        <div><Database size={18} /><span>資料庫</span><strong title={embeddingStatus.data?.database_name}>{embeddingStatus.data?.database_name ?? "讀取中"}</strong></div>
        <div><Calculator size={18} /><span>語意模型</span><strong title={configuredModel}>{configuredModel}</strong></div>
        <div><ShieldCheck size={18} /><span>執行位置</span><strong>{configuredProvider === "local_bge" ? "本機執行" : configuredProvider}</strong></div>
      </div>

      {embeddingStatus.error && (
        <div className="semantic-unavailable-note">目前無法讀取模型狀態，但下方計算規則仍可查閱。</div>
      )}

      <nav className="method-toc" aria-label="計算方法章節">
        <a href="#keyword-search">全文搜尋</a>
        <a href="#query-similarity">搜尋相似度</a>
        <a href="#related-cases">相關案件</a>
        <a href="#decision-result">評議結果</a>
        <a href="#quality-limits">驗證與限制</a>
      </nav>

      <MethodSection
        id="text-chunking"
        icon={<BookOpenCheck size={20} />}
        title="案件文字如何準備"
        plain="完整決定書太長，系統先把文字切成多段，後續比較時才能找到真正接近搜尋內容的段落。"
      >
        <ol className="method-steps">
          <li>每段目標長度為 1,000 個字元，最短切點範圍為 250 個字元。</li>
          <li>相鄰段落重疊 180 個字元，降低重要句子剛好被切斷的影響。</li>
          <li>優先在換行、句號或分號附近切割，並保留主文、申請人主張、判斷理由等章節標示。</li>
        </ol>
      </MethodSection>

      <MethodSection
        id="keyword-search"
        icon={<SearchCheck size={20} />}
        title="全文搜尋與關鍵字相關性"
        plain="系統先找出文字中確實命中查詢詞的案件。一般排序會把關鍵字較集中、較具代表性的案件放前面。"
      >
        <div className="formula-block">
          <strong>SQLite FTS5 BM25</strong>
          <code>BM25(D,Q) = - Σ IDF(qᵢ) × [f(qᵢ,D) × (k₁ + 1)] / [f(qᵢ,D) + k₁ × (1 - b + b × |D| / avgdl)]</code>
          <span>目前 SQLite 固定 k₁ = 1.2、b = 0.75；因公式乘上 -1，所以數值越小代表全文命中越好。</span>
        </div>
        <p className="method-note">
          中文斷詞可能讓 FTS5 找不到結果。若 FTS5 發生錯誤，或沒有任何結果，系統會改用 LIKE 檢查案號、爭議類型與案件全文。LIKE 結果依日期與案號排列，不使用 BM25。
        </p>
        <a className="method-source-link" href={SQLITE_FTS5_DOCS} target="_blank" rel="noreferrer">
          SQLite 官方 FTS5 bm25() 說明
        </a>
      </MethodSection>

      <MethodSection
        id="query-similarity"
        icon={<Calculator size={20} />}
        title="搜尋文字與案件相似度"
        plain="系統把搜尋文字和每個命中案件的各段內容做比較，取其中最接近的一段作為該案件分數。"
      >
        <div className="formula-block">
          <strong>搜尋到案件的分數</strong>
          <code>s(q,cᵢ) = cos(E(q), E(cᵢ))</code>
          <code>Squery(q,C) = maxᵢ s(q,cᵢ)</code>
          <code>畫面百分比 = round(clamp(Squery, 0, 1) × 100)%</code>
          <span>E 代表本機 BGE 將文字轉成的向量；cos 代表餘弦相似度。</span>
        </div>
        <p className="method-note">
          選擇「相似度：高到低」時，系統會先算完所有關鍵字命中案件，再排序與分頁。最多快取最近 16 組查詢，翻頁時不必重新計算整批結果。
        </p>
      </MethodSection>

      <MethodSection
        id="related-cases"
        icon={<Calculator size={20} />}
        title="案件 Dashboard 的相關案件"
        plain="這裡不是拿搜尋詞比較，而是先把目前案件整理成一個代表向量，再找其他案件中最接近它的段落。"
      >
        <div className="formula-block">
          <strong>案件 A 到案件 B 的相關程度</strong>
          <code>VA = normalize(Σᵢ E(aᵢ))</code>
          <code>Srelated(A,B) = maxⱼ cos(VA, E(bⱼ))</code>
          <code>畫面百分比 = round(clamp(Srelated, 0, 1) × 100)%</code>
          <span>系統保留每個候選案件的最高分與最接近段落，依分數、日期及案號排列，顯示前 5 件。</span>
        </div>
        <div className="method-warning">
          A 找 B 與 B 找 A 的分數可能不同；另外，只要某一段高度相近就可能得到高分，因此制式文字或共同條款可能拉高結果。相關案件只能協助查找，不能直接判定案件可比性。
        </div>
      </MethodSection>

      <MethodSection
        id="decision-result"
        icon={<ShieldCheck size={20} />}
        title="搜尋結果中的評議結果"
        plain="評議結果不是由相似度推算，而是從案件主文中的明確文字保守分類。"
      >
        <div className="decision-rule-table" role="table" aria-label="評議結果分類規則">
          <div role="row"><strong role="cell">有理由</strong><span role="cell">出現應給付、應恢復、確認契約存在或明確有理由等結論。</span></div>
          <div role="row"><strong role="cell">部分有理由</strong><span role="cell">同時出現有利結論與其餘請求駁回、無理由或不受理。</span></div>
          <div role="row"><strong role="cell">無理由</strong><span role="cell">出現駁回或難為有利認定等明確結論。</span></div>
          <div role="row"><strong role="cell">不受理</strong><span role="cell">主文只出現不予受理或不受理，且沒有有利結論。</span></div>
          <div role="row"><strong role="cell">尚未整理</strong><span role="cell">文字不足以可靠分類時不猜測，提示使用者查看正式原文。</span></div>
        </div>
      </MethodSection>

      <MethodSection
        id="quality-limits"
        icon={<BookOpenCheck size={20} />}
        title="驗證方式與使用限制"
        plain="系統用 Precision@5 檢查每個查詢前五筆中有多少筆被標註為相關，但這只是查找品質指標。"
      >
        <div className="formula-block">
          <strong>Precision@5</strong>
          <code>Precision@5 = 前 5 筆中的相關案件數 / 5</code>
          <span>現有 POC 輔助標註紀錄：Strict 0.9200、Lenient 0.9733。這不是獨立盲測，不能當作正式模型準確率。</span>
        </div>
        <ul className="method-limit-list">
          <li>相似度只表示文字語意接近，不表示應賠、勝訴機率或法律適用結論。</li>
          <li>法源依據只列決定書中辨識到的法規條文，不呈現保單或契約條款。</li>
          <li>本機 BGE 不會呼叫 Hugging Face API；模型與 embeddings 必須事先存在於本機。</li>
          <li>摘要與評議結果仍可能受到 PDF 文字抽取、章節辨識及規則式分類限制。</li>
        </ul>
      </MethodSection>
    </section>
  );
}

function MethodSection({
  id,
  icon,
  title,
  plain,
  children,
}: {
  id: string;
  icon: React.ReactNode;
  title: string;
  plain: string;
  children: React.ReactNode;
}) {
  return (
    <section className="method-section" id={id}>
      <header>
        {icon}
        <div>
          <h3>{title}</h3>
          <p>{plain}</p>
        </div>
      </header>
      <div className="method-section-content">{children}</div>
    </section>
  );
}
