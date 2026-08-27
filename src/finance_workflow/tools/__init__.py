"""Data providers and tool wrappers.

Each provider tries a live source first (``yfinance``) and falls back to
bundled, reproducible sample data. Every returned payload carries a ``source``
field (``"live"`` or ``"sample"``) so downstream steps — and the final memo —
stay honest about provenance.
"""
from __future__ import annotations

from .document import DocumentProvider
from .fundamentals import FundamentalsProvider
from .market_data import MarketDataProvider
from .monitor import MonitorProvider
from .news import NewsProvider
from .portfolio import PortfolioProvider

__all__ = [
    "MarketDataProvider",
    "FundamentalsProvider",
    "NewsProvider",
    "PortfolioProvider",
    "DocumentProvider",
    "MonitorProvider",
]
