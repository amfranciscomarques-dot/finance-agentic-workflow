from __future__ import annotations

from finance_workflow.registry import registry


def test_equity_research_is_registered():
    # Importing the package's workflows registers built-ins.
    import finance_workflow.workflows  # noqa: F401

    assert "equity-research" in registry.names()
    wf = registry.get("equity-research")
    assert wf.title
    assert wf.description


def test_unknown_workflow_raises():
    import pytest

    with pytest.raises(KeyError):
        registry.get("does-not-exist")
