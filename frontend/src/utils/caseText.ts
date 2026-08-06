export type CaseTextMode = "normalized" | "raw";

export type CaseTextSelection = {
  text: string;
  sourceMode: CaseTextMode | null;
  actualChars: number;
  expectedChars: number | null;
  matchesExpected: boolean | null;
  usedFallback: boolean;
};

type CaseTextInput = {
  normalizedText: string | null;
  rawText: string | null;
  normalizedTextChars: number | null;
  rawTextChars: number | null;
};

/**
 * Selects one complete text source without slicing it. When the requested source is
 * unavailable, the other source remains readable and the UI can disclose the fallback.
 */
export function selectCompleteCaseText(input: CaseTextInput, requestedMode: CaseTextMode): CaseTextSelection {
  const requestedText = requestedMode === "normalized" ? input.normalizedText : input.rawText;
  const fallbackMode: CaseTextMode = requestedMode === "normalized" ? "raw" : "normalized";
  const fallbackText = fallbackMode === "normalized" ? input.normalizedText : input.rawText;
  const sourceMode = requestedText ? requestedMode : fallbackText ? fallbackMode : null;
  const text = requestedText || fallbackText || "";
  const expectedChars = sourceMode === "normalized" ? input.normalizedTextChars
    : sourceMode === "raw" ? input.rawTextChars
      : null;
  const actualChars = countUnicodeCharacters(text);

  return {
    text,
    sourceMode,
    actualChars,
    expectedChars,
    matchesExpected: expectedChars === null ? null : actualChars === expectedChars,
    usedFallback: sourceMode !== null && sourceMode !== requestedMode,
  };
}

/** Python records Unicode code points, so Array.from avoids counting surrogate pairs twice. */
export function countUnicodeCharacters(value: string): number {
  return Array.from(value).length;
}
