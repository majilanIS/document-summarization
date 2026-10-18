
"""Chat about a document after it has been summarized.

Each question is answered from the document itself:

1. Retrieval: the document is split into passages, ranked against the
   question with TF-IDF over words and word pairs (scikit-learn).
2. Answering, with one of two engines:
   - `gemini`: Google Gemini, given the whole document (or the best
     passages when it is too long) plus the conversation so far, under the
     grounding rules in prompt.py. It answers in a schema: supporting
     quotes, whether the document covers the question, then the answer.
   - `local`: google/flan-t5-base on this machine, given the best
     passages. Works offline, but answers are short and it does not see
     earlier turns.
3. Verification: Gemini's quotes are checked against the document, and
   only verified ones are shown as sources. An answer with figures that
   aren't in the document and no verified quote gets a warning.

CHAT_ENGINE picks the engine: `auto` (default: Gemini when a key is set, the
local model otherwise or when Gemini can't be reached), `gemini` or `local`.
"""

import json
import logging
import re
import threading
import uuid
from datetime import datetime, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from app.config import get_settings
from app.db import get_connection
from app.services import document_summariser as summariser
from app.services import gemini, prompt


log = logging.getLogger(__name__)

# Documents up to this size go to Gemini whole; longer ones as passages.
GEMINI_MAX_DOCUMENT_CHARS = 400_000
# Earlier messages sent along for follow-up questions.
HISTORY_MESSAGES = 10

LOCAL_MODEL = "flan-t5"
LOCAL_MAX_ANSWER_TOKENS = 160

PASSAGE_WORDS = 120
# Passages shown with an answer, and given to the model.
SOURCES_SHOWN = 3
PASSAGES_FOR_MODEL = 8

NOT_FOUND = "I couldn't find that in the document."
UNVERIFIED_NOTE = (
    "\n\n(Note: I couldn't match this answer to the document's exact "
    "wording, so please check it against the document.)"
)


class ChatError(RuntimeError):
    """The answer could not be generated (shown to the user)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------- retrieval

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def split_passages(text: str) -> list[str]:
    """~PASSAGE_WORDS-word passages that end on sentence boundaries."""
    passages = []
    current = []
    count = 0

    for paragraph in text.split("\n\n"):
        for sentence in SENTENCE_END.split(paragraph.strip()):
            words = len(sentence.split())
            if not words:
                continue
            if current and count + words > PASSAGE_WORDS:
                passages.append(" ".join(current))
                current, count = [], 0
            current.append(sentence)
            count += words
        # Don't carry a short tail into the next paragraph's topic.
        if count >= PASSAGE_WORDS // 2:
            passages.append(" ".join(current))
            current, count = [], 0

    if current:
        passages.append(" ".join(current))

    return passages


class PassageIndex:
    """TF-IDF over words and word pairs, so "interest rate" matches as a
    phrase and rare, specific terms count for more than common ones."""

    def __init__(self, passages: list[str]):
        self.passages = passages
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
        )
        try:
            self.matrix = self.vectorizer.fit_transform(passages)
        except ValueError:
            # Only stop words (or nothing) in the document.
            self.matrix = None

    def search(self, query: str, k: int) -> list[tuple[float, int]]:
        if self.matrix is None:
            return []
        scores = linear_kernel(self.vectorizer.transform([query]), self.matrix)[0]
        best = scores.argsort()[::-1][:k]
        return [(float(scores[i]), int(i)) for i in best if scores[i] > 0]


_index_cache = {}
_index_lock = threading.Lock()


def _indexes(document: dict) -> tuple[PassageIndex, prompt.DocumentIndex]:
    """(retrieval index, quote verification index) for the document.
    Documents never change after upload, so both can be kept."""
    with _index_lock:
        if document["id"] not in _index_cache:
            if len(_index_cache) >= 16:
                _index_cache.pop(next(iter(_index_cache)))
            text = document["clean_text"]
            _index_cache[document["id"]] = (
                PassageIndex(split_passages(text)),
                prompt.DocumentIndex(text),
            )
        return _index_cache[document["id"]]


def retrieve(document: dict, summary: str | None, query: str, k: int) -> list[dict]:
    """Best passages for the query: from the document, falling back to the
    summary for broad questions ("what is this about?") that match no
    passage in particular."""
    index, _ = _indexes(document)
    hits = [
        {"kind": "document", "text": index.passages[i]}
        for _, i in index.search(query, k)
    ]

    if summary and len(hits) < k:
        hits.append({"kind": "summary", "text": summary})

    return hits[:k]


# ------------------------------------------------------------------ engines

def _engine() -> str:
    engine = get_settings().chat_engine
    if engine == "auto":
        return "gemini" if gemini.available() else "local"
    return engine


def _ask_gemini(
    document: dict,
    question: str,
    history: list[dict],
    passages: list[dict],
) -> tuple[str, list[dict], dict]:
    """(answer text, sources, details).

    sources are the answer's quotes that were verified against the
    document, or the retrieved passages if none were. details is the
    structured answer the front-end shows: the direct answer, key points
    that each cite a source by number, and what the document doesn't cover.
    """
    text = document["clean_text"]
    if len(text) > GEMINI_MAX_DOCUMENT_CHARS:
        text = (
            "[The document is too long to include whole. These are the "
            "passages most relevant to the question; answer from them.]\n\n"
            + "\n\n---\n\n".join(p["text"] for p in passages)
        )

    contents = [
        {
            "role": "user" if m["role"] == "user" else "model",
            "parts": [{"text": m["content"]}],
        }
        for m in history[-HISTORY_MESSAGES:]
    ]
    contents.append({"role": "user", "parts": [{"text": question}]})

    try:
        reply = gemini.generate_json(
            prompt.chat_system(text, document["filename"]),
            contents,
            prompt.ChatAnswer,
            temperature=0.1,
        )[0]
    except gemini.GeminiError as error:
        raise ChatError(str(error))

    reply.direct_answer = prompt.plain_text(reply.direct_answer) or NOT_FOUND
    if not reply.found_in_document:
        reply.points = []

    _, index = _indexes(document)

    # Keep the verified quotes, numbered 1.. in their original order, and
    # point each point at its quote's new number (or at none).
    renumbered = {}
    sources = []
    if reply.found_in_document:
        for number, quote in enumerate(reply.quotes, start=1):
            if index.contains_quote(quote):
                sources.append({"kind": "quote", "text": quote.strip()})
                renumbered[number] = len(sources)

    answer = prompt.answer_text(reply)
    # Figures the document doesn't contain, with nothing to back them up.
    warning = bool(
        reply.found_in_document
        and not sources
        and index.unsupported_numbers(answer)
    )
    if warning:
        answer += UNVERIFIED_NOTE

    details = {
        "direct_answer": reply.direct_answer,
        "points": [
            {"text": p.text.strip(), "source": renumbered.get(p.quote)}
            for p in reply.points
            if p.text.strip()
        ],
        "not_covered": (reply.not_covered or "").strip() or None,
        "unverified": warning,
    }

    if reply.found_in_document and not sources:
        sources = _shown(passages)
    return answer, sources, details


def _ask_local(question: str, passages: list[dict]) -> str:
    try:
        tokenizer, model = summariser.get_model(LOCAL_MODEL)
    except ValueError as error:
        raise ChatError(str(error))
    limit = summariser.MODELS[LOCAL_MODEL].max_input_tokens

    head = (
        "Answer the question using only the passages. If the passages do "
        f'not contain the answer, reply "{NOT_FOUND}"\n\nPassages:\n'
    )
    tail = f"\n\nQuestion: {question}\nAnswer:"
    budget = limit - len(tokenizer.encode(head + tail))

    # As many of the best passages as fit; the last one may be cut.
    context = []
    for passage in passages:
        if budget <= 20:
            break
        ids = tokenizer.encode(passage["text"], add_special_tokens=False)
        context.append(tokenizer.decode(ids[:budget], skip_special_tokens=True))
        budget -= len(ids) + 2

    inputs = tokenizer(
        head + "\n\n".join(context) + tail,
        return_tensors="pt",
        truncation=True,
        max_length=limit + 32,
    ).to(summariser.device)

    with summariser.generate_lock(LOCAL_MODEL), summariser.torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=LOCAL_MAX_ANSWER_TOKENS,
            num_beams=4,
            no_repeat_ngram_size=3,
        )

    answer = tokenizer.decode(output[0], skip_special_tokens=True).strip()
    return answer or NOT_FOUND


def _shown(passages: list[dict]) -> list[dict]:
    return [{"kind": p["kind"], "text": p["text"]} for p in passages[:SOURCES_SHOWN]]


# -------------------------------------------------------------- persistence

def _row_to_message(row) -> dict:
    message = dict(row)
    message["sources"] = json.loads(message["sources"] or "[]")
    message["details"] = json.loads(message["details"]) if message["details"] else None
    return message


def list_messages(document_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM chat_messages
            WHERE document_id = ?
            ORDER BY created_at, role DESC
            """,
            (document_id,),
        ).fetchall()

    return [_row_to_message(r) for r in rows]


def clear_messages(document_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM chat_messages WHERE document_id = ?",
            (document_id,),
        )


def rate_message(message_id: str, rating: int | None) -> dict | None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE chat_messages SET rating = ?
            WHERE id = ? AND role = 'assistant'
            """,
            (rating, message_id),
        )
        row = conn.execute(
            "SELECT * FROM chat_messages WHERE id = ? AND role = 'assistant'",
            (message_id,),
        ).fetchone()

    return _row_to_message(row) if row else None


def ask(document: dict, summary: str | None, question: str) -> tuple[dict, dict]:
    """Answer a question and save both messages. Returns (question, answer)."""
    history = list_messages(document["id"])

    # Follow-ups like "why?" say little by themselves; search with the
    # previous question too.
    query = question
    if len(question.split()) < 4:
        previous = [m["content"] for m in history if m["role"] == "user"]
        if previous:
            query = f"{previous[-1]} {question}"

    passages = retrieve(document, summary, query, PASSAGES_FOR_MODEL)

    engine = _engine()
    details = None
    if engine == "gemini":
        try:
            answer, sources, details = _ask_gemini(
                document, question, history, passages
            )
        except ChatError as error:
            # Only fall back when the engine wasn't chosen explicitly and
            # the local model is installed.
            if (
                get_settings().chat_engine != "auto"
                or not summariser.LOCAL_MODELS_AVAILABLE
            ):
                raise
            log.warning("Gemini failed, answering locally: %s", error)
            engine = "local"
    if engine == "local":
        answer, sources = _ask_local(question, passages), _shown(passages)

    created = _now()
    user_message = {
        "id": str(uuid.uuid4()),
        "document_id": document["id"],
        "role": "user",
        "content": question,
        "sources": [],
        "details": None,
        "engine": None,
        "rating": None,
        "created_at": created,
    }
    assistant_message = {
        "id": str(uuid.uuid4()),
        "document_id": document["id"],
        "role": "assistant",
        "content": answer,
        "sources": sources,
        "details": details,
        "engine": engine,
        "rating": None,
        # Same timestamp; ordering by role puts the question first.
        "created_at": created,
    }

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO chat_messages
                (id, document_id, role, content, sources, details, engine,
                 rating, created_at)
            VALUES
                (:id, :document_id, :role, :content, :sources, :details,
                 :engine, :rating, :created_at)
            """,
            [
                {
                    **m,
                    "sources": json.dumps(m["sources"]),
                    "details": json.dumps(m["details"]) if m["details"] else None,
                }
                for m in (user_message, assistant_message)
            ],
        )

    return user_message, assistant_message
