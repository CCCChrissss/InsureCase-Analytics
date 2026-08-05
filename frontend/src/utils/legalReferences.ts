export type LegalReference = {
  id: string;
  title: string;
  category: "法規";
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

const LAW_REFERENCE_PATTERN = new RegExp(
  `(?:${LAW_NAMES.join("|")})\\s*第\\s*${ARTICLE_NUMBER}\\s*條(?:\\s*第\\s*${ARTICLE_NUMBER}\\s*(?:項|款|目))*`,
  "g"
);

// 法源區刻意採法規名稱白名單，不解析保單、附約或個別契約條款。
export function extractLegalReferences(text: string | null | undefined, limit = 8): LegalReference[] {
  if (!text?.trim()) return [];

  const matches: Array<{ title: string; index: number }> = [];
  for (const match of text.matchAll(LAW_REFERENCE_PATTERN)) {
    if (match.index === undefined) continue;
    matches.push({
      title: cleanText(match[0]),
      index: match.index,
    });
  }

  matches.sort((left, right) => left.index - right.index);
  const seen = new Set<string>();
  const references: LegalReference[] = [];
  for (const match of matches) {
    const key = match.title.replace(/\s+/g, "");
    if (seen.has(key)) continue;
    seen.add(key);
    references.push({
      id: `法規-${match.index}-${key}`,
      title: match.title,
      category: "法規",
    });
    if (references.length >= limit) break;
  }
  return references;
}

function cleanText(value: string) {
  return value
    .replace(/---\s*page\s+\d+\s*---/gi, " ")
    .replace(/-第\s*\d+\s*頁[^-]*-/g, " ")
    .replace(/\s+/g, " ")
    .replace(/([\u3400-\u9fff])\s+(?=[\u3400-\u9fff])/g, "$1")
    .trim();
}
