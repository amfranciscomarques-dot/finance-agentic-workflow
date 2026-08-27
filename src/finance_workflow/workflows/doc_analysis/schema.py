"""Structured output schema for financial document analysis.

The ``extract_financials`` node asks Claude to return this object (via
``with_structured_output``), ensuring key financial figures, source citations,
and risk disclosures are validated and typed.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MetricCitation(BaseModel):
    """A financial figure extracted from the document with citation."""

    metric_name: str = Field(
        description="Name of the financial metric, e.g. 'Revenue', 'Gross Margin', 'Operating Margin', 'Net Income', 'Diluted EPS', 'Operating Cash Flow', 'Free Cash Flow', 'Total Debt'."
    )
    value: str = Field(
        description="Extracted value formatted with units (e.g. '$391,035 million', '46.2%', '$6.75 per share')."
    )
    period: str | None = Field(
        default=None,
        description="Fiscal period covered if specified (e.g. 'FY2025', 'Q4 2025').",
    )
    citation: str = Field(
        description="Exact source chunk citation and quote (e.g. '[Chunk 2] Total net sales reached $391,035 million in fiscal 2025...')."
    )
    context: str | None = Field(
        default=None,
        description="Brief note on YoY growth, driver, or significance.",
    )


class RiskFactorCitation(BaseModel):
    """A risk factor disclosure with severity and chunk citation."""

    title: str = Field(description="Short title or category of the risk factor.")
    description: str = Field(
        description="Concise description of the specific risk and potential operational impact."
    )
    severity: Literal["Low", "Medium", "High"] = Field(
        description="Assessed severity based on filing language."
    )
    citation: str = Field(
        description="Source chunk reference (e.g. '[Chunk 4] 1. Global Supply Chain Concentration: The Company depends on...')."
    )


class DocumentAnalysisResult(BaseModel):
    """Structured extraction and analysis of a financial filing or report."""

    company_name: str = Field(description="Name of the reporting company.")
    ticker: str | None = Field(default=None, description="Stock ticker symbol if identified.")
    doc_type: str = Field(
        description="Document classification (e.g. '10-K Annual Report', 'Earnings Release')."
    )
    period: str | None = Field(default=None, description="Reporting period covered.")
    executive_summary: str = Field(
        description="A 3-5 sentence executive synthesis of operational performance and strategic highlights."
    )
    key_metrics: list[MetricCitation] = Field(
        description="Key financial metrics extracted with exact source citations."
    )
    risk_factors: list[RiskFactorCitation] = Field(
        description="Disclosed risk factors categorized with severity and chunk citations."
    )
    outlook: str = Field(
        description="Management commentary on business outlook, forward guidance, and growth drivers."
    )
