
"""Prompts for Gemini, and the rules that keep its output grounded.

Context understanding
    The summary prompt makes the model read the whole document and fill in
    an analysis first (what kind of document, its purpose, its sections and
    key facts) before it writes. The schema's field order makes that
    happen in one call: the analysis comes before the paragraphs.

Hallucination control
    1. Rules in every prompt: use only the document, say when something is
       not in it, never fill gaps from general knowledge.
    2. Evidence: every summary paragraph and chat answer comes with
       verbatim quotes from the document that support it.
    3. Verification, done here in code rather than trusted to the model:
       - each quote must really occur in the document;
       - each number in the output must occur in the document.
    4. Repair: a summary that fails verification is sent back once with
       the problems listed, to be corrected against the document.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ shared

GROUNDING_RULES = """Grounding rules (follow strictly):
1. Use ONLY the document. Never add facts, numbers, names, dates or
   explanations from general knowledge, even if you are sure they are true.
2. If the document does not say something, do not guess or infer it.
   Say that the document does not cover it.
3. Keep every number, date, name and unit exactly as the document gives it.
   Do not round, convert or calculate new figures.
4. Keep the document's level of certainty: "may", "suggests" and "about"
   must not become "will", "proves" or "exactly".
5. Attribute claims correctly. If the document reports someone else's view
   or a claim it argues against, say so; do not present it as the
   document's own conclusion.
6. Evidence quotes must be copied word for word from the document: no
   paraphrasing, no ellipses, no fixing of typos. Keep each under 40 words."""


def document_block(document: str, filename: str) -> str:
    """The document goes first and the instructions after it, which helps
    models with long inputs keep the instructions in mind."""
    return (
        f'<document name="{filename}" words="{len(document.split())}">\n'
        f"{document}\n"
        f"</document>"
    )


# ----------------------------------------------------------------- summary

class Section(BaseModel):
    title: str = Field(description="Short name for this part of the document")
    main_idea: str = Field(description="One sentence: what this part says")


class DocumentAnalysis(BaseModel):
    document_type: str = Field(
        description="e.g. research paper, contract, news article, report"
    )
    purpose: str = Field(description="Why the document was written, one sentence")
    audience: str = Field(description="Who it is written for")
    main_point: str = Field(description="Its central claim or finding, one sentence")
    sections: list[Section] = Field(
        description="The document's main parts, in order"
    )
    key_facts: list[str] = Field(
        description="The most important figures, names, dates and decisions, "
        "each exactly as written in the document"
    )


class SummaryParagraph(BaseModel):
    text: str = Field(description="The paragraph, plain text, complete sentences")
    evidence: list[str] = Field(
        description="1-3 verbatim quotes from the document that support "
        "the paragraph's claims"
    )


class SummaryDraft(BaseModel):
    # Field order matters: the model analyses before it writes.
    analysis: DocumentAnalysis
    paragraphs: list[SummaryParagraph]


SUMMARY_SYSTEM = f"""You are an expert analyst who writes accurate,
well-organized summaries of documents for readers who have not read them.

Work in two steps:
1. Analysis: read the entire document, then record what kind of document it
   is, its purpose and audience, its central point, its main sections in
   order, and its key facts. Base this on the whole text, not just the
   opening.
2. Summary: using your analysis, write the summary paragraphs.

{GROUNDING_RULES}

Writing rules:
- Each paragraph covers one main section or theme, in the document's order.
- The first paragraph says what the document is and states its main point.
- Start each paragraph with its main point, then support it with the
  specifics that matter: findings, figures, names, dates, decisions.
- Explain how ideas connect (causes, consequences, comparisons) instead of
  listing disconnected facts.
- Give weight in proportion to the document: do not let one detail crowd out
  a major section.
- Plain text only: no headings, bullets, numbering, bold or Markdown, and no
  meta phrases such as "This summary" or "Here is"."""


def summary_request(document: str, filename: str, words: int, paragraphs: int) -> str:
    return (
        f"{document_block(document, filename)}\n\n"
        f"Analyse the document above, then summarize it in about {words} "
        f"words across about {paragraphs} paragraph(s). Every paragraph needs "
        f"verbatim evidence quotes."
    )


REPAIR_SYSTEM = f"""You correct summaries so that every statement is supported
by the document. Change only what is needed: remove or correct unsupported
claims, keep everything that is supported, and keep the same structure,
length and plain-text style.

{GROUNDING_RULES}"""


def repair_request(
    document: str,
    filename: str,
    draft: str,
    problems: list[str],
) -> str:
    listed = "\n".join(f"- {p}" for p in problems)
    return (
        f"{document_block(document, filename)}\n\n"
        f"<draft_summary>\n{draft}\n</draft_summary>\n\n"
        f"Checking the draft against the document found these problems:\n"
        f"{listed}\n\n"
        f"Rewrite the draft so every statement is supported by the document. "
        f"Fill in `analysis` again and give evidence quotes for each paragraph."
    )


# -------------------------------------------------------------------- chat

class AnswerPoint(BaseModel):
    text: str = Field(
        description='One specific point. Starts with its key term in bold '
        'and a colon, e.g. "**Training cost:** falls by half when ..."'
    )
    quote: Optional[int] = Field(
        default=None,
        description="Number (1-based) of the quote in `quotes` that supports "
        "this point, or null if none does",
    )


class ChatAnswer(BaseModel):
    # Quotes first, so the answer is written from the evidence.
    quotes: list[str] = Field(
        description="0-5 verbatim quotes from the document that the answer "
        "is based on; empty if the document does not cover the question"
    )
    found_in_document: bool = Field(
        description="True only if the document contains the information asked for"
    )
    direct_answer: str = Field(
        description="The answer itself in 1-2 sentences, no preamble"
    )
    points: list[AnswerPoint] = Field(
        description="2-6 supporting points for questions that need detail "
        "(lists, how/why, comparisons, steps); empty for simple factual questions"
    )
    not_covered: Optional[str] = Field(
        default=None,
        description="One sentence on what part of the question the document "
        "does not address, or null if it covers all of it",
    )


CHAT_SYSTEM = """You are a careful assistant answering questions about one
document the user uploaded. The document is below; a summary of it was
already shown to the user.

{document}

How to answer:
- First collect the quotes that answer the question, then answer from them.
- direct_answer: answer the question itself in 1-2 sentences. Lead with the
  answer, not with background, and never start with "The document says".
- points: when the question asks for a list, an explanation, steps, causes
  or a comparison, give 2-6 points that build the full answer:
  - each point is one specific idea, fact or step, in 1-2 sentences;
  - start each with its key term in bold and a colon: "**Key term:** ...";
    use bold nowhere else;
  - order them logically: steps in sequence, otherwise most important first;
  - don't repeat the direct answer;
  - set `quote` to the number of the quote that supports the point.
  For a simple factual question, leave points empty.
- For follow-up questions, use the conversation to work out what "it",
  "they" or "that" refer to.
- If the question is only partly covered, answer the covered part and put
  the rest in not_covered.
- If the document does not cover it at all, set found_in_document to false,
  say so in direct_answer without guessing, and leave points empty. You may
  mention the closest related thing the document does say.
- If the user asks for your opinion or for outside information, explain that
  you can only report what the document says.
- No headings and no other Markdown.

{rules}"""


def answer_text(reply: ChatAnswer) -> str:
    """The answer as plain text: stored as the message content and sent
    back to the model as conversation history."""
    lines = [reply.direct_answer.strip()]
    lines += [f"- {p.text.strip()}" for p in reply.points if p.text.strip()]
    if reply.not_covered:
        lines.append(f"Not covered by the document: {reply.not_covered.strip()}")
    return "\n".join(line for line in lines if line)


def chat_system(document: str, filename: str) -> str:
    return CHAT_SYSTEM.format(
        document=document_block(document, filename),
        rules=GROUNDING_RULES,
    )


# ------------------------------------------------------------ verification

WORD = re.compile(r"[a-z0-9]+")
# 1,200 | 3.5 | 90% | 2024
NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def _tokens(text: str) -> list[str]:
    return WORD.findall(text.lower())


def extract_numbers(text: str) -> set[str]:
    """Numbers in the text, normalized ("1,200" -> "1200"). Single digits
    are left out: "three steps" written as "3 steps" is not a fact."""
    found = set()
    for match in NUMBER.findall(text):
        value = match.replace(",", "").rstrip(".")
        if value.endswith(".0"):
            value = value[:-2]
        if len(value.replace(".", "")) > 1:
            found.add(value)
    return found


class DocumentIndex:
    """What verification compares against; build once per document."""

    def __init__(self, document: str):
        tokens = _tokens(document)
        self.text = " ".join(tokens)
        self.fourgrams = set(zip(tokens, tokens[1:], tokens[2:], tokens[3:]))
        self.numbers = extract_numbers(document)

    def contains_quote(self, quote: str, min_overlap: float = 0.8) -> bool:
        """True if the quote appears in the document, ignoring case,
        punctuation and spacing. Long quotes may differ slightly (e.g. a
        quote that runs across a paragraph break): then 80% of their
        4-word sequences must occur in the document."""
        tokens = _tokens(quote)
        if not tokens:
            return False
        if " ".join(tokens) in self.text:
            return True
        grams = list(zip(tokens, tokens[1:], tokens[2:], tokens[3:]))
        if len(grams) < 3:
            return False
        return sum(g in self.fourgrams for g in grams) / len(grams) >= min_overlap

    def unsupported_numbers(self, text: str) -> list[str]:
        return sorted(extract_numbers(text) - self.numbers)


@dataclass
class GroundingReport:
    quotes: int = 0
    verified_quotes: int = 0
    unverified_quotes: list[str] = field(default_factory=list)
    unsupported_numbers: list[str] = field(default_factory=list)
    # Paragraphs without a single verified quote.
    unsupported_paragraphs: list[int] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Share of the checks that passed, 0..1."""
        checks = self.quotes + len(self.unsupported_numbers) + len(
            self.unsupported_paragraphs
        )
        if not checks:
            return 1.0
        return self.verified_quotes / checks

    @property
    def ok(self) -> bool:
        return not self.unsupported_numbers and not self.unsupported_paragraphs

    def problems(self) -> list[str]:
        problems = [
            f'The number "{n}" does not appear in the document.'
            for n in self.unsupported_numbers
        ]
        problems += [
            f"Paragraph {i + 1} has no evidence quote that appears in the "
            f"document, so its claims could not be verified."
            for i in self.unsupported_paragraphs
        ]
        problems += [
            f'This "quote" is not in the document: "{q[:200]}"'
            for q in self.unverified_quotes
        ]
        return problems


def check_summary(draft: SummaryDraft, index: DocumentIndex) -> GroundingReport:
    report = GroundingReport()

    for i, paragraph in enumerate(draft.paragraphs):
        verified = 0
        for quote in paragraph.evidence:
            report.quotes += 1
            if index.contains_quote(quote):
                verified += 1
            else:
                report.unverified_quotes.append(quote)
        report.verified_quotes += verified
        if not verified:
            report.unsupported_paragraphs.append(i)

        report.unsupported_numbers += index.unsupported_numbers(paragraph.text)

    report.unsupported_numbers = sorted(set(report.unsupported_numbers))
    return report


# Meta phrases models add despite instructions.
META_PREFIX = re.compile(
    r"^(?:here is|here's|this summary|in summary,|summary:)[^.:]*[.:]\s*",
    re.IGNORECASE,
)


def plain_text(text: str) -> str:
    """Strip Markdown and meta phrases from one paragraph."""
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:#+\s*|[-*•]\s+|\d+[.)]\s+)", "", line)
        line = re.sub(r"(\*\*|__)(.+?)\1", r"\2", line).strip()
        if line:
            lines.append(line)
    return META_PREFIX.sub("", " ".join(lines)).strip()


def draft_text(draft: SummaryDraft) -> str:
    """The summary as the front-end expects it: paragraphs separated by a
    blank line."""
    paragraphs = (plain_text(p.text) for p in draft.paragraphs)
    return "\n\n".join(p for p in paragraphs if p)
