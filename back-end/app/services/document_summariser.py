
import re
import threading
from dataclasses import dataclass

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


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

DEFAULT_MODEL = "distilbart"

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

# CPU inference
device = torch.device("cpu")

_loaded = {}
_load_lock = threading.Lock()
_generate_locks = {key: threading.Lock() for key in MODELS}


def get_model(model_key: str):
    """Load a model the first time it is requested, then reuse it."""
    if model_key not in MODELS:
        raise ValueError(
            f"Unknown model. Available: {', '.join(MODELS)}"
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


def summarize_piece(model_key: str, text: str, target_tokens: int) -> str:
    """Summarize one chunk to roughly target_tokens tokens."""
    config = MODELS[model_key]
    tokenizer, model = get_model(model_key)

    inputs = tokenizer(
        config.prefix + text,
        return_tensors="pt",
        truncation=True,
        max_length=config.max_input_tokens + 32,
    ).to(device)

    # Never ask for more than about half the input back.
    input_tokens = inputs["input_ids"].shape[1]
    target = max(
        MIN_PIECE_TOKENS,
        min(target_tokens, MAX_PIECE_TOKENS, input_tokens // 2),
    )

    with _generate_locks[model_key], torch.inference_mode():
        output = model.generate(
            **inputs,
            # Allow some room either side of the target.
            max_new_tokens=int(target * 1.25) + 5,
            min_new_tokens=int(target * 0.75),
            num_beams=2,
            no_repeat_ngram_size=3,
            do_sample=False,
        )

    summary = tokenizer.decode(
        output[0],
        skip_special_tokens=True,
    )

    # CNN-trained models emit "word ." - drop the space before punctuation.
    return re.sub(r"\s+([.,;:!?])", r"\1", summary).strip()


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
    model_key: str = DEFAULT_MODEL,
) -> str:
    """Summarize to a length proportional to the document: each chunk is
    summarized to its share of the target, and the chunk summaries become
    the paragraphs of the result."""
    if length not in LENGTH_RATIOS:
        raise ValueError("Invalid summary length")

    tokenizer, _ = get_model(model_key)

    def count(s: str) -> int:
        return len(tokenizer.encode(s, add_special_tokens=False))

    total_tokens = count(text)

    # Too short to be worth summarizing.
    if total_tokens < MIN_DOCUMENT_TOKENS:
        return text

    target_tokens = round(total_tokens * LENGTH_RATIOS[length])
    target_tokens = max(MIN_SUMMARY_TOKENS, min(target_tokens, MAX_SUMMARY_TOKENS))

    chunks = split_text(model_key, text)
    chunk_tokens = [count(chunk) for chunk in chunks]
    chunked_total = sum(chunk_tokens) or 1

    paragraphs = [
        summarize_piece(
            model_key,
            chunk,
            round(target_tokens * tokens / chunked_total),
        )
        for chunk, tokens in zip(chunks, chunk_tokens)
    ]

    return "\n\n".join(p for p in paragraphs if p)
