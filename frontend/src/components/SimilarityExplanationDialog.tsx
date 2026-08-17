import React from "react";
import { Info, X } from "lucide-react";

export function SimilarityExplanationDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const closeButtonRef = React.useRef<HTMLButtonElement>(null);

  React.useEffect(() => {
    if (!open) return;
    closeButtonRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div className="similarity-explanation-overlay" role="presentation" onMouseDown={onClose}>
      <section
        className="similarity-explanation-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="similarity-explanation-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <span className="similarity-explanation-icon"><Info size={20} /></span>
          <div>
            <h3 id="similarity-explanation-title">相似度怎麼看</h3>
            <p>不必先想出正式關鍵字，也可以直接描述事情經過。</p>
          </div>
          <button
            ref={closeButtonRef}
            className="icon-button"
            type="button"
            onClick={onClose}
            aria-label="關閉相似度說明"
            title="關閉"
          >
            <X size={18} />
          </button>
        </header>

        <div className="similarity-explanation-body">
          <div className="similarity-plain-steps" aria-label="相似度產生方式">
            <span>輸入搜尋內容</span>
            <span aria-hidden="true">→</span>
            <span>比較全部案件</span>
            <span aria-hidden="true">→</span>
            <span>合併文字與語意結果</span>
          </div>
          <p>系統會同時尋找相同文字，也會比較整段敘述的意思，再把兩種結果合併排序。</p>
          <ul>
            <li>即使沒有出現完全相同的詞，只要敘述意思接近，案件仍可能被找到。</li>
            <li>同時有文字命中與語意接近的案件，通常會排得更前面。</li>
            <li>「查找範圍」決定是否只保留文字命中的案件；「排序方向」決定從最相關或最不相關開始顯示。</li>
            <li>分數越高，表示案件內容和搜尋文字越接近。</li>
            <li>分數不是理賠結果，也不代表案件一定適用。</li>
            <li>實際判斷仍需要查看案件摘要、理由與原文。</li>
          </ul>
          <div className="similarity-example">
            輸入「住院後保險公司認為不需要住院」時，系統也可能找到寫著「不符合醫療必要性」的案件。顯示 85% 只代表文字意思接近，不代表有 85% 的機率應該理賠。
          </div>
          <small>搜尋使用本機 BGE 完成，不會把輸入內容傳送到外部 AI 服務。</small>
        </div>
      </section>
    </div>
  );
}
