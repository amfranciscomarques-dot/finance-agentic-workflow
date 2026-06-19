"""Runtime configuration.

All settings are environment-driven (via ``.env`` / process env) so the same
code runs locally, in CI, or in a container without edits. ``Settings`` is a
frozen dataclass; call :func:`get_settings` to read the current environment.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load a local .env if present. Never raises if the file is absent.
load_dotenv()

# Resolve key paths relative to this file so the package works from anywhere.
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
SAMPLES_DIR = PACKAGE_ROOT / "data" / "samples"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", ""}


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for a single run."""

    anthropic_api_key: str | None = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY") or None
    )
    model: str = field(default_factory=lambda: os.getenv("FINWF_MODEL", "claude-opus-4-8"))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("FINWF_MAX_TOKENS", "4096")))
    allow_live_data: bool = field(default_factory=lambda: _env_flag("FINWF_ALLOW_LIVE", True))
    output_dir: Path = field(
        default_factory=lambda: Path(os.getenv("FINWF_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR)))
    )
    samples_dir: Path = field(default=SAMPLES_DIR)

    @property
    def llm_enabled(self) -> bool:
        """True when an API key is available for real Claude calls."""
        return bool(self.anthropic_api_key)


def get_settings() -> Settings:
    """Return configuration resolved from the current environment."""
    return Settings()
