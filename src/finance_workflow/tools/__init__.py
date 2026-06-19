"""Data providers and tool wrappers.

Each provider tries a live source first (``yfinance``) and falls back to
bundled, reproducible sample data. Every returned payload carries a ``source``
field (``"live"`` or ``"sample"``) so downstream steps — and the final memo —
stay honest about provenance.
"""
from __future__ import annotations

from .fundamentals import FundamentalsProvider
from .market_data import MarketDataProvider
from .news import NewsProvider

__all__ = ["MarketDataProvider", "FundamentalsProvider", "NewsProvider"]
