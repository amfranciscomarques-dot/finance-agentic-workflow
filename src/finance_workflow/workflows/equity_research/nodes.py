"""Graph nodes for the equity-research workflow.

Each function takes the current state and returns a *partial* state update
(LangGraph merges it in). The three ``gather_*`` nodes call data providers; the
``analyze`` and ``write_memo`` nodes call Claude — or, when no API key is set
(or ``--offline``), fall back to deterministic logic so the graph always runs.
"""
from __future__ import annotations

import json
from typing import Any

from ...logging_utils import step, warn
from ...tools import FundamentalsProvider, MarketDataProvider, NewsProvider
from .prompts import (
    ANALYST_SYSTEM,
    MEMO_SYSTEM,
    analyst_human_prompt,
    memo_human_prompt,
)
from .schema import AnalysisResult
from .state import EquityResearchState

# --------------------------------------------------------------------------- #
# Data-gathering nodes (run in parallel)
# --------------------------------------------------------------------------- #


def gather_market_data(state: EquityResearchState) -> dict[str, Any]:
    ticker = state["ticker"]
    step(f"Gathering market data for {ticker} …")
    snapshot = MarketDataProvider(allow_live=state.get("allow_live", True)).snapshot(ticker)
    step(f"  market data source: {snapshot['source']}")
    return {"market": snapshot}


def gather_fundamentals(state: EquityResearchState) -> dict[str, Any]:
    ticker = state["ticker"]
    step(f"Gathering fundamentals for {ticker} …")
    data = FundamentalsProvider(allow_live=state.get("allow_live", True)).get(ticker)
    step(f"  fundamentals source: {data['source']}")
    return {"fundamentals": data}


def gather_news(state: EquityResearchState) -> dict[str, Any]:
    ticker = state["ticker"]
    step(f"Gathering news for {ticker} …")
    data = NewsProvider(allow_live=state.get("allow_live", True)).get(
        ticker, limit=state.get("news_limit", 5)
    )
    step(f"  news source: {data['source']} ({len(data['items'])} items)")
    return {"news": data}


# --------------------------------------------------------------------------- #
# Reasoning nodes (Claude, with deterministic fallback)
# --------------------------------------------------------------------------- #


def analyze(state: EquityResearchState) -> dict[str, Any]:
    packet = _data_packet(state)
    if state.get("use_llm"):
        try:
            step("Analyzing with Claude …")
            from ...llm import get_llm

            llm = get_llm().with_structured_output(AnalysisResult)
            result: AnalysisResult = llm.invoke(
                [
                    ("system", ANALYST_SYSTEM),
                    ("human", analyst_human_prompt(state["ticker"], state["company_name"], packet)),
                ]
            )
            return {"analysis": result.model_dump(), "analysis_used_llm": True}
        except Exception as exc:  # network, auth, parsing — degrade gracefully
            warn(f"LLM analysis failed ({exc}); using deterministic fallback.")
    else:
        step("Analyzing (deterministic offline analyst) …")
    return {"analysis": _fallback_analysis(state), "analysis_used_llm": False}


def write_memo(state: EquityResearchState) -> dict[str, Any]:
    analysis = state["analysis"]
    packet = _data_packet(state)
    if state.get("use_llm"):
        try:
            step("Drafting memo with Claude …")
            from ...llm import get_llm

            analysis_block = json.dumps(analysis, indent=2)
            message = get_llm().invoke(
                [
                    ("system", MEMO_SYSTEM),
                    (
                        "human",
                        memo_human_prompt(
                            state["ticker"], state["company_name"], analysis_block, packet
                        ),
                    ),
                ]
            )
            text = message.content if isinstance(message.content, str) else str(message.content)
            return {"memo": text.strip(), "memo_used_llm": True}
        except Exception as exc:
            warn(f"LLM memo drafting failed ({exc}); using template fallback.")
    else:
        step("Drafting memo (template) …")
    return {"memo": _fallback_memo(state, analysis), "memo_used_llm": False}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _data_packet(state: EquityResearchState) -> str:
    """Render gathered data into a compact, LLM-friendly text block."""
    market = state.get("market", {})
    fundamentals = state.get("fundamentals", {})
    news = state.get("news", {})

    lines: list[str] = []
    lines.append(f"PRICE METRICS (source: {market.get('source', 'n/a')})")
    for key in (
        "as_of",
        "last_close",
        "daily_change_pct",
        "return_1m_pct",
        "return_3m_pct",
        "return_6m_pct",
        "return_1y_pct",
        "high_52w",
        "low_52w",
        "pct_below_52w_high",
        "annualized_volatility_pct",
    ):
        if market.get(key) is not None:
            lines.append(f"  {key}: {market[key]}")

    lines.append(f"\nFUNDAMENTALS (source: {fundamentals.get('source', 'n/a')})")
    for key in (
        "sector",
        "industry",
        "market_cap",
        "trailing_pe",
        "forward_pe",
        "price_to_book",
        "profit_margin",
        "revenue_growth",
        "dividend_yield",
        "beta",
    ):
        if fundamentals.get(key) is not None:
            lines.append(f"  {key}: {fundamentals[key]}")
    if fundamentals.get("summary"):
        lines.append(f"  summary: {fundamentals['summary']}")

    items = news.get("items", [])
    lines.append(f"\nRECENT NEWS (source: {news.get('source', 'n/a')}, {len(items)} items)")
    for item in items:
        published = item.get("published", "")
        title = item.get("title", "")
        publisher = item.get("publisher", "")
        lines.append(f"  - [{published}] {title} ({publisher})")
        if item.get("summary"):
            lines.append(f"      {item['summary']}")

    return "\n".join(lines)


def _fallback_analysis(state: EquityResearchState) -> dict[str, Any]:
    """A transparent, rule-based stand-in for the LLM analyst.

    Deliberately simple and explainable: it scores momentum and valuation to
    produce a Buy/Hold/Sell. It exists so the graph completes end-to-end with
    no API key — not to be a serious model.
    """
    market = state.get("market", {})
    fundamentals = state.get("fundamentals", {})

    ret_1y = _num(market.get("return_1y_pct"))
    ret_3m = _num(market.get("return_3m_pct"))
    vol = _num(market.get("annualized_volatility_pct"))
    fwd_pe = _num(fundamentals.get("forward_pe"))
    margin = _num(fundamentals.get("profit_margin"))
    rev_growth = _num(fundamentals.get("revenue_growth"))

    score = 0
    strengths: list[str] = []
    risks: list[str] = []

    if ret_1y is not None:
        if ret_1y > 15:
            score += 1
            strengths.append(f"Positive 1-year momentum ({ret_1y:.1f}%).")
        elif ret_1y < -10:
            score -= 1
            risks.append(f"Weak 1-year price trend ({ret_1y:.1f}%).")
    if rev_growth is not None and rev_growth > 0.10:
        score += 1
        strengths.append(f"Double-digit revenue growth ({rev_growth * 100:.1f}%).")
    if margin is not None and margin > 0.15:
        score += 1
        strengths.append(f"Healthy profit margin ({margin * 100:.1f}%).")
    if fwd_pe is not None:
        if fwd_pe > 35:
            score -= 1
            risks.append(f"Rich forward valuation (forward P/E {fwd_pe:.1f}).")
        elif fwd_pe < 15:
            score += 1
            strengths.append(f"Undemanding forward valuation (forward P/E {fwd_pe:.1f}).")
    if vol is not None and vol > 40:
        risks.append(f"Elevated volatility ({vol:.1f}% annualized).")
    if ret_3m is not None and ret_3m < -10:
        risks.append(f"Negative 3-month drift ({ret_3m:.1f}%).")

    if score >= 2:
        recommendation = "Buy"
    elif score <= -1:
        recommendation = "Sell"
    else:
        recommendation = "Hold"

    if not strengths:
        strengths.append("No standout strengths identified from the available metrics.")
    if not risks:
        risks.append("No major red flags identified from the available metrics.")

    confidence = "Low"  # a rule-based stand-in should not overstate confidence
    company = state.get("company_name", state["ticker"])
    thesis = (
        f"{company} screens as a '{recommendation}' on a simple momentum-and-valuation "
        f"rule set. This is a deterministic offline estimate (no LLM); treat it as a "
        f"baseline, not a considered view."
    )
    return AnalysisResult(
        thesis=thesis,
        strengths=strengths,
        risks=risks,
        valuation_view=_valuation_blurb(fwd_pe),
        recommendation=recommendation,
        confidence=confidence,
    ).model_dump()


def _valuation_blurb(fwd_pe: float | None) -> str:
    if fwd_pe is None:
        return "Valuation multiples were unavailable in the data packet."
    if fwd_pe > 35:
        return f"At a forward P/E of {fwd_pe:.1f}, the stock prices in strong growth expectations."
    if fwd_pe < 15:
        return f"A forward P/E of {fwd_pe:.1f} looks undemanding versus the broad market."
    return f"A forward P/E of {fwd_pe:.1f} is roughly in line with the broad market."


def _fallback_memo(state: EquityResearchState, analysis: dict[str, Any]) -> str:
    """Template-based memo used when the LLM is unavailable."""
    market = state.get("market", {})
    fundamentals = state.get("fundamentals", {})
    news = state.get("news", {})
    ticker = state["ticker"]
    company = state.get("company_name", ticker)

    strengths = "\n".join(f"- {s}" for s in analysis.get("strengths", []))
    risks = "\n".join(f"- {r}" for r in analysis.get("risks", []))

    metrics_rows = [
        ("Last close", market.get("last_close")),
        ("1Y return %", market.get("return_1y_pct")),
        ("3M return %", market.get("return_3m_pct")),
        ("52w high / low", f"{market.get('high_52w')} / {market.get('low_52w')}"),
        ("Annualized vol %", market.get("annualized_volatility_pct")),
        ("Sector", fundamentals.get("sector")),
        ("Forward P/E", fundamentals.get("forward_pe")),
        ("Profit margin", fundamentals.get("profit_margin")),
        ("Revenue growth", fundamentals.get("revenue_growth")),
    ]
    table = "| Metric | Value |\n| --- | --- |\n" + "\n".join(
        f"| {label} | {value} |" for label, value in metrics_rows if value is not None
    )

    headlines = "\n".join(
        f"- {item.get('published', '')} — {item.get('title', '')}"
        for item in news.get("items", [])[:5]
    ) or "- (no recent headlines in the data packet)"

    sources = (
        f"market={market.get('source', 'n/a')}, "
        f"fundamentals={fundamentals.get('source', 'n/a')}, "
        f"news={news.get('source', 'n/a')}"
    )

    return f"""# {company} ({ticker}) — Investment Memo

**Recommendation: {analysis.get('recommendation')} ({analysis.get('confidence')} confidence)**

_Generated by the deterministic offline analyst. Data sources: {sources}. As of {market.get('as_of', 'n/a')}._

## Thesis

{analysis.get('thesis', '')}

## What we like

{strengths}

## Key risks

{risks}

## Valuation & price action

{analysis.get('valuation_view', '')}

## The numbers

{table}

## Recent headlines

{headlines}

_Educational use only — not investment advice._
"""


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
