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
            (live + sample)    via langchain-anthropic
```

- **`registry`** maps a name (`equity-research`) to a `Workflow` instance.
- A **`Workflow`** knows how to `build()` a compiled LangGraph graph, construct
  `initial_state(**params)`, and turn the final state into a Markdown
  deliverable (`result_markdown`) plus a small `metadata` summary.
- **Nodes** in the graph call **data providers** (the tool layer) and **Claude**
  (via `llm.py`).
- The CLI (and `examples/`) call `run_workflow(name, **params)`, which builds the
  graph, invokes it, and wraps the output in a `WorkflowResult`.

## The graph (equity research)

```
START ─┬─> gather_market_data ─┐
       ├─> gather_fundamentals ─┼─> analyze ─> write_memo ─> END
       └─> gather_news ─────────┘
```

LangGraph executes in **supersteps**. The three `gather_*` nodes have no
dependencies on each other, so they run in parallel in the first superstep.
`analyze` has three incoming edges and therefore runs once, only after all three
gather nodes complete (fan-in). `write_memo` follows `analyze`.

### Why each gather node writes a distinct state key

Parallel nodes that write the *same* state key would need a reducer (LangGraph
otherwise raises on concurrent updates). We sidestep that entirely: each gather
node writes its own key (`market` / `fundamentals` / `news`). Simpler to read,
no reducer to reason about.

### Structured analysis

`analyze` uses `ChatAnthropic(...).with_structured_output(AnalysisResult)`, so
Claude returns a **validated Pydantic object** — `thesis`, `strengths`, `risks`,
`valuation_view`, `recommendation` (`Buy`/`Hold`/`Sell`), `confidence`. The rest
of the graph never parses free text.

`write_memo` then turns that structured view plus the underlying data packet into
a readable Markdown memo.

## The data layer (`tools/`)

Each provider exposes one job and a uniform contract: **try live, fall back to
sample, and always tag the `source`.**

| Provider | Live source | Fallback | Returns |
|---|---|---|---|
| `MarketDataProvider` | `yfinance` history | `data/samples/<T>/prices.csv` | price snapshot dict |
| `FundamentalsProvider` | `yfinance` `.info` | `data/samples/<T>/fundamentals.json` | profile dict |
| `NewsProvider` | `yfinance` `.news` | `data/samples/<T>/news.json` | `{source, items}` |

Live failures (no network, bad ticker, `yfinance` not installed) are caught and
silently downgraded to sample data — the workflow never hard-fails on data.

The same providers are also exposed as LangChain `@tool`s in
`tools/langchain_tools.py`, ready for a tool-calling agent variant.

## The LLM layer (`llm.py`)

- Model defaults to **`claude-opus-4-8`** (override with `FINWF_MODEL`).
- We **don't** send `temperature` or a `thinking` budget — on Opus 4.8 those are
  rejected by the API, and adaptive thinking is the default.
- `langchain_anthropic` is imported lazily, so the data layer, registry, and
  `finwf list` work even without the LLM stack installed.

## Graceful degradation (offline mode)

Every reasoning node checks `state["use_llm"]`:

- **With a key** (and not `--offline`): call Claude.
- **Without a key** (or `--offline`): use a transparent, rule-based analyst and a
  templated memo.

This means a reviewer can `pip install`, generate samples, and get a complete
end-to-end run with **no API key and no internet**. If a live Claude call fails
mid-run (network/auth), the node catches it and falls back rather than crashing.

## Configuration (`config.py`)

All settings are environment-driven (`Settings` frozen dataclass): API key,
model, max tokens, whether live data is allowed, output directory. See
[.env.example](../.env.example).

## Design decisions, briefly

- **Deterministic DAG over a free-roaming agent.** For research that must be
  auditable, an explicit graph you can read and test beats an open agent loop.
  The tool-calling variant is documented as an extension, not the default.
- **Provenance everywhere.** `source: live|sample` flows from the provider into
  the memo, so output is never silently synthetic.
- **Small `Workflow` surface.** Four methods. That's what makes the other three
  planned workflows cheap to add.
- **Offline-first.** A portfolio reviewer should be able to run it in 60 seconds.
