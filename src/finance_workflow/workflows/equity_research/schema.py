"""Structured output schema for the analysis step.

The ``analyze`` node asks Claude to return *this* object (via
``with_structured_output``), so the rest of the graph works with validated,
typed fields instead of free-form text.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """A buy-side analyst's structured view of a single name."""

    thesis: str = Field(description="A 2-4 sentence core investment thesis.")
    strengths: list[str] = Field(
        description="Key strengths / bull points, each a short phrase or sentence."
    )
    risks: list[str] = Field(
        description="Key risks / bear points, each a short phrase or sentence."
    )
    valuation_view: str = Field(
        description="A brief view on valuation given the multiples and recent price action."
    )
    recommendation: Literal["Buy", "Hold", "Sell"] = Field(
        description="Overall stance on the stock."
    )
    confidence: Literal["Low", "Medium", "High"] = Field(
        description="Confidence in the recommendation given the available data."
    )
