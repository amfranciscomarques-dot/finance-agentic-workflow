"""Structured output schema for the portfolio assessment step.

The ``assess`` node asks Claude to return *this* object (via
``with_structured_output``), so the report renderer works with validated, typed
fields instead of free-form text — the same pattern as the equity-research
workflow's ``AnalysisResult``.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PortfolioAssessment(BaseModel):
    """A risk analyst's structured read of a portfolio."""

    overall_view: str = Field(description="A 2-4 sentence summary of the portfolio's profile.")
    diversification: str = Field(
        description="A short comment on diversification given the weights and sector exposures."
    )
    key_risks: list[str] = Field(
        description="Key portfolio-level risks, each a short phrase or sentence."
    )
    suggestions: list[str] = Field(
        description="Actionable, non-personalized observations or rebalancing ideas."
    )
    risk_rating: Literal["Low", "Moderate", "Elevated", "High"] = Field(
        description="Overall risk rating given concentration, volatility, and beta."
    )
