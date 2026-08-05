export type LegalReference = {
  id: string;
  title: string;
  category: "法規" | "契約條款";
  excerpt: string;
};

const ARTICLE_NUMBER = "[0-9一二三四五六七八九十百千]+(?:\\s*之\\s*[0-9一二三四五六七八九十]+)?";
const LAW_NAMES = [
  "保險法",
  "民法",
  "刑法",
  "金融消費者保護法",
  "消費者保護法",
  "個人資料保護法",
  "醫療法",
  "全民健康保險法",
  "優生保健法",
  "毒品危害防制條例",
  "道路交通管理處罰條例",
  "道路交通安全規則",
];

function referencePatterns() {
  return [
    {
      category: "法規" as const,
      pattern: new RegExp(
        `(?:${LAW_NAMES.join("|")})\\s*第\\s*${ARTICLE_NUMBER}\\s*條(?:\\s*第\\s*${ARTICLE_NUMBER}\\s*(?:項|款|目))*`,
        "g"
      ),
    },
    {
      category: "契約條款" as const,
      pattern: new RegExp(
        `(?:系爭\\s*)?(?:[A-ZＡ-Ｚ]?[○〇]{0,3})?(?:保險契約|保單條款|保險條款|契約條款|附約條款|保單|附約|條款)\\s*第\\s*${ARTICLE_NUMBER}\\s*條(?:\\s*【[^】]{1,40}】)?(?:\\s*第\\s*${ARTICLE_NUMBER}\\s*(?:項|款|目))*`,
        "g"
      ),
    },
  ];
}

export function extractLegalReferences(text: string | null | undefined, limit = 8): LegalReference[] {
  if (!text?.trim()) return [];

  const matches: Array<{ title: string; category: LegalReference["category"]; index: number; end: number }> = [];
  for (const { category, pattern } of referencePatterns()) {
    for (const match of text.matchAll(pattern)) {
      if (match.index === undefined) continue;
      matches.push({
        title: cleanText(match[0]),
        category,
        index: match.index,
        end: match.index + match[0].length,
      });
    }
  }

  matches.sort((left, right) => left.index - right.index);
  const seen = new Set<string>();
  const references: LegalReference[] = [];
  for (const match of matches) {
    const key = match.title.replace(/\s+/g, "");
    if (seen.has(key)) continue;
    seen.add(key);
    references.push({
      id: `${match.category}-${match.index}-${key}`,
      title: match.title,
      category: match.category,
      excerpt: sourceExcerpt(text, match.index, match.end),
    });
    if (references.length >= limit) break;
  }
  return references;
}

function sourceExcerpt(text: string, start: number, end: number) {
  const excerptStart = Math.max(0, start - 70);
  const excerptEnd = Math.min(text.length, end + 150);
  const excerpt = cleanText(text.slice(excerptStart, excerptEnd));
  return `${excerptStart > 0 ? "..." : ""}${excerpt}${excerptEnd < text.length ? "..." : ""}`;
}

function cleanText(value: string) {
  return value
    .replace(/---\s*page\s+\d+\s*---/gi, " ")
    .replace(/-第\s*\d+\s*頁[^-]*-/g, " ")
    .replace(/\s+/g, " ")
    .replace(/([\u3400-\u9fff])\s+(?=[\u3400-\u9fff])/g, "$1")
    .trim();
}
