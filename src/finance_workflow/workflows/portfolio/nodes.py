"""Graph nodes for the portfolio & risk-analytics workflow.

Pipeline: ``load_positions`` parses the holdings, ``compute_metrics`` prices them
and derives portfolio analytics (reusing the shared data layer), and ``narrate``
forms a structured assessment — with Claude, or a deterministic fallback when no
API key is set — and renders the Markdown report.
"""
from __future__ import annotations

import json
from typing import Any

from ...logging_utils import step, warn
from ...tools import PortfolioProvider
from .prompts import ASSESSOR_SYSTEM, assessor_human_prompt
from .schema import PortfolioAssessment
from .state import PortfolioState

# --------------------------------------------------------------------------- #
# Pipeline nodes
# --------------------------------------------------------------------------- #


def load_positions(state: PortfolioState) -> dict[str, Any]:
    step("Loading positions …")
    positions = PortfolioProvider(allow_live=state.get("allow_live", True)).load_positions(
        state.get("holdings_source")
    )
    step(f"  loaded {len(positions)} position(s)")
    return {"positions": positions}


def compute_metrics(state: PortfolioState) -> dict[str, Any]:
    step("Computing portfolio metrics …")
    metrics = PortfolioProvider(allow_live=state.get("allow_live", True)).metrics(state["positions"])
    step(f"  data source: {metrics['source']} · total value: {metrics['total_value']:,}")
    return {"metrics": metrics}


def narrate(state: PortfolioState) -> dict[str, Any]:
    metrics = state["metrics"]
    packet = _metrics_packet(metrics)
    used_llm = False

    if state.get("use_llm"):
        try:
            step("Assessing portfolio with Claude …")
            from ...llm import get_llm

            llm = get_llm().with_structured_output(PortfolioAssessment)
            result: PortfolioAssessment = llm.invoke(
                [("system", ASSESSOR_SYSTEM), ("human", assessor_human_prompt(packet))]
            )
            assessment = result.model_dump()
            used_llm = True
        except Exception as exc:  # network, auth, parsing — degrade gracefully
            warn(f"LLM assessment failed ({exc}); using deterministic fallback.")
            assessment = _fallback_assessment(metrics)
    else:
        step("Assessing portfolio (deterministic offline analyst) …")
        assessment = _fallback_assessment(metrics)

    return {
        "assessment": assessment,
        "used_llm": used_llm,
        "report": _render_report(metrics, assessment),
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _metrics_packet(metrics: dict[str, Any]) -> str:
    """Render metrics into a compact, LLM-friendly text block."""
    lines: list[str] = [
        f"PORTFOLIO (source: {metrics.get('source', 'n/a')}, as of {metrics.get('as_of', 'n/a')})",
        f"  total_value: {metrics.get('total_value')}",
        f"  annualized_volatility_pct: {metrics.get('annualized_volatility_pct')}",
        f"  max_drawdown_pct: {metrics.get('max_drawdown_pct')}",
        f"  weighted_beta: {metrics.get('weighted_beta')}",
    ]
    returns = metrics.get("returns", {})
    lines.append(f"  trailing_returns_pct: {json.dumps(returns)}")

    conc = metrics.get("concentration", {})
    lines.append(
        f"  concentration: top_weight_pct={conc.get('top_weight_pct')}, "
        f"hhi={conc.get('hhi')}, n_positions={conc.get('n_positions')}"
    )

    lines.append("\nPOSITIONS (weight %):")
    for p in metrics.get("positions", []):
        lines.append(
            f"  - {p['ticker']} ({p.get('sector', 'n/a')}): {p['weight'] * 100:.1f}% "
            f"value={p['value']} 1y={p.get('return_1y_pct')} beta={p.get('beta')}"
        )

    lines.append("\nSECTOR EXPOSURE (%):")
    for sector, pct in metrics.get("sector_exposure", {}).items():
        lines.append(f"  - {sector}: {pct}")

    return "\n".join(lines)


def _fallback_assessment(metrics: dict[str, Any]) -> dict[str, Any]:
    """A transparent, rule-based stand-in for the LLM assessment.

    Rates risk from concentration, volatility, and beta. Deliberately simple and
    explainable; it exists so the graph completes end-to-end with no API key.
    """
    conc = metrics.get("concentration", {})
    top = _num(conc.get("top_weight_pct")) or 0.0
    hhi = _num(conc.get("hhi")) or 0.0
    n = conc.get("n_positions", 0)
    vol = _num(metrics.get("annualized_volatility_pct"))
    beta = _num(metrics.get("weighted_beta"))

    risks: list[str] = []
    suggestions: list[str] = []
    score = 0

    if top > 40:
        score += 2
        risks.append(f"High single-name concentration (top position {top:.1f}% of the book).")
        suggestions.append("Consider trimming the largest position to reduce idiosyncratic risk.")
    elif top > 25:
        score += 1
        risks.append(f"Moderate single-name concentration (top position {top:.1f}%).")

    if hhi > 0.3:
        score += 1
        risks.append(f"Concentrated overall (HHI {hhi:.2f}; 1/N would be {1 / max(n, 1):.2f}).")

    if vol is not None and vol > 35:
        score += 1
        risks.append(f"Elevated portfolio volatility ({vol:.1f}% annualized).")
    if beta is not None and beta > 1.2:
        score += 1
        risks.append(f"High market sensitivity (weighted beta {beta:.2f}).")
    elif beta is not None and beta < 0.8:
        suggestions.append(f"Defensive tilt (weighted beta {beta:.2f}); may lag in strong rallies.")

    sectors = metrics.get("sector_exposure", {})
    if sectors:
        top_sector, top_sector_pct = next(iter(sectors.items()))
        if top_sector_pct > 50:
            score += 1
            risks.append(f"Heavy sector concentration ({top_sector} at {top_sector_pct:.1f}%).")
            suggestions.append(f"Diversify away from {top_sector} to balance sector exposure.")

    rating = "High" if score >= 4 else "Elevated" if score >= 3 else "Moderate" if score >= 1 else "Low"

    if not risks:
        risks.append("No major concentration or volatility red flags from the available metrics.")
    if not suggestions:
        suggestions.append("Maintain current diversification; rebalance periodically.")

    overall = (
        f"A {n}-position portfolio with a '{rating}' risk profile on a simple "
        f"concentration-volatility-beta rule set. This is a deterministic offline estimate "
        f"(no LLM); treat it as a baseline, not a considered view."
    )
    diversification = (
        f"Top position is {top:.1f}% of the book; HHI is {hhi:.2f} across {n} names "
        f"(an equal-weight book would be {1 / max(n, 1):.2f})."
    )
    return PortfolioAssessment(
        overall_view=overall,
        diversification=diversification,
        key_risks=risks,
        suggestions=suggestions,
        risk_rating=rating,
    ).model_dump()


def _render_report(metrics: dict[str, Any], assessment: dict[str, Any]) -> str:
    """Template-based Markdown report from the metrics and the assessment."""
    returns = metrics.get("returns", {})
    conc = metrics.get("concentration", {})

    positions_table = "| Ticker | Weight | Value | Sector | 1Y % | Beta |\n| --- | --- | --- | --- | --- | --- |\n" + "\n".join(
        f"| {p['ticker']} | {p['weight'] * 100:.1f}% | {p['value']:,} | "
        f"{p.get('sector', 'n/a')} | {p.get('return_1y_pct')} | {p.get('beta')} |"
        for p in metrics.get("positions", [])
    )

    metrics_rows = [
        ("Total value", f"{metrics.get('total_value'):,}"),
        ("1Y return %", returns.get("return_1y_pct")),
        ("3M return %", returns.get("return_3m_pct")),
        ("Annualized vol %", metrics.get("annualized_volatility_pct")),
        ("Max drawdown %", metrics.get("max_drawdown_pct")),
        ("Weighted beta", metrics.get("weighted_beta")),
        ("Top position %", conc.get("top_weight_pct")),
        ("HHI", conc.get("hhi")),
    ]
    metrics_table = "| Metric | Value |\n| --- | --- |\n" + "\n".join(
        f"| {label} | {value} |" for label, value in metrics_rows if value is not None
    )

    sector_lines = "\n".join(
        f"- {sector}: {pct}%" for sector, pct in metrics.get("sector_exposure", {}).items()
    ) or "- (no sector data)"

    risks = "\n".join(f"- {r}" for r in assessment.get("key_risks", []))
    suggestions = "\n".join(f"- {s}" for s in assessment.get("suggestions", []))

    return f"""# Portfolio Risk Report

**Risk rating: {assessment.get('risk_rating')}**

_Data source: {metrics.get('source', 'n/a')}. As of {metrics.get('as_of', 'n/a')}._

## Overview

{assessment.get('overall_view', '')}

## Diversification

{assessment.get('diversification', '')}

## Key risks

{risks}

## Suggestions

{suggestions}

## Holdings

{positions_table}

## Portfolio metrics

{metrics_table}

## Sector exposure

{sector_lines}

_Educational use only — not investment advice._
"""


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
