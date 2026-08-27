"""Market & News monitor workflow.

The fourth concrete workflow in the framework. Scans a universe/watchlist of
tickers, calculates top gainers, losers, and volatility metrics, gathers recent
news, and synthesizes an institutional watchlist digest with Claude (or
deterministic fallback).
"""
from __future__ import annotations

from typing import Any

from ...llm import llm_available
from ...workflow import Workflow
from .graph import build_graph


class MonitorWorkflow(Workflow):
    name = "monitor"
    title = "Market & News Monitor"
    description = (
        "Scan a universe of tickers, detect top movers and volatility outliers, "
        "summarize headlines, and generate a watchlist digest."
    )

    def build(self) -> Any:
        return build_graph()

    def initial_state(
        self,
        tickers: list[str] | str | None = None,
        watchlist: list[str] | str | None = None,
        offline: bool = False,
        news_limit: int = 3,
        **_: Any,
    ) -> dict[str, Any]:
        target = tickers or watchlist
        if isinstance(target, str):
            target_list = [t.strip().upper() for t in target.split(",") if t.strip()]
        elif isinstance(target, (list, tuple, set)):
            target_list = [str(t).strip().upper() for t in target if str(t).strip()]
        else:
            target_list = ["AAPL", "MSFT", "NVDA"]

        return {
            "tickers": target_list,
            "allow_live": not offline,
            "use_llm": llm_available() and not offline,
            "news_limit": news_limit,
        }

    def result_markdown(self, final_state: dict[str, Any]) -> str:
        return final_state.get("report", "")

    def metadata(self, final_state: dict[str, Any]) -> dict[str, Any]:
        scan = final_state.get("scan", {})
        digest = final_state.get("digest", {})
        movers = scan.get("movers", {})
        used_llm = bool(
            final_state.get("digest_used_llm") and final_state.get("report_used_llm")
        )
        return {
            "label": "monitor",
            "universe_size": len(final_state.get("tickers", [])),
            "market_sentiment": digest.get("market_sentiment"),
            "top_gainer": movers.get("top_gainer"),
            "top_loser": movers.get("top_loser"),
            "as_of": scan.get("as_of"),
            "used_llm": used_llm,
            "sources": {"market": scan.get("source"), "news": scan.get("source")},
        }


__all__ = ["MonitorWorkflow"]
