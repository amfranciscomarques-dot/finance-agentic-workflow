"""Base contract that every workflow implements.

A *workflow* bundles a compiled LangGraph graph with the glue the CLI needs:
how to build initial state from user parameters, and how to turn the graph's
final state into a human-readable result. Keeping this surface small is what
lets new workflows (document analysis, portfolio analytics, news monitor) plug
into the registry and CLI without touching the core.

This lives at the package top level (not inside ``workflows/``) so the registry
can depend on it without importing the concrete workflows — that separation
keeps the import graph acyclic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowResult:
    """The outcome of one workflow run, ready for display or saving."""

    workflow: str
    params: dict[str, Any]
    markdown: str
    metadata: dict[str, Any] = field(default_factory=dict)
    state: dict[str, Any] = field(default_factory=dict)


class Workflow(ABC):
    """Abstract base class for a finance workflow.

    Subclasses set ``name``/``title``/``description`` and implement the methods
    below. ``build`` should return a compiled LangGraph graph.
    """

    #: Stable CLI identifier, e.g. ``"equity-research"``.
    name: str = ""
    #: Human-readable title.
    title: str = ""
    #: One-line description shown by ``finwf list``.
    description: str = ""

    @abstractmethod
    def build(self) -> Any:
        """Return a compiled LangGraph graph (exposes ``.invoke``)."""

    @abstractmethod
    def initial_state(self, **params: Any) -> dict[str, Any]:
        """Construct the graph's initial state from CLI/user parameters."""

    @abstractmethod
    def result_markdown(self, final_state: dict[str, Any]) -> str:
        """Extract the primary deliverable (e.g. the memo) as Markdown."""

    def metadata(self, final_state: dict[str, Any]) -> dict[str, Any]:
        """Optional small summary (recommendation, data sources, ...)."""
        return {}
