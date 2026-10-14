
from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode
from typing_extensions import Annotated


class Settings(BaseSettings):
    """Read from environment variables (and back-end/.env, which app/__init__
    loads), matched case-insensitively: GEMINI_API_KEY -> gemini_api_key."""

    gemini_api_key: Optional[str] = None
    # Alias that always points at the current Flash model.
    gemini_model: str = "gemini-flash-latest"
    # Tried in order when the model above is rate limited or overloaded.
    # Quotas are per model, so on the free tier (5 requests a minute per
    # model) switching is much faster than waiting. Comma-separated in env.
    gemini_fallback_models: Annotated[list[str], NoDecode] = [
        "gemini-flash-lite-latest",
        "gemini-3.5-flash",
    ]
    # How much the model reasons before answering. "low" keeps answers fast;
    # the summary prompt already makes it analyse the document explicitly.
    # Empty to use the model's default.
    gemini_thinking_level: Optional[Literal["minimal", "low", "medium", "high"]] = "low"
    gemini_timeout_seconds: int = 180
    # Attempts per model before moving on to the next one.
    gemini_attempts: int = 2

    # auto: Gemini when a key is set, local flan-t5 otherwise (or when
    # Gemini can't be reached).
    chat_engine: Literal["auto", "gemini", "local"] = "auto"

    # RLHF best-of-N: candidate summaries the reward model chooses from.
    rlhf_candidates: int = Field(default=3, ge=1, le=8)

    @field_validator("gemini_fallback_models", mode="before")
    @classmethod
    def split_models(cls, value):
        if isinstance(value, str):
            return [m.strip() for m in value.split(",") if m.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
