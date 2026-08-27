"""Graph state for the market and news monitor workflow.

Pipeline:
``scan_universe`` -> ``detect_movers`` -> ``generate_digest``
"""
from __future__ import annotations

from typing import Any, TypedDict


class MonitorState(TypedDict, total=False):
    # Inputs
    tickers: list[str]
    allow_live: bool
    use_llm: bool
    news_limit: int

    # Gathered data
    scan: dict[str, Any]  # full payload from MonitorProvider
    movers: dict[str, Any]  # classified movers and rankings

    # Derived
    digest: dict[str, Any]  # MarketMonitorDigest.model_dump()
    digest_used_llm: bool  # whether Claude produced the digest
    report: str  # final Markdown deliverable
    report_used_llm: bool  # whether Claude drafted the report
