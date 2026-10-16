"""Equity-research workflow: the first concrete workflow in the framework."""
from __future__ import annotations

from typing import Any

from ...inputs import normalize_ticker, validate_news_limit
from ...runtime import runtime_options
from ...tools.base import company_name
from ...workflow import Workflow
from .graph import build_graph


class EquityResearchWorkflow(Workflow):
    name = "equity-research"
    title = "Equity Research Assistant"
    description = (
        "Gather market data, fundamentals, and news for a ticker, then "
        "draft a structured investment memo."
    )

    def build(self) -> Any:
        return build_graph()

    def initial_state(
        self,
        ticker: str,
        offline: bool = False,
        news_limit: int = 5,
        **_: Any,
    ) -> dict[str, Any]:
        ticker = normalize_ticker(ticker)
        return {
            "ticker": ticker,
            "company_name": company_name(ticker),
            **runtime_options(offline),
            "news_limit": validate_news_limit(news_limit),
        }

    def result_markdown(self, final_state: dict[str, Any]) -> str:
        return final_state.get("memo", "")

    def metadata(self, final_state: dict[str, Any]) -> dict[str, Any]:
        analysis = final_state.get("analysis", {})
        market = final_state.get("market", {})
        # Actual provenance: True only if Claude produced *both* reasoning outputs
        # (the structured analysis and the memo). If either degraded to the
        # deterministic fallback, the deliverable isn't wholly LLM-generated — so we
        # report what ran, not what was requested.
        used_llm = bool(
            final_state.get("analysis_used_llm") and final_state.get("memo_used_llm")
        )
        return {
            "ticker": final_state.get("ticker"),
            "company": final_state.get("company_name"),
            "recommendation": analysis.get("recommendation"),
            "confidence": analysis.get("confidence"),
            "as_of": market.get("as_of"),
            "used_llm": used_llm,
            "sources": {
                "market": market.get("source"),
                "fundamentals": final_state.get("fundamentals", {}).get("source"),
                "news": final_state.get("news", {}).get("source"),
            },
        }


__all__ = ["EquityResearchWorkflow"]
