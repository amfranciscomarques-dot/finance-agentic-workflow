"""LangChain ``@tool`` wrappers around the data providers.

The equity-research workflow calls the providers directly (a deterministic DAG),
but exposing them as LangChain tools lets you build a *tool-calling* agent
variant — e.g. ``langgraph.prebuilt.create_react_agent(llm, TOOLS)`` — that
decides which data to pull. See docs/adding-a-workflow.md.
"""
from __future__ import annotations

from langchain_core.tools import tool

from .fundamentals import FundamentalsProvider
from .market_data import MarketDataProvider
from .news import NewsProvider


@tool
def market_snapshot(ticker: str) -> dict:
    """Get latest price, trailing returns, 52-week range, and volatility for a ticker."""
    return MarketDataProvider().snapshot(ticker)


@tool
def company_fundamentals(ticker: str) -> dict:
    """Get valuation, profitability, and profile fundamentals for a ticker."""
    return FundamentalsProvider().get(ticker)


@tool
def recent_news(ticker: str, limit: int = 5) -> dict:
    """Get recent news headlines and summaries for a ticker."""
    return NewsProvider().get(ticker, limit=limit)


#: Convenient bundle for binding to a tool-calling agent.
TOOLS = [market_snapshot, company_fundamentals, recent_news]
