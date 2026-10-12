
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

LENGTH_SETTINGS = {
    "short": 70,
    "medium": 120,
    "detailed": 180,
}

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


def summarize_piece(model_key: str, text: str, max_length: int) -> str:
    config = MODELS[model_key]
    tokenizer, model = get_model(model_key)

    inputs = tokenizer(
        config.prefix + text,
        return_tensors="pt",
        truncation=True,
        max_length=config.max_input_tokens + 32,
    ).to(device)

    # Very short inputs should not be forced into long outputs.
    input_tokens = inputs["input_ids"].shape[1]
    min_length = min(20, max(5, input_tokens // 4))

    with _generate_locks[model_key], torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=max_length,
            min_new_tokens=min_length,
            num_beams=2,
            no_repeat_ngram_size=3,
            do_sample=False,
        )

    return tokenizer.decode(
        output[0],
        skip_special_tokens=True,
    ).strip()


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
    if length not in LENGTH_SETTINGS:
        raise ValueError("Invalid summary length")

    target_length = LENGTH_SETTINGS[length]
    config = MODELS[model_key]
    tokenizer, _ = get_model(model_key)

    summaries = [
        summarize_piece(model_key, chunk, target_length)
        for chunk in split_text(model_key, text)
    ]

    # Reduce: pack chunk summaries into groups that fit the model and
    # summarize each group until a single summary remains.
    while len(summaries) > 1:
        groups = []
        current = []
        current_tokens = 0

        for summary in summaries:
            tokens = len(
                tokenizer.encode(summary, add_special_tokens=False)
            )
            if current and current_tokens + tokens > config.max_input_tokens:
                groups.append(current)
                current, current_tokens = [], 0
            current.append(summary)
            current_tokens += tokens

        if current:
            groups.append(current)

        # Guard against an infinite loop: force pairs if nothing merged.
        if len(groups) >= len(summaries):
            groups = [
                summaries[i:i + 2]
                for i in range(0, len(summaries), 2)
            ]

        summaries = [
            summarize_piece(model_key, " ".join(group), target_length)
            for group in groups
        ]

    return summaries[0] if summaries else ""
