"""Recent news headlines for a ticker.

Returns ``{"source": ..., "items": [{title, publisher, published, summary, url}]}``.
Live headlines come from ``yfinance``; otherwise bundled sample headlines.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from .base import load_sample_json


class NewsProvider:
    """Fetch recent news items (live or sample)."""

    def __init__(self, allow_live: bool | None = None) -> None:
        settings = get_settings()
        self.allow_live = settings.allow_live_data if allow_live is None else allow_live

    def get(self, ticker: str, limit: int = 5) -> dict[str, Any]:
        ticker = ticker.upper()
        if self.allow_live:
            try:
                items = self._live(ticker, limit)
                if items:
                    return {"source": "live", "items": items}
            except Exception:
                pass
        sample = load_sample_json(ticker, "news.json")
        return {"source": "sample", "items": list(sample)[:limit]}

    def _live(self, ticker: str, limit: int) -> list[dict[str, Any]]:
        import yfinance as yf  # optional dependency

        raw = yf.Ticker(ticker).news or []
        items: list[dict[str, Any]] = []
        for entry in raw[:limit]:
            # yfinance has used both a flat shape and a nested {"content": {...}} shape.
            content = entry.get("content", entry)
            published = content.get("pubDate") or _epoch_to_iso(entry.get("providerPublishTime"))
            items.append(
                {
                    "title": content.get("title") or entry.get("title", ""),
                    "publisher": _publisher(content, entry),
                    "published": published,
                    "summary": content.get("summary", ""),
                    "url": _url(content, entry),
                }
            )
        return items


def _publisher(content: dict[str, Any], entry: dict[str, Any]) -> str:
    provider = content.get("provider")
    if isinstance(provider, dict):
        return provider.get("displayName", "")
    return entry.get("publisher", "")


def _url(content: dict[str, Any], entry: dict[str, Any]) -> str:
    url = content.get("canonicalUrl")
    if isinstance(url, dict):
        return url.get("url", "")
    return entry.get("link", "")


def _epoch_to_iso(epoch: Any) -> str:
    if not epoch:
        return ""
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).date().isoformat()
    except (ValueError, OSError, OverflowError):
        return ""
