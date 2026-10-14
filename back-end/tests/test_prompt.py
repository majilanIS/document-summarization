
from app.services import prompt
from app.services.prompt import DocumentIndex, SummaryDraft

from conftest import DOCUMENT


def draft(*paragraphs):
    """paragraphs: (text, [evidence quotes])"""
    return SummaryDraft.model_validate({
        "analysis": {
            "document_type": "report",
            "purpose": "p",
            "audience": "a",
            "main_point": "m",
            "sections": [],
            "key_facts": [],
        },
        "paragraphs": [{"text": t, "evidence": e} for t, e in paragraphs],
    })


def test_quote_found_ignoring_case_and_punctuation():
    index = DocumentIndex(DOCUMENT)
    assert index.contains_quote("costs have dropped by about 90% over the last decade")
    assert index.contains_quote('"China leads global manufacturing of panels."')


def test_quote_across_paragraph_break_still_found():
    index = DocumentIndex(DOCUMENT)
    assert index.contains_quote(
        "in many countries. However, solar output depends on weather"
    )


def test_invented_quote_rejected():
    index = DocumentIndex(DOCUMENT)
    assert not index.contains_quote("Wind power is the cheapest source of energy")
    assert not index.contains_quote("")


def test_numbers_not_in_document_are_flagged():
    index = DocumentIndex(DOCUMENT)
    assert index.unsupported_numbers("Costs fell 90% and solar will hit 33% by 2050.") == ["33"]
    # Thousands separators and single digits are not false alarms.
    assert DocumentIndex("Revenue was 1200 dollars.").unsupported_numbers(
        "Revenue was 1,200 dollars over 3 years."
    ) == []


def test_check_summary_passes_grounded_draft():
    report = prompt.check_summary(
        draft(("Solar costs fell about 90%.", ["Costs have dropped by about 90%"])),
        DocumentIndex(DOCUMENT),
    )
    assert report.ok
    assert report.score == 1.0


def test_check_summary_flags_hallucinations():
    report = prompt.check_summary(
        draft(
            ("Solar costs fell 75%.", ["Costs dropped by 75 percent last year"]),
            ("China leads manufacturing.", ["China leads global manufacturing of panels"]),
        ),
        DocumentIndex(DOCUMENT),
    )
    assert not report.ok
    assert report.unsupported_numbers == ["75"]
    assert report.unsupported_paragraphs == [0]
    assert 0 < report.score < 1
    assert any("75" in p for p in report.problems())


def test_plain_text_strips_markdown_and_meta():
    assert prompt.plain_text("Here is a summary of the report:\n- **Solar** is growing") == (
        "Solar is growing"
    )
    assert prompt.plain_text("## Costs\n1. Costs fell.") == "Costs Costs fell."


def test_draft_text_separates_paragraphs_with_blank_line():
    text = prompt.draft_text(draft(("One.", []), ("Two.", [])))
    assert text == "One.\n\nTwo."


def test_document_comes_before_instructions():
    request = prompt.summary_request(DOCUMENT, "solar.txt", 100, 2)
    assert request.index("<document") < request.index("summarize it in about 100 words")
