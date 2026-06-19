from __future__ import annotations

from finance_workflow.tools import FundamentalsProvider, MarketDataProvider, NewsProvider


def test_market_snapshot_from_sample():
    snap = MarketDataProvider(allow_live=False).snapshot("AAPL")
    assert snap["source"] == "sample"
    assert snap["ticker"] == "AAPL"
    assert snap["last_close"] > 0
    assert snap["observations"] > 100
    # Volatility and 1Y return should be computable from a full year of samples.
    assert snap["annualized_volatility_pct"] is not None
    assert snap["return_1y_pct"] is not None


def test_fundamentals_from_sample():
    data = FundamentalsProvider(allow_live=False).get("MSFT")
    assert data["source"] == "sample"
    assert data["company_name"] == "Microsoft Corporation"
    assert data["sector"] == "Technology"
    assert data["forward_pe"] > 0


def test_news_from_sample():
    news = NewsProvider(allow_live=False).get("NVDA", limit=2)
    assert news["source"] == "sample"
    assert len(news["items"]) == 2
    assert news["items"][0]["title"]
