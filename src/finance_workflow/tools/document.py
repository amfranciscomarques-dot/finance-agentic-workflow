"""Financial document ingestion, chunking, and metric extraction.

``DocumentProvider`` ingests financial documents (10-K filings, earnings releases,
PDFs, plain text, or markdown) and chunks them with stable identifiers and metadata.
It also includes a deterministic extraction engine that parses key financial figures
(Revenue, Net Income, Margins, Debt, EPS, Cash Flow) and risk factors with precise
chunk-level citations.

When no custom file is provided, it falls back to bundled sample 10-K filings for
offline reproducibility.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..config import get_settings
from .base import company_name, sample_path


class DocumentProvider:
    """Ingest, chunk, and extract information from financial documents."""

    def __init__(self, allow_live: bool | None = None) -> None:
        settings = get_settings()
        self.allow_live = settings.allow_live_data if allow_live is None else allow_live

    # -- document ingestion ------------------------------------------------ #
    def load_document(
        self,
        source: str | Path | None = None,
        ticker: str | None = None,
    ) -> dict[str, Any]:
        """Ingest document text from a file path, raw text string, or bundled sample."""
        if source:
            path = (
                Path(source)
                if isinstance(source, (str, Path))
                and (isinstance(source, Path) or "\n" not in str(source))
                else None
            )
            if path and path.exists() and path.is_file():
                text = self._read_file(path)
                inferred_ticker = ticker or self._infer_ticker_from_text(text)
                return {
                    "source": "file",
                    "doc_name": path.name,
                    "file_path": str(path.resolve()),
                    "ticker": inferred_ticker.upper() if inferred_ticker else None,
                    "company_name": company_name(inferred_ticker)
                    if inferred_ticker
                    else "Custom Entity",
                    "doc_type": self._infer_doc_type(path.name, text),
                    "text": text.strip(),
                }
            elif isinstance(source, str) and "\n" in source:
                inferred_ticker = ticker or self._infer_ticker_from_text(source)
                return {
                    "source": "custom",
                    "doc_name": "inline_document.txt",
                    "file_path": None,
                    "ticker": inferred_ticker.upper() if inferred_ticker else None,
                    "company_name": company_name(inferred_ticker)
                    if inferred_ticker
                    else "Custom Entity",
                    "doc_type": self._infer_doc_type("inline_document.txt", source),
                    "text": source.strip(),
                }
            elif path and not path.exists():
                raise FileNotFoundError(f"Financial document not found: {source}")

        # Fallback to bundled sample 10-K filing
        tk = (ticker or "AAPL").upper()
        return self._sample_document(tk)

    def _sample_document(self, ticker: str) -> dict[str, Any]:
        path = sample_path(ticker, "filing_10k.txt")
        if not path.exists():
            raise FileNotFoundError(
                f"No sample 10-K filing for '{ticker}' at {path}. "
                f"Run `python scripts/generate_samples.py` to create sample data."
            )
        text = path.read_text(encoding="utf-8")
        return {
            "source": "sample",
            "doc_name": f"{ticker}_10K_Filing.txt",
            "file_path": str(path),
            "ticker": ticker,
            "company_name": company_name(ticker),
            "doc_type": "10-K Annual Report",
            "text": text.strip(),
        }

    def _read_file(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._read_pdf(path)
        return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _read_pdf(path: Path) -> str:
        try:
            import pypdf

            reader = pypdf.PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
        except ImportError:
            pass
        try:
            import pypdf2

            reader = pypdf2.PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
        except ImportError:
            pass
        raise ImportError(
            f"Cannot parse PDF file '{path.name}'. Install pypdf (`pip install pypdf`) to read PDF documents."
        )

    # -- chunking ---------------------------------------------------------- #
    def chunk(
        self,
        text: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> list[dict[str, Any]]:
        """Split document text into clean, indexed chunks with section headers."""
        if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
            raise ValueError("Require chunk_size > 0 and 0 <= chunk_overlap < chunk_size.")
        if not text.strip():
            return []

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        chunks: list[dict[str, Any]] = []
        current_chunk: list[str] = []
        current_len = 0
        current_section = "General"
        chunk_id = 1
        char_cursor = 0

        section_pattern = re.compile(
            r"^(?:ITEM\s+[0-9A-Z]+|PART\s+[0-9A-Z]+|[A-Z0-9\s]{4,30}:|EXECUTIVE SUMMARY|MANAGEMENT DISCUSSION|RISK FACTORS|OUTLOOK)",
            re.IGNORECASE,
        )

        for para in paragraphs:
            first_line = para.split("\n")[0].strip()
            if section_pattern.search(first_line) or (len(first_line) < 60 and first_line.isupper()):
                current_section = first_line[:60]

            para_len = len(para)
            if current_len + para_len > chunk_size and current_chunk:
                chunk_text = "\n\n".join(current_chunk)
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "text": chunk_text,
                        "section": current_section,
                        "start_char": char_cursor,
                        "end_char": char_cursor + len(chunk_text),
                    }
                )
                chunk_id += 1
                char_cursor += len(chunk_text)

                if chunk_overlap > 0 and len(current_chunk[-1]) <= chunk_overlap:
                    current_chunk = [current_chunk[-1], para]
                    current_len = len(current_chunk[0]) + para_len
                else:
                    current_chunk = [para]
                    current_len = para_len
            else:
                current_chunk.append(para)
                current_len += para_len

        if current_chunk:
            chunk_text = "\n\n".join(current_chunk)
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "text": chunk_text,
                    "section": current_section,
                    "start_char": char_cursor,
                    "end_char": char_cursor + len(chunk_text),
                }
            )

        return chunks

    # -- retrieval / search ------------------------------------------------ #
    def search_chunks(
        self,
        chunks: list[dict[str, Any]],
        query: str,
        top_k: int = 4,
    ) -> list[dict[str, Any]]:
        """Keyword-scored chunk retrieval for specific topics."""
        terms = set(re.findall(r"\w+", query.lower()))
        if not terms:
            return chunks[:top_k]

        scored: list[tuple[float, dict[str, Any]]] = []
        for chunk in chunks:
            text_lower = chunk["text"].lower()
            score = sum(text_lower.count(term) for term in terms)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        results = [item[1] for item in scored[:top_k]]
        return results if results else chunks[:top_k]

    # -- deterministic extraction engine ----------------------------------- #
    def extract_metrics_deterministic(
        self,
        chunks: list[dict[str, Any]],
        company_name: str = "",
        ticker: str | None = None,
    ) -> dict[str, Any]:
        """Rule-based extraction of key financial figures and risk factors with citations."""
        full_text = "\n\n".join(c["text"] for c in chunks)
        period = self._infer_period(full_text)
        doc_type = self._infer_doc_type("", full_text)

        metrics: list[dict[str, Any]] = []

        # 1. Revenue
        rev_match, rev_chunk = self._find_pattern_in_chunks(
            chunks,
            [
                r"(?:total net sales|total revenue|full-year revenue|annual revenue)[^\n\.\$]*\$?([0-9,]+(?:\.[0-9]+)?\s*(?:million|billion|M|B)?)",
                r"revenue reached \$?([0-9,]+(?:\.[0-9]+)?\s*(?:million|billion|M|B)?)",
                r"(?:revenue of|revenue was|revenue:)\s*\$?([0-9,]+(?:\.[0-9]+)?\s*(?:million|billion|M|B)?)",
            ],
        )
        if rev_match and rev_chunk:
            metrics.append(
                {
                    "metric_name": "Revenue / Total Net Sales",
                    "value": self._format_currency(rev_match[0]),
                    "period": period,
                    "citation": f"[Chunk {rev_chunk['chunk_id']}] {rev_match[1]}",
                    "context": "Top-line revenue reported for the period.",
                }
            )

        # 2. Gross Margin
        gm_match, gm_chunk = self._find_pattern_in_chunks(
            chunks,
            [
                r"(?:gross margin)[^\n\.\$]*\$?([0-9,]+(?:\.[0-9]+)?\s*(?:million|billion|M|B)?\s*(?:\([0-9\.]+\%\))?)",
                r"gross margin (?:was|of)\s*([0-9]+(?:\.[0-9]+)?\%)",
            ],
        )
        if gm_match and gm_chunk:
            metrics.append(
                {
                    "metric_name": "Gross Margin",
                    "value": gm_match[0].strip(),
                    "period": period,
                    "citation": f"[Chunk {gm_chunk['chunk_id']}] {gm_match[1]}",
                    "context": "Gross profitability and cost efficiency.",
                }
            )

        # 3. Operating Income / Margin
        op_match, op_chunk = self._find_pattern_in_chunks(
            chunks,
            [
                r"(?:operating income)[^\n\.\$]*\$?([0-9,]+(?:\.[0-9]+)?\s*(?:million|billion|M|B)?\s*(?:\([^\)]+\))?)",
                r"operating margin of ([0-9]+(?:\.[0-9]+)?\%)",
            ],
        )
        if op_match and op_chunk:
            metrics.append(
                {
                    "metric_name": "Operating Income / Margin",
                    "value": op_match[0].strip(),
                    "period": period,
                    "citation": f"[Chunk {op_chunk['chunk_id']}] {op_match[1]}",
                    "context": "Core operating profitability.",
                }
            )

        # 4. Net Income
        ni_match, ni_chunk = self._find_pattern_in_chunks(
            chunks,
            [
                r"(?:net income|net earnings)[^\n\.\$]*\$?([0-9,]+(?:\.[0-9]+)?\s*(?:million|billion|M|B)?)",
            ],
        )
        if ni_match and ni_chunk:
            metrics.append(
                {
                    "metric_name": "Net Income",
                    "value": self._format_currency(ni_match[0]),
                    "period": period,
                    "citation": f"[Chunk {ni_chunk['chunk_id']}] {ni_match[1]}",
                    "context": "Bottom-line net earnings.",
                }
            )

        # 5. EPS
        eps_match, eps_chunk = self._find_pattern_in_chunks(
            chunks,
            [
                r"(?:diluted (?:earnings per share|eps)|earnings per diluted share|eps)[^\n\.\$]*\$?([0-9]+(?:\.[0-9]+)?(?:\s*per\s+(?:diluted\s+)?share)?)",
            ],
        )
        if eps_match and eps_chunk:
            metrics.append(
                {
                    "metric_name": "Diluted EPS",
                    "value": f"${eps_match[0].strip()}"
                    if not eps_match[0].startswith("$")
                    else eps_match[0].strip(),
                    "period": period,
                    "citation": f"[Chunk {eps_chunk['chunk_id']}] {eps_match[1]}",
                    "context": "Diluted earnings per share.",
                }
            )

        # 6. Operating / Free Cash Flow
        cf_match, cf_chunk = self._find_pattern_in_chunks(
            chunks,
            [
                r"(?:free cash flow|operating cash flow|cash generated by operating activities)[^\n\.\$]*\$?([0-9,]+(?:\.[0-9]+)?\s*(?:million|billion|M|B)?)",
            ],
        )
        if cf_match and cf_chunk:
            metrics.append(
                {
                    "metric_name": "Operating / Free Cash Flow",
                    "value": self._format_currency(cf_match[0]),
                    "period": period,
                    "citation": f"[Chunk {cf_chunk['chunk_id']}] {cf_match[1]}",
                    "context": "Cash flow generation.",
                }
            )

        # 7. Total Debt / Leverage
        debt_match, debt_chunk = self._find_pattern_in_chunks(
            chunks,
            [
                r"(?:total (?:term )?debt|long-term debt|debt position)[^\n\.\$]*\$?([0-9,]+(?:\.[0-9]+)?\s*(?:million|billion|M|B)?)",
            ],
        )
        if debt_match and debt_chunk:
            metrics.append(
                {
                    "metric_name": "Total Debt / Leverage",
                    "value": self._format_currency(debt_match[0]),
                    "period": period,
                    "citation": f"[Chunk {debt_chunk['chunk_id']}] {debt_match[1]}",
                    "context": "Balance sheet debt obligations.",
                }
            )

        risk_factors = self._extract_risk_factors_deterministic(chunks)
        outlook = self._extract_outlook_deterministic(chunks)

        summary_name = company_name or (ticker if ticker else "The Company")
        exec_summary = (
            f"{summary_name} filed its {doc_type} for {period or 'the recent period'}. "
            f"The filing reveals revenue of {metrics[0]['value'] if metrics else 'undisclosed'}, "
            f"and the parser identified {len(risk_factors)} disclosed risk areas. "
            f"Extracted deterministically via offline document parser with chunk citations."
        )

        return {
            "company_name": company_name or (ticker if ticker else "Company"),
            "ticker": ticker,
            "doc_type": doc_type,
            "period": period,
            "executive_summary": exec_summary,
            "key_metrics": metrics,
            "risk_factors": risk_factors,
            "outlook": outlook,
        }

    # -- extraction helpers ------------------------------------------------ #
    @staticmethod
    def _find_pattern_in_chunks(
        chunks: list[dict[str, Any]], patterns: list[str]
    ) -> tuple[tuple[str, str] | None, dict[str, Any] | None]:
        for pattern in patterns:
            rx = re.compile(pattern, re.IGNORECASE)
            for chunk in chunks:
                lines = chunk["text"].split("\n")
                for line in lines:
                    match = rx.search(line)
                    if match:
                        val = match.group(1).strip()
                        sentence = line.strip()
                        return (val, sentence), chunk
        return None, None

    @staticmethod
    def _extract_risk_factors_deterministic(
        chunks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        risks: list[dict[str, Any]] = []
        numbered_rx = re.compile(r"^[0-9]+\.\s*([^:\n]+):\s*([^\n]+)", re.MULTILINE)
        severity_rx = re.compile(r"\(Severity:\s*(High|Medium|Low)\)", re.IGNORECASE)

        for chunk in chunks:
            # Look inside risk sections or chunks mentioning risk factors
            if "risk" in chunk["section"].lower() or "risk factors" in chunk["text"].lower() or "item 1a" in chunk["text"].lower():
                matches = list(numbered_rx.finditer(chunk["text"]))
                for m in matches:
                    title = m.group(1).strip()
                    desc = m.group(2).strip()
                    sev_match = severity_rx.search(desc)
                    severity = sev_match.group(1).capitalize() if sev_match else "Medium"
                    clean_desc = severity_rx.sub("", desc).strip()
                    risks.append(
                        {
                            "title": title,
                            "description": clean_desc,
                            "severity": severity if severity in {"Low", "Medium", "High"} else "Medium",
                            "citation": f"[Chunk {chunk['chunk_id']}] {m.group(0).strip()}",
                        }
                    )

        return risks

    @staticmethod
    def _extract_outlook_deterministic(chunks: list[dict[str, Any]]) -> str:
        for chunk in chunks:
            text_lower = chunk["text"].lower()
            section_lower = chunk.get("section", "").lower()
            if "outlook" in section_lower or "guidance" in section_lower or "outlook" in text_lower or "guidance" in text_lower:
                lines = [line.strip() for line in chunk["text"].split("\n") if line.strip()]
                for line in lines:
                    if (
                        line.startswith("ITEM ")
                        or line.startswith("PART ")
                        or (len(line) < 40 and line.isupper())
                        or re.match(r"^[0-9]+\.", line)
                    ):
                        continue
                    if any(w in line.lower() for w in ("anticipates", "expects", "forecasts", "guidance", "momentum", "expansion", "growth", "demand")):
                        return line
        return "No explicit management outlook was identified in this document."

    @staticmethod
    def _infer_doc_type(name: str, text: str) -> str:
        n_lower = name.lower()
        t_lower = text[:500].lower()
        if "10-k" in n_lower or "10-k" in t_lower or "form 10-k" in t_lower or "annual report" in t_lower:
            return "10-K Annual Report"
        if "10-q" in n_lower or "10-q" in t_lower or "quarterly report" in t_lower:
            return "10-Q Quarterly Report"
        if "earnings" in n_lower or "earnings release" in t_lower or "results" in t_lower:
            return "Earnings Release"
        return "Financial Document"

    @staticmethod
    def _infer_period(text: str) -> str:
        match = re.search(
            r"(?:fiscal(?:\s+year)?\s+(?:ended\s+)?)?(?:September|June|December|January|March|Q[1-4]|FY)?\s*(?:202[0-9])",
            text,
            re.IGNORECASE,
        )
        if match:
            return match.group(0).strip()
        return "Recent Period"

    @staticmethod
    def _infer_ticker_from_text(text: str) -> str | None:
        header = text[:600]
        for tk in ["AAPL", "MSFT", "NVDA"]:
            if tk in header:
                return tk
        return None

    @staticmethod
    def _format_currency(val: str) -> str:
        val = val.strip()
        if not val.startswith("$"):
            return f"${val}"
        return val
