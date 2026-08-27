"""LangGraph assembly for the financial document analysis workflow.

Pipeline:
    START -> load_document -> chunk_document -> extract_financials -> summarize -> END
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import DocAnalysisState


def build_graph() -> Any:
    """Build and compile the document analysis graph."""
    graph = StateGraph(DocAnalysisState)

    graph.add_node("load_document", nodes.load_document)
    graph.add_node("chunk_document", nodes.chunk_document)
    graph.add_node("extract_financials", nodes.extract_financials)
    graph.add_node("summarize", nodes.summarize)

    graph.add_edge(START, "load_document")
    graph.add_edge("load_document", "chunk_document")
    graph.add_edge("chunk_document", "extract_financials")
    graph.add_edge("extract_financials", "summarize")
    graph.add_edge("summarize", END)

    return graph.compile()
