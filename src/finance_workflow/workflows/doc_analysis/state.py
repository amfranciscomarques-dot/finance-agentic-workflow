"""Graph state for the document-analysis workflow.

Pipeline:
``load_document`` -> ``chunk_document`` -> ``extract_financials`` -> ``summarize``
"""
from __future__ import annotations

from typing import Any, TypedDict


class DocAnalysisState(TypedDict, total=False):
    # Inputs
    document_source: Any  # file path, raw text, or None
    ticker: str | None
    allow_live: bool
    use_llm: bool
    chunk_size: int
    chunk_overlap: int

    # Ingested / chunked
    document: dict[str, Any]  # loaded document payload from DocumentProvider
    chunks: list[dict[str, Any]]  # indexed chunks
    company_name: str
    doc_source: str  # "file", "sample", or "custom"

    # Extraction & Deliverable
    analysis: dict[str, Any]  # DocumentAnalysisResult.model_dump()
    analysis_used_llm: bool  # whether Claude performed the extraction
    memo: str  # Markdown deliverable
    memo_used_llm: bool  # whether Claude wrote the memo
