"""Graph nodes for the market and news monitor workflow.

Pipeline:
1. ``scan_universe``: Pulls snapshots, fundamentals, and headlines across the universe.
2. ``detect_movers``: Calculates mover rankings, volatility outliers, and themes.
3. ``generate_digest``: Synthesizes structured digest with Claude (or deterministic fallback) and renders the Markdown report.
"""
from __future__ import annotations

import json
from typing import Any

from ...logging_utils import step, warn
from ...tools import MonitorProvider
from .prompts import (
    MONITOR_REPORT_SYSTEM,
    MONITOR_SYSTEM,
    monitor_human_prompt,
    monitor_report_human_prompt,
)
from .schema import MarketMonitorDigest, TickerMoverNote
from .state import MonitorState

# --------------------------------------------------------------------------- #
# Pipeline nodes
# --------------------------------------------------------------------------- #


def scan_universe(state: MonitorState) -> dict[str, Any]:
    step("Scanning universe data & news …")
    provider = MonitorProvider(allow_live=state.get("allow_live", True))
    scan = provider.scan_universe(
        tickers=state.get("tickers"),
        news_limit=state.get("news_limit", 3),
    )
    step(
        f"  scanned {len(scan['universe'])} tickers (source: {scan['source']}) · "
        f"{len(scan['news_feed'])} total news items"
    )
    return {"scan": scan}


def detect_movers(state: MonitorState) -> dict[str, Any]:
    step("Detecting market movers & volatility outliers …")
    scan = state["scan"]
    movers = scan.get("movers", {})
    top_g = movers.get("top_gainer") or "None"
    top_l = movers.get("top_loser") or "None"
    step(f"  top gainer: {top_g} · top loser: {top_l}")
    return {"movers": movers}


def generate_digest(state: MonitorState) -> dict[str, Any]:
    scan = state["scan"]
    packet = _scan_packet(scan)

    if state.get("use_llm"):
        try:
            step("Synthesizing market digest with Claude …")
            from ...llm import get_llm

            llm = get_llm().with_structured_output(MarketMonitorDigest)
            result: MarketMonitorDigest = llm.invoke(
                [("system", MONITOR_SYSTEM), ("human", monitor_human_prompt(packet))]
            )
            digest = result.model_dump()

            # Draft report with LLM
            step("Drafting market digest memo with Claude …")
            message = get_llm().invoke(
                [
                    ("system", MONITOR_REPORT_SYSTEM),
                    (
                        "human",
                        monitor_report_human_prompt(json.dumps(digest, indent=2), packet),
                    ),
                ]
            )
            report_text = (
                message.content if isinstance(message.content, str) else str(message.content)
            )
            return {
                "digest": digest,
                "digest_used_llm": True,
                "report": report_text.strip(),
                "report_used_llm": True,
            }
        except Exception as exc:
            warn(f"LLM monitor digest failed ({exc}); using deterministic fallback.")

    step("Synthesizing market digest (deterministic offline engine) …")
    digest = _fallback_digest(scan)
    report = _fallback_report(scan, digest)
    return {
        "digest": digest,
        "digest_used_llm": False,
        "report": report,
        "report_used_llm": False,
    }


# --------------------------------------------------------------------------- #
# Helpers & Fallback
# --------------------------------------------------------------------------- #


def _scan_packet(scan: dict[str, Any]) -> str:
    """Format universe scan data into a compact text block for LLM prompts."""
    lines = [
        f"UNIVERSE OVERVIEW (source: {scan.get('source')}, as of {scan.get('as_of')})",
        f"  total tickers: {scan['summary']['total_tickers']}",
        f"  average daily change: {scan['summary']['avg_daily_change_pct']}%",
        f"  gainers: {scan['summary']['gainers_count']} | losers: {scan['summary']['losers_count']}",
        "\nTICKER SNAPSHOTS:",
    ]
    for ticker, snap in scan.get("snapshots", {}).items():
        fund = scan.get("fundamentals", {}).get(ticker, {})
        lines.append(
            f"  - {ticker} ({fund.get('company_name', ticker)} | {fund.get('sector', 'n/a')}): "
            f"Close=${snap.get('last_close')} "
            f"DayChange={snap.get('daily_change_pct')}% "
            f"1Y={snap.get('return_1y_pct')}% "
            f"Vol={snap.get('annualized_volatility_pct')}% "
            f"52wHighDist={snap.get('pct_below_52w_high')}%"
        )

    lines.append(f"\nRECENT NEWS HEADLINES ({len(scan.get('news_feed', []))} items):")
    for item in scan.get("news_feed", [])[:10]:
        lines.append(
            f"  - [{item.get('published', '')}] ({item.get('ticker')}) {item.get('title')} ({item.get('publisher')})"
        )
        if item.get("summary"):
            lines.append(f"      {item.get('summary')}")

    return "\n".join(lines)


def _fallback_digest(scan: dict[str, Any]) -> dict[str, Any]:
    """Deterministic rule-based market digest."""
    summary = scan.get("summary", {})
    movers = scan.get("movers", {})
    news_by_ticker = scan.get("news_by_ticker", {})

    avg_chg = summary.get("avg_daily_change_pct", 0.0)
    gainers = summary.get("gainers_count", 0)
    losers = summary.get("losers_count", 0)

    if avg_chg > 0.75 and gainers > losers:
        sentiment = "Bullish"
    elif avg_chg < -0.75 and losers > gainers:
        sentiment = "Bearish"
    elif gainers > 0 and losers > 0:
        sentiment = "Mixed"
    else:
        sentiment = "Neutral"

    top_gainers_summary: list[dict[str, Any]] = []
    for g in movers.get("top_gainers", [])[:3]:
        tk = g["ticker"]
        news = news_by_ticker.get(tk, [])
        headline = news[0]["title"] if news else "Positive price momentum and accumulation."
        top_gainers_summary.append(
            TickerMoverNote(
                ticker=tk,
                move_pct=g.get("daily_change_pct", 0.0),
                driver_or_catalyst=headline,
                actionable_takeaway=f"Advancing with {g.get('daily_change_pct')}% daily gain; trailing 1Y return at {g.get('return_1y_pct')}%.",
            ).model_dump()
        )

    top_losers_summary: list[dict[str, Any]] = []
    for loser in movers.get("top_losers", [])[:3]:
        tk = loser["ticker"]
        news = news_by_ticker.get(tk, [])
        headline = news[0]["title"] if news else "Profit-taking or sector rotation pressure."
        top_losers_summary.append(
            TickerMoverNote(
                ticker=tk,
                move_pct=loser.get("daily_change_pct", 0.0),
                driver_or_catalyst=headline,
                actionable_takeaway=f"Decline of {loser.get('daily_change_pct')}%; 52-week drawdown currently {loser.get('pct_below_52w_high')}%.",
            ).model_dump()
        )

    vol_flags: list[str] = []
    for v in movers.get("most_volatile", [])[:2]:
        vol = v.get("annualized_volatility_pct")
        if vol and vol > 35:
            vol_flags.append(f"{v['ticker']} shows elevated volatility ({vol:.1f}% annualized).")

    if not vol_flags:
        vol_flags.append("Volatility across the universe remains within normal historical bands.")

    key_themes = [
        f"Universe average daily change settled at {avg_chg:+.2f}% with {gainers} advancers vs {losers} decliners.",
        "Technology and mega-cap growth names drive primary cross-sectional dispersion.",
        "Headline catalysts focus on earnings updates, AI infrastructure demand, and valuation discussions.",
    ]

    watchlist_alerts = [
        f"Monitor top gainer {movers.get('top_gainer', 'N/A')} for momentum continuation.",
        f"Track pullback support levels on top decliner {movers.get('top_loser', 'N/A')}.",
        "Re-scan on next market open or scheduled cron interval.",
    ]

    exec_summary = (
        f"The monitored universe of {summary.get('total_tickers', 0)} names reflects a {sentiment} posture "
        f"with an average daily return of {avg_chg:+.2f}%. Breadth shows {gainers} gainers and {losers} losers. "
        f"Generated deterministically by the offline market monitor engine."
    )

    return MarketMonitorDigest(
        market_sentiment=sentiment,
        executive_summary=exec_summary,
        top_gainers_summary=[TickerMoverNote(**n) for n in top_gainers_summary],
        top_losers_summary=[TickerMoverNote(**n) for n in top_losers_summary],
        volatility_and_risk_flags=vol_flags,
        key_themes=key_themes,
        watchlist_alerts=watchlist_alerts,
    ).model_dump()


def _fallback_report(scan: dict[str, Any], digest: dict[str, Any]) -> str:
    """Render template-based markdown daily digest."""
    summary = scan.get("summary", {})
    snapshots = scan.get("snapshots", {})
    fundamentals = scan.get("fundamentals", {})
    as_of = scan.get("as_of", "Recent")
    source = scan.get("source", "sample")

    gainers_rows = [
        f"| **{g.get('ticker')}** | {fundamentals.get(g.get('ticker'), {}).get('company_name', g.get('ticker'))} | "
        f"${snapshots.get(g.get('ticker'), {}).get('last_close')} | **{'+' if (g.get('move_pct') or 0) > 0 else ''}{g.get('move_pct')}%** | "
        f"{g.get('driver_or_catalyst')} |"
        for g in digest.get("top_gainers_summary", [])
    ]
    gainers_table = (
        "| Ticker | Company | Last Close | Daily Move | Primary Driver / Headline |\n| --- | --- | --- | --- | --- |\n"
        + "\n".join(gainers_rows)
        if gainers_rows
        else "_No significant advancing tickers._"
    )

    losers_rows = [
        f"| **{loser.get('ticker')}** | {fundamentals.get(loser.get('ticker'), {}).get('company_name', loser.get('ticker'))} | "
        f"${snapshots.get(loser.get('ticker'), {}).get('last_close')} | **{loser.get('move_pct')}%** | "
        f"{loser.get('driver_or_catalyst')} |"
        for loser in digest.get("top_losers_summary", [])
    ]
    losers_table = (
        "| Ticker | Company | Last Close | Daily Move | Primary Driver / Headline |\n| --- | --- | --- | --- | --- |\n"
        + "\n".join(losers_rows)
        if losers_rows
        else "_No significant declining tickers._"
    )

    theme_lines = "\n".join(f"- {t}" for t in digest.get("key_themes", []))
    alert_lines = "\n".join(f"- {a}" for a in digest.get("watchlist_alerts", []))
    vol_lines = "\n".join(f"- {v}" for v in digest.get("volatility_and_risk_flags", []))

    news_lines = "\n".join(
        f"- **[{item.get('published', '')}] ({item.get('ticker')})** {item.get('title')} — _{item.get('publisher', '')}_"
        for item in scan.get("news_feed", [])[:6]
    ) or "- _(no recent headlines in universe feed)_"

    return f"""# Market & News Watchlist Monitor

**Market Sentiment: {digest.get('market_sentiment')} | Universe: {summary.get('total_tickers')} Tickers | As of: {as_of}**

_Data sources: market={source}, news={source}. LLM: no (deterministic offline engine)._

## Executive Overview

{digest.get('executive_summary', '')}

## Top Advancers & Catalysts

{gainers_table}

## Top Decliners & Downside Risks

{losers_table}

## Key Market & Sector Themes

{theme_lines}

## Volatility & Outlier Activity

{vol_lines}

## Watchlist Alerts & Action Items

{alert_lines}

## Recent Headline Wire

{news_lines}

---

_Educational use only — not investment advice._
"""
