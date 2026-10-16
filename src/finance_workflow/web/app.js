"use strict";

const $ = (id) => document.getElementById(id);
const workflows = {
  "equity-research": {
    name: "Equity research", title: "A clearer view of your next idea.",
    description: "Bring market data, fundamentals, and news into one research memo.",
    button: "Run research", report: "Investment memo", empty: "Choose a company and run the workflow.",
    stages: ["Gather sources", "Analyze the business", "Draft memo"], index: "01",
  },
  portfolio: {
    name: "Portfolio analytics", title: "Know what your portfolio carries.",
    description: "Understand returns, exposure, concentration, and the risks behind your holdings.",
    button: "Analyze portfolio", report: "Portfolio risk report", empty: "Add your holdings and analyze your portfolio.",
    stages: ["Load holdings", "Calculate risk", "Write report"], index: "02",
  },
  "doc-analysis": {
    name: "Document analysis", title: "Find the signal in the filing.",
    description: "Extract financial figures and risk disclosures, with citations back to their source.",
    button: "Analyze document", report: "Document analysis", empty: "Select a sample filing or paste your document.",
    stages: ["Read document", "Extract & cite", "Summarize findings"], index: "03",
  },
  monitor: {
    name: "Market monitor", title: "Keep your watchlist in focus.",
    description: "Connect price moves, volatility, and headline catalysts across your watchlist.",
    button: "Scan watchlist", report: "Watchlist digest", empty: "Set your watchlist and scan the market.",
    stages: ["Scan watchlist", "Detect movers", "Prepare digest"], index: "04",
  },
};
let activeWorkflow = "equity-research";
let busy = false;
let catalog = null;
const completed = new Map();

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}
function money(value, digits = 2) {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: digits }).format(value) : "—";
}
function percentage(value) {
  return typeof value === "number" && Number.isFinite(value) ? `${value > 0 ? "+" : ""}${value.toFixed(2)}%` : "—";
}
function metric(label, value, note, tone = "") {
  const card = node("div", "metric-card");
  const heading = node("div", "metric-label", label);
  heading.append(node("span", "metric-arrow", "↗"));
  card.append(heading, node("div", `metric-value ${tone}`, value ?? "—"), node("div", "metric-note", note));
  return card;
}
function insight(label, text) {
  const block = node("div", "insight-block");
  block.append(node("div", "insight-label", label), node("p", "insight-copy", text || "Not available in this result."));
  return block;
}
function insightList(label, items) {
  const block = node("div", "insight-block");
  block.append(node("div", "insight-label", label));
  const list = node("ul", "insight-list");
  for (const text of items.slice(0, 3)) list.append(node("li", "", text));
  block.append(list);
  return block;
}
function setWorkflow(name) {
  if (busy) return;
  activeWorkflow = name;
  const config = workflows[name];
  document.querySelectorAll(".nav-item").forEach((button) => {
    const selected = button.dataset.workflow === name;
    button.classList.toggle("active", selected);
    if (selected) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  $("breadcrumb-title").textContent = config.name;
  $("page-title").textContent = config.title;
  $("page-description").textContent = config.description;
  $("run-button-label").textContent = config.button;
  $("ticker-field").hidden = !["equity-research", "doc-analysis"].includes(name);
  $("watchlist-field").hidden = name !== "monitor";
  $("news-field").hidden = !["equity-research", "monitor"].includes(name);
  $("portfolio-fields").hidden = name !== "portfolio";
  $("document-fields").hidden = name !== "doc-analysis";
  $("ticker").required = name === "equity-research";
  $("watchlist").required = name === "monitor";
  $("holdings").required = name === "portfolio";
  $("empty-state").querySelector("p").textContent = `${config.empty} Your report and source details will appear here.`;
  $("empty-state").querySelector(".empty-index").textContent = `${config.index} / 04`;
  const stages = $("pipeline-stages");
  stages.replaceChildren();
  config.stages.forEach((label, i) => {
    if (i) stages.append(node("span", "arrow", "→"));
    const stage = node("span", "stage");
    stage.append(node("span", "stage-dot"), node("span", "", label));
    stages.append(stage);
  });
  $("error").hidden = true;
  const previous = completed.get(name);
  if (previous) renderResult(previous.result, previous.elapsed, previous.time);
  else {
    $("results").hidden = true;
    $("empty-state").hidden = false;
    $("pipeline-status").textContent = "Ready";
    document.querySelector(".pipeline").classList.remove("complete");
  }
}

function renderResult(result, elapsed, time) {
  const meta = result.metadata;
  const data = result.data;
  const config = workflows[result.workflow];
  const cards = [];
  const insights = $("insights");
  insights.replaceChildren();
  let subtitle = "";
  if (result.workflow === "equity-research") {
    const market = data.market || {};
    const analysis = data.analysis || {};
    cards.push(metric("Latest close", money(market.last_close), `As of ${meta.as_of || "unknown"}`));
    cards.push(metric("Daily change", percentage(market.daily_change_pct), "Versus previous close", market.daily_change_pct >= 0 ? "positive" : "negative"));
    cards.push(metric("Analyst view", meta.recommendation, `${meta.confidence || "Unknown"} confidence`, "positive"));
    cards.push(metric("Annualized volatility", percentage(market.annualized_volatility_pct).replace(/^\+/, ""), "Historical daily returns"));
    subtitle = `${meta.company || meta.ticker} · ${meta.ticker}`;
    insights.append(insight("THE INVESTMENT VIEW", analysis.thesis));
    if (analysis.strengths?.length) insights.append(insightList("BUSINESS STRENGTHS", analysis.strengths));
    if (analysis.risks?.length) insights.append(insightList("RISKS TO WATCH", analysis.risks));
  } else if (result.workflow === "portfolio") {
    cards.push(metric("Portfolio value", money(meta.total_value, 0), `As of ${meta.as_of || "unknown"}`));
    cards.push(metric("Risk rating", meta.risk_rating, `${meta.positions} distinct holdings`, "positive"));
    cards.push(metric("Annualized volatility", percentage(data.annualized_volatility_pct).replace(/^\+/, ""), "Historical portfolio returns"));
    cards.push(metric("Maximum drawdown", percentage(data.max_drawdown_pct), "Peak-to-trough decline", "negative"));
    subtitle = `${meta.positions} holdings · ${money(meta.total_value, 0)}`;
    insights.append(node("div", "insight-label", "LARGEST POSITIONS"));
    for (const holding of (data.positions || []).slice(0, 5)) {
      const row = node("div", "holding-row");
      row.append(node("span", "", holding.ticker), node("span", "", `${(holding.weight * 100).toFixed(1)}%`));
      insights.append(row);
    }
    insights.append(insight("SECTOR EXPOSURE", Object.entries(data.sector_exposure || {}).map(([sector, weight]) => `${sector}: ${weight}%`).join(" · ")));
  } else if (result.workflow === "doc-analysis") {
    cards.push(metric("Financial metrics", String(meta.metrics_extracted), "With source chunk citations", "positive"));
    cards.push(metric("Risk disclosures", String(meta.risk_factors_count), "Extracted from the document"));
    cards.push(metric("Reporting period", meta.period || "Unknown", meta.doc_type || "Financial document"));
    cards.push(metric("Data source", meta.sources?.document || "unknown", meta.company || "Custom document"));
    subtitle = `${meta.company || "Custom document"} · ${meta.doc_type || "Financial document"}`;
    insights.append(insight("EXECUTIVE SUMMARY", data.executive_summary));
    if (data.risk_factors?.length) insights.append(insightList("RISK FACTORS", data.risk_factors.map((risk) => `${risk.title} · ${risk.severity}`)));
  } else {
    cards.push(metric("Watchlist", String(meta.universe_size), `${data.summary?.total_tickers ?? 0} companies priced`));
    cards.push(metric("Market sentiment", meta.market_sentiment, "Across this watchlist", "positive"));
    cards.push(metric("Top mover", meta.top_gainer, "Highest daily change"));
    cards.push(metric("Average daily change", percentage(data.summary?.avg_daily_change_pct), `As of ${meta.as_of || "unknown"}`, data.summary?.avg_daily_change_pct >= 0 ? "positive" : "negative"));
    subtitle = `${meta.universe_size} companies · ${meta.as_of || "unknown date"}`;
    insights.append(node("div", "insight-label", "DAILY MOVES"));
    const snapshots = Object.values(data.snapshots || {}).sort((a, b) => b.daily_change_pct - a.daily_change_pct);
    for (const snapshot of snapshots.slice(0, 8)) {
      const row = node("div", "holding-row");
      row.append(node("span", "", snapshot.ticker), node("span", snapshot.daily_change_pct >= 0 ? "positive" : "negative", percentage(snapshot.daily_change_pct)));
      insights.append(row);
    }
    if (data.news_feed?.length) insights.append(insightList("HEADLINE CATALYSTS", data.news_feed.map((item) => `${item.ticker}: ${item.title}`)));
  }
  $("metric-grid").replaceChildren(...cards);
  $("report-label").replaceChildren(document.createTextNode(config.report), node("span", "", subtitle));
  // The server renders Markdown with raw HTML disabled; dynamic metadata uses textContent.
  $("report").innerHTML = result.html;
  $("sources").replaceChildren();
  for (const [label, source] of Object.entries(meta.sources || {})) {
    const row = node("div", "source-row");
    row.append(node("span", "", label), node("span", "", (source || "unknown").toUpperCase()));
    $("sources").append(row);
  }
  const sample = Object.values(meta.sources || {}).includes("sample");
  $("analyst-label").textContent = `${meta.used_llm ? "Model-generated analysis" : "Deterministic analysis"}.${sample ? " Bundled demo data; not current market information." : " Review the full report and its citations."}`;
  $("run-time").textContent = `${time} · ${elapsed.toFixed(1)}s`;
  $("empty-state").hidden = true;
  $("results").hidden = false;
  $("pipeline-status").textContent = "Complete ✓";
  document.querySelector(".pipeline").classList.add("complete");
}

async function runWorkflow(event) {
  if (event) event.preventDefault();
  if (busy) return;
  const name = activeWorkflow;
  const payload = { workflow: name, offline: $("execution-mode").value === "sample" };
  if (["equity-research", "doc-analysis"].includes(name)) payload.ticker = $("ticker").value.trim();
  if (["equity-research", "monitor"].includes(name)) payload.news_limit = Number($("news-limit").value);
  if (name === "monitor") payload.tickers = $("watchlist").value.trim();
  if (name === "portfolio") payload.holdings_csv = $("holdings").value;
  if (name === "doc-analysis") payload.document_text = $("document").value;
  busy = true;
  document.querySelectorAll(".nav-item, #run-form input, #run-form select, #run-form textarea, #run-button").forEach((element) => { element.disabled = true; });
  $("run-button-label").textContent = "Running…";
  $("error").hidden = true;
  $("empty-state").hidden = true;
  $("results").hidden = true;
  $("loading-state").hidden = false;
  $("pipeline-status").textContent = "Running…";
  document.querySelector(".pipeline").classList.remove("complete");
  document.querySelector(".pipeline").classList.add("running");
  const start = performance.now();
  try {
    const response = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "The workflow could not complete.");
    const elapsed = (performance.now() - start) / 1000;
    const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    completed.set(name, { result, elapsed, time });
    renderResult(result, elapsed, time);
  } catch (error) {
    $("error").textContent = error.message || "Could not reach the local server.";
    $("error").hidden = false;
    const previous = completed.get(name);
    if (previous) renderResult(previous.result, previous.elapsed, previous.time);
    else { $("empty-state").hidden = false; $("pipeline-status").textContent = "Check inputs"; }
  } finally {
    busy = false;
    $("loading-state").hidden = true;
    document.querySelector(".pipeline").classList.remove("running");
    document.querySelectorAll(".nav-item, #run-form input, #run-form select, #run-form textarea, #run-button").forEach((element) => { element.disabled = false; });
    $("run-button-label").textContent = workflows[name].button;
  }
}

function updateMode() {
  const sample = $("execution-mode").value === "sample";
  $("mode-label").textContent = sample ? "SAMPLE DATA" : "LIVE / FALLBACK";
  $("execution-note").textContent = sample
    ? "Bundled AAPL, MSFT, and NVDA samples. No API key needed. These are demo data, not current prices."
    : `Live providers fall back to samples if unavailable. ${catalog?.llm_available ? `Configured model: ${catalog.model}.` : "No model key configured; analysis stays deterministic."}`;
}

async function readUpload(input, target) {
  const file = input.files[0];
  if (!file) return;
  try {
    if (file.size > 900000) throw new Error("Choose a file under 900 KB.");
    target.value = await file.text();
    $("error").hidden = true;
  } catch (error) {
    $("error").textContent = error.message;
    $("error").hidden = false;
  }
  input.value = "";
}

document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => setWorkflow(button.dataset.workflow)));
$("run-form").addEventListener("submit", runWorkflow);
$("execution-mode").addEventListener("change", updateMode);
$("holdings-upload").addEventListener("change", (event) => readUpload(event.target, $("holdings")));
$("document-upload").addEventListener("change", (event) => readUpload(event.target, $("document")));
$("download-button").addEventListener("click", () => {
  const item = completed.get(activeWorkflow);
  if (!item) return;
  const url = URL.createObjectURL(new Blob([item.result.markdown], { type: "text/markdown;charset=utf-8" }));
  const link = node("a");
  link.href = url;
  link.download = `${item.result.metadata.ticker || "finance"}_${activeWorkflow}_${Date.now()}.md`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});

async function initialize() {
  setWorkflow(activeWorkflow);
  try {
    const response = await fetch("/api/workflows");
    if (!response.ok) throw new Error("Could not load workflows. Check the local server.");
    catalog = await response.json();
    for (const item of catalog.samples) {
      const option = node("option");
      option.value = item.ticker;
      option.label = item.company;
      $("sample-tickers").append(option);
    }
    updateMode();
    await runWorkflow();
  } catch (error) {
    $("error").textContent = error.message;
    $("error").hidden = false;
  }
}
initialize();
