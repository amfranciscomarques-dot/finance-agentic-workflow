# Workflows

The framework is designed so multiple finance workflows share one tool layer,
registry, and CLI. All four core workflows are fully implemented and available
out of the box.

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

## ✅ Financial Document Analysis — `doc-analysis`

**Implemented.** Ingest a 10-K filing, earnings release, PDF, or text report, chunk
the text into indexed segments, extract key figures (Revenue, Net Income, Margins,
EPS, Cash Flow, Debt) and risk factors with precise source citations back to chunk
IDs, and draft an institutional Markdown analytical memo.

```powershell
finwf run doc-analysis --file examples/sample_earnings_release.txt            # analyze custom filing
finwf run doc-analysis --ticker AAPL --offline                                # analyze bundled 10-K offline
```

Output: a Markdown document analysis memo (printed and saved to `outputs/`), plus
a metadata summary (company, document type, period, citation count, and `used_llm`).

- Tool: `DocumentProvider` (file/sample ingestion, chunking with overlap, section tagging, deterministic extraction engine).
- Graph: `load_document → chunk_document → extract_financials → summarize`.
- Reuses: registry, CLI, `llm.py`, `Workflow` base, and structured Pydantic output (`DocumentAnalysisResult`).

## ✅ Portfolio & Risk Analytics — `portfolio`

**Implemented.** Take a holdings file (CSV) — or inline positions — and compute
position weights, portfolio-level returns, volatility, max drawdown, sector
exposures, weighted beta, and concentration (top weight / HHI), then have Claude
narrate the risks. Plays directly to fixed-income / ALM analytics.

```powershell
finwf run portfolio --holdings examples/sample_portfolio.csv            # uses Claude if a key is set
finwf run portfolio --holdings examples/sample_portfolio.csv --offline  # deterministic, no key/network
```

Output: a Markdown risk report (printed and saved to `outputs/`), plus a
metadata summary (risk rating, total value, position count, data source, and
`used_llm` — which reports whether Claude actually produced the assessment or it
fell back to the deterministic analyst).

- Tool: `PortfolioProvider` (positions + price history → metrics).
- Graph: `load_positions → compute_metrics → narrate`.
- Reuses: `MarketDataProvider`, `FundamentalsProvider`, registry, CLI,
  structured-output + report pattern.

## ✅ Market & News Monitor — `monitor`

**Implemented.** Watch a list of tickers or an entire universe, detect top movers
(advancers, decliners, volatility outliers), aggregate and deduplicate recent news
headlines, and generate a watchlist digest with catalysts and risk flags.

```powershell
finwf run monitor --tickers AAPL,MSFT,NVDA            # uses Claude if a key is set
finwf run monitor --tickers AAPL,MSFT,NVDA --offline  # deterministic, no key/network
```

Output: a Markdown watchlist digest (printed and saved to `outputs/`), plus a
metadata summary (market sentiment, universe size, top movers, as-of date, and `used_llm`).

- Tool: `MonitorProvider` (universe price scanning, mover ranking, news aggregation).
- Graph: `scan_universe → detect_movers → generate_digest`.
- Reuses: `MarketDataProvider`, `FundamentalsProvider`, `NewsProvider`, registry, CLI,
  structured-output + report pattern.

---

To build your own workflow, see [adding-a-workflow.md](adding-a-workflow.md).
