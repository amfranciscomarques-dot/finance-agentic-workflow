from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from finance_workflow import run_workflow
from finance_workflow.tools import DocumentProvider
from finance_workflow.workflows.doc_analysis import DocumentAnalysisWorkflow
from finance_workflow.workflows.doc_analysis.graph import build_graph
from finance_workflow.workflows.doc_analysis.schema import (
    DocumentAnalysisResult,
    MetricCitation,
    RiskFactorCitation,
)


def test_offline_run_produces_memo():
    result = run_workflow("doc-analysis", ticker="AAPL", offline=True)

    assert result.metadata["label"] == "doc-analysis"
    assert result.metadata["company"] == "Apple Inc."
    assert result.metadata["ticker"] == "AAPL"
    assert result.metadata["metrics_extracted"] >= 4
    assert result.metadata["risk_factors_count"] >= 2
    assert result.metadata["used_llm"] is False
    assert result.metadata["sources"]["document"] == "sample"

    memo = result.markdown
    assert "Financial Document Analysis" in memo
    assert "Executive Summary" in memo
    assert "Key Financial Metrics & Source Citations" in memo
    assert "Risk Factors & Governance Disclosures" in memo
    assert "[Chunk" in memo
    assert "Educational and analytical use only" in memo


def test_unrecognized_document_does_not_invent_disclosures():
    provider = DocumentProvider(allow_live=False)
    analysis = provider.extract_metrics_deterministic(provider.chunk("A brief company notice."))
    assert analysis["key_metrics"] == []
    assert analysis["risk_factors"] == []
    assert "No explicit management outlook" in analysis["outlook"]
    assert "healthy cash generation" not in analysis["executive_summary"]


def test_run_with_custom_file():
    doc_path = Path(__file__).resolve().parents[1] / "examples" / "sample_earnings_release.txt"
    result = run_workflow("doc-analysis", file=str(doc_path), offline=True)

    assert result.metadata["sources"]["document"] == "file"
    assert result.metadata["metrics_extracted"] >= 4
    assert "Revenue / Total Net Sales" in result.markdown
    assert "[Chunk" in result.markdown


def test_document_provider_chunking():
    provider = DocumentProvider(allow_live=False)
    doc = provider.load_document(ticker="MSFT")
    chunks = provider.chunk(doc["text"], chunk_size=500, chunk_overlap=100)

    assert len(chunks) >= 2
    assert chunks[0]["chunk_id"] == 1
    assert "text" in chunks[0]
    assert "section" in chunks[0]
    assert chunks[0]["start_char"] >= 0
    assert chunks[0]["end_char"] > chunks[0]["start_char"]


def test_document_provider_search():
    provider = DocumentProvider(allow_live=False)
    doc = provider.load_document(ticker="NVDA")
    chunks = provider.chunk(doc["text"])
    matches = provider.search_chunks(chunks, "GPU Compute and Networking", top_k=2)

    assert len(matches) <= 2
    assert any("GPU" in m["text"] or "Compute" in m["text"] for m in matches)


def test_missing_file_raises():
    provider = DocumentProvider(allow_live=False)
    with pytest.raises(FileNotFoundError):
        provider.load_document(source="non_existent_file_12345.pdf")


def test_graph_state_has_all_data():
    graph = build_graph()
    state = graph.invoke(
        {
            "ticker": "AAPL",
            "document_source": None,
            "allow_live": False,
            "use_llm": False,
            "chunk_size": 1000,
            "chunk_overlap": 150,
        }
    )
    assert state["document"]["source"] == "sample"
    assert len(state["chunks"]) > 0
    assert len(state["analysis"]["key_metrics"]) >= 4
    assert state["memo"]


def test_used_llm_reports_actual_provenance_not_intent(monkeypatch):
    """Requesting the LLM with no key must degrade to fallback and report used_llm=False."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    state = build_graph().invoke(
        {
            "ticker": "AAPL",
            "document_source": None,
            "allow_live": False,
            "use_llm": True,
            "chunk_size": 1000,
            "chunk_overlap": 150,
        }
    )

    assert state["analysis_used_llm"] is False
    assert state["memo_used_llm"] is False
    assert state["memo"]
    assert DocumentAnalysisWorkflow().metadata(state)["used_llm"] is False


# --------------------------------------------------------------------------- #
# LLM success-branch coverage (mocked Claude)
# --------------------------------------------------------------------------- #

_ANALYSIS = DocumentAnalysisResult(
    company_name="Apple Inc.",
    ticker="AAPL",
    doc_type="10-K Annual Report",
    period="FY2025",
    executive_summary="SENTINEL summary from Claude.",
    key_metrics=[
        MetricCitation(
            metric_name="Revenue",
            value="$391.04B",
            period="FY2025",
            citation="[Chunk 2] Total net sales reached $391,035 million...",
            context="+2.0% YoY expansion.",
        )
    ],
    risk_factors=[
        RiskFactorCitation(
            title="Supply Chain",
            description="Geographic supplier concentration in Asia.",
            severity="High",
            citation="[Chunk 3] Concentrated third-party manufacturing partners...",
        )
    ],
    outlook="Continued mid-single-digit momentum.",
)


class _StructuredStub:
    def __init__(self, result):
        self._result = result

    def invoke(self, _messages):
        return self._result


class _LLMStub:
    def __init__(self, analysis, memo_text, *, memo_raises=False):
        self._analysis = analysis
        self._memo_text = memo_text
        self._memo_raises = memo_raises

    def with_structured_output(self, _schema):
        return _StructuredStub(self._analysis)

    def invoke(self, _messages):
        if self._memo_raises:
            raise RuntimeError("simulated memo API failure")
        return SimpleNamespace(content=self._memo_text)


def _invoke_graph():
    return build_graph().invoke(
        {
            "ticker": "AAPL",
            "document_source": None,
            "allow_live": False,
            "use_llm": True,
            "chunk_size": 1000,
            "chunk_overlap": 150,
        }
    )


def test_used_llm_true_when_both_reasoning_nodes_run(monkeypatch):
    memo_text = "# SENTINEL document memo from Claude."
    monkeypatch.setattr(
        "finance_workflow.llm.get_llm", lambda **_: _LLMStub(_ANALYSIS, memo_text)
    )

    state = _invoke_graph()

    assert state["analysis_used_llm"] is True
    assert state["memo_used_llm"] is True
    assert state["analysis"]["company_name"] == "Apple Inc."
    assert state["memo"] == memo_text

    meta = DocumentAnalysisWorkflow().metadata(state)
    assert meta["used_llm"] is True
    assert meta["metrics_extracted"] == 1
    assert meta["risk_factors_count"] == 1


def test_used_llm_false_when_memo_node_degrades(monkeypatch):
    monkeypatch.setattr(
        "finance_workflow.llm.get_llm",
        lambda **_: _LLMStub(_ANALYSIS, memo_text=None, memo_raises=True),
    )

    state = _invoke_graph()

    assert state["analysis_used_llm"] is True
    assert state["memo_used_llm"] is False
    assert state["memo"]
    assert DocumentAnalysisWorkflow().metadata(state)["used_llm"] is False
