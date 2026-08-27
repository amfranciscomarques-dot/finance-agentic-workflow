"""LangGraph assembly for the market and news monitor workflow.

Pipeline:
    START -> scan_universe -> detect_movers -> generate_digest -> END
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import MonitorState


def build_graph() -> Any:
    """Build and compile the market monitor graph."""
    graph = StateGraph(MonitorState)

    graph.add_node("scan_universe", nodes.scan_universe)
    graph.add_node("detect_movers", nodes.detect_movers)
    graph.add_node("generate_digest", nodes.generate_digest)

    graph.add_edge(START, "scan_universe")
    graph.add_edge("scan_universe", "detect_movers")
    graph.add_edge("detect_movers", "generate_digest")
    graph.add_edge("generate_digest", END)

    return graph.compile()
