"""Structured output schema for the market and news monitor workflow.

The ``generate_digest`` node asks Claude to return this object (via
``with_structured_output``), synthesizing mover action, catalysts, and watchlist
takeaways into validated, typed fields.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TickerMoverNote(BaseModel):
    """Notable mover summary with catalyst context."""

    ticker: str = Field(description="Stock ticker symbol.")
    move_pct: float = Field(description="Intraday price change percentage.")
    driver_or_catalyst: str = Field(
        description="Key catalyst, earnings result, headline, or sector momentum driving the move."
    )
    actionable_takeaway: str = Field(
        description="Key analytical observation or risk/reward implication for watchlist monitoring."
    )


class MarketMonitorDigest(BaseModel):
    """Comprehensive structured market and news watchlist digest."""

    market_sentiment: Literal["Bullish", "Bearish", "Neutral", "Mixed"] = Field(
        description="Overall market sentiment across the monitored universe."
    )
    executive_summary: str = Field(
        description="A 3-5 sentence executive overview of broad market action, breadth, and sector leadership."
    )
    top_gainers_summary: list[TickerMoverNote] = Field(
        description="Analysis of top advancing tickers and upside catalysts."
    )
    top_losers_summary: list[TickerMoverNote] = Field(
        description="Analysis of top declining tickers and downside risks."
    )
    volatility_and_risk_flags: list[str] = Field(
        description="Key volatility spikes, drawdowns, or risk alerts across the universe."
    )
    key_themes: list[str] = Field(
        description="Dominant market, macro, and sector themes observed from news and price action."
    )
    watchlist_alerts: list[str] = Field(
        description="Actionable watchlist alerts or upcoming catalysts to track."
    )
