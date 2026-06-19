"""Workflow registry + the top-level runner.

Workflows register themselves by name; the CLI and examples discover and run
them through this module. This indirection is what makes the framework
extensible — adding a workflow is a ``registry.register(...)`` call, after
which it appears in ``finwf list`` and is runnable via ``finwf run <name>``.
"""
from __future__ import annotations

from typing import Any

from .workflow import Workflow, WorkflowResult


class WorkflowRegistry:
    """A name -> Workflow mapping with simple discovery helpers."""

    def __init__(self) -> None:
        self._workflows: dict[str, Workflow] = {}

    def register(self, workflow: Workflow) -> Workflow:
        if not workflow.name:
            raise ValueError(f"{type(workflow).__name__} must define a non-empty `name`.")
        if workflow.name in self._workflows:
            raise ValueError(f"Workflow '{workflow.name}' is already registered.")
        self._workflows[workflow.name] = workflow
        return workflow

    def get(self, name: str) -> Workflow:
        try:
            return self._workflows[name]
        except KeyError:
            available = ", ".join(sorted(self._workflows)) or "(none)"
            raise KeyError(f"Unknown workflow '{name}'. Available: {available}") from None

    def names(self) -> list[str]:
        return sorted(self._workflows)

    def all(self) -> list[Workflow]:
        return [self._workflows[n] for n in self.names()]


#: The process-wide registry. Importing ``finance_workflow.workflows`` populates it.
registry = WorkflowRegistry()


def run_workflow(name: str, **params: Any) -> WorkflowResult:
    """Build and execute a registered workflow, returning its result.

    Ensures workflows are imported/registered (lazy) before lookup.
    """
    # Importing the workflows package triggers self-registration of each workflow.
    from . import workflows  # noqa: F401  (import for side effects)

    workflow = registry.get(name)
    graph = workflow.build()
    state = workflow.initial_state(**params)
    final_state: dict[str, Any] = graph.invoke(state)
    return WorkflowResult(
        workflow=name,
        params=params,
        markdown=workflow.result_markdown(final_state),
        metadata=workflow.metadata(final_state),
        state=final_state,
    )
