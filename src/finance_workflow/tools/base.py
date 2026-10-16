"""Shared helpers for data providers (sample-data loading, lookups)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..inputs import normalize_ticker


def sample_path(ticker: str, filename: str) -> Path:
    """Path to a bundled sample file for ``ticker``."""
    return get_settings().samples_dir / normalize_ticker(ticker) / filename


def load_sample_json(ticker: str, filename: str) -> Any:
    """Load a bundled sample JSON file, with a helpful error if missing."""
    path = sample_path(ticker, filename)
    if not path.exists():
        raise FileNotFoundError(
            f"No sample data for '{ticker.upper()}' at {path}. "
            f"Run `python scripts/generate_samples.py` to create sample data, "
            f"or choose a bundled ticker (see data/samples/index.json)."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def known_sample_tickers() -> list[str]:
    """Tickers that ship with bundled sample data."""
    index = get_settings().samples_dir / "index.json"
    if not index.exists():
        return []
    data = json.loads(index.read_text(encoding="utf-8"))
    return sorted(data.get("tickers", {}))


def company_name(ticker: str) -> str:
    """Best-effort company name from the sample index; falls back to the ticker."""
    index = get_settings().samples_dir / "index.json"
    if index.exists():
        data = json.loads(index.read_text(encoding="utf-8"))
        name = data.get("tickers", {}).get(ticker.upper())
        if name:
            return name
    return ticker.upper()
