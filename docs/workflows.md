# Workflows

The framework is designed so multiple finance workflows share one tool layer,
registry, and CLI. One is implemented; three more are planned and slot in
without changing the core.

## ✅ Equity Research Assistant — `equity-research`

**Implemented.** Given a ticker, gather market data, fundamentals, and recent
news in parallel, have Claude form a structured view, and draft an investment
memo.

```powershell
finwf run equity-research --ticker AAPL            # uses Claude if a key is set
finwf run equity-research --ticker AAPL --offline  # deterministic, no key/network
```

Output: a Markdown memo (printed and saved to `outputs/`), plus a metadata
summary (recommendation, confidence, data sources, as-of date).

See [architecture.md](architecture.md) for the graph anatomy.

## 🚧 Financial Document Analysis — `doc-analysis` (planned)

Ingest a filing (10-K / earnings release / PDF), chunk and extract key figures,
and summarize highlights and risk factors with citations back to the source.

- New tool: a `DocumentProvider` (PDF/HTML loader) + a retrieval step.
- New graph: `load → chunk → extract (structured) → summarize`.
- Reuses: registry, CLI, `llm.py`, the `Workflow` base, structured-output pattern.

## 🚧 Portfolio & Risk Analytics — `portfolio` (planned)

Take a holdings file (CSV) and compute returns, volatility, drawdown, exposures,
and simple risk metrics, then have Claude narrate the results. Plays directly to
fixed-income / ALM analytics.

- New tool: a `PortfolioProvider` (positions + price history → metrics).
- New graph: `load_positions → compute_metrics → narrate`.
- Reuses: `MarketDataProvider`, registry, CLI, memo-writing pattern.

## 🚧 Market & News Monitor — `monitor` (planned)

Watch a list of tickers, summarize notable moves and headlines, and flag items of
interest — designed to run on a schedule.

- New tool: extends `NewsProvider`; adds a mover-detection step.
- New graph: `scan_universe → fan-out per-ticker summaries → digest`.
- Reuses: `MarketDataProvider`, `NewsProvider`, registry, CLI.

---

To build one of these (or your own), see
[adding-a-workflow.md](adding-a-workflow.md).
