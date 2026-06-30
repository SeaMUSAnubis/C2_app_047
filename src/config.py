"""Compatibility settings for the legacy LLM explanation service."""

from __future__ import annotations

import os


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class LegacySettings:
    llm_provider: str = os.environ.get("LLM_PROVIDER", "openai_compatible")
    llm_base_url: str = os.environ.get(
        "LLM_BASE_URL",
        os.environ.get("LLM_OPENAI_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"),
    )
    llm_api_key: str = os.environ.get(
        "LLM_API_KEY",
        os.environ.get("OPENROUTER_API_KEY", os.environ.get("LLM_OPENAI_API_KEY", "")),
    )
    llm_model: str = os.environ.get(
        "LLM_MODEL",
        os.environ.get("OPENROUTER_MODEL", os.environ.get("LLM_CHAT_MODEL", "openrouter/free")),
    )
    llm_timeout_seconds: float = _float_env("LLM_TIMEOUT_SECONDS", 20.0)
    llm_max_retries: int = _int_env("LLM_MAX_RETRIES", 2)
    llm_temperature: float = _float_env("LLM_TEMPERATURE", 0.1)
    llm_enabled: bool = _bool_env("LLM_ENABLED", True)
    llm_prompt_version: str = os.environ.get("LLM_PROMPT_VERSION", "ueba-explanation-v1")


settings = LegacySettings()

