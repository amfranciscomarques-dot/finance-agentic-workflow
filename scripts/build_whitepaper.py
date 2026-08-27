"""Generate the project whitepaper as a Word (.docx) document.

Run:  python scripts/build_whitepaper.py
Output:  Finance-Agentic-Workflow-Whitepaper.docx (repo root)

The content is grounded in README.md and docs/ — it is a polished narrative of
the framework's design, not marketing copy.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
INK = RGBColor(0x14, 0x1B, 0x2E)        # near-black navy for body
NAVY = RGBColor(0x1B, 0x2A, 0x4A)       # headings
ACCENT = RGBColor(0x2E, 0x6F, 0x9E)     # links / accents (teal-blue)
MUTED = RGBColor(0x5B, 0x66, 0x77)      # captions / subtitles
CODE_FG = RGBColor(0x1A, 0x1A, 0x1A)
CODE_SHADE = "F2F4F7"
RULE = "D7DCE3"
HEAD_SHADE = "1B2A4A"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------
def _shade(element, fill_hex: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    element.append(shd)


def _cell_shade(cell, fill_hex: str) -> None:
    _shade(cell._tc.get_or_add_tcPr(), fill_hex)


def _para_shade(paragraph, fill_hex: str) -> None:
    _shade(paragraph._p.get_or_add_pPr(), fill_hex)


def _set_cell_margins(cell, top=60, bottom=60, left=120, right=120) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    margins = OxmlElement("w:tcMar")
    for tag, val in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        node = OxmlElement(f"w:{tag}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        margins.append(node)
    tcPr.append(margins)


def _field(paragraph, instruction: str, placeholder: str) -> None:
    """Insert a Word field (used for the auto Table of Contents)."""
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    run._r.append(fld_begin)

    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    run._r.append(instr)

    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    run._r.append(fld_sep)

    placeholder_run = paragraph.add_run(placeholder)
    placeholder_run.italic = True
    placeholder_run.font.color.rgb = MUTED

    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    paragraph.add_run()._r.append(fld_end)


def _page_number_field(paragraph) -> None:
    run = paragraph.add_run()
    for kind, text in (("begin", None), ("instr", "PAGE"), ("end", None)):
        if kind == "instr":
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = " PAGE "
        else:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        run._r.append(el)


# ---------------------------------------------------------------------------
# Document setup
# ---------------------------------------------------------------------------
def build() -> Path:
    doc = Document()

    # Base styles -----------------------------------------------------------
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = INK
    pf = normal.paragraph_format
    pf.space_after = Pt(8)
    pf.line_spacing = 1.18

    for level, size in ((1, 16), (2, 13), (3, 11.5)):
        st = doc.styles[f"Heading {level}"]
        st.font.name = "Calibri"
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = NAVY
        st.paragraph_format.space_before = Pt(16 if level == 1 else 12)
        st.paragraph_format.space_after = Pt(6)
        st.paragraph_format.keep_with_next = True

    title_style = doc.styles["Title"]
    title_style.font.name = "Calibri"
    title_style.font.color.rgb = NAVY

    # Margins
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.05)
        section.right_margin = Inches(1.05)

    # ---- helper closures over `doc` --------------------------------------
    def para(text="", *, size=10.5, color=INK, bold=False, italic=False,
             align=None, space_after=8, space_before=0):
        p = doc.add_paragraph()
        if align is not None:
            p.alignment = align
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.space_before = Pt(space_before)
        if text:
            r = p.add_run(text)
            r.font.size = Pt(size)
            r.font.color.rgb = color
            r.bold = bold
            r.italic = italic
        return p

    def body(text):
        return para(text)

    def bullet(text, *, runs=None):
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(4)
        if runs:
            for t, b in runs:
                r = p.add_run(t)
                r.bold = b
                r.font.color.rgb = INK
        else:
            r = p.add_run(text)
            r.font.color.rgb = INK
        return p

    def lead_bullet(lead, rest):
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(lead)
        r.bold = True
        r.font.color.rgb = NAVY
        r2 = p.add_run(rest)
        r2.font.color.rgb = INK
        return p

    def code_block(lines):
        """Monospace, lightly shaded single-cell block."""
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.cell(0, 0)
        _cell_shade(cell, CODE_SHADE)
        _set_cell_margins(cell, top=100, bottom=100, left=160, right=160)
        cell.paragraphs[0].text = ""
        for i, line in enumerate(lines):
            p = cell.paragraphs[0] if i == 0 else cell.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.0
            r = p.add_run(line if line else " ")
            r.font.name = "Consolas"
            r.font.size = Pt(9)
            r.font.color.rgb = CODE_FG
        # subtle border
        doc.add_paragraph().paragraph_format.space_after = Pt(6)
        return table

    def caption(text):
        para(text, size=9, color=MUTED, italic=True, space_after=12)

    def rule():
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(8)
        pPr = p._p.get_or_add_pPr()
        pbdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), RULE)
        pbdr.append(bottom)
        pPr.append(pbdr)

    def table(headers, rows, widths=None):
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = "Table Grid"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        hdr = t.rows[0].cells
        for i, h in enumerate(headers):
            _cell_shade(hdr[i], HEAD_SHADE)
            _set_cell_margins(hdr[i])
            p = hdr[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(h)
            r.bold = True
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        for ridx, row in enumerate(rows):
            cells = t.add_row().cells
            for i, val in enumerate(row):
                _set_cell_margins(cells[i])
                if ridx % 2 == 1:
                    _cell_shade(cells[i], "F6F8FA")
                p = cells[i].paragraphs[0]
                p.paragraph_format.space_after = Pt(0)
                r = p.add_run(val)
                r.font.size = Pt(9.5)
                r.font.color.rgb = INK
        if widths:
            for i, w in enumerate(widths):
                for row in t.rows:
                    row.cells[i].width = Inches(w)
        doc.add_paragraph().paragraph_format.space_after = Pt(4)
        return t

    # ======================================================================
    # COVER PAGE
    # ======================================================================
    for _ in range(3):
        doc.add_paragraph()

    # Eyebrow
    para("TECHNICAL WHITEPAPER", size=11, color=ACCENT, bold=True,
         align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.paragraph_format.space_after = Pt(4)
    r = t.add_run("Finance Agentic Workflow")
    r.font.size = Pt(34)
    r.font.bold = True
    r.font.color.rgb = NAVY
    r.font.name = "Calibri"

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.paragraph_format.space_after = Pt(24)
    rs = sub.add_run(
        "A Deterministic, Provenance-Aware Framework for\nFinance AI Workflows on LangGraph"
    )
    rs.font.size = Pt(15)
    rs.font.color.rgb = MUTED

    # Thin accent rule centered
    rl = doc.add_paragraph()
    rl.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rl.paragraph_format.space_after = Pt(24)
    pPr = rl._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "2E6F9E")
    pbdr.append(bottom)
    pPr.append(pbdr)

    para(
        "An autonomous equity-research and portfolio-analytics assistant that gathers "
        "market data, fundamentals, and news, reasons over them with Claude, and drafts "
        "an auditable investment memo — with graceful offline fallback and end-to-end "
        "provenance.",
        size=11, color=INK, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=36,
    )

    for _ in range(4):
        doc.add_paragraph()

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.paragraph_format.space_after = Pt(2)
    rm = meta.add_run("Author: A. Marques")
    rm.font.size = Pt(11)
    rm.bold = True
    rm.font.color.rgb = INK

    meta2 = doc.add_paragraph()
    meta2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rm2 = meta2.add_run(
        f"Version 1.0  ·  {date.today():%B %Y}  ·  LangGraph · Claude Opus 4.8 · Python 3.10+"
    )
    rm2.font.size = Pt(9.5)
    rm2.font.color.rgb = MUTED

    doc.add_page_break()

    # ======================================================================
    # TABLE OF CONTENTS
    # ======================================================================
    para("Contents", size=16, color=NAVY, bold=True, space_after=8)
    rule()
    toc_p = doc.add_paragraph()
    _field(
        toc_p,
        'TOC \\o "1-2" \\h \\z \\u',
        "Right-click here and choose “Update Field” in Word to build the table of contents.",
    )
    doc.add_page_break()

    # ======================================================================
    # 1. EXECUTIVE SUMMARY
    # ======================================================================
    doc.add_heading("1. Executive Summary", level=1)
    body(
        "Finance Agentic Workflow is a documented, extensible framework for building "
        "finance AI workflows on LangGraph. Its first two workflows — an equity-research "
        "assistant and a portfolio & risk-analytics engine — gather data, reason over it "
        "with a large language model, and produce a readable, auditable deliverable."
    )
    body(
        "Most “AI agent” demonstrations are a single prompt in a loop: easy to show, hard "
        "to trust. Real financial workflows have a higher bar. They must be auditable, "
        "reproducible, and honest about where every number came from. This framework is "
        "built around four commitments that follow from that bar:"
    )
    lead_bullet("Deterministic orchestration — ",
                "an explicit LangGraph state graph you can read, test, and reason about, "
                "rather than a free-roaming agent loop.")
    lead_bullet("A clean tool/data boundary — ",
                "providers that try a live source, then fall back to reproducible sample "
                "data, so the workflow always runs.")
    lead_bullet("Structured, typed LLM output — ",
                "the analysis step returns a validated Pydantic object, not free text the "
                "rest of the graph has to parse.")
    lead_bullet("End-to-end provenance — ",
                "every data point is tagged live, sample, or mixed, and the run records "
                "whether the LLM actually produced the output or a deterministic fallback did.")
    body(
        "The practical result: a reviewer can install the package and get a complete, "
        "honest, end-to-end run in about sixty seconds — with no API key and no internet "
        "connection — and later point it at live data and Claude with a single environment "
        "variable. The remainder of this paper explains how the framework achieves this and "
        "why each design decision was made."
    )

    # ======================================================================
    # 2. INTRODUCTION
    # ======================================================================
    doc.add_heading("2. The Problem", level=1)
    body(
        "AI systems in finance face a credibility problem. An analyst will not act on a "
        "memo that cannot be traced back to its inputs, and a risk committee will not sign "
        "off on numbers a model may have invented. Yet the dominant pattern for LLM agents "
        "— a single model in an open tool-calling loop — is exactly the opposite of "
        "auditable. The control flow is emergent, the data lineage is implicit, and a "
        "failed network call can silently become a hallucinated fact."
    )
    body("A workflow that finance professionals can actually use needs to answer four questions at all times:")
    lead_bullet("What did it do? ", "The orchestration must be explicit and inspectable, not emergent from a prompt.")
    lead_bullet("Where did the data come from? ", "Every figure must carry its provenance into the final deliverable.")
    lead_bullet("Did the model actually run? ", "The output must distinguish genuine LLM reasoning from a deterministic fallback.")
    lead_bullet("Can I run it right now? ", "It must degrade gracefully — no key, no network, no problem — so it is always reviewable.")
    body(
        "This framework is a portfolio-grade answer to those four questions. It is "
        "deliberately a small, legible core rather than a large feature set: a registry, a "
        "tool layer, a provider-agnostic LLM factory, and a four-method workflow contract "
        "that new workflows implement without touching the core."
    )

    # ======================================================================
    # 3. DESIGN PRINCIPLES
    # ======================================================================
    doc.add_heading("3. Design Principles", level=1)

    doc.add_heading("3.1  Deterministic DAG over a free-roaming agent", level=2)
    body(
        "For research that must be auditable, an explicit directed graph you can read and "
        "test beats an open agent loop. The control flow is visible in code; each node has "
        "a single responsibility; the same inputs produce the same shape of output. A "
        "tool-calling agent variant is documented as an extension — bind the same tools to "
        "a ReAct agent — but it is not the default, because the default optimizes for "
        "auditability."
    )

    doc.add_heading("3.2  Provenance everywhere", level=2)
    body(
        "The data source — live, sample, or mixed — flows from the provider all the way "
        "into the deliverable, and a used_llm flag records whether Claude actually produced "
        "the output or the deterministic analyst did. The output is therefore never "
        "silently synthetic, and the metadata never claims an LLM view it did not produce. "
        "In the equity-research workflow, used_llm is true only when Claude produced both "
        "the structured analysis and the memo; if either node degrades, it honestly reports "
        "false."
    )

    doc.add_heading("3.3  A small workflow surface", level=2)
    body(
        "Every workflow implements the same four-method contract — build, initial_state, "
        "result_markdown, and metadata. That small surface is precisely what makes "
        "additional workflows cheap to add and keeps the core stable as the catalogue grows."
    )

    doc.add_heading("3.4  Offline-first", level=2)
    body(
        "A reviewer should be able to run the framework in sixty seconds. Sample data is "
        "bundled and reproducibly seeded; the reasoning nodes have a transparent rule-based "
        "fallback. Offline-first is not a degraded mode bolted on at the end — it is the "
        "default the whole design is verified against."
    )

    # ======================================================================
    # 4. ARCHITECTURE
    # ======================================================================
    doc.add_heading("4. Architecture Overview", level=1)
    body(
        "At a high level, the command-line interface (or an example script) asks the "
        "registry for a workflow by name, the workflow builds a compiled LangGraph graph, "
        "and invoking that graph produces a WorkflowResult — a Markdown deliverable plus a "
        "small metadata summary."
    )
    code_block([
        "            ┌──────────────────────────────────────────────┐",
        "   CLI ───► │  registry  →  Workflow  →  compiled LangGraph │ ───► WorkflowResult",
        "            └──────────────────────────────────────────────┘",
        "                                  │",
        "                 ┌────────────────┼────────────────┐",
        "                 ▼                ▼                ▼",
        "            tools/ providers   llm.py (Claude)   prompts / schema",
        "            (live + sample)    via init_chat_model",
    ])
    caption("Figure 1. The 10,000-foot view: a registry resolves a workflow, which compiles a graph whose nodes call the tool layer and the LLM factory.")

    lead_bullet("registry — ", "maps a name such as “equity-research” to a Workflow instance.")
    lead_bullet("Workflow — ", "knows how to build() a compiled graph, construct initial_state(**params), and turn the final state into a Markdown deliverable plus a metadata summary.")
    lead_bullet("Nodes — ", "call data providers (the tool layer) and Claude (via llm.py).")
    lead_bullet("Entry point — ", "the CLI and examples call run_workflow(name, **params), which builds the graph, invokes it, and wraps the output in a WorkflowResult.")

    doc.add_heading("4.1  The equity-research graph", level=2)
    body(
        "LangGraph executes in supersteps. The three gather nodes have no dependencies on "
        "one another, so they run in parallel in the first superstep. The analyze node has "
        "three incoming edges and therefore runs once, only after all three gather nodes "
        "complete — a fan-in. The write_memo node follows analyze."
    )
    code_block([
        "START ─┬─> gather_market_data ─┐",
        "       ├─> gather_fundamentals ─┼─> analyze ─> write_memo ─> END",
        "       └─> gather_news ─────────┘",
    ])
    caption("Figure 2. Equity research: a parallel fan-out gather, a structured-analysis fan-in, and a memo-writing step.")
    body(
        "Parallel nodes that write the same state key would require a reducer — LangGraph "
        "otherwise raises on concurrent updates. The design sidesteps that entirely: each "
        "gather node writes its own key (market, fundamentals, news). It is simpler to read "
        "and there is no reducer to reason about."
    )
    body(
        "The analyze node calls the model with structured output bound to an AnalysisResult "
        "schema, so Claude returns a validated Pydantic object — thesis, strengths, risks, "
        "valuation view, a Buy/Hold/Sell recommendation, and a confidence score. The rest "
        "of the graph never parses free text. write_memo then turns that structured view, "
        "plus the underlying data packet, into a readable Markdown memo."
    )

    doc.add_heading("4.2  The portfolio graph", level=2)
    body(
        "The portfolio workflow is a linear pipeline — no fan-out, so every state key is "
        "written by exactly one node and no reducer is needed."
    )
    code_block([
        "START ─> load_positions ─> compute_metrics ─> narrate ─> END",
    ])
    caption("Figure 3. Portfolio & risk analytics: a deterministic three-stage pipeline.")
    body(
        "load_positions normalizes the holdings — an inline {ticker, shares} list or a "
        "ticker,shares CSV. compute_metrics prices them via the PortfolioProvider and "
        "derives weights, trailing returns, volatility, max drawdown, sector exposure, "
        "weighted beta, and concentration. narrate forms a structured PortfolioAssessment — "
        "with Claude or the deterministic fallback — and renders the Markdown risk report."
    )

    # ======================================================================
    # 5. DATA LAYER
    # ======================================================================
    doc.add_heading("5. The Tool & Data Layer", level=1)
    body(
        "Each provider exposes one job and a uniform contract: try live, fall back to "
        "sample, and always tag the source. Live failures — no network, a bad ticker, or "
        "a missing optional dependency — are caught and silently downgraded to sample data, "
        "so the workflow never hard-fails on data acquisition."
    )
    table(
        ["Provider", "Live source", "Fallback", "Returns"],
        [
            ["MarketDataProvider", "yfinance history", "data/samples/<T>/prices.csv", "price snapshot dict"],
            ["FundamentalsProvider", "yfinance .info", "data/samples/<T>/fundamentals.json", "profile dict"],
            ["NewsProvider", "yfinance .news", "data/samples/<T>/news.json", "{source, items}"],
        ],
        widths=[1.7, 1.6, 2.3, 1.6],
    )
    caption("Table 1. Each provider tries a live source, falls back to bundled sample data, and tags every result with its source.")
    body(
        "The same providers are also exposed as LangChain tools, ready for a tool-calling "
        "agent variant. The PortfolioProvider sits one level up: it composes the "
        "MarketDataProvider and FundamentalsProvider to turn positions into analytics, so "
        "it inherits their fallback and source tagging. Because a book can price some "
        "holdings live and others from samples, its tag carries a third value — mixed — "
        "alongside live and sample."
    )

    # ======================================================================
    # 6. LLM LAYER
    # ======================================================================
    doc.add_heading("6. The LLM Layer", level=1)
    body(
        "The reasoning nodes are provider-agnostic. The LLM factory builds its client via "
        "LangChain's init_chat_model, so swapping models is configuration, not code — the "
        "workflows never name a provider. The default is Claude Opus 4.8."
    )
    code_block([
        "from langchain.chat_models import init_chat_model",
        "",
        "# provider inferred from the model name",
        "# (claude-* -> anthropic, gpt-* -> openai, ...)",
        "llm = init_chat_model(\"claude-opus-4-8\", max_tokens=4096)",
        "structured = llm.with_structured_output(AnalysisResult)  # validated out",
    ])
    caption("Figure 4. Model-agnostic wiring: the provider is inferred from the model name, and structured output yields a validated Pydantic object.")
    lead_bullet("Provider resolution. ",
                "The provider is taken from FINWF_MODEL_PROVIDER, else a provider:model "
                "shorthand, else inferred from the model-name prefix.")
    lead_bullet("Key-aware availability. ",
                "The offline gate checks the configured provider's key, so it is correct "
                "regardless of which provider you target; keyless providers such as a local "
                "Ollama are always considered available.")
    lead_bullet("Portable defaults. ",
                "The factory does not send temperature or a thinking budget — some models "
                "reject them — keeping it portable; pass overrides explicitly if a model needs them.")
    lead_bullet("Lazy imports. ",
                "LangChain and the provider integration package are imported lazily, so the "
                "data layer, registry, and finwf list work even without the LLM stack installed.")
    body(
        "Supported provider extras include OpenAI, Google, Groq, Mistral, and Ollama; "
        "Anthropic works out of the box. Choosing a different model is a matter of "
        "installing the extra and setting two environment variables."
    )

    # ======================================================================
    # 7. GRACEFUL DEGRADATION
    # ======================================================================
    doc.add_heading("7. Graceful Degradation", level=1)
    body("Every reasoning node checks a single flag in the graph state, use_llm:")
    lead_bullet("With a key (and not --offline): ", "call Claude.")
    lead_bullet("Without a key (or --offline): ", "use a transparent, rule-based analyst and a templated memo.")
    body(
        "This is what lets a reviewer install the package, generate samples, and get a "
        "complete end-to-end run with no API key and no internet. Critically, the fallback "
        "is also a safety net at runtime: if a live Claude call fails mid-run — a network "
        "blip, an auth error — the node catches it and falls back rather than crashing, and "
        "records that it did."
    )
    body(
        "The run's used_llm flag reports whether Claude actually produced the output, not "
        "merely that it was requested. An --offline run and a run whose live call failed "
        "both honestly report used_llm: false. Provenance, again, is the point: the "
        "metadata never overstates what produced the result."
    )

    # ======================================================================
    # 8. EXTENSIBILITY
    # ======================================================================
    doc.add_heading("8. Extensibility", level=1)
    body(
        "A new workflow is a LangGraph graph plus a small adapter the registry and CLI "
        "understand. It implements the same four-method Workflow contract, registers itself "
        "in one line, and then appears in finwf list and runs via finwf run. Nothing in the "
        "core changes."
    )
    code_block([
        "class MyWorkflow(Workflow):",
        "    name = \"my-workflow\"",
        "    title = \"My Workflow\"",
        "    description = \"What it does, in one line.\"",
        "",
        "    def build(self): return build_graph()",
        "    def initial_state(self, symbol, offline=False, **_): ...",
        "    def result_markdown(self, final_state): ...",
        "    def metadata(self, final_state): ...",
        "",
        "registry.register(MyWorkflow())  # now in `finwf list`",
    ])
    caption("Figure 5. The complete contract a new workflow implements before it is registered.")
    body(
        "New workflows reuse the existing data layer, the LLM factory, the structured-output "
        "pattern, and the report-rendering convention. The recommended practice is to keep a "
        "deterministic offline branch in every reasoning node and to mirror the existing "
        "tests, which run each graph in offline mode and assert on the result."
    )

    doc.add_heading("8.1  Workflow catalogue", level=2)
    table(
        ["Workflow", "Command", "Status"],
        [
            ["Equity research assistant", "equity-research", "Implemented"],
            ["Portfolio & risk analytics", "portfolio", "Implemented"],
            ["Financial document analysis", "doc-analysis", "Planned"],
            ["Market & news monitor", "monitor", "Planned"],
        ],
        widths=[2.5, 1.9, 1.4],
    )
    caption("Table 2. Two of four planned workflows are implemented; the framework is built so the remaining two slot in without changing the core.")

    # ======================================================================
    # 9. USAGE
    # ======================================================================
    doc.add_heading("9. Getting Started", level=1)
    body("The framework requires Python 3.10 or later. A complete offline run takes four commands:")
    code_block([
        "# 1. Create and activate a virtual environment",
        "py -3.12 -m venv .venv",
        ".\\.venv\\Scripts\\Activate.ps1",
        "",
        "# 2. Install (with live-data extras)",
        "pip install -e \".[live,dev]\"",
        "",
        "# 3. Generate the bundled sample data (reproducible, seeded)",
        "python scripts/generate_samples.py",
        "",
        "# 4. Run a workflow — works offline, no API key needed",
        "finwf run equity-research --ticker AAPL --offline",
    ])
    caption("Figure 6. Zero-setup quickstart: no API key and no network connection required.")
    body("To use Claude for real analysis, set the key and drop the offline flag:")
    code_block([
        "$env:ANTHROPIC_API_KEY = \"sk-ant-...\"",
        "finwf run equity-research --ticker MSFT",
        "finwf run portfolio --holdings examples/sample_portfolio.csv",
    ])
    caption("Figure 7. The same workflows, now backed by live data and Claude Opus 4.8.")

    # ======================================================================
    # 10. CONCLUSION
    # ======================================================================
    doc.add_heading("10. Conclusion", level=1)
    body(
        "Finance Agentic Workflow demonstrates that the qualities finance teams need from AI "
        "— auditability, reproducibility, and honesty about provenance — are achievable "
        "without sacrificing capability. The recipe is a deliberately small core: a "
        "deterministic LangGraph DAG instead of an open agent loop; a tool layer that always "
        "runs by falling back to seeded sample data; a provider-agnostic LLM factory with "
        "structured, validated output; and a provenance trail that follows every figure from "
        "source to deliverable and never overstates what produced it."
    )
    body(
        "Because the workflow surface is just four methods, the framework grows by addition "
        "rather than modification. The two planned workflows — financial document analysis "
        "and a market & news monitor — plug into the same registry, tool layer, and CLI. The "
        "design goal throughout has been a system a reviewer can run in sixty seconds and "
        "trust the moment it finishes."
    )

    rule()
    para(
        "Finance Agentic Workflow is released under the MIT License. This whitepaper "
        "accompanies the project's README and the architecture, workflows, and "
        "adding-a-workflow documents in the docs/ directory.",
        size=9, color=MUTED, italic=True,
    )

    # ---- Footer with page numbers ----------------------------------------
    footer = doc.sections[0].footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = fp.add_run("Finance Agentic Workflow — Technical Whitepaper   ·   Page ")
    fr.font.size = Pt(8)
    fr.font.color.rgb = MUTED
    _page_number_field(fp)
    for r in fp.runs:
        r.font.size = Pt(8)
        r.font.color.rgb = MUTED

    out = Path(__file__).resolve().parent.parent / "Finance-Agentic-Workflow-Whitepaper.docx"
    doc.save(out)
    return out


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path}")
