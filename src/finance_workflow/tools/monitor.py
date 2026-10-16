"""Market & News universe monitoring, mover detection, and headline aggregation.

``MonitorProvider`` scans a watchlist of tickers, derives intraday and multi-period
performance rankings (top gainers, losers, volatility outliers), and aggregates
news feeds across the universe. It composes :class:`MarketDataProvider`,
:class:`FundamentalsProvider`, and :class:`NewsProvider`.
"""
from __future__ import annotations

from typing import Any

from ..config import get_settings
from ..inputs import normalize_tickers
from .base import company_name, known_sample_tickers
from .fundamentals import FundamentalsProvider
from .market_data import MarketDataProvider
from .news import NewsProvider


class MonitorProvider:
    """Universe scanner and mover detection engine."""

    def __init__(self, allow_live: bool | None = None) -> None:
        settings = get_settings()
        self.allow_live = settings.allow_live_data if allow_live is None else allow_live
        self.market = MarketDataProvider(allow_live=self.allow_live)
        self.fundamentals = FundamentalsProvider(allow_live=self.allow_live)
        self.news = NewsProvider(allow_live=self.allow_live)

    def scan_universe(
        self,
        tickers: list[str] | str | None = None,
        news_limit: int = 3,
    ) -> dict[str, Any]:
        """Scan market snapshots and news across a list of tickers."""
        target_tickers = self._normalize_tickers(tickers)
        if not target_tickers:
            raise ValueError("No valid tickers specified to monitor.")

        snapshots: dict[str, dict[str, Any]] = {}
        fundamentals_map: dict[str, dict[str, Any]] = {}
        news_items_by_ticker: dict[str, list[dict[str, Any]]] = {}
        all_news_feed: list[dict[str, Any]] = []
        sources: set[str] = set()

        for ticker in target_tickers:
            try:
                snap = self.market.snapshot(ticker)
                snapshots[ticker] = snap
                sources.add(snap.get("source", "sample"))
            except Exception:
                continue

            try:
                fund = self.fundamentals.get(ticker)
                fundamentals_map[ticker] = fund
                sources.add(fund.get("source", "sample"))
            except Exception:
                fundamentals_map[ticker] = {
                    "company_name": company_name(ticker),
                    "sector": "Unknown",
                }

            try:
                n_data = self.news.get(ticker, limit=news_limit)
                items = n_data.get("items", [])
                news_items_by_ticker[ticker] = items
                sources.add(n_data.get("source", "sample"))
                for it in items:
                    it_copy = dict(it)
                    it_copy["ticker"] = ticker
                    it_copy["company_name"] = fundamentals_map[ticker].get("company_name", ticker)
                    all_news_feed.append(it_copy)
            except Exception:
                news_items_by_ticker[ticker] = []

        if not snapshots:
            raise ValueError(f"Could not fetch market data for any ticker in {target_tickers}.")

        # Sort news by publication date descending
        all_news_feed.sort(key=lambda x: str(x.get("published", "")), reverse=True)

        # Mover classifications
        ranked = list(snapshots.values())
        ranked_by_change = sorted(
            ranked, key=lambda s: s.get("daily_change_pct") or 0.0, reverse=True
        )
        top_gainers = [s for s in ranked_by_change if (s.get("daily_change_pct") or 0.0) >= 0]
        if not top_gainers and ranked_by_change:
            top_gainers = [ranked_by_change[0]]

        top_losers = [s for s in reversed(ranked_by_change) if (s.get("daily_change_pct") or 0.0) < 0]
        if not top_losers and ranked_by_change:
            top_losers = [ranked_by_change[-1]]

        most_volatile = sorted(
            ranked, key=lambda s: s.get("annualized_volatility_pct") or 0.0, reverse=True
        )

        avg_change = round(
            sum((s.get("daily_change_pct") or 0.0) for s in ranked) / len(ranked), 2
        )
        gainers_count = sum(1 for s in ranked if (s.get("daily_change_pct") or 0.0) > 0)
        losers_count = sum(1 for s in ranked if (s.get("daily_change_pct") or 0.0) < 0)
        unchanged_count = len(ranked) - gainers_count - losers_count

        source_label = (
            "live"
            if sources == {"live"}
            else ("sample" if sources == {"sample"} else "mixed")
        )
        as_of = max(s.get("as_of", "") for s in ranked) if ranked else None

        return {
            "source": source_label,
            "as_of": as_of,
            "universe": target_tickers,
            "snapshots": snapshots,
            "fundamentals": fundamentals_map,
            "news_by_ticker": news_items_by_ticker,
            "news_feed": all_news_feed,
            "summary": {
                "total_tickers": len(ranked),
                "avg_daily_change_pct": avg_change,
                "gainers_count": gainers_count,
                "losers_count": losers_count,
                "unchanged_count": unchanged_count,
            },
            "movers": {
                "top_gainers": top_gainers,
                "top_losers": top_losers,
                "most_volatile": most_volatile,
                "top_gainer": ranked_by_change[0]["ticker"] if ranked_by_change else None,
                "top_loser": ranked_by_change[-1]["ticker"] if ranked_by_change else None,
            },
        }

    def _normalize_tickers(self, tickers: list[str] | str | None) -> list[str]:
        if tickers is None:
            return known_sample_tickers() or ["AAPL", "MSFT", "NVDA"]
        return normalize_tickers(tickers)
