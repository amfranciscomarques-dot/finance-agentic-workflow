"""Minimal programmatic example: run the equity-research workflow.

    python examples/run_equity_research.py AAPL

Runs offline (sample data + deterministic analyst) so it works with no API key.
Set ANTHROPIC_API_KEY and pass ``--live`` to use Claude.
"""
from __future__ import annotations

import sys

from finance_workflow import run_workflow


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    ticker = args[0] if args else "AAPL"
    offline = "--live" not in sys.argv[1:]

    result = run_workflow("equity-research", ticker=ticker, offline=offline)

    print(f"=== {result.metadata.get('company')} ({result.metadata.get('ticker')}) ===")
    print(f"Recommendation: {result.metadata.get('recommendation')} "
          f"({result.metadata.get('confidence')} confidence)")
    print(f"Sources: {result.metadata.get('sources')}\n")
    print(result.markdown)


if __name__ == "__main__":
    main()
