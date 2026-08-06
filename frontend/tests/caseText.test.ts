import assert from "node:assert/strict";
import test from "node:test";

import { countUnicodeCharacters, selectCompleteCaseText } from "../src/utils/caseText.ts";

test("完整案件文字保留開頭、中段與結尾且不做切片", () => {
  const text = `開頭-${"判斷內容".repeat(900)}-結尾`;
  const selection = selectCompleteCaseText({
    normalizedText: text,
    rawText: "原始文字",
    normalizedTextChars: countUnicodeCharacters(text),
    rawTextChars: 4,
  }, "normalized");

  assert.equal(selection.text, text);
  assert.ok(selection.text.startsWith("開頭-"));
  assert.ok(selection.text.includes("判斷內容".repeat(50)));
  assert.ok(selection.text.endsWith("-結尾"));
  assert.equal(selection.matchesExpected, true);
  assert.equal(selection.usedFallback, false);
});

test("指定文字不存在時揭露 fallback 並核對實際來源字數", () => {
  const selection = selectCompleteCaseText({
    normalizedText: null,
    rawText: "原始抽取文字🙂",
    normalizedTextChars: null,
    rawTextChars: 7,
  }, "normalized");

  assert.equal(selection.sourceMode, "raw");
  assert.equal(selection.usedFallback, true);
  assert.equal(selection.actualChars, 7);
  assert.equal(selection.matchesExpected, true);
});
