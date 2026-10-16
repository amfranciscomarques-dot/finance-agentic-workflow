"""Regression coverage for the shared offline / live-data policy."""

from __future__ import annotations

import pytest

from finance_workflow.workflows.doc_analysis import DocumentAnalysisWorkflow
from finance_workflow.workflows.equity_research import EquityResearchWorkflow
from finance_workflow.workflows.monitor import MonitorWorkflow
from finance_workflow.workflows.portfolio import PortfolioWorkflow

WORKFLOWS = [
    (EquityResearchWorkflow(), {"ticker": " aapl "}),
    (PortfolioWorkflow(), {"positions": [{"ticker": "AAPL", "shares": 1}]}),
    (DocumentAnalysisWorkflow(), {"ticker": "AAPL"}),
    (MonitorWorkflow(), {"tickers": "AAPL,MSFT"}),
]


@pytest.mark.parametrize("workflow,params", WORKFLOWS)
def test_global_live_data_setting_applies_to_every_workflow(monkeypatch, workflow, params):
    monkeypatch.setenv("FINWF_ALLOW_LIVE", "0")
    state = workflow.initial_state(**params)
    assert state["allow_live"] is False


@pytest.mark.parametrize("workflow,params", WORKFLOWS)
def test_offline_never_checks_or_uses_the_llm(monkeypatch, workflow, params):
    def forbidden():
        raise AssertionError("Offline mode must not consult an LLM provider")

    monkeypatch.setattr("finance_workflow.runtime.llm_available", forbidden)
    monkeypatch.setenv("FINWF_ALLOW_LIVE", "1")
    state = workflow.initial_state(offline=True, **params)
    assert state["allow_live"] is False
    assert state["use_llm"] is False


def test_watchlist_normalizes_and_deduplicates():
    state = MonitorWorkflow().initial_state(tickers=" aapl, MSFT, aapl ", offline=True)
    assert state["tickers"] == ["AAPL", "MSFT"]


@pytest.mark.parametrize("ticker", [None, "", "   ", "../AAPL", "/etc/passwd", 123])
def test_bad_ticker_fails_before_execution(ticker):
    with pytest.raises(ValueError):
        EquityResearchWorkflow().initial_state(ticker=ticker, offline=True)


def test_empty_watchlist_is_not_silently_replaced_by_defaults():
    with pytest.raises(ValueError):
        MonitorWorkflow().initial_state(tickers=" , ", offline=True)


def test_negative_news_limit_rejected():
    with pytest.raises(ValueError):
        EquityResearchWorkflow().initial_state(ticker="AAPL", news_limit=-1)
