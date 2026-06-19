"""Shared test fixtures.

Ensures bundled sample data exists before the suite runs, so tests work on a
fresh checkout without a separate generation step.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_generator():
    path = PROJECT_ROOT / "scripts" / "generate_samples.py"
    spec = importlib.util.spec_from_file_location("generate_samples", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["generate_samples"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session", autouse=True)
def _ensure_samples():
    from finance_workflow.config import get_settings

    samples_dir = get_settings().samples_dir
    if not (samples_dir / "index.json").exists():
        _load_generator().generate_all(samples_dir)
    yield
