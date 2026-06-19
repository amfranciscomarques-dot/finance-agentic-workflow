"""Workflow package — importing it registers all built-in workflows.

To add a workflow: implement a :class:`~finance_workflow.workflow.Workflow`
subclass in a submodule, then register it here. It will immediately appear in
``finwf list`` and be runnable via ``finwf run <name>``.
"""
from __future__ import annotations

from ..registry import registry
from .equity_research import EquityResearchWorkflow

# Register built-in workflows (idempotent: this module is imported once).
registry.register(EquityResearchWorkflow())

__all__ = ["registry"]
