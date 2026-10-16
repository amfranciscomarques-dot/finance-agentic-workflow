# Architecture

This document explains how the framework is put together and *why* — the design
decisions are the point of the portfolio piece.

## 10,000-foot view

```
            ┌──────────────────────────────────────────────┐
   CLI ───► │  registry  →  Workflow  →  compiled LangGraph │ ───► WorkflowResult
            └──────────────────────────────────────────────┘
                                  │
                 ┌────────────────┼────────────────┐
                 ▼                ▼                ▼
            tools/ providers   llm.py (Claude)   prompts/schema
            (live + sample)    via init_chat_model
```

- **`registry`** maps a name (`equity-research`, `portfolio`, `doc-analysis`, `monitor`) to a `Workflow` instance.
- A **`Workflow`** knows how to `build()` a compiled LangGraph graph, construct
  `initial_state(**params)`, and turn the final state into a Markdown
  deliverable (`result_markdown`) plus a small `metadata` summary.
- **Nodes** in the graph call **data providers** (the tool layer) and **Claude**
  (via `llm.py`).
- The CLI (and `examples/`) call `run_workflow(name, **params)`, which builds the
  graph, invokes it, and wraps the output in a `WorkflowResult`.

## Local dashboard

`finwf serve` runs a `ThreadingHTTPServer` on `127.0.0.1:8765`. Static assets in
`web/` need no build step, CDN, or external font. The dashboard calls the same
`run_workflow` entry point as the CLI; it does not duplicate workflow logic.

- `GET /healthz` returns the app identity and readiness.
- `GET /api/workflows` lists workflows, bundled tickers, and model availability.
- `POST /api/run` accepts a workflow name plus its inputs and returns the memo,
  rendered Markdown, metadata, and workflow-specific summary data.
- Sample mode is the browser default. Raw HTML in generated Markdown is escaped.
- Browser inputs use inline CSV/positions and document text rather than local
  filesystem paths. Requests must use a local Host and same-origin browser Origin.
- Request bodies are capped at 1 MB and at most two workflows execute concurrently.

The dashboard is intended for a single user's local machine. Results remain in
the browser's memory until downloaded. It is not a public deployment service.

## Shared execution and inputs

`runtime.runtime_options` resolves live-data access and LLM availability for
every workflow. `FINWF_ALLOW_LIVE=0` now applies consistently to all four graphs,
and offline runs short-circuit model availability checks. `inputs.py` normalizes
symbols and deduplicates watchlists. The registry validates initial state before
building a graph, so invalid requests fail early.

Portfolio holdings are normalized and combined by ticker before pricing and
weighting. Nonfinite share counts are rejected. Mixed live/sample price histories
are labeled `mixed`. Document extraction leaves unmatched risk disclosures empty
and explicitly reports missing management outlook rather than inventing citations.
`results.save_result` separates CLI persistence from rendering and uses distinct
UTC timestamps for automatic output paths.

## Graph Anatomy

### 1. Equity Research (`equity-research`)

```
START ─┬─> gather_market_data ─┐
       ├─> gather_fundamentals ─┼─> analyze ─> write_memo ─> END
       └─> gather_news ─────────┘
```

LangGraph executes in **supersteps**. The three `gather_*` nodes run in parallel in the first superstep.
`analyze` has three incoming edges and runs once after all three complete (fan-in). `write_memo` follows.

### 2. Portfolio Risk Analytics (`portfolio`)

```
START ─> load_positions ─> compute_metrics ─> narrate ─> END
```

A linear pipeline: `load_positions` normalizes holdings, `compute_metrics` prices them via `PortfolioProvider` and derives portfolio analytics, and `narrate` forms a structured `PortfolioAssessment` and renders the risk report.

### 3. Financial Document Analysis (`doc-analysis`)

```
START ─> load_document ─> chunk_document ─> extract_financials ─> summarize ─> END
```

A document analysis pipeline: `load_document` ingests a filing or PDF (or falls back to bundled sample filings), `chunk_document` creates indexed chunks with section headers, `extract_financials` extracts structured metrics and risks with chunk citations (via Claude or deterministic extraction), and `summarize` formats an analytical memo.

### 4. Market & News Monitor (`monitor`)

```
START ─> scan_universe ─> detect_movers ─> generate_digest ─> END
```

A market surveillance pipeline: `scan_universe` queries price snapshots and headlines across the universe, `detect_movers` ranks top gainers, losers, and volatility outliers, and `generate_digest` synthesizes a structured watchlist digest and markdown report.

## The Data Layer (`tools/`)

Each provider exposes one job and a uniform contract: **try live, fall back to
sample, and always tag the `source`.**

| Provider | Live source | Fallback | Returns |
|---|---|---|---|
| `MarketDataProvider` | `yfinance` history | `data/samples/<T>/prices.csv` | price snapshot dict |
| `FundamentalsProvider` | `yfinance` `.info` | `data/samples/<T>/fundamentals.json` | profile dict |
| `NewsProvider` | `yfinance` `.news` | `data/samples/<T>/news.json` | `{source, items}` |
| `PortfolioProvider` | composes Market & Fundamentals | bundled sample price CSVs | portfolio metrics dict |
| `DocumentProvider` | file / PDF loader | `data/samples/<T>/filing_10k.txt` | doc payload, chunks, extracted metrics |
| `MonitorProvider` | composes Market, Fund & News | bundled sample data | universe scan & mover rankings |

Live failures (no network, bad ticker, `yfinance` not installed) fall back to
bundled sample data when that ticker is available. Unsupported tickers without
sample data produce an input/data error instead of a fabricated result.

The same providers are also exposed as LangChain `@tool`s in
`tools/langchain_tools.py`, ready for a tool-calling agent variant.

## The LLM Layer (`llm.py`)

The reasoning nodes are **provider-agnostic**. `get_llm()` builds the client via
LangChain's `init_chat_model`, so swapping models is configuration, not code —
the workflows never name a provider.

- Model defaults to **`claude-opus-4-8`** (override with `FINWF_MODEL`).
- **Provider resolution.** `resolve_model_provider()` takes the provider from
  `FINWF_MODEL_PROVIDER`, else the `provider:model` shorthand
  (`groq:llama-3.3-70b-versatile`), else infers it from the model-name prefix
  (`claude-*` → Anthropic, `gpt-*` → OpenAI, `gemini-*` → Google, …).
- **Key-aware availability.** `llm_available()` checks the *configured provider's*
  key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, …), so the offline gate is correct
  regardless of which provider you target; keyless providers (local Ollama) are
  always available.
- `langchain` and the provider integration package are imported lazily, so the
  data layer, registry, and `finwf list` work even without the LLM stack installed.

## Graceful Degradation (Offline Mode)

Every reasoning node checks `state["use_llm"]`:

- **With a key** (and not `--offline`): call Claude.
- **Without a key** (or `--offline`): use transparent, rule-based reasoning engines and templated memos.

This means a reviewer can `pip install`, generate samples, and get complete
end-to-end runs for all 4 workflows with **no API key and no internet**. If a live
Claude call fails mid-run (network/auth), the node catches it and falls back rather
than crashing — and records that it did. The run's `used_llm` flag reports whether
Claude *actually* produced the output, not merely that it was requested.

## Configuration (`config.py`)

All settings are environment-driven (`Settings` frozen dataclass): API key,
model, max tokens, whether live data is allowed, output directory. See
[.env.example](../.env.example).
