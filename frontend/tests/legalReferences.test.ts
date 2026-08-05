import assert from "node:assert/strict";
import test from "node:test";

import { extractLegalReferences } from "../src/utils/legalReferences.ts";

test("法源依據只保留法規條文並排除契約條款", () => {
  // 同一段刻意混合法規與契約條款，避免只測到單一正向案例。
  const references = extractLegalReferences(
    "本件引用保險法第 54 條第 2 項，另載有系爭保險契約第 13 條及附約條款第 5 條。"
  );

  assert.deepEqual(references.map((reference) => reference.title), ["保險法第 54 條第 2 項"]);
  assert.ok(references.every((reference) => reference.category === "法規"));
  assert.ok(references.every((reference) => !/契約|保單|附約|條款/.test(reference.title)));
});
