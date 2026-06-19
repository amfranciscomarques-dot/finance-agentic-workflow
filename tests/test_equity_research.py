from __future__ import annotations

from finance_workflow import run_workflow
from finance_workflow.workflows.equity_research.graph import build_graph


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
