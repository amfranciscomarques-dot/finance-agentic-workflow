"""Portfolio & risk-analytics workflow.

The second concrete workflow in the framework. It reuses the shared data layer
(:class:`~finance_workflow.tools.MarketDataProvider`,
:class:`~finance_workflow.tools.FundamentalsProvider`) and the same
structured-output + Markdown-report pattern as the equity-research workflow.
"""
from __future__ import annotations

from typing import Any

from ...runtime import runtime_options
from ...workflow import Workflow
from .graph import build_graph


class PortfolioWorkflow(Workflow):
    name = "portfolio"
    title = "Portfolio & Risk Analytics"
    description = (
        "Take a holdings file (or inline positions), compute returns, volatility, "
        "drawdown, exposures, and concentration, then narrate the risks."
    )

    def build(self) -> Any:
        return build_graph()

    def initial_state(
        self,
        holdings: str | None = None,
        positions: list[dict[str, Any]] | None = None,
        offline: bool = False,
        **_: Any,
    ) -> dict[str, Any]:
        # `positions` (inline list) wins over `holdings` (CSV path); the latter is
        # what the CLI passes via --holdings.
        source: Any = positions if positions is not None else holdings
        if source is None:
            raise ValueError("Provide `positions` (a list) or `holdings` (a CSV path).")
        return {
            "holdings_source": source,
            **runtime_options(offline),
        }

    def result_markdown(self, final_state: dict[str, Any]) -> str:
        return final_state.get("report", "")

    def metadata(self, final_state: dict[str, Any]) -> dict[str, Any]:
        metrics = final_state.get("metrics", {})
        assessment = final_state.get("assessment", {})
        return {
            "label": "portfolio",
            "positions": metrics.get("concentration", {}).get("n_positions"),
            "total_value": metrics.get("total_value"),
            "risk_rating": assessment.get("risk_rating"),
            "as_of": metrics.get("as_of"),
            # Actual provenance: True only if Claude produced the assessment, not
            # merely that it was requested (the LLM call can fail into the fallback).
            "used_llm": final_state.get("used_llm", False),
            "sources": {"market": metrics.get("source")},
        }


__all__ = ["PortfolioWorkflow"]
