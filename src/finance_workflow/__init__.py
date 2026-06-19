"""Finance Agentic Workflow.

A documented, extensible LangGraph framework for finance AI workflows.

Public surface:
    get_settings()      -> runtime configuration
    registry            -> the workflow registry (name -> Workflow)
    run_workflow(...)    -> convenience runner used by the CLI and examples
"""
from __future__ import annotations

from .config import Settings, get_settings
from .registry import registry, run_workflow

__all__ = ["Settings", "get_settings", "registry", "run_workflow", "__version__"]

__version__ = "0.1.0"
