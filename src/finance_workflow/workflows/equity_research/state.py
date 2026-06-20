"""Graph state for the equity-research workflow.

The three ``gather_*`` nodes run in parallel, so each writes to a *distinct*
key (``market`` / ``fundamentals`` / ``news``) — that avoids concurrent writes
to the same field and keeps the graph reducer-free.
"""
from __future__ import annotations

from typing import Any, TypedDict


class EquityResearchState(TypedDict, total=False):
    # Inputs
    ticker: str
    company_name: str
    allow_live: bool  # may use live data sources
    use_llm: bool  # call Claude vs. deterministic fallback
    news_limit: int

    # Gathered data (each written by exactly one parallel node)
    market: dict[str, Any]
    fundamentals: dict[str, Any]
    news: dict[str, Any]

    # Derived (sequential nodes)
    analysis: dict[str, Any]  # AnalysisResult.model_dump()
    analysis_used_llm: bool  # whether Claude produced the analysis (vs. fallback)
    memo: str  # final Markdown deliverable
    memo_used_llm: bool  # whether Claude drafted the memo (vs. template)
