"""Claude LLM factory.

The reasoning nodes call Claude through ``langchain-anthropic``. We default to
``claude-opus-4-8`` and deliberately do **not** pass ``temperature`` or a
``thinking`` budget: on Opus 4.8 those are rejected by the API, and adaptive
thinking is the model's default behaviour.

Import of ``langchain_anthropic`` is done lazily so the rest of the package
(data providers, registry, CLI ``list``) works even if the optional LLM stack
or an API key is missing.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .config import get_settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from langchain_anthropic import ChatAnthropic


def llm_available() -> bool:
    """True when a real Claude call can be made (API key present)."""
    return get_settings().llm_enabled


def get_llm(**overrides: Any) -> "ChatAnthropic":
    """Build a configured ``ChatAnthropic`` client.

    Raises:
        RuntimeError: if no ``ANTHROPIC_API_KEY`` is configured. Callers that
            want to degrade gracefully should check :func:`llm_available` first.
    """
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Run the workflow with --offline for a "
            "deterministic, no-key analysis, or set the key to use Claude."
        )

    from langchain_anthropic import ChatAnthropic  # lazy import

    kwargs: dict[str, Any] = {
        "model": settings.model,
        "max_tokens": settings.max_tokens,
        "api_key": settings.anthropic_api_key,
    }
    kwargs.update(overrides)
    return ChatAnthropic(**kwargs)
