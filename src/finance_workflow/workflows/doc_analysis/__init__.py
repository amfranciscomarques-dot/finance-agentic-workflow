"""Financial document analysis workflow.

The third concrete workflow in the framework. Ingests 10-K filings, earnings
releases, or PDFs, chunks the text, extracts key financial figures and risk
factors with exact source citations, and produces a structured Markdown memo.
"""
from __future__ import annotations

from typing import Any

from ...llm import llm_available
from ...workflow import Workflow
from .graph import build_graph


class DocumentAnalysisWorkflow(Workflow):
    name = "doc-analysis"
    title = "Financial Document Analysis"
    description = (
        "Ingest a 10-K filing, earnings release, or PDF, extract key figures and "
        "risks with source citations, and draft an analytical memo."
    )

    def build(self) -> Any:
        return build_graph()

    def initial_state(
        self,
        file: str | None = None,
        doc: str | None = None,
        ticker: str | None = None,
        offline: bool = False,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
        **_: Any,
    ) -> dict[str, Any]:
        source = file or doc
        return {
            "document_source": source,
            "ticker": ticker.upper() if ticker else None,
            "allow_live": not offline,
            "use_llm": llm_available() and not offline,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }

    def result_markdown(self, final_state: dict[str, Any]) -> str:
        return final_state.get("memo", "")

    def metadata(self, final_state: dict[str, Any]) -> dict[str, Any]:
        analysis = final_state.get("analysis", {})
        used_llm = bool(
            final_state.get("analysis_used_llm") and final_state.get("memo_used_llm")
        )
        return {
            "label": "doc-analysis",
            "company": final_state.get("company_name"),
            "ticker": final_state.get("ticker"),
            "doc_type": analysis.get("doc_type"),
            "period": analysis.get("period"),
            "metrics_extracted": len(analysis.get("key_metrics", [])),
            "risk_factors_count": len(analysis.get("risk_factors", [])),
            "used_llm": used_llm,
            "sources": {"document": final_state.get("doc_source")},
        }


__all__ = ["DocumentAnalysisWorkflow"]
