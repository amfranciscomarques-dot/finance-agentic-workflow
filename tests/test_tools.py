from __future__ import annotations

from finance_workflow.tools import (
    DocumentProvider,
    FundamentalsProvider,
    MarketDataProvider,
    MonitorProvider,
    NewsProvider,
)
from finance_workflow.tools.langchain_tools import TOOLS


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


def test_document_provider_deterministic_extraction():
    provider = DocumentProvider(allow_live=False)
    doc = provider.load_document(ticker="AAPL")
    assert doc["source"] == "sample"
    chunks = provider.chunk(doc["text"])
    assert len(chunks) >= 2

    metrics = provider.extract_metrics_deterministic(chunks, company_name="Apple Inc.", ticker="AAPL")
    assert metrics["company_name"] == "Apple Inc."
    assert len(metrics["key_metrics"]) >= 4
    assert len(metrics["risk_factors"]) >= 2
    # Verify citations
    for m in metrics["key_metrics"]:
        assert "[Chunk" in m["citation"]


def test_monitor_provider_scan():
    provider = MonitorProvider(allow_live=False)
    scan = provider.scan_universe(["AAPL", "MSFT"])
    assert scan["source"] == "sample"
    assert scan["summary"]["total_tickers"] == 2
    assert "movers" in scan
    assert "news_feed" in scan


def test_langchain_tools_bundle():
    assert len(TOOLS) == 5
    tool_names = {t.name for t in TOOLS}
    assert "market_snapshot" in tool_names
    assert "company_fundamentals" in tool_names
    assert "recent_news" in tool_names
    assert "document_analysis_extract" in tool_names
    assert "market_monitor_scan" in tool_names
