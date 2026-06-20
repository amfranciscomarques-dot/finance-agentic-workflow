from __future__ import annotations

from types import SimpleNamespace

from finance_workflow import run_workflow
from finance_workflow.workflows.equity_research import EquityResearchWorkflow
from finance_workflow.workflows.equity_research.graph import build_graph
from finance_workflow.workflows.equity_research.schema import AnalysisResult


def test_offline_run_produces_memo():
    result = run_workflow("equity-research", ticker="AAPL", offline=True)

    assert result.metadata["recommendation"] in {"Buy", "Hold", "Sell"}
    assert result.metadata["confidence"] in {"Low", "Medium", "High"}
    assert result.metadata["used_llm"] is False
    assert result.metadata["sources"]["market"] == "sample"

    memo = result.markdown
    assert "Investment Memo" in memo
    assert "AAPL" in memo
    assert "Educational use only" in memo


def test_graph_state_has_all_gathered_data():
    graph = build_graph()
    state = graph.invoke(
        {
            "ticker": "MSFT",
            "company_name": "Microsoft Corporation",
            "allow_live": False,
            "use_llm": False,
            "news_limit": 3,
        }
    )
    assert state["market"]["source"] == "sample"
    assert state["fundamentals"]["source"] == "sample"
    assert state["news"]["source"] == "sample"
    assert state["analysis"]["recommendation"] in {"Buy", "Hold", "Sell"}
    assert state["memo"]


def test_used_llm_reports_actual_provenance_not_intent(monkeypatch):
    """Requesting the LLM but having it fail must report used_llm=False.

    With no API key, ``get_llm()`` raises and both reasoning nodes degrade to
    their deterministic fallbacks — so provenance, at the node and metadata
    layers, must reflect what actually ran, not what was requested.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    state = build_graph().invoke(
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "allow_live": False,
            "use_llm": True,
            "news_limit": 3,
        }
    )

    assert state["analysis_used_llm"] is False  # fell back to the rule-based analyst
    assert state["memo_used_llm"] is False  # fell back to the template memo
    assert state["memo"]
    assert EquityResearchWorkflow().metadata(state)["used_llm"] is False


# --------------------------------------------------------------------------- #
# LLM success-branch coverage (mocked Claude)
# --------------------------------------------------------------------------- #

_ANALYSIS = AnalysisResult(
    thesis="SENTINEL thesis from Claude.",
    strengths=["Durable competitive moat."],
    risks=["Cyclical end-market demand."],
    valuation_view="Roughly fairly valued.",
    recommendation="Buy",
    confidence="High",
)


class _StructuredStub:
    """Stands in for ``llm.with_structured_output(AnalysisResult)``."""

    def __init__(self, result):
        self._result = result

    def invoke(self, _messages):
        return self._result


class _LLMStub:
    """``get_llm()`` stub: structured call for `analyze`, plain call for `write_memo`."""

    def __init__(self, analysis, memo_text, *, memo_raises=False):
        self._analysis = analysis
        self._memo_text = memo_text
        self._memo_raises = memo_raises

    def with_structured_output(self, _schema):
        return _StructuredStub(self._analysis)

    def invoke(self, _messages):  # the memo node's plain call
        if self._memo_raises:
            raise RuntimeError("simulated memo API failure")
        return SimpleNamespace(content=self._memo_text)


def _invoke_graph():
    return build_graph().invoke(
        {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "allow_live": False,
            "use_llm": True,
            "news_limit": 3,
        }
    )


def test_used_llm_true_when_both_reasoning_nodes_run(monkeypatch):
    """Both LLM nodes succeed → used_llm True and the model's text flows through."""
    memo_text = "# SENTINEL memo body from Claude."
    monkeypatch.setattr(
        "finance_workflow.llm.get_llm", lambda **_: _LLMStub(_ANALYSIS, memo_text)
    )

    state = _invoke_graph()

    assert state["analysis_used_llm"] is True
    assert state["memo_used_llm"] is True
    assert state["analysis"]["recommendation"] == "Buy"
    assert state["memo"] == memo_text

    meta = EquityResearchWorkflow().metadata(state)
    assert meta["used_llm"] is True
    assert meta["recommendation"] == "Buy"
    assert meta["confidence"] == "High"


def test_used_llm_false_when_memo_node_degrades(monkeypatch):
    """AND semantics: analysis from Claude but memo fell back → used_llm False."""
    monkeypatch.setattr(
        "finance_workflow.llm.get_llm",
        lambda **_: _LLMStub(_ANALYSIS, memo_text=None, memo_raises=True),
    )

    state = _invoke_graph()

    assert state["analysis_used_llm"] is True  # structured analysis succeeded
    assert state["memo_used_llm"] is False  # memo drafting raised → template fallback
    assert state["memo"]  # but a memo was still produced
    assert EquityResearchWorkflow().metadata(state)["used_llm"] is False
