"""Minimal programmatic example: run the document analysis workflow.

    python examples/run_doc_analysis.py examples/sample_earnings_release.txt
    python examples/run_doc_analysis.py --ticker AAPL

Runs offline (sample data + deterministic extractor) so it works with no API key.
Set ANTHROPIC_API_KEY and pass ``--live`` to use Claude.
"""
from __future__ import annotations

import sys
from pathlib import Path

from finance_workflow import run_workflow

DEFAULT_DOC = Path(__file__).resolve().parent / "sample_earnings_release.txt"


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    file_path = args[0] if args else str(DEFAULT_DOC)
    offline = "--live" not in sys.argv[1:]

    result = run_workflow("doc-analysis", file=file_path, offline=offline)

    meta = result.metadata
    print(f"=== {meta.get('company')} ({meta.get('ticker') or 'N/A'}) — {meta.get('doc_type')} ===")
    print(f"Period: {meta.get('period')} | Citations: {meta.get('metrics_extracted')} metrics, {meta.get('risk_factors_count')} risks")
    print(f"LLM: {'yes' if meta.get('used_llm') else 'no (deterministic)'} | Sources: {meta.get('sources')}\n")
    print(result.markdown)


if __name__ == "__main__":
    main()
