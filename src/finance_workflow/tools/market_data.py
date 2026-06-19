"""Price history and derived market metrics.

``MarketDataProvider.snapshot`` returns a compact dict of the numbers an
analyst cares about: latest price, trailing returns, 52-week range, and
annualised volatility — computed identically whether the prices came from
``yfinance`` or the bundled sample CSVs.
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from ..config import get_settings
from .base import sample_path

TRADING_DAYS = 252
_WINDOWS = {"return_1m_pct": 21, "return_3m_pct": 63, "return_6m_pct": 126, "return_1y_pct": 252}


class MarketDataProvider:
    """Fetch daily prices (live or sample) and compute summary metrics."""

    def __init__(self, allow_live: bool | None = None) -> None:
        settings = get_settings()
        self.allow_live = settings.allow_live_data if allow_live is None else allow_live

    # -- price history -----------------------------------------------------
    def get_price_history(self, ticker: str) -> tuple[pd.DataFrame, str]:
        """Return (OHLCV dataframe indexed by Date, source)."""
        ticker = ticker.upper()
        if self.allow_live:
            try:
                df = self._live_prices(ticker)
                if df is not None and not df.empty:
                    return df, "live"
            except Exception:
                # Any live failure (no network, bad ticker, yfinance missing)
                # silently falls through to sample data.
                pass
        return self._sample_prices(ticker), "sample"

    def _live_prices(self, ticker: str) -> pd.DataFrame | None:
        import yfinance as yf  # optional dependency

        hist = yf.Ticker(ticker).history(period="1y", interval="1d")
        if hist is None or hist.empty:
            return None
        hist = hist.rename(columns=str.title)
        cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in hist.columns]
        df = hist[cols].copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.index.name = "Date"
        return df

    def _sample_prices(self, ticker: str) -> pd.DataFrame:
        path = sample_path(ticker, "prices.csv")
        if not path.exists():
            raise FileNotFoundError(
                f"No sample prices for '{ticker}' at {path}. "
                f"Run `python scripts/generate_samples.py` first."
            )
        return pd.read_csv(path, parse_dates=["Date"]).set_index("Date").sort_index()

    # -- derived metrics ---------------------------------------------------
    def snapshot(self, ticker: str) -> dict[str, Any]:
        """Compact dict of price metrics for ``ticker``."""
        df, source = self.get_price_history(ticker)
        close = df["Close"].astype(float).dropna()
        if close.empty:
            raise ValueError(f"No closing prices available for {ticker}.")

        last = float(close.iloc[-1])
        prev = float(close.iloc[-2]) if len(close) > 1 else last
        daily_returns = close.pct_change().dropna()

        snap: dict[str, Any] = {
            "ticker": ticker.upper(),
            "source": source,
            "as_of": close.index[-1].date().isoformat(),
            "observations": int(len(close)),
            "last_close": round(last, 2),
            "daily_change_pct": _pct(last / prev - 1),
            "high_52w": round(float(close.max()), 2),
            "low_52w": round(float(close.min()), 2),
            "annualized_volatility_pct": _pct(
                float(daily_returns.std()) * math.sqrt(TRADING_DAYS)
            )
            if not daily_returns.empty
            else None,
        }
        for label, window in _WINDOWS.items():
            snap[label] = (
                _pct(last / float(close.iloc[-1 - window]) - 1) if len(close) > window else None
            )
        # Distance from the 52-week high, a quick momentum/drawdown read.
        snap["pct_below_52w_high"] = _pct(last / snap["high_52w"] - 1)
        return snap


def _pct(value: float) -> float:
    """Convert a fractional return to a rounded percentage."""
    return round(value * 100, 2)
