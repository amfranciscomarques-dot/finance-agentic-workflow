"""Graph nodes for the financial document analysis workflow.

Pipeline:
1. ``load_document``: Ingests document from file path, raw string, or bundled sample.
2. ``chunk_document``: Chunks text into structured segments with chunk IDs.
3. ``extract_financials``: Uses Claude (or deterministic extractor) for structured metrics and risks.
4. ``summarize``: Drafts an institutional Markdown memo deliverable.
"""
from __future__ import annotations

import json
from typing import Any

from ...logging_utils import step, warn
from ...tools import DocumentProvider
from .prompts import (
    DOC_ANALYST_SYSTEM,
    DOC_MEMO_SYSTEM,
    doc_analyst_human_prompt,
    doc_memo_human_prompt,
)
from .schema import DocumentAnalysisResult
from .state import DocAnalysisState

# --------------------------------------------------------------------------- #
# Pipeline nodes
# --------------------------------------------------------------------------- #


def load_document(state: DocAnalysisState) -> dict[str, Any]:
    step("Loading financial document …")
    provider = DocumentProvider(allow_live=state.get("allow_live", True))
    doc = provider.load_document(
        source=state.get("document_source"),
        ticker=state.get("ticker"),
    )
    step(f"  loaded '{doc['doc_name']}' (source: {doc['source']})")
    return {
        "document": doc,
        "ticker": doc.get("ticker"),
        "company_name": doc.get("company_name", "Company"),
        "doc_source": doc.get("source", "sample"),
    }


def chunk_document(state: DocAnalysisState) -> dict[str, Any]:
    step("Chunking document text …")
    provider = DocumentProvider(allow_live=state.get("allow_live", True))
    text = state["document"]["text"]
    chunks = provider.chunk(
        text,
        chunk_size=state.get("chunk_size", 1000),
        chunk_overlap=state.get("chunk_overlap", 150),
    )
    step(f"  created {len(chunks)} indexed chunks")
    return {"chunks": chunks}


def extract_financials(state: DocAnalysisState) -> dict[str, Any]:
    chunks = state["chunks"]
    chunks_text = _format_chunks(chunks)
    doc_name = state["document"]["doc_name"]
    company = state.get("company_name", "Company")

    if state.get("use_llm"):
        try:
            step("Extracting financial metrics & risks with Claude …")
            from ...llm import get_llm

            llm = get_llm().with_structured_output(DocumentAnalysisResult)
            result: DocumentAnalysisResult = llm.invoke(
                [
                    ("system", DOC_ANALYST_SYSTEM),
                    ("human", doc_analyst_human_prompt(doc_name, company, chunks_text)),
                ]
            )
            return {
                "analysis": result.model_dump(),
                "analysis_used_llm": True,
            }
        except Exception as exc:
            warn(f"LLM document extraction failed ({exc}); using deterministic fallback.")

    step("Extracting financial metrics (deterministic offline engine) …")
    provider = DocumentProvider(allow_live=state.get("allow_live", True))
    fallback = provider.extract_metrics_deterministic(
        chunks,
        company_name=company,
        ticker=state.get("ticker"),
    )
    return {"analysis": fallback, "analysis_used_llm": False}


def summarize(state: DocAnalysisState) -> dict[str, Any]:
    analysis = state["analysis"]
    chunks = state["chunks"]
    chunks_text = _format_chunks(chunks)
    company = state.get("company_name", "Company")
    ticker = state.get("ticker")
    doc_type = analysis.get("doc_type", "Financial Document")

    if state.get("use_llm"):
        try:
            step("Drafting document analysis memo with Claude …")
            from ...llm import get_llm

            analysis_block = json.dumps(analysis, indent=2)
            message = get_llm().invoke(
                [
                    ("system", DOC_MEMO_SYSTEM),
                    (
                        "human",
                        doc_memo_human_prompt(
                            company, ticker, doc_type, analysis_block, chunks_text
                        ),
                    ),
                ]
            )
            text = message.content if isinstance(message.content, str) else str(message.content)
            return {"memo": text.strip(), "memo_used_llm": True}
        except Exception as exc:
            warn(f"LLM memo drafting failed ({exc}); using template fallback.")

    step("Drafting document memo (template) …")
    return {"memo": _fallback_memo(state, analysis), "memo_used_llm": False}


# --------------------------------------------------------------------------- #
# Helpers & Fallback
# --------------------------------------------------------------------------- #


def _format_chunks(chunks: list[dict[str, Any]]) -> str:
    """Format chunks into numbered reference blocks for LLM prompt context."""
    blocks = []
    for c in chunks:
        blocks.append(f"--- [Chunk {c['chunk_id']}] Section: {c.get('section', 'General')} ---\n{c['text']}")
    return "\n\n".join(blocks)


def _fallback_memo(state: DocAnalysisState, analysis: dict[str, Any]) -> str:
    """Institutional template-based markdown memo for offline runs."""
    company = state.get("company_name", "Company")
    ticker = state.get("ticker")
    ticker_str = f" ({ticker})" if ticker else ""
    doc_type = analysis.get("doc_type", "Financial Document")
    period = analysis.get("period", "Recent Period")
    doc_source = state.get("doc_source", "sample")

    metrics = analysis.get("key_metrics", [])
    if metrics:
        metrics_table = "| Financial Metric | Value | Period | Source Citation | Notes |\n| --- | --- | --- | --- | --- |\n" + "\n".join(
            f"| {m.get('metric_name')} | **{m.get('value')}** | {m.get('period', period)} | `{m.get('citation')}` | {m.get('context', '')} |"
            for m in metrics
        )
    else:
        metrics_table = "_No financial figures identified in the document text._"

    risks = analysis.get("risk_factors", [])
    if risks:
        risks_table = "| Risk Category | Severity | Description | Source Citation |\n| --- | --- | --- | --- |\n" + "\n".join(
            f"| **{r.get('title')}** | `{r.get('severity')}` | {r.get('description')} | `{r.get('citation')}` |"
            for r in risks
        )
    else:
        risks_table = "_No specific risk disclosures identified._"

    return f"""# Financial Document Analysis: {company}{ticker_str}

**Document: {doc_type} | Period: {period} | Source: {doc_source}**

_Generated by the deterministic offline document analyst with chunk citations. As of {period}._

## Executive Summary

{analysis.get('executive_summary', '')}

## Key Financial Metrics & Source Citations

{metrics_table}

## Risk Factors & Governance Disclosures

{risks_table}

## Management Guidance & Outlook

{analysis.get('outlook', '')}

---

_Educational and analytical use only — not investment advice._
"""
