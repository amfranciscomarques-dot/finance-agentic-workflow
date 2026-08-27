from __future__ import annotations

import pytest

from finance_workflow.registry import registry


def test_all_workflows_are_registered():
    import finance_workflow.workflows  # noqa: F401

    names = registry.names()
    assert "equity-research" in names
    assert "portfolio" in names
    assert "doc-analysis" in names
    assert "monitor" in names

    for name in ["equity-research", "portfolio", "doc-analysis", "monitor"]:
        wf = registry.get(name)
        assert wf.title
        assert wf.description
        assert wf.name == name


def test_unknown_workflow_raises():
    with pytest.raises(KeyError):
        registry.get("does-not-exist")
