"""Portfolio holdings + risk metrics.

``PortfolioProvider`` turns a set of positions (ticker + share count) into a
compact metrics dict: position values and weights, portfolio-level trailing
returns / volatility / max drawdown computed from a synthesized value series,
plus exposures and concentration. It *reuses* the existing data layer
(:class:`MarketDataProvider`, :class:`FundamentalsProvider`), so it inherits the
same live-then-sample fallback and ``source`` tagging.

Positions can come from an in-memory list (handy for tests / programmatic use)
or a CSV with ``ticker,shares`` columns.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import get_settings
from ..inputs import normalize_ticker
from .base import company_name
from .fundamentals import FundamentalsProvider
from .market_data import TRADING_DAYS, MarketDataProvider

# Trailing-return windows in trading days, mirroring MarketDataProvider.
_WINDOWS = {"return_1m_pct": 21, "return_3m_pct": 63, "return_6m_pct": 126, "return_1y_pct": 252}


class PortfolioProvider:
    """Compute portfolio analytics from positions (live or sample data)."""

    def __init__(self, allow_live: bool | None = None) -> None:
        settings = get_settings()
        self.allow_live = settings.allow_live_data if allow_live is None else allow_live
        self.market = MarketDataProvider(allow_live=self.allow_live)
        self.fundamentals = FundamentalsProvider(allow_live=self.allow_live)

    # -- input ------------------------------------------------------------- #
    def load_positions(self, source: Any) -> list[dict[str, Any]]:
        """Normalize positions from an in-memory list or a ``ticker,shares`` CSV."""
        if isinstance(source, (str, Path)):
            rows = self._read_csv(Path(source))
        else:
            rows = list(source or [])

        shares_by_ticker: dict[str, float] = {}
        for row in rows:
            try:
                ticker = normalize_ticker(row["ticker"])
                shares = float(row["shares"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("Each holding must have a valid ticker and numeric shares.") from exc
            if not math.isfinite(shares):
                raise ValueError(f"Shares for {ticker} must be finite.")
            shares_by_ticker[ticker] = shares_by_ticker.get(ticker, 0.0) + shares
        positions = [
            {"ticker": ticker, "shares": shares}
            for ticker, shares in shares_by_ticker.items()
            if shares != 0
        ]
        if not positions:
            raise ValueError(
                "No valid positions found. Provide a list of {ticker, shares} or a CSV "
                "with 'ticker' and 'shares' columns."
            )
        return positions

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            raise FileNotFoundError(f"Holdings file not found: {path}")
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        missing = {"ticker", "shares"} - set(df.columns)
        if missing:
            raise ValueError(f"Holdings CSV is missing column(s): {', '.join(sorted(missing))}.")
        return df[["ticker", "shares"]].to_dict("records")

    # -- metrics ----------------------------------------------------------- #
    def metrics(self, positions: list[dict[str, Any]]) -> dict[str, Any]:
        """Compute position- and portfolio-level analytics."""
        positions = self.load_positions(positions)
        close_by_ticker: dict[str, pd.Series] = {}
        sources: set[str] = set()
        enriched: list[dict[str, Any]] = []

        for pos in positions:
            ticker, shares = pos["ticker"], pos["shares"]
            df, source = self.market.get_price_history(ticker)
            close = df["Close"].astype(float).dropna()
            if close.empty:
                continue
            sources.add(source)
            close_by_ticker[ticker] = close

            fundamentals = self.fundamentals.get(ticker)
            last_close = float(close.iloc[-1])
            enriched.append(
                {
                    "ticker": ticker,
                    "company_name": fundamentals.get("company_name") or company_name(ticker),
                    "shares": shares,
                    "last_close": round(last_close, 2),
                    "value": round(shares * last_close, 2),
                    "sector": fundamentals.get("sector"),
                    "beta": _num(fundamentals.get("beta")),
                    "return_1y_pct": _trailing_return(close, _WINDOWS["return_1y_pct"]),
                }
            )

        if not enriched:
            raise ValueError("Could not price any position in the portfolio.")

        total_value = sum(p["value"] for p in enriched)
        for p in enriched:
            p["weight"] = round(p["value"] / total_value, 4) if total_value else 0.0

        value_series = _portfolio_value_series(close_by_ticker, positions)

        return {
            "source": "live" if sources == {"live"} else ("sample" if sources == {"sample"} else "mixed"),
            "as_of": value_series.index[-1].date().isoformat() if not value_series.empty else None,
            "total_value": round(total_value, 2),
            "positions": sorted(enriched, key=lambda p: p["weight"], reverse=True),
            "returns": {label: _trailing_return(value_series, w) for label, w in _WINDOWS.items()},
            "annualized_volatility_pct": _annualized_vol(value_series),
            "max_drawdown_pct": _max_drawdown(value_series),
            "weighted_beta": _weighted_beta(enriched),
            "sector_exposure": _sector_exposure(enriched),
            "concentration": {
                "top_weight_pct": round(max(p["weight"] for p in enriched) * 100, 2),
                # Herfindahl-Hirschman Index: 1/N (diversified) … 1.0 (single name).
                "hhi": round(sum(p["weight"] ** 2 for p in enriched), 4),
                "n_positions": len(enriched),
            },
        }


# --------------------------------------------------------------------------- #
# Calculation helpers
# --------------------------------------------------------------------------- #


def _portfolio_value_series(
    close_by_ticker: dict[str, pd.Series], positions: list[dict[str, Any]]
) -> pd.Series:
    """Synthesize a portfolio value time series by aligning per-ticker closes.

    Aligns on the dates common to every priced holding (inner join) so the
    weighted series is well-defined, then sums ``shares * close``.
    """
    shares = {p["ticker"]: p["shares"] for p in positions}
    frame = pd.DataFrame(close_by_ticker).dropna()
    if frame.empty:
        return pd.Series(dtype=float)
    weighted = sum(frame[ticker] * shares[ticker] for ticker in frame.columns)
    return weighted.sort_index()


def _trailing_return(series: pd.Series, window: int) -> float | None:
    if len(series) <= window:
        return None
    return round((float(series.iloc[-1]) / float(series.iloc[-1 - window]) - 1) * 100, 2)


def _annualized_vol(series: pd.Series) -> float | None:
    daily = series.pct_change().dropna()
    if daily.empty:
        return None
    return round(float(daily.std()) * math.sqrt(TRADING_DAYS) * 100, 2)


def _max_drawdown(series: pd.Series) -> float | None:
    if series.empty:
        return None
    running_max = series.cummax()
    drawdown = series / running_max - 1.0
    return round(float(drawdown.min()) * 100, 2)


def _weighted_beta(positions: list[dict[str, Any]]) -> float | None:
    pairs = [(p["weight"], p["beta"]) for p in positions if p.get("beta") is not None]
    if not pairs:
        return None
    return round(sum(w * b for w, b in pairs), 3)


def _sector_exposure(positions: list[dict[str, Any]]) -> dict[str, float]:
    exposure: dict[str, float] = {}
    for p in positions:
        sector = p.get("sector") or "Unknown"
        exposure[sector] = round(exposure.get(sector, 0.0) + p["weight"] * 100, 2)
    return dict(sorted(exposure.items(), key=lambda kv: kv[1], reverse=True))


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
