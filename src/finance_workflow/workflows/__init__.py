"""Workflow package — importing it registers all built-in workflows.

To add a workflow: implement a :class:`~finance_workflow.workflow.Workflow`
subclass in a submodule, then register it here. It will immediately appear in
``finwf list`` and be runnable via ``finwf run <name>``.
"""
from __future__ import annotations

from ..registry import registry
from .doc_analysis import DocumentAnalysisWorkflow
from .equity_research import EquityResearchWorkflow
from .monitor import MonitorWorkflow
from .portfolio import PortfolioWorkflow

# Register built-in workflows (idempotent: this module is imported once).
registry.register(EquityResearchWorkflow())
registry.register(PortfolioWorkflow())
registry.register(DocumentAnalysisWorkflow())
registry.register(MonitorWorkflow())

__all__ = [
    "registry",
    "EquityResearchWorkflow",
    "PortfolioWorkflow",
    "DocumentAnalysisWorkflow",
    "MonitorWorkflow",
]
