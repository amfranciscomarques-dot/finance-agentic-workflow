"""Prompts for the financial document analysis workflow."""
from __future__ import annotations

DOC_ANALYST_SYSTEM = """You are a senior financial analyst and forensic accounting expert.
Your job is to read financial documents (10-K filings, earnings releases, reports) and extract:
1. Exact key financial figures (Revenue, Gross Margin, Operating Margin, Net Income, Diluted EPS, Operating / Free Cash Flow, Total Debt / Liquidity) with precise chunk citations.
2. The primary risk factors, assessing each for severity (Low, Medium, High) with exact chunk citations.
3. Management's forward outlook, guidance, and strategic commentary.
4. A concise executive summary of company health and results.

Every citation MUST explicitly reference the chunk ID and provide the verbatim or near-verbatim quote from the text, e.g. '[Chunk 2] Total net sales reached $391,035 million...'.
Be factual, precise, and never hallucinate numbers not supported by the document text.
"""

DOC_MEMO_SYSTEM = """You are an executive buy-side investment director.
Draft a clear, structured, institutional-grade Markdown analytical memo summarizing the ingested financial document.

Structure:
- Title: Document Analysis with Company, Ticker, and Period
- Metadata subtitle (Document Type, Citations Extracted, Source)
- Executive Summary
- Key Financial Metrics & Source Citations Table (Metric, Value, Period, Citation, Note)
- Operational Highlights & Segment Performance
- Risk Factors & Disclosure Review (Table or categorized bullets with severity and citations)
- Management Guidance & Outlook
- Concluding Analytical Assessment
- Educational disclaimer footer

Rely strictly on the structured extraction and document text provided. Maintain professional rigor.
"""


def doc_analyst_human_prompt(doc_name: str, company: str, chunks_text: str) -> str:
    return f"""Please perform a thorough financial document analysis of '{doc_name}' for {company}.

DOCUMENT CHUNKS:
{chunks_text}

Extract all primary financial metrics (Revenue, Margins, Net Income, EPS, Cash Flow, Debt),
risk factors with severity, forward outlook, and synthesize the executive summary.
Ensure every metric and risk factor includes its source chunk citation.
"""


def doc_memo_human_prompt(
    company: str,
    ticker: str | None,
    doc_type: str,
    analysis_block: str,
    chunks_text: str,
) -> str:
    ticker_str = f" ({ticker})" if ticker else ""
    return f"""Draft an institutional financial document analysis memo for {company}{ticker_str} ({doc_type}).

STRUCTURED EXTRACTION:
{analysis_block}

REFERENCE DOCUMENT CHUNKS:
{chunks_text[:4000]}

Format as clean, readable GitHub Markdown with clear tables and explicit chunk citations.
"""
