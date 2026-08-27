from __future__ import annotations

from types import SimpleNamespace

import pytest

from finance_workflow import run_workflow
from finance_workflow.tools import MonitorProvider
from finance_workflow.workflows.monitor import MonitorWorkflow
from finance_workflow.workflows.monitor.graph import build_graph
from finance_workflow.workflows.monitor.schema import MarketMonitorDigest, TickerMoverNote


def test_offline_run_produces_digest():
    result = run_workflow("monitor", tickers=["AAPL", "MSFT", "NVDA"], offline=True)

    assert result.metadata["label"] == "monitor"
    assert result.metadata["universe_size"] == 3
    assert result.metadata["market_sentiment"] in {"Bullish", "Bearish", "Neutral", "Mixed"}
    assert result.metadata["top_gainer"] in {"AAPL", "MSFT", "NVDA"}
    assert result.metadata["used_llm"] is False
    assert result.metadata["sources"]["market"] == "sample"

    report = result.markdown
    assert "Market & News Watchlist Monitor" in report
    assert "Executive Overview" in report
    assert "Top Advancers & Catalysts" in report
    assert "Top Decliners & Downside Risks" in report
    assert "Key Market & Sector Themes" in report
    assert "Educational use only" in report


def test_run_with_comma_separated_tickers():
    result = run_workflow("monitor", tickers="AAPL,MSFT", offline=True)

    assert result.metadata["universe_size"] == 2
    assert "AAPL" in result.markdown or "MSFT" in result.markdown


def test_monitor_provider_metrics_consistency():
    provider = MonitorProvider(allow_live=False)
    scan = provider.scan_universe(["AAPL", "MSFT", "NVDA"])

    summary = scan["summary"]
    assert summary["total_tickers"] == 3
    assert summary["gainers_count"] + summary["losers_count"] + summary["unchanged_count"] == 3

    movers = scan["movers"]
    assert len(movers["most_volatile"]) == 3
    # Verify volatility ordering
    vols = [s.get("annualized_volatility_pct") or 0.0 for s in movers["most_volatile"]]
    assert vols == sorted(vols, reverse=True)
    assert len(scan["news_feed"]) > 0


def test_empty_tickers_raise():
    provider = MonitorProvider(allow_live=False)
    with pytest.raises(ValueError):
        provider.scan_universe(["NON_EXISTENT_TICKER_99999"])


def test_graph_state_has_all_data():
    graph = build_graph()
    state = graph.invoke(
        {
            "tickers": ["AAPL", "MSFT"],
            "allow_live": False,
            "use_llm": False,
            "news_limit": 2,
        }
    )
    assert state["scan"]["summary"]["total_tickers"] == 2
    assert state["movers"]
    assert state["digest"]["market_sentiment"]
    assert state["report"]


def test_used_llm_reports_actual_provenance_not_intent(monkeypatch):
    """Requesting the LLM with no key must degrade to fallback and report used_llm=False."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    state = build_graph().invoke(
        {
            "tickers": ["AAPL", "MSFT"],
            "allow_live": False,
            "use_llm": True,
            "news_limit": 2,
        }
    )

    assert state["digest_used_llm"] is False
    assert state["report_used_llm"] is False
    assert state["report"]
    assert MonitorWorkflow().metadata(state)["used_llm"] is False


# --------------------------------------------------------------------------- #
# LLM success-branch coverage (mocked Claude)
# --------------------------------------------------------------------------- #

_DIGEST = MarketMonitorDigest(
    market_sentiment="Bullish",
    executive_summary="SENTINEL summary from Claude.",
    top_gainers_summary=[
        TickerMoverNote(
            ticker="NVDA",
            move_pct=3.5,
            driver_or_catalyst="AI chip demand surge.",
            actionable_takeaway="Leading momentum name.",
        )
    ],
    top_losers_summary=[],
    volatility_and_risk_flags=["Elevated semiconductor volatility."],
    key_themes=["Mega-cap AI leadership."],
    watchlist_alerts=["Monitor earnings catalyst."],
)


class _StructuredStub:
    def __init__(self, result):
        self._result = result

    def invoke(self, _messages):
        return self._result


class _LLMStub:
    def __init__(self, digest, report_text, *, report_raises=False):
        self._digest = digest
        self._report_text = report_text
        self._report_raises = report_raises

    def with_structured_output(self, _schema):
        return _StructuredStub(self._digest)

    def invoke(self, _messages):
        if self._report_raises:
            raise RuntimeError("simulated report API failure")
        return SimpleNamespace(content=self._report_text)


def _invoke_graph():
    return build_graph().invoke(
        {
            "tickers": ["AAPL", "NVDA"],
            "allow_live": False,
            "use_llm": True,
            "news_limit": 2,
        }
    )


def test_used_llm_true_when_both_reasoning_nodes_run(monkeypatch):
    report_text = "# SENTINEL monitor report from Claude."
    monkeypatch.setattr(
        "finance_workflow.llm.get_llm", lambda **_: _LLMStub(_DIGEST, report_text)
    )

    state = _invoke_graph()

    assert state["digest_used_llm"] is True
    assert state["report_used_llm"] is True
    assert state["digest"]["market_sentiment"] == "Bullish"
    assert state["report"] == report_text

    meta = MonitorWorkflow().metadata(state)
    assert meta["used_llm"] is True
    assert meta["market_sentiment"] == "Bullish"


def test_used_llm_false_when_report_node_degrades(monkeypatch):
    monkeypatch.setattr(
        "finance_workflow.llm.get_llm",
        lambda **_: _LLMStub(_DIGEST, report_text=None, report_raises=True),
    )

    state = _invoke_graph()

    assert state["digest_used_llm"] is False
    assert state["report_used_llm"] is False
    assert state["report"]
    assert MonitorWorkflow().metadata(state)["used_llm"] is False
