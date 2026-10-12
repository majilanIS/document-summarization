
import re
import unicodedata


# Lines that are only a page number, e.g. "12", "- 12 -", "Page 3 of 10".
PAGE_NUMBER_LINE = re.compile(
    r"^\s*(?:page\s+)?-?\s*\d+\s*-?(?:\s+of\s+\d+)?\s*$",
    re.IGNORECASE,
)


def normalize_unicode(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)

    replacements = {
        "­": "",   # soft hyphen
        "​": "",   # zero-width space
        "﻿": "",   # byte order mark
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "•": "-",  # bullet
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Drop remaining control characters except newlines and tabs.
    return "".join(
        ch for ch in text
        if ch in "\n\t" or unicodedata.category(ch)[0] != "C"
    )


def clean_text(text: str) -> str:
    text = normalize_unicode(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Re-join words hyphenated across line breaks: "summa-\nrization".
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    lines = [
        line.strip()
        for line in text.split("\n")
        if not PAGE_NUMBER_LINE.match(line)
    ]

    # Blank lines separate paragraphs; single line breaks inside
    # a paragraph are just PDF layout and become spaces.
    paragraphs = []
    current = []

    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []

    if current:
        paragraphs.append(" ".join(current))

    paragraphs = [
        re.sub(r"[ \t]+", " ", p).strip()
        for p in paragraphs
    ]

    return "\n\n".join(p for p in paragraphs if p)


def word_count(text: str) -> int:
    return len(text.split())
