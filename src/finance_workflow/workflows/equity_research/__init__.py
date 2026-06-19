"""Equity-research workflow: the first concrete workflow in the framework."""
from __future__ import annotations

from typing import Any

from ...config import get_settings
from ...llm import llm_available
from ...tools.base import company_name
from ...workflow import Workflow
from .graph import build_graph


class EquityResearchWorkflow(Workflow):
    name = "equity-research"
    title = "Equity Research Assistant"
    description = (
        "Gather market data, fundamentals, and news for a ticker, then have Claude "
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
        settings = get_settings()
        # `offline` forces both sample data and the deterministic analyst, for a
        # fully reproducible, no-network, no-key run.
        allow_live = settings.allow_live_data and not offline
        use_llm = llm_available() and not offline
        return {
            "ticker": ticker.upper(),
            "company_name": company_name(ticker),
            "allow_live": allow_live,
            "use_llm": use_llm,
            "news_limit": news_limit,
        }

    def result_markdown(self, final_state: dict[str, Any]) -> str:
        return final_state.get("memo", "")

    def metadata(self, final_state: dict[str, Any]) -> dict[str, Any]:
        analysis = final_state.get("analysis", {})
        market = final_state.get("market", {})
        return {
            "ticker": final_state.get("ticker"),
            "company": final_state.get("company_name"),
            "recommendation": analysis.get("recommendation"),
            "confidence": analysis.get("confidence"),
            "as_of": market.get("as_of"),
            "used_llm": final_state.get("use_llm"),
            "sources": {
                "market": market.get("source"),
                "fundamentals": final_state.get("fundamentals", {}).get("source"),
                "news": final_state.get("news", {}).get("source"),
            },
        }


__all__ = ["EquityResearchWorkflow"]
