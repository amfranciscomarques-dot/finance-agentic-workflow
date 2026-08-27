"""LangChain ``@tool`` wrappers around the data providers.

The equity-research workflow calls the providers directly (a deterministic DAG),
but exposing them as LangChain tools lets you build a *tool-calling* agent
variant — e.g. ``langgraph.prebuilt.create_react_agent(llm, TOOLS)`` — that
decides which data to pull. See docs/adding-a-workflow.md.
"""
from __future__ import annotations

from langchain_core.tools import tool

from .document import DocumentProvider
from .fundamentals import FundamentalsProvider
from .market_data import MarketDataProvider
from .monitor import MonitorProvider
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


@tool
def document_analysis_extract(
    ticker: str | None = None, file_path: str | None = None
) -> dict:
    """Ingest a financial filing document, chunk it, and extract key metrics with citations."""
    provider = DocumentProvider()
    doc = provider.load_document(source=file_path, ticker=ticker)
    chunks = provider.chunk(doc["text"])
    return provider.extract_metrics_deterministic(
        chunks,
        company_name=doc.get("company_name", ""),
        ticker=doc.get("ticker"),
    )


@tool
def market_monitor_scan(tickers: str | None = None) -> dict:
    """Scan a watchlist or universe of tickers for movers, volatility, and news."""
    ticker_list = [t.strip().upper() for t in tickers.split(",")] if tickers else None
    return MonitorProvider().scan_universe(ticker_list)


#: Convenient bundle for binding to a tool-calling agent.
TOOLS = [
    market_snapshot,
    company_fundamentals,
    recent_news,
    document_analysis_extract,
    market_monitor_scan,
]
