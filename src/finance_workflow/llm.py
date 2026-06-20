"""Provider-agnostic chat-model factory.

The reasoning nodes call an LLM through LangChain's
:func:`~langchain.chat_models.init_chat_model`, so the framework is **not tied to
any single provider**. The model is chosen with ``FINWF_MODEL`` and the provider
is either inferred from the name or set with ``FINWF_MODEL_PROVIDER``:

    FINWF_MODEL=claude-opus-4-8                  # Anthropic (default)
    FINWF_MODEL=gpt-4o                           # OpenAI
    FINWF_MODEL=gemini-1.5-pro                    # Google
    FINWF_MODEL=groq:llama-3.3-70b-versatile     # explicit provider:model

We deliberately do **not** pass ``temperature`` or a ``thinking`` budget: some
models (e.g. Anthropic Opus 4.8) reject them, and leaving them unset keeps the
factory portable across providers. Pass overrides explicitly if a model needs them.

``langchain`` and the provider integration package are imported lazily, so the
rest of the package (data providers, registry, ``finwf list``) works even if the
LLM stack or an API key is missing.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from .config import get_settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from langchain_core.language_models.chat_models import BaseChatModel

# Provider -> the env var holding its API key. Providers that need no key
# (e.g. a local Ollama server) map to ``None``. Anything not listed falls back
# to the conventional ``<PROVIDER>_API_KEY``.
_PROVIDER_API_KEYS: dict[str, str | None] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "azure_openai": "AZURE_OPENAI_API_KEY",
    "google_genai": "GOOGLE_API_KEY",
    "google_vertexai": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
    "mistralai": "MISTRAL_API_KEY",
    "cohere": "COHERE_API_KEY",
    "fireworks": "FIREWORKS_API_KEY",
    "together": "TOGETHER_API_KEY",
    "xai": "XAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "ollama": None,  # local, keyless
}


def _infer_provider(model: str) -> str | None:
    """Best-effort provider inference from a model-name prefix.

    Covers the common cases LangChain's ``init_chat_model`` also understands. For
    anything ambiguous (e.g. a hosted llama), set ``FINWF_MODEL_PROVIDER`` or use
    the ``provider:model`` form.
    """
    m = model.lower()
    if m.startswith(("gpt-", "o1", "o3", "o4", "chatgpt")):
        return "openai"
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gemini"):
        return "google_genai"
    if m.startswith("command"):
        return "cohere"
    if m.startswith(("mistral", "ministral", "magistral", "pixtral", "codestral", "devstral")):
        return "mistralai"
    if m.startswith("deepseek"):
        return "deepseek"
    if m.startswith("grok"):
        return "xai"
    return None


def resolve_model_provider() -> tuple[str, str | None]:
    """Resolve ``(model, provider)`` from settings.

    Supports the ``provider:model`` shorthand and falls back to prefix inference.
    ``provider`` may be ``None`` if it can't be determined — in which case
    ``init_chat_model`` is left to infer it.
    """
    settings = get_settings()
    model = settings.model
    provider = settings.model_provider
    if provider is None and ":" in model:
        provider, model = model.split(":", 1)
    if provider is None:
        provider = _infer_provider(model)
    return model, provider


def _api_key_env(provider: str) -> str | None:
    """The env var expected to hold ``provider``'s key (``None`` if keyless)."""
    if provider in _PROVIDER_API_KEYS:
        return _PROVIDER_API_KEYS[provider]
    return f"{provider.upper()}_API_KEY"


def llm_available() -> bool:
    """True when a real LLM call can be made for the configured model.

    Checks the configured provider's API key. Keyless providers (e.g. a local
    Ollama) are always considered available. If the provider can't be determined,
    we optimistically report available when *any* known key is set — a wrong
    guess simply degrades to the deterministic fallback at call time.
    """
    _, provider = resolve_model_provider()
    if provider is None:
        return any(os.getenv(env) for env in _PROVIDER_API_KEYS.values() if env)
    env_var = _api_key_env(provider)
    if env_var is None:  # keyless provider
        return True
    return bool(os.getenv(env_var))


def get_llm(**overrides: Any) -> "BaseChatModel":
    """Build a configured chat model for the workflow's reasoning nodes.

    Raises:
        RuntimeError: if the configured provider has no API key available.
            Callers that want to degrade gracefully should check
            :func:`llm_available` first (the workflow nodes do).
    """
    settings = get_settings()
    model, provider = resolve_model_provider()

    if not llm_available():
        env_var = _api_key_env(provider) if provider else "the provider's API key"
        raise RuntimeError(
            f"No API key found for model '{model}'"
            + (f" (provider '{provider}')" if provider else "")
            + f". Set {env_var}, or run with --offline for a deterministic, "
            "no-key analysis."
        )

    from langchain.chat_models import init_chat_model  # lazy import

    kwargs: dict[str, Any] = {
        "model": model,
        "model_provider": provider,
        "max_tokens": settings.max_tokens,
    }
    kwargs.update(overrides)
    return init_chat_model(**kwargs)
