"""Shared execution policy for every workflow."""

from __future__ import annotations

from .config import get_settings
from .llm import llm_available


def runtime_options(offline: bool = False) -> dict[str, bool]:
    """Respect the global live-data setting and short-circuit offline LLM checks."""
    return {
        "allow_live": not offline and get_settings().allow_live_data,
        "use_llm": not offline and llm_available(),
    }
