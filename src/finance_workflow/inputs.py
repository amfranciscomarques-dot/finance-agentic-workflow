"""Input normalization shared by workflows and data providers."""

from __future__ import annotations

import re
from collections.abc import Iterable


def normalize_ticker(value: str) -> str:
    """Accept market symbols, rejecting empty names and filesystem paths."""
    if not isinstance(value, str):
        raise ValueError("Ticker must be a string.")
    ticker = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=\-]{0,19}", ticker):
        raise ValueError(f"Invalid ticker: {value!r}.")
    return ticker


def normalize_tickers(values: str | Iterable[str]) -> list[str]:
    """Normalize and deduplicate symbols while preserving their order."""
    if isinstance(values, str):
        values = values.split(",")
    normalized = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError("Each ticker must be a string.")
        if value.strip():
            normalized.append(normalize_ticker(value))
    tickers = list(dict.fromkeys(normalized))
    if not tickers:
        raise ValueError("Provide at least one ticker.")
    return tickers


def validate_news_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("News limit must be a non-negative integer.")
    return value
