"""LangGraph assembly for the portfolio & risk-analytics workflow.

A linear pipeline:

    START ─> load_positions ─> compute_metrics ─> narrate ─> END

``load_positions`` normalizes the holdings, ``compute_metrics`` prices them and
derives portfolio analytics, and ``narrate`` produces the structured assessment
and Markdown report.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import PortfolioState


def build_graph() -> Any:
    """Build and compile the portfolio graph."""
    graph = StateGraph(PortfolioState)

    graph.add_node("load_positions", nodes.load_positions)
    graph.add_node("compute_metrics", nodes.compute_metrics)
    graph.add_node("narrate", nodes.narrate)

    graph.add_edge(START, "load_positions")
    graph.add_edge("load_positions", "compute_metrics")
    graph.add_edge("compute_metrics", "narrate")
    graph.add_edge("narrate", END)

    return graph.compile()
