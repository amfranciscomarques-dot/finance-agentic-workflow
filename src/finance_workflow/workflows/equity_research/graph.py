"""LangGraph assembly for the equity-research workflow.

Shape (a fan-out / fan-in DAG):

    START ─┬─> gather_market_data ─┐
           ├─> gather_fundamentals ─┼─> analyze ─> write_memo ─> END
           └─> gather_news ─────────┘

The three gather nodes run in one superstep (parallel); ``analyze`` has three
incoming edges, so LangGraph runs it once, after all three complete.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import EquityResearchState


def build_graph() -> Any:
    """Build and compile the equity-research graph."""
    graph = StateGraph(EquityResearchState)

    graph.add_node("gather_market_data", nodes.gather_market_data)
    graph.add_node("gather_fundamentals", nodes.gather_fundamentals)
    graph.add_node("gather_news", nodes.gather_news)
    graph.add_node("analyze", nodes.analyze)
    graph.add_node("write_memo", nodes.write_memo)

    # Fan out from START to the three independent data-gathering nodes.
    graph.add_edge(START, "gather_market_data")
    graph.add_edge(START, "gather_fundamentals")
    graph.add_edge(START, "gather_news")

    # Fan in: analyze waits for all three before running.
    graph.add_edge("gather_market_data", "analyze")
    graph.add_edge("gather_fundamentals", "analyze")
    graph.add_edge("gather_news", "analyze")

    graph.add_edge("analyze", "write_memo")
    graph.add_edge("write_memo", END)

    return graph.compile()
