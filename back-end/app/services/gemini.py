
"""Google Gemini through the official google-genai SDK.

Calls are retried with exponential backoff when Gemini is rate limited or
overloaded, and `generate_json` makes Gemini answer in a given Pydantic
schema, so the code gets fields (answer, evidence quotes, ...) instead of
free text it would have to parse.
"""

import logging
import threading
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings


log = logging.getLogger(__name__)

Schema = TypeVar("Schema", bound=BaseModel)

# A temporary problem on Google's side: worth retrying the same model.
RETRY_CODES = {500, 502, 503, 504}
# Rate limited (quota used up for the minute or day): retrying the same
# model soon won't help, so go straight to the next one.
RATE_LIMITED = 429


class GeminiError(RuntimeError):
    """Gemini could not be reached or gave no usable answer."""


def available() -> bool:
    return bool(get_settings().gemini_api_key)


def model_name() -> str:
    return get_settings().gemini_model


_client = None
_client_lock = threading.Lock()
# Cleared the first time Gemini refuses candidate_count > 1.
_multiple_candidates = True


def _get_client() -> genai.Client:
    global _client
    settings = get_settings()
    if not settings.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY is not set")

    with _client_lock:
        if _client is None:
            _client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=types.HttpOptions(
                    timeout=settings.gemini_timeout_seconds * 1000
                ),
            )
    return _client


def _is_retryable(error: BaseException) -> bool:
    return isinstance(error, errors.APIError) and error.code in RETRY_CODES


def _call(system: str, contents: list[dict], config: dict):
    """Send the request, retrying briefly when Gemini is busy, then moving
    on to the fallback models."""
    settings = get_settings()

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(settings.gemini_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=lambda state: log.warning(
            "Gemini busy, retrying (attempt %d): %s",
            state.attempt_number,
            _short(state.outcome.exception()),
        ),
        reraise=True,
    )
    def send(model: str, thinking: bool):
        extra = {}
        if thinking and settings.gemini_thinking_level:
            extra["thinking_config"] = types.ThinkingConfig(
                thinking_level=types.ThinkingLevel(
                    settings.gemini_thinking_level.upper()
                )
            )
        return _get_client().models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system, **config, **extra
            ),
        )

    models = [settings.gemini_model, *settings.gemini_fallback_models]
    for i, model in enumerate(models):
        try:
            try:
                return send(model, thinking=True)
            except errors.ClientError as error:
                # Models without a thinking level setting: send without it.
                if error.code == 400 and "thinking" in str(error.message).lower():
                    return send(model, thinking=False)
                raise
        except errors.APIError as error:
            # A fallback that isn't offered to this key (404) is skipped too.
            busy = _is_retryable(error) or error.code == RATE_LIMITED
            missing = error.code == 404 and i > 0
            if (busy or missing) and i + 1 < len(models):
                log.warning(
                    "%s unavailable (%s), trying %s",
                    model, _short(error), models[i + 1],
                )
                continue
            raise GeminiError(
                f"Gemini returned an error ({error.code}): {_short(error)}"
            )
        except Exception as error:  # network problems, timeouts
            raise GeminiError(f"Can't reach Gemini: {error}")


def _short(error: BaseException) -> str:
    """First line of an API error's message, without the JSON details."""
    message = getattr(error, "message", None) or str(error)
    return str(message).strip().splitlines()[0][:300]


def _texts(response) -> list[str]:
    texts = []
    for candidate in response.candidates or []:
        parts = candidate.content.parts if candidate.content else None
        text = "".join(p.text or "" for p in parts or []).strip()
        if text:
            texts.append(text)

    if not texts:
        feedback = response.prompt_feedback
        reason = feedback.block_reason if feedback else None
        raise GeminiError(f"Gemini gave no answer{f' ({reason})' if reason else ''}")
    return texts


def generate(
    system: str,
    contents: list[dict],
    temperature: float = 0.2,
) -> str:
    """Free-text answer.

    contents: [{"role": "user" | "model", "parts": [{"text": ...}]}, ...]
    """
    return _texts(_call(system, contents, {"temperature": temperature}))[0]


def generate_json(
    system: str,
    contents: list[dict],
    schema: type[Schema],
    temperature: float = 0.2,
    candidates: int = 1,
) -> list[Schema]:
    """Answers that follow `schema`, one per candidate (at least one)."""
    global _multiple_candidates
    config = {
        "temperature": temperature,
        "response_mime_type": "application/json",
        "response_schema": schema,
    }
    if not _multiple_candidates:
        candidates = 1

    try:
        response = _call(system, contents, {**config, "candidate_count": candidates})
    except GeminiError as error:
        # Some models (and free-tier keys) only return one candidate. Ask
        # again for one, and don't spend a request on asking for more again.
        if candidates == 1 or "candidate" not in str(error).lower():
            raise
        log.info("Multiple candidates not available; using one per request")
        _multiple_candidates = False
        response = _call(system, contents, {**config, "candidate_count": 1})

    results = []
    for text in _texts(response):
        try:
            results.append(schema.model_validate_json(text))
        except ValidationError as error:
            log.warning("Gemini answer didn't match %s: %s", schema.__name__, error)

    if not results:
        raise GeminiError("Gemini's answer was not in the expected format")
    return results
