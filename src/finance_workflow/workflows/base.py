"""Compatibility re-export.

The base classes live at ``finance_workflow.workflow`` (top level) so the
registry can import them without pulling in the concrete workflows. Import from
there in new code; this module is kept so ``from .workflows.base import ...``
also works.
"""
from __future__ import annotations

from ..workflow import Workflow, WorkflowResult

__all__ = ["Workflow", "WorkflowResult"]
