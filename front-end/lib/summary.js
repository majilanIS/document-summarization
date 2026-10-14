// Turns the back-end's summary text into sections of sentences.
// The back-end separates each part of the document's summary with a blank line.

// Split after . ! ? when the next sentence starts with a capital, digit or
// quote, so decimals ("1.5") and lowercase abbreviations ("e.g. this") stay
// put. Initials ("Joseph E. Gonzalez") and common abbreviations don't split.
const SENTENCE_BREAK =
  /(?<=[.!?])(?<!\b[A-Z]\.)(?<!\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|St|vs|etc|Fig|No|Eq|Vol|al)\.)\s+(?=["'“(\[]?[A-Z0-9])/;

export function splitSentences(paragraph) {
  return paragraph
    .split(SENTENCE_BREAK)
    .map((s) => s.trim())
    .filter(Boolean);
}

/** [{ text, sentences: [...] }, ...] — one entry per part of the document. */
export function structureSummary(text) {
  return text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((paragraph) => ({
      text: paragraph,
      sentences: splitSentences(paragraph),
    }));
}

/** Plain-text version for copying and downloading. */
export function summaryToText(sections, view) {
  const multiple = sections.length > 1;

  return sections
    .map((section, i) => {
      const heading = multiple ? `Part ${i + 1}\n` : "";
      const body =
        view === "points"
          ? section.sentences.map((s) => `• ${s}`).join("\n")
          : section.text;
      return heading + body;
    })
    .join("\n\n");
}

/** Minutes to read at ~200 words per minute (at least 1). */
export function readingMinutes(words) {
  return Math.max(1, Math.round(words / 200));
}
