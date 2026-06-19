"""Lightweight, rich-aware console helpers.

Kept separate so workflows can emit progress without importing CLI concerns.
Falls back to plain ``print`` if ``rich`` is unavailable.
"""
from __future__ import annotations

try:  # pragma: no cover - presentation only
    from rich.console import Console

    _console: "Console | None" = Console()
except Exception:  # pragma: no cover
    _console = None


def step(message: str) -> None:
    """Print a workflow progress line."""
    if _console is not None:
        _console.print(f"[dim]›[/dim] {message}")
    else:
        print(f"> {message}")


def warn(message: str) -> None:
    if _console is not None:
        _console.print(f"[yellow]![/yellow] {message}")
    else:
        print(f"! {message}")
