"""``finwf`` — command-line entry point.

    finwf list                                  # show available workflows
    finwf info equity-research                  # describe one workflow
    finwf run equity-research --ticker AAPL     # run it (uses Claude if a key is set)
    finwf run equity-research --ticker AAPL --offline   # deterministic, no key/network
    finwf run portfolio --holdings examples/sample_portfolio.csv --offline
    finwf run doc-analysis --ticker AAPL --offline
    finwf run monitor --tickers AAPL,MSFT,NVDA --offline
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import workflows  # noqa: F401 — import for side effect: registers workflows
from .config import get_settings
from .llm import llm_available, resolve_model_provider
from .registry import registry, run_workflow


def _console():
    try:
        from rich.console import Console

        return Console()
    except Exception:  # pragma: no cover
        return None


def cmd_list(_: argparse.Namespace) -> int:
    console = _console()
    if console is not None:
        from rich.table import Table

        table = Table(title="Available workflows", title_justify="left")
        table.add_column("name", style="bold cyan")
        table.add_column("description")
        for wf in registry.all():
            table.add_row(wf.name, wf.description)
        console.print(table)
        model, provider = resolve_model_provider()
        label = f"{provider}:{model}" if provider else model
        mode = f"{label} (API key set)" if llm_available() else "offline (no API key)"
        console.print(f"\nLLM mode: [bold]{mode}[/bold]")
    else:  # pragma: no cover
        for wf in registry.all():
            print(f"{wf.name}\t{wf.description}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    try:
        wf = registry.get(args.name)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"{wf.title} ({wf.name})\n")
    print(wf.description)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    console = _console()
    settings = get_settings()

    if args.workflow == "equity-research" and not args.ticker:
        print("error: --ticker is required for equity-research", file=sys.stderr)
        return 2
    if args.workflow == "portfolio" and not args.holdings:
        print("error: --holdings is required for portfolio", file=sys.stderr)
        return 2

    if args.offline:
        _print(console, "[dim]Running in offline mode (sample data + deterministic analyst).[/dim]")
    elif not llm_available():
        _print(
            console,
            "[yellow]No ANTHROPIC_API_KEY found — falling back to the deterministic "
            "analyst. Set the key (or use --offline) for Claude analysis.[/yellow]",
        )

    try:
        # Each workflow's initial_state ignores params it doesn't use (via **_),
        # so a single passthrough covers every workflow.
        result = run_workflow(
            args.workflow,
            ticker=args.ticker,
            holdings=args.holdings,
            file=args.file,
            tickers=args.tickers,
            offline=args.offline,
            news_limit=args.news_limit,
        )
    except KeyError as exc:  # unknown workflow
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - surface runtime errors cleanly
        print(f"error: workflow failed: {exc}", file=sys.stderr)
        return 1

    _render_result(console, result)

    if not args.no_save:
        path = _save(result, settings.output_dir, args.output)
        _print(console, f"\n[green]Saved memo to[/green] {path}")
    return 0


# --------------------------------------------------------------------------- #
# Rendering / saving helpers
# --------------------------------------------------------------------------- #


def _render_result(console, result) -> None:
    meta = result.metadata
    if console is not None:
        from rich.markdown import Markdown
        from rich.panel import Panel

        if meta.get("recommendation"):  # equity-research style summary
            summary = (
                f"[bold]{meta.get('company')} ({meta.get('ticker')})[/bold]\n"
                f"Recommendation: [bold]{meta.get('recommendation')}[/bold] "
                f"({meta.get('confidence')} confidence)\n"
                f"As of: {meta.get('as_of')}   "
                f"LLM: {'yes' if meta.get('used_llm') else 'no (deterministic)'}\n"
                f"Sources: {meta.get('sources')}"
            )
        elif meta.get("label") == "doc-analysis":
            summary = (
                f"[bold]Financial Document Analysis: {meta.get('company')}"
                f" ({meta.get('ticker') or 'N/A'})[/bold]\n"
                f"Document Type: {meta.get('doc_type')} | Period: {meta.get('period')}\n"
                f"Metrics Extracted: {meta.get('metrics_extracted')} | Risks: {meta.get('risk_factors_count')}\n"
                f"LLM: {'yes' if meta.get('used_llm') else 'no (deterministic)'} | Sources: {meta.get('sources')}"
            )
        elif meta.get("label") == "monitor":
            summary = (
                f"[bold]Market & News Monitor Digest[/bold]\n"
                f"Sentiment: [bold]{meta.get('market_sentiment')}[/bold] | Universe Size: {meta.get('universe_size')}\n"
                f"Top Gainer: {meta.get('top_gainer')} | Top Loser: {meta.get('top_loser')}\n"
                f"As of: {meta.get('as_of')} | LLM: {'yes' if meta.get('used_llm') else 'no (deterministic)'}"
            )
        else:  # generic summary for other workflows (e.g. portfolio)
            llm = "yes" if meta.get("used_llm") else "no (deterministic)"
            rows = [f"{k}: {v}" for k, v in meta.items() if k != "used_llm"]
            summary = "\n".join(rows + [f"LLM: {llm}"])
        console.print(Panel(summary, title="Result", title_align="left"))
        console.print(Markdown(result.markdown))
    else:  # pragma: no cover
        print(result.markdown)


def _save(result, output_dir: Path, explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
    else:
        stamp = date.today().isoformat()
        ticker = result.metadata.get("ticker")
        stem = f"{ticker}_{result.workflow}" if ticker else result.workflow
        path = output_dir / f"{stem}_{stamp}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.markdown, encoding="utf-8")
    return path


def _print(console, message: str) -> None:
    if console is not None:
        console.print(message)
    else:  # pragma: no cover
        # Strip the simplest rich markup for plain output.
        import re

        print(re.sub(r"\[/?[^\]]+\]", "", message))


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="finwf",
        description="Finance Agentic Workflow — run LangGraph finance workflows.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List available workflows.")
    p_list.set_defaults(func=cmd_list)

    p_info = sub.add_parser("info", help="Describe a workflow.")
    p_info.add_argument("name", help="Workflow name, e.g. equity-research")
    p_info.set_defaults(func=cmd_info)

    p_run = sub.add_parser("run", help="Run a workflow.")
    p_run.add_argument("workflow", help="Workflow name, e.g. equity-research, doc-analysis, monitor, portfolio")
    p_run.add_argument("--ticker", help="Ticker symbol, e.g. AAPL (equity-research, doc-analysis)")
    p_run.add_argument(
        "--holdings", help="Path to a holdings CSV with ticker,shares columns (portfolio)"
    )
    p_run.add_argument(
        "--file", help="Path to a financial document file (PDF, TXT, MD) (doc-analysis)"
    )
    p_run.add_argument(
        "--tickers", help="Comma-separated ticker list, e.g. AAPL,MSFT,NVDA (monitor)"
    )
    p_run.add_argument(
        "--offline",
        action="store_true",
        help="Force sample data + deterministic analyst (no API key or network).",
    )
    p_run.add_argument(
        "--news-limit", type=int, default=5, help="Max news headlines to gather (default 5)."
    )
    p_run.add_argument("--output", help="Explicit output file path for the memo.")
    p_run.add_argument(
        "--no-save", action="store_true", help="Do not write the memo to disk."
    )
    p_run.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
