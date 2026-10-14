
import logging
import re
import threading
from dataclasses import dataclass

from app.config import get_settings
from app.services import gemini, prompt
from app.services.reward_model import reward_model


log = logging.getLogger(__name__)

# The local models need torch and transformers (requirements.txt). The
# Gemini-only server install (requirements-server.txt, the Docker image)
# leaves them out.
try:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
except ImportError:
    torch = None

LOCAL_MODELS_AVAILABLE = torch is not None


@dataclass(frozen=True)
class ModelConfig:
    name: str
    # Tokens per chunk fed to the model (below its context limit).
    max_input_tokens: int
    # Instruction-tuned models like T5 need a task prefix.
    prefix: str = ""


MODELS = {
    "distilbart": ModelConfig(
        name="sshleifer/distilbart-cnn-12-6",
        max_input_tokens=900,
    ),
    "flan-t5": ModelConfig(
        name="google/flan-t5-base",
        max_input_tokens=480,
        prefix="summarize: ",
    ),
}

LOCAL_DEFAULT_MODEL = "distilbart"

# Google Gemini reads the whole document in one go, so the summary follows
# the document's overall argument and how its parts connect. The local
# models above only see one ~900-token chunk at a time, and are much
# slower on a CPU.
GEMINI = "gemini"
# Longer documents (beyond Gemini's ~1M-token context) use the local model.
GEMINI_MAX_DOCUMENT_CHARS = 2_500_000
GEMINI_MAX_SUMMARY_WORDS = 1500
MIN_SUMMARY_WORDS = 40
# Words per paragraph the summary is organized into.
WORDS_PER_PARAGRAPH = 90
# Some variety between candidates gives the reward model a real choice;
# kept moderate because higher temperatures invent more.
CANDIDATE_TEMPERATURE = 0.4


@dataclass(frozen=True)
class Summary:
    text: str
    # Model that wrote it (differs from the one asked for after a fallback).
    model: str
    # Candidates the reward model chose between (RLHF best-of-N).
    candidates: int
    # Share of grounding checks passed (Gemini only; see prompt.py).
    grounding: float | None = None


def default_model() -> str:
    return GEMINI if gemini.available() else LOCAL_DEFAULT_MODEL


# Summary size as a share of the document, so longer documents get
# longer summaries. Keep in sync with LENGTHS in front-end/lib/format.js.
LENGTH_RATIOS = {
    "short": 0.10,
    "medium": 0.20,
    "detailed": 0.30,
}

# Whole-summary bounds in tokens (~0.75 words per token): at least a couple
# of sentences, and at most ~1,100 words so generation time stays bearable.
MIN_SUMMARY_TOKENS = 35
MAX_SUMMARY_TOKENS = 1500

# Bounds for a single model call (one chunk's summary).
MIN_PIECE_TOKENS = 15
MAX_PIECE_TOKENS = 300

# Documents shorter than this are returned as they are.
MIN_DOCUMENT_TOKENS = 60

# Chunks summarized together in one model call. Faster on CPU; more needs
# more memory (~4 chunks of 900 tokens is comfortable).
BATCH_SIZE = 4

# RLHF best-of-N: candidate summaries generated (per chunk for the local
# models, where they are the beams of one beam search), of which the reward
# model keeps the best. 1 turns it off. Each extra beam adds roughly 20-30%
# generation time on a CPU.
NUM_CANDIDATES = get_settings().rlhf_candidates

# Use an NVIDIA GPU when there is one (much faster), otherwise the CPU.
device = (
    torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if LOCAL_MODELS_AVAILABLE
    else None
)

_loaded = {}
_load_lock = threading.Lock()
_generate_locks = {key: threading.Lock() for key in MODELS}


def get_model(model_key: str):
    """Load a model the first time it is requested, then reuse it."""
    if model_key not in MODELS:
        raise ValueError(
            f"Unknown model. Available: {', '.join(MODELS)}"
        )
    if not LOCAL_MODELS_AVAILABLE:
        raise ValueError(
            "Local models aren't installed on this server. Set "
            "GEMINI_API_KEY, or install requirements.txt."
        )

    with _load_lock:
        if model_key not in _loaded:
            config = MODELS[model_key]
            tokenizer = AutoTokenizer.from_pretrained(config.name)
            model = AutoModelForSeq2SeqLM.from_pretrained(config.name)
            model.eval()
            model.to(device)
            _loaded[model_key] = (tokenizer, model)

    return _loaded[model_key]


def is_loaded(model_key: str) -> bool:
    return model_key in _loaded


def generate_lock(model_key: str) -> threading.Lock:
    """Held while a model generates; one generation at a time per model."""
    return _generate_locks[model_key]


def summarize_pieces(
    model_key: str,
    texts: list[str],
    target_tokens: list[int],
) -> list[str]:
    """Summarize each text to roughly its target length, keeping the
    candidate the reward model scores highest.

    Texts with similar targets run through the model together in one
    batch, which is ~1.8x faster on CPU than one at a time with the same
    output.
    """
    tokenizer, _ = get_model(model_key)

    # Never ask for more than about half the input back.
    targets = [
        max(
            MIN_PIECE_TOKENS,
            min(
                target,
                MAX_PIECE_TOKENS,
                len(tokenizer.encode(text, add_special_tokens=False)) // 2,
            ),
        )
        for text, target in zip(texts, target_tokens)
    ]

    # Group by similar target so one length setting suits the whole batch.
    order = sorted(range(len(texts)), key=lambda i: targets[i])
    batches = []
    for i in order:
        batch = batches[-1] if batches else None
        if (
            batch
            and len(batch) < BATCH_SIZE
            and targets[i] <= targets[batch[0]] * 1.3
        ):
            batch.append(i)
        else:
            batches.append([i])

    results = [""] * len(texts)
    for batch in batches:
        candidates = _generate(
            model_key,
            [texts[i] for i in batch],
            low=min(targets[i] for i in batch),
            high=max(targets[i] for i in batch),
        )
        for i, options in zip(batch, candidates):
            results[i], _ = reward_model.best(texts[i], options)

    return results


def _generate(
    model_key: str,
    texts: list[str],
    low: int,
    high: int,
) -> list[list[str]]:
    """NUM_CANDIDATES candidate summaries for each text."""
    config = MODELS[model_key]
    tokenizer, model = get_model(model_key)

    inputs = tokenizer(
        [config.prefix + text for text in texts],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=config.max_input_tokens + 32,
    ).to(device)

    with generate_lock(model_key), torch.inference_mode():
        output = model.generate(
            **inputs,
            # The model tends to stop early, so hold it close to the target.
            max_new_tokens=int(high * 1.2) + 5,
            min_new_tokens=int(low * 0.9),
            num_beams=max(2, NUM_CANDIDATES),
            num_return_sequences=NUM_CANDIDATES,
            no_repeat_ngram_size=3,
            do_sample=False,
        )

    # CNN-trained models emit "word ." - drop the space before punctuation.
    decoded = [
        re.sub(r"\s+([.,;:!?])", r"\1", summary).strip()
        for summary in tokenizer.batch_decode(output, skip_special_tokens=True)
    ]
    # Sequences come back grouped by input text.
    return [
        decoded[i:i + NUM_CANDIDATES]
        for i in range(0, len(decoded), NUM_CANDIDATES)
    ]


def split_text(model_key: str, text: str) -> list[str]:
    """Split text into chunks that fit the model, preferring
    paragraph boundaries over hard token cuts."""
    config = MODELS[model_key]
    tokenizer, _ = get_model(model_key)
    limit = config.max_input_tokens

    def count(s: str) -> int:
        return len(tokenizer.encode(s, add_special_tokens=False))

    chunks = []
    current = []
    current_tokens = 0

    for paragraph in text.split("\n\n"):
        tokens = count(paragraph)

        if tokens > limit:
            # Paragraph alone is too long: flush, then hard-split it.
            if current:
                chunks.append(" ".join(current))
                current, current_tokens = [], 0

            ids = tokenizer.encode(paragraph, add_special_tokens=False)
            for start in range(0, len(ids), limit):
                piece = tokenizer.decode(
                    ids[start:start + limit],
                    skip_special_tokens=True,
                )
                if piece.strip():
                    chunks.append(piece)
            continue

        if current_tokens + tokens > limit:
            chunks.append(" ".join(current))
            current, current_tokens = [], 0

        current.append(paragraph)
        current_tokens += tokens

    if current:
        chunks.append(" ".join(current))

    return [c for c in chunks if c.strip()]


def summarize_document(
    text: str,
    length: str = "medium",
    model_key: str | None = None,
    filename: str = "document",
) -> Summary:
    """Summarize to a length proportional to the document.

    Without a model_key, Gemini is used when GEMINI_API_KEY is set, falling
    back to the local model if Gemini fails or the document is too long.
    """
    if length not in LENGTH_RATIOS:
        raise ValueError("Invalid summary length")

    explicit = model_key is not None
    model_key = model_key or default_model()

    if model_key == GEMINI:
        if len(text) <= GEMINI_MAX_DOCUMENT_CHARS:
            try:
                return _summarize_gemini(text, length, filename)
            except gemini.GeminiError as error:
                # Nothing to fall back to on a Gemini-only server.
                if explicit or not LOCAL_MODELS_AVAILABLE:
                    raise
                log.warning("Gemini failed, summarizing locally: %s", error)
        elif explicit or not LOCAL_MODELS_AVAILABLE:
            raise ValueError("Document is too long for Gemini")
        model_key = LOCAL_DEFAULT_MODEL

    return _summarize_local(text, length, model_key)


def _summarize_gemini(text: str, length: str, filename: str) -> Summary:
    """The whole document in one request (see prompt.py):

    1. Gemini analyses the document, then writes NUM_CANDIDATES summaries
       with evidence quotes for each paragraph.
    2. Each candidate is checked against the document: quotes must occur
       in it, and so must every number.
    3. The best-grounded candidates go to the reward model, which keeps
       the one users are expected to like best (RLHF best-of-N).
    4. If even that one fails the checks, Gemini corrects it once.
    """
    words = len(text.split())
    if words < MIN_SUMMARY_WORDS:
        return Summary(text, GEMINI, 1, 1.0)

    target = round(words * LENGTH_RATIOS[length])
    target = max(MIN_SUMMARY_WORDS, min(target, GEMINI_MAX_SUMMARY_WORDS))
    paragraphs = max(1, min(8, round(target / WORDS_PER_PARAGRAPH)))

    drafts = gemini.generate_json(
        prompt.SUMMARY_SYSTEM,
        [_user(prompt.summary_request(text, filename, target, paragraphs))],
        prompt.SummaryDraft,
        temperature=CANDIDATE_TEMPERATURE if NUM_CANDIDATES > 1 else 0.2,
        candidates=NUM_CANDIDATES,
    )

    index = prompt.DocumentIndex(text)
    scored = []
    for draft in drafts:
        summary = prompt.draft_text(draft)
        if summary:
            report = prompt.check_summary(draft, index)
            scored.append((report, summary, reward_model.score(text, summary)))
    if not scored:
        raise gemini.GeminiError("Gemini returned an empty summary")

    # Grounding first: a summary that passes the checks beats one that
    # doesn't, however well written. Among equals, the reward model decides.
    report, best, _ = max(
        scored, key=lambda s: (s[0].ok, round(s[0].score, 1), s[2])
    )

    if not report.ok:
        log.info("Repairing summary: %s", report.problems())
        try:
            repaired = gemini.generate_json(
                prompt.REPAIR_SYSTEM,
                [_user(prompt.repair_request(text, filename, best, report.problems()))],
                prompt.SummaryDraft,
                temperature=0.1,
            )[0]
            repaired_report = prompt.check_summary(repaired, index)
            repaired_text = prompt.draft_text(repaired)
            if repaired_text and repaired_report.score >= report.score:
                report, best = repaired_report, repaired_text
        except gemini.GeminiError as error:
            # The unrepaired summary is still the best we have.
            log.warning("Summary repair failed: %s", error)

    return Summary(best, GEMINI, len(scored), round(report.score, 3))


def _user(text: str) -> dict:
    return {"role": "user", "parts": [{"text": text}]}


def _summarize_local(text: str, length: str, model_key: str) -> Summary:
    """Each chunk is summarized to its share of the target, and the chunk
    summaries become the paragraphs of the result."""
    tokenizer, _ = get_model(model_key)

    def count(s: str) -> int:
        return len(tokenizer.encode(s, add_special_tokens=False))

    total_tokens = count(text)

    # Too short to be worth summarizing.
    if total_tokens < MIN_DOCUMENT_TOKENS:
        return Summary(text, model_key, 1)

    target_tokens = round(total_tokens * LENGTH_RATIOS[length])
    target_tokens = max(MIN_SUMMARY_TOKENS, min(target_tokens, MAX_SUMMARY_TOKENS))

    chunks = split_text(model_key, text)
    chunk_tokens = [count(chunk) for chunk in chunks]
    chunked_total = sum(chunk_tokens) or 1

    paragraphs = summarize_pieces(
        model_key,
        chunks,
        [round(target_tokens * tokens / chunked_total) for tokens in chunk_tokens],
    )

    return Summary(
        "\n\n".join(p for p in paragraphs if p),
        model_key,
        NUM_CANDIDATES,
    )
