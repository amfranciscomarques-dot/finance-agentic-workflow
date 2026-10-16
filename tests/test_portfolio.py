from __future__ import annotations

from pathlib import Path

import pytest

from finance_workflow import run_workflow
from finance_workflow.tools import PortfolioProvider
from finance_workflow.workflows.portfolio import PortfolioWorkflow
from finance_workflow.workflows.portfolio.graph import build_graph
from finance_workflow.workflows.portfolio.schema import PortfolioAssessment

POSITIONS = [
    {"ticker": "AAPL", "shares": 120},
    {"ticker": "MSFT", "shares": 60},
    {"ticker": "NVDA", "shares": 200},
]


def test_offline_run_produces_report():
    result = run_workflow("portfolio", positions=POSITIONS, offline=True)

    assert result.metadata["risk_rating"] in {"Low", "Moderate", "Elevated", "High"}
    assert result.metadata["used_llm"] is False
    assert result.metadata["positions"] == 3
    assert result.metadata["total_value"] > 0
    assert result.metadata["sources"]["market"] == "sample"

    report = result.markdown
    assert "Portfolio Risk Report" in report
    assert "Sector exposure" in report
    assert "Educational use only" in report


def test_metrics_are_internally_consistent():
    metrics = PortfolioProvider(allow_live=False).metrics(POSITIONS)

    # Weights are normalized and sum to ~1.
    assert abs(sum(p["weight"] for p in metrics["positions"]) - 1.0) < 1e-6
    # Positions are sorted by weight descending.
    weights = [p["weight"] for p in metrics["positions"]]
    assert weights == sorted(weights, reverse=True)
    # Sector exposure (in %) sums to ~100.
    assert abs(sum(metrics["sector_exposure"].values()) - 100.0) < 0.5
    # Concentration is a valid HHI in (0, 1].
    assert 0 < metrics["concentration"]["hhi"] <= 1.0
    assert metrics["max_drawdown_pct"] <= 0
    assert metrics["source"] == "sample"


def test_load_positions_from_csv():
    csv = Path(__file__).resolve().parents[1] / "examples" / "sample_portfolio.csv"
    positions = PortfolioProvider(allow_live=False).load_positions(csv)
    assert {p["ticker"] for p in positions} == {"AAPL", "MSFT", "NVDA"}
    assert all(p["shares"] > 0 for p in positions)


def test_empty_positions_raise():
    with pytest.raises(ValueError):
        PortfolioProvider(allow_live=False).load_positions([])


def test_duplicate_holdings_have_the_same_metrics_as_combined_positions():
    provider = PortfolioProvider(allow_live=False)
    combined = [{"ticker": "AAPL", "shares": 30}, {"ticker": "MSFT", "shares": 10}]
    duplicated = [
        {"ticker": " aapl ", "shares": 10},
        {"ticker": "AAPL", "shares": 20},
        {"ticker": "MSFT", "shares": 10},
    ]
    assert provider.metrics(duplicated) == provider.metrics(combined)


@pytest.mark.parametrize("shares", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_holdings_rejected(shares):
    with pytest.raises(ValueError, match="finite"):
        PortfolioProvider(allow_live=False).load_positions([{"ticker": "AAPL", "shares": shares}])


def test_mixed_price_sources_are_labeled_mixed(monkeypatch):
    provider = PortfolioProvider(allow_live=False)
    sample_history = provider.market.get_price_history

    def mixed_history(ticker):
        frame, _ = sample_history(ticker)
        return frame, "live" if ticker == "AAPL" else "sample"

    monkeypatch.setattr(provider.market, "get_price_history", mixed_history)
    metrics = provider.metrics(POSITIONS)
    assert metrics["source"] == "mixed"


def test_graph_runs_end_to_end():
    state = build_graph().invoke(
        {"holdings_source": POSITIONS, "allow_live": False, "use_llm": False}
    )
    assert state["metrics"]["total_value"] > 0
    assert state["assessment"]["risk_rating"]
    assert state["report"]


def test_used_llm_reports_actual_provenance_not_intent(monkeypatch):
    """Requesting the LLM but having it fail must report used_llm=False.

    With no API key, ``get_llm()`` raises and ``narrate`` degrades to the
    deterministic fallback — so provenance, at both the node and metadata
    layers, must reflect what actually ran, not what was requested.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    state = build_graph().invoke(
        {"holdings_source": POSITIONS, "allow_live": False, "use_llm": True}
    )

    assert state["used_llm"] is False  # fell back to the deterministic assessment
    assert state["report"]
    assert PortfolioWorkflow().metadata(state)["used_llm"] is False


class _StructuredStub:
    """Stands in for ``llm.with_structured_output(Schema)``: returns a fixed model."""

    def __init__(self, result):
        self._result = result

    def invoke(self, _messages):
        return self._result


class _LLMStub:
    """Stands in for ``get_llm()`` for the portfolio's single structured call."""

    def __init__(self, structured_result):
        self._structured_result = structured_result

    def with_structured_output(self, _schema):
        return _StructuredStub(self._structured_result)


def test_narrate_uses_llm_when_available(monkeypatch):
    """The Claude success branch: a mocked LLM sets used_llm and feeds the report.

    Exercises the path the no-key test can't reach — ``narrate`` calls Claude,
    gets a structured assessment back, and must mark provenance true and render
    the model's text into the deliverable.
    """
    assessment = PortfolioAssessment(
        overall_view="SENTINEL overall view from Claude.",
        diversification="Reasonably diversified across sectors.",
        key_risks=["SENTINEL concentration risk in semiconductors."],
        suggestions=["Trim the largest position."],
        risk_rating="Elevated",
    )
    monkeypatch.setattr("finance_workflow.llm.get_llm", lambda **_: _LLMStub(assessment))

    state = build_graph().invoke(
        {"holdings_source": POSITIONS, "allow_live": False, "use_llm": True}
    )

    assert state["used_llm"] is True
    assert state["assessment"]["risk_rating"] == "Elevated"
    # The LLM's text flows through the renderer into the final report.
    assert "SENTINEL overall view from Claude." in state["report"]
    assert "SENTINEL concentration risk in semiconductors." in state["report"]

    meta = PortfolioWorkflow().metadata(state)
    assert meta["used_llm"] is True
    assert meta["risk_rating"] == "Elevated"
