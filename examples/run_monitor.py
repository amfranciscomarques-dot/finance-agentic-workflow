"""Minimal programmatic example: run the market & news monitor workflow.

    python examples/run_monitor.py AAPL,MSFT,NVDA

Runs offline (sample data + deterministic monitor) so it works with no API key.
Set ANTHROPIC_API_KEY and pass ``--live`` to use Claude.
"""
from __future__ import annotations

import sys

from finance_workflow import run_workflow


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    tickers = args[0] if args else "AAPL,MSFT,NVDA"
    offline = "--live" not in sys.argv[1:]

    result = run_workflow("monitor", tickers=tickers, offline=offline)

    meta = result.metadata
    print(f"=== Watchlist Monitor ({meta.get('universe_size')} tickers) ===")
    print(f"Sentiment: {meta.get('market_sentiment')} | As of: {meta.get('as_of')}")
    print(f"Top Gainer: {meta.get('top_gainer')} | Top Loser: {meta.get('top_loser')}")
    print(f"LLM: {'yes' if meta.get('used_llm') else 'no (deterministic)'} | Sources: {meta.get('sources')}\n")
    print(result.markdown)


if __name__ == "__main__":
    main()
