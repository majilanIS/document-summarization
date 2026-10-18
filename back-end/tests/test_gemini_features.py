
"""Summaries and chat through Gemini, with Gemini mocked."""

from types import SimpleNamespace

import pytest
from google.genai import errors

from app.services import chat, gemini, prompt
from app.services import document_summariser as summariser

from conftest import DOCUMENT
from test_prompt import draft


GROUNDED = draft(
    (
        "This report describes the growth of solar power, whose costs have "
        "dropped by about 90% over the last decade.",
        ["Costs have dropped by about 90% over the last decade"],
    ),
    (
        "Storage is the main challenge, and experts expect solar to supply a "
        "third of global electricity by 2050.",
        ["Experts expect solar to supply a third of global electricity by 2050"],
    ),
)
HALLUCINATED = draft(
    (
        "Solar costs fell 75% and it will supply 60% of power by 2040.",
        ["Solar will supply 60 percent of power by 2040"],
    ),
)


@pytest.fixture
def calls(monkeypatch):
    """Replace generate_json; set `calls.replies` to what each call returns."""
    state = SimpleNamespace(replies=[], requests=[])

    def fake(system, contents, schema, temperature=0.2, candidates=1):
        state.requests.append(SimpleNamespace(
            system=system, contents=contents, schema=schema,
            temperature=temperature, candidates=candidates,
        ))
        return state.replies.pop(0)

    monkeypatch.setattr(gemini, "generate_json", fake)
    return state


def test_grounded_candidate_beats_hallucinated_one(calls):
    calls.replies = [[HALLUCINATED, GROUNDED]]
    result = summariser.summarize_document(DOCUMENT, "detailed", filename="solar.txt")

    assert result.model == "gemini"
    assert result.candidates == 2
    assert result.grounding == 1.0
    assert "90%" in result.text and "75%" not in result.text
    # One request, asking for several candidates, document before instructions.
    assert len(calls.requests) == 1
    assert calls.requests[0].candidates == 2
    assert calls.requests[0].system == prompt.SUMMARY_SYSTEM


def test_failing_summary_is_repaired_once(calls):
    calls.replies = [[HALLUCINATED], [GROUNDED]]
    result = summariser.summarize_document(DOCUMENT, "medium")

    assert len(calls.requests) == 2
    repair = calls.requests[1]
    assert repair.system == prompt.REPAIR_SYSTEM
    request_text = repair.contents[0]["parts"][0]["text"]
    assert '"75"' in request_text and "<draft_summary>" in request_text
    assert result.grounding == 1.0
    assert "75%" not in result.text


def test_falls_back_to_local_model_when_gemini_fails(calls, monkeypatch):
    def fail(*args, **kwargs):
        raise gemini.GeminiError("quota")

    monkeypatch.setattr(gemini, "generate_json", fail)
    # CI installs only requirements-server.txt, so torch is absent there.
    monkeypatch.setattr(summariser, "LOCAL_MODELS_AVAILABLE", True)
    monkeypatch.setattr(
        summariser,
        "_summarize_local",
        lambda text, length, model_key: summariser.Summary("local", model_key, 1),
    )
    assert summariser.summarize_document(DOCUMENT).model == "distilbart"


def test_explicit_gemini_failure_is_reported(monkeypatch):
    def fail(*args, **kwargs):
        raise gemini.GeminiError("quota")

    monkeypatch.setattr(gemini, "generate_json", fail)
    with pytest.raises(gemini.GeminiError):
        summariser.summarize_document(DOCUMENT, model_key="gemini")


def test_summary_api_stores_grounding_and_reward(client, document, calls):
    calls.replies = [[GROUNDED]]
    response = client.post(
        "/api/summaries/generate",
        json={"document_id": document["id"], "length": "short"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["model"] == "gemini"
    assert body["grounding"] == 1.0
    assert body["reward"] is not None


def test_retrieval_finds_relevant_passage():
    index = chat.PassageIndex(chat.split_passages(DOCUMENT))
    (_, best), *_ = index.search("who manufactures the panels", 3)
    assert "China" in index.passages[best]


def test_chat_shows_only_verified_quotes(client, document, calls):
    calls.replies = [[prompt.ChatAnswer(
        quotes=[
            "China leads global manufacturing of panels",
            "China makes 95% of all panels",  # not in the document
        ],
        found_in_document=True,
        direct_answer="China leads global manufacturing of panels.", points=[],
    )]]
    response = client.post(f"/api/chat/{document['id']}", json={"message": "Who makes panels?"})
    assert response.status_code == 201
    answer = response.json()["answer"]
    assert answer["engine"] == "gemini"
    assert [s["text"] for s in answer["sources"]] == [
        "China leads global manufacturing of panels"
    ]

    # Grounding rules and the document are in the system prompt.
    system = calls.requests[0].system
    assert "Use ONLY the document" in system and "photovoltaic" in system


def test_chat_points_cite_renumbered_verified_sources(client, document, calls):
    calls.replies = [[prompt.ChatAnswer(
        quotes=[
            "Solar is the only renewable that matters",  # 1: invented
            "Batteries and grid upgrades are needed to store energy for the night",
            "Governments offer subsidies to speed adoption",
        ],
        found_in_document=True,
        direct_answer="Storage and policy support are the main levers.",
        points=[
            prompt.AnswerPoint(text="**Storage:** batteries cover the night.", quote=2),
            prompt.AnswerPoint(text="**Subsidies:** speed up adoption.", quote=3),
            prompt.AnswerPoint(text="**Dominance:** solar matters most.", quote=1),
        ],
        not_covered="The document gives no costs for storage.",
    )]]
    answer = client.post(
        f"/api/chat/{document['id']}", json={"message": "What helps solar grow?"}
    ).json()["answer"]

    assert len(answer["sources"]) == 2
    details = answer["details"]
    assert details["direct_answer"] == "Storage and policy support are the main levers."
    # Quote 1 was dropped, so 2 and 3 become sources 1 and 2.
    assert [p["source"] for p in details["points"]] == [1, 2, None]
    assert details["not_covered"] == "The document gives no costs for storage."
    assert details["unverified"] is False
    # Plain-text form for history and the local fallback view.
    assert answer["content"].splitlines()[1] == "- **Storage:** batteries cover the night."


def test_chat_warns_about_unverifiable_figures(client, document, calls):
    calls.replies = [[prompt.ChatAnswer(
        quotes=["Solar provides 45% of power today"],
        found_in_document=True,
        direct_answer="Solar provides 45% of power today.", points=[],
    )]]
    answer = client.post(
        f"/api/chat/{document['id']}", json={"message": "How much power is solar?"}
    ).json()["answer"]
    assert answer["content"].endswith(chat.UNVERIFIED_NOTE)


def test_chat_not_found_has_no_sources(client, document, calls):
    calls.replies = [[prompt.ChatAnswer(
        quotes=[], found_in_document=False,
        direct_answer="The document doesn't say what panels cost per watt.", points=[],
    )]]
    answer = client.post(
        f"/api/chat/{document['id']}", json={"message": "Price per watt?"}
    ).json()["answer"]
    assert answer["sources"] == []


def test_chat_history_rating_and_clear(client, document, calls):
    calls.replies = [
        [prompt.ChatAnswer(quotes=[], found_in_document=False, direct_answer="First.", points=[])],
        [prompt.ChatAnswer(quotes=[], found_in_document=False, direct_answer="Second.", points=[])],
    ]
    url = f"/api/chat/{document['id']}"
    client.post(url, json={"message": "one"})
    client.post(url, json={"message": "and then?"})

    # The follow-up is sent with the earlier turn.
    roles = [c["role"] for c in calls.requests[1].contents]
    assert roles == ["user", "model", "user"]

    messages = client.get(url).json()
    assert [m["role"] for m in messages] == ["user", "assistant"] * 2

    rated = client.put(
        f"/api/chat/messages/{messages[1]['id']}/rating", json={"rating": 1}
    ).json()
    assert rated["rating"] == 1
    assert client.get("/api/feedback/stats").json()["chat_helpful"] >= 1

    assert client.delete(url).status_code == 204
    assert client.get(url).json() == []


def test_rate_limited_model_falls_back_to_next(monkeypatch):
    tried = []

    class Models:
        def generate_content(self, model, contents, config):
            tried.append(model)
            if model == "primary":
                raise errors.ClientError(429, {"error": {"message": "quota"}})
            part = SimpleNamespace(text='{"ok": true}')
            return SimpleNamespace(
                candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))],
                prompt_feedback=None,
            )

    settings = gemini.get_settings()
    monkeypatch.setattr(settings, "gemini_model", "primary")
    monkeypatch.setattr(settings, "gemini_fallback_models", ["backup"])
    monkeypatch.setattr(gemini, "_get_client", lambda: SimpleNamespace(models=Models()))

    assert gemini.generate("system", []) == '{"ok": true}'
    # No waiting on the rate-limited model: straight to the next one.
    assert tried == ["primary", "backup"]
