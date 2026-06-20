"""Minimal programmatic example: run the portfolio workflow.

    python examples/run_portfolio.py examples/sample_portfolio.csv

Runs offline (sample data + deterministic analyst) so it works with no API key.
Set ANTHROPIC_API_KEY and pass ``--live`` to use Claude.
"""
from __future__ import annotations

import sys
from pathlib import Path

from finance_workflow import run_workflow

DEFAULT_HOLDINGS = Path(__file__).resolve().parent / "sample_portfolio.csv"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    holdings = args[0] if args else str(DEFAULT_HOLDINGS)
    offline = "--live" not in sys.argv[1:]

    result = run_workflow("portfolio", holdings=holdings, offline=offline)

    meta = result.metadata
    print(f"=== Portfolio ({meta.get('positions')} positions) ===")
    print(f"Total value: {meta.get('total_value'):,}")
    print(f"Risk rating: {meta.get('risk_rating')}")
    print(f"Sources: {meta.get('sources')}\n")
    print(result.markdown)


if __name__ == "__main__":
    main()
