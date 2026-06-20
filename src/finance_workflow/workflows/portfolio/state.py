"""Graph state for the portfolio & risk-analytics workflow.

A simple linear pipeline (no parallel nodes), so every key is written by
exactly one node and no reducers are needed.
"""
from __future__ import annotations

from typing import Any, TypedDict


class PortfolioState(TypedDict, total=False):
    # Inputs
    holdings_source: Any  # an in-memory list[{ticker, shares}] or a CSV path (str)
    allow_live: bool  # may use live data sources
    use_llm: bool  # call Claude vs. deterministic fallback

    # Derived (sequential nodes)
    positions: list[dict[str, Any]]  # normalized [{ticker, shares}]
    metrics: dict[str, Any]  # PortfolioProvider.metrics() output
    assessment: dict[str, Any]  # PortfolioAssessment.model_dump()
    used_llm: bool  # whether Claude actually produced the assessment (vs. fallback)
    report: str  # final Markdown deliverable
