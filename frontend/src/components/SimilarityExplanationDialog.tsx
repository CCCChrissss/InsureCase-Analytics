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
            <p>這個數字是協助你快速排列案件的參考。</p>
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
            <span>比較案件文字</span>
            <span aria-hidden="true">→</span>
            <span>顯示接近程度</span>
          </div>
          <p>系統會把你輸入的內容和案件文字逐一比較，再找出案件中意思最接近的一段。</p>
          <ul>
            <li>分數越高，表示案件內容和搜尋文字越接近。</li>
            <li>分數適合用來排序，以及快速找出可能相關的案件。</li>
            <li>分數不是理賠結果，也不代表案件一定適用。</li>
            <li>實際判斷仍需要查看案件摘要、理由與原文。</li>
          </ul>
          <div className="similarity-example">
            搜尋「癌症住院」時顯示 85%，代表案件中有內容和這個搜尋方向接近，不代表有 85% 的機率應該理賠。
          </div>
          <small>搜尋與比較都在本機完成，不會傳送到外部 AI 服務。</small>
        </div>
      </section>
    </div>
  );
}
