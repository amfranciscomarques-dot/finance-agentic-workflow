"""``finwf`` — command-line entry point.

    finwf list                                  # show available workflows
    finwf info equity-research                  # describe one workflow
    finwf run equity-research --ticker AAPL     # run it (uses Claude if a key is set)
    finwf run equity-research --ticker AAPL --offline   # deterministic, no key/network
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import workflows  # noqa: F401 — import for side effect: registers workflows
from .config import get_settings
from .llm import llm_available
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
        mode = "Claude (ANTHROPIC_API_KEY set)" if llm_available() else "offline (no API key)"
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

    if args.offline:
        _print(console, "[dim]Running in offline mode (sample data + deterministic analyst).[/dim]")
    elif not llm_available():
        _print(
            console,
            "[yellow]No ANTHROPIC_API_KEY found — falling back to the deterministic "
            "analyst. Set the key (or use --offline) for Claude analysis.[/yellow]",
        )

    try:
        result = run_workflow(
            args.workflow,
            ticker=args.ticker,
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

        summary = (
            f"[bold]{meta.get('company')} ({meta.get('ticker')})[/bold]\n"
            f"Recommendation: [bold]{meta.get('recommendation')}[/bold] "
            f"({meta.get('confidence')} confidence)\n"
            f"As of: {meta.get('as_of')}   "
            f"LLM: {'yes' if meta.get('used_llm') else 'no (deterministic)'}\n"
            f"Sources: {meta.get('sources')}"
        )
        console.print(Panel(summary, title="Result", title_align="left"))
        console.print(Markdown(result.markdown))
    else:  # pragma: no cover
        print(result.markdown)


def _save(result, output_dir: Path, explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
    else:
        ticker = result.metadata.get("ticker", "output")
        stamp = date.today().isoformat()
        path = output_dir / f"{ticker}_{result.workflow}_{stamp}.md"
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
    p_run.add_argument("workflow", help="Workflow name, e.g. equity-research")
    p_run.add_argument("--ticker", help="Ticker symbol, e.g. AAPL")
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
