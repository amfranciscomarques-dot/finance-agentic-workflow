"""Saving workflow deliverables independently of the presentation layer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .workflow import WorkflowResult


def save_result(result: WorkflowResult, output_dir: Path, explicit: str | None = None) -> Path:
    """Write a memo; automatic filenames keep successive runs distinct."""
    if explicit:
        path = Path(explicit)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_%f")
        ticker = result.metadata.get("ticker")
        stem = f"{ticker}_{result.workflow}" if ticker else result.workflow
        path = output_dir / f"{stem}_{stamp}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.markdown, encoding="utf-8")
    return path
