"""Company fundamentals (valuation, profitability, profile).

Returns a normalised dict regardless of whether the data came from
``yfinance`` ``.info`` or the bundled sample JSON.
"""
from __future__ import annotations

from typing import Any

from ..config import get_settings
from .base import company_name, load_sample_json

# Map normalised field name -> yfinance `.info` key.
_LIVE_FIELDS = {
    "company_name": "longName",
    "sector": "sector",
    "industry": "industry",
    "market_cap": "marketCap",
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "price_to_book": "priceToBook",
    "profit_margin": "profitMargins",
    "revenue_growth": "revenueGrowth",
    "dividend_yield": "dividendYield",
    "beta": "beta",
    "summary": "longBusinessSummary",
}


class FundamentalsProvider:
    """Fetch a compact fundamentals profile (live or sample)."""

    def __init__(self, allow_live: bool | None = None) -> None:
        settings = get_settings()
        self.allow_live = settings.allow_live_data if allow_live is None else allow_live

    def get(self, ticker: str) -> dict[str, Any]:
        ticker = ticker.upper()
        if self.allow_live:
            try:
                data = self._live(ticker)
                if data:
                    return data
            except Exception:
                pass
        return self._sample(ticker)

    def _live(self, ticker: str) -> dict[str, Any] | None:
        import yfinance as yf  # optional dependency

        info = yf.Ticker(ticker).info or {}
        if not info.get("longName") and not info.get("marketCap"):
            return None
        data: dict[str, Any] = {key: info.get(src) for key, src in _LIVE_FIELDS.items()}
        data["ticker"] = ticker
        data["source"] = "live"
        if not data.get("company_name"):
            data["company_name"] = company_name(ticker)
        return data

    def _sample(self, ticker: str) -> dict[str, Any]:
        data: dict[str, Any] = dict(load_sample_json(ticker, "fundamentals.json"))
        data["ticker"] = ticker
        data["source"] = "sample"
        data.setdefault("company_name", company_name(ticker))
        return data
