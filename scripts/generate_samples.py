"""Generate reproducible sample data for the bundled tickers.

Run once after install:  ``python scripts/generate_samples.py``

The output (price CSVs, fundamentals/news JSON, and an index) is what the data
providers fall back to when live ``yfinance`` lookups are unavailable. Prices
are a seeded geometric Brownian motion so the files are deterministic — the
same every time, regardless of when you run it.

These are synthetic, illustrative figures — not real market data.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = PROJECT_ROOT / "src" / "finance_workflow" / "data" / "samples"

# Fixed reference end date so committed sample data stays stable across runs.
END_DATE = "2026-06-18"
N_DAYS = 260  # ~ one year of trading days

# Per-ticker synthetic profile: (name, sector, industry, start_price, annual_drift,
# annual_vol, market_cap, trailing_pe, forward_pe, p/b, margin, rev_growth, div_yield, beta, summary)
TICKERS: dict[str, dict] = {
    "AAPL": {
        "company_name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "start_price": 185.0,
        "drift": 0.12,
        "vol": 0.26,
        "market_cap": 3_050_000_000_000,
        "trailing_pe": 31.2,
        "forward_pe": 28.4,
        "price_to_book": 46.0,
        "profit_margin": 0.262,
        "revenue_growth": 0.052,
        "dividend_yield": 0.0046,
        "beta": 1.21,
        "summary": (
            "Apple designs and sells consumer electronics, software, and services, "
            "anchored by the iPhone with a fast-growing high-margin services segment."
        ),
    },
    "MSFT": {
        "company_name": "Microsoft Corporation",
        "sector": "Technology",
        "industry": "Software—Infrastructure",
        "start_price": 410.0,
        "drift": 0.16,
        "vol": 0.24,
        "market_cap": 3_300_000_000_000,
        "trailing_pe": 35.8,
        "forward_pe": 30.1,
        "price_to_book": 12.5,
        "profit_margin": 0.361,
        "revenue_growth": 0.155,
        "dividend_yield": 0.0072,
        "beta": 0.93,
        "summary": (
            "Microsoft develops software, cloud (Azure), and productivity platforms. "
            "Cloud and AI services are the primary growth engines."
        ),
    },
    "NVDA": {
        "company_name": "NVIDIA Corporation",
        "sector": "Technology",
        "industry": "Semiconductors",
        "start_price": 120.0,
        "drift": 0.35,
        "vol": 0.52,
        "market_cap": 3_100_000_000_000,
        "trailing_pe": 58.0,
        "forward_pe": 38.7,
        "price_to_book": 49.0,
        "profit_margin": 0.488,
        "revenue_growth": 0.612,
        "dividend_yield": 0.0003,
        "beta": 1.67,
        "summary": (
            "NVIDIA designs GPUs and accelerated-computing platforms central to AI "
            "training and inference, with very high margins and rapid revenue growth."
        ),
    },
}


def _price_series(profile: dict, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=END_DATE, periods=N_DAYS)
    dt = 1 / 252
    mu, sigma = profile["drift"], profile["vol"]
    shocks = rng.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), size=N_DAYS)
    close = profile["start_price"] * np.exp(np.cumsum(shocks))

    # Build plausible OHLCV around the close path.
    intraday = np.abs(rng.normal(0, sigma * np.sqrt(dt), size=N_DAYS))
    open_ = close * (1 + rng.normal(0, 0.003, size=N_DAYS))
    high = np.maximum(open_, close) * (1 + intraday)
    low = np.minimum(open_, close) * (1 - intraday)
    volume = rng.integers(20_000_000, 90_000_000, size=N_DAYS)

    return pd.DataFrame(
        {
            "Date": dates,
            "Open": open_.round(2),
            "High": high.round(2),
            "Low": low.round(2),
            "Close": close.round(2),
            "Volume": volume,
        }
    )


def _news(ticker: str, profile: dict) -> list[dict]:
    name = profile["company_name"]
    return [
        {
            "title": f"{name} reports quarterly results, reaffirms full-year outlook",
            "publisher": "Sample Wire",
            "published": "2026-06-16",
            "summary": (
                f"{name} posted results broadly in line with expectations and kept its "
                "guidance unchanged, citing steady demand."
            ),
            "url": f"https://example.com/{ticker.lower()}/earnings",
        },
        {
            "title": f"Analysts weigh {name} valuation after recent run",
            "publisher": "Sample Markets",
            "published": "2026-06-12",
            "summary": (
                "Commentators are split on whether the current multiple is justified by "
                "the growth outlook."
            ),
            "url": f"https://example.com/{ticker.lower()}/valuation",
        },
        {
            "title": f"{name} expands product roadmap at industry event",
            "publisher": "Sample Tech Daily",
            "published": "2026-06-05",
            "summary": "New products were previewed, with availability expected later in the year.",
            "url": f"https://example.com/{ticker.lower()}/roadmap",
        },
    ]


def _fundamentals(profile: dict) -> dict:
    keys = (
        "company_name",
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
        "summary",
    )
    return {k: profile[k] for k in keys}


def _filing_10k(ticker: str, profile: dict) -> str:
    name = profile["company_name"]
    if ticker == "AAPL":
        return f"""UNITED STATES SECURITIES AND EXCHANGE COMMISSION
Washington, D.C. 20549
FORM 10-K
ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934
For the fiscal year ended September 27, 2025
Commission File Number: 001-36743
{name.upper()}

ITEM 1. BUSINESS
{name} designs, manufactures, and markets smartphones, personal computers, tablets, wearables, and accessories, and sells a variety of related services.

ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS
Fiscal 2025 Consolidated Financial Results and Highlights:
- Revenue / Total Net Sales: Total net sales reached $391,035 million in fiscal 2025, up 2.0% compared to $383,285 million in fiscal 2024, driven by record performance in Services ($96,169 million) and resilient iPhone sales.
- Gross Margin: Gross margin was $180,683 million, representing a 46.2% gross margin, compared to $170,782 million (44.6% gross margin) in fiscal 2024.
- Operating Income and Operating Margin: Operating income increased to $123,216 million (operating margin of 31.5%) compared to $114,301 million (29.8% operating margin) in fiscal 2024.
- Net Income: Net income for the fiscal year was $102,450 million (net profit margin of 26.2%), compared to $96,995 million in fiscal 2024.
- Diluted Earnings Per Share (EPS): Diluted earnings per share (EPS) rose to $6.75 per diluted share, compared to $6.11 in the previous fiscal year.
- Operating Cash Flow and Free Cash Flow: Cash generated by operating activities was $118,254 million. Deducting capital expenditures of $9,450 million yielded Free Cash Flow of $108,804 million.
- Debt and Capital Resources: Total term debt was $106,629 million as of year-end, while cash, cash equivalents, and marketable securities stood at $156,652 million.

ITEM 1A. RISK FACTORS
The Company's business and financial results are subject to significant risks:
1. Global Supply Chain Concentration: The Company depends on single-source or concentrated third-party manufacturing partners primarily located in Asia. Any disruption from geopolitical tensions, natural disasters, or export controls could materially reduce shipments. (Severity: High)
2. Geopolitical and Trade Complexities: International trade restrictions, tariffs, and regulatory scrutiny in foreign markets could impair gross margins and market access. (Severity: High)
3. Rapid Technological Change & AI: Failure to innovate and deploy competitive artificial intelligence capabilities across operating systems and hardware could erode customer loyalty and ecosystem value. (Severity: Medium)
4. Regulatory and Antitrust Scrutiny: Evolving digital market regulations (e.g. EU Digital Markets Act) and governmental antitrust inquiries targeting app ecosystem fees may restrict business practices and impact service revenue. (Severity: High)
5. Information Security and Privacy: Security breaches, cyberattacks, or network outages could compromise user privacy, harm brand equity, and result in substantial financial liabilities. (Severity: Medium)

ITEM 7A. OUTLOOK AND GUIDANCE
Management anticipates continued moderate revenue expansion fueled by installed base growth, higher customer engagement in cloud and digital services, and expanding subscription offerings.
"""
    elif ticker == "MSFT":
        return f"""UNITED STATES SECURITIES AND EXCHANGE COMMISSION
Washington, D.C. 20549
FORM 10-K
ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934
For the fiscal year ended June 30, 2025
Commission File Number: 001-14278
{name.upper()}

ITEM 1. BUSINESS
{name} is a global leader in technology, delivering software, cloud infrastructure (Azure), productivity platforms (Microsoft 365), and personal computing solutions.

ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS
Fiscal 2025 Financial Performance:
- Revenue / Total Net Sales: Total revenue was $245,120 million in fiscal 2025, an increase of 15.5% compared to $211,915 million in fiscal 2024, driven by commercial cloud demand.
- Gross Margin: Gross margin expanded to $170,858 million, achieving a 69.7% gross margin compared to $146,052 million (68.9%) in fiscal 2024.
- Operating Income and Operating Margin: Operating income totaled $109,433 million, representing an operating margin of 44.6%, up 24% year-over-year.
- Net Income: Net income reached $88,488 million (net profit margin of 36.1%), compared to $72,361 million in the prior fiscal year.
- Diluted Earnings Per Share (EPS): Diluted earnings per share (EPS) was $11.86 per share, compared to $9.68 in fiscal 2024.
- Cash Flow and Free Cash Flow: Operating cash flow reached $118,548 million. After capital expenditures of $44,500 million for cloud and AI datacenters, Free Cash Flow stood at $74,048 million.
- Debt Position: Long-term debt and finance leases were $47,250 million, supported by cash and short-term investments of $75,500 million.

ITEM 1A. RISK FACTORS
Key risk considerations include:
1. Intense Cloud & AI Competition: Fierce competition from other hyperscale cloud providers and AI foundation model builders could pressure pricing and market share. (Severity: High)
2. Datacenter Infrastructure and Capital Intensity: High capital expenditures for AI infrastructure and specialized silicon availability constraints could depress returns on invested capital. (Severity: Medium)
3. Cybersecurity and Platform Resilience: Sophisticated state-sponsored cyberattacks or cloud outages could disrupt enterprise operations and trigger severe regulatory penalties. (Severity: High)
4. Regulatory and Antitrust Oversight: Scrutiny over AI partnerships, software bundling, and cross-border data sovereignty could impose compliance overhead and structural constraints. (Severity: Medium)
5. Macroeconomic and Enterprise IT Spending: Slower global enterprise IT budget growth could lengthen sales cycles for cloud migrations and software renewals. (Severity: Medium)

ITEM 7A. OUTLOOK AND GUIDANCE
Management expects commercial cloud revenue to continue driving top-line growth, with ongoing AI investments expanding addressable software markets.
"""
    else:  # NVDA
        return f"""UNITED STATES SECURITIES AND EXCHANGE COMMISSION
Washington, D.C. 20549
FORM 10-K
ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934
For the fiscal year ended January 25, 2026
Commission File Number: 000-26497
{name.upper()}

ITEM 1. BUSINESS
{name} pioneered accelerated computing to tackle challenges no one else can solve. The company's platforms power generative AI, high-performance computing (HPC), gaming, and autonomous systems.

ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS
Fiscal 2026 Financial Highlights:
- Revenue / Total Net Sales: Total revenue was $126,050 million, an increase of 61.2% year-over-year compared to $78,190 million in fiscal 2025, powered by Compute & Networking data center platforms.
- Gross Margin: Gross margin was $94,537 million (75.0% gross margin), reflecting strong data center pricing power and full-stack software monetization.
- Operating Income and Operating Margin: Operating income climbed to $78,151 million, generating an exceptional operating margin of 62.0%.
- Net Income: Net income was $61,512 million (net profit margin of 48.8%), compared to $34,480 million in the previous fiscal year.
- Diluted Earnings Per Share (EPS): Diluted earnings per share (EPS) surged to $2.48 per diluted share (post-split adjusted) from $1.39 in fiscal 2025.
- Cash Flow and Free Cash Flow: Operating cash flow was $65,200 million. Capital expenditures were $3,100 million, producing Free Cash Flow of $62,100 million.
- Balance Sheet and Debt: Total debt remained modest at $11,000 million, while cash, cash equivalents, and marketable securities reached $43,500 million.

ITEM 1A. RISK FACTORS
The Company's operations are subject to distinct operational and geopolitical risks:
1. Customer and Channel Concentration: A significant portion of Compute revenue is concentrated among a small number of cloud service providers and tier-one hyperscalers. (Severity: High)
2. Export Controls and Geopolitical Tensions: U.S. government licensing requirements and restrictions on shipping advanced GPUs to certain international regions impact revenue opportunities. (Severity: High)
3. Advanced Packaging and Foundry Dependencies: The Company relies heavily on single or limited foundry partners (such as TSMC) for wafer fabrication and advanced CoWoS packaging. (Severity: High)
4. AI Demand Volatility and Transition Cycles: Transitioning between GPU architecture generations (e.g. Hopper to Blackwell) may create product transition pauses or inventory adjustments. (Severity: Medium)
5. Custom Silicon Competition: Major cloud customers developing internal ASIC accelerators could moderate long-term external GPU procurement growth. (Severity: Medium)

ITEM 7A. OUTLOOK AND GUIDANCE
Demand for accelerated computing and generative AI infrastructure remains strong across enterprise software, autonomous vehicles, and sovereign AI initiatives.
"""


def generate_all(samples_dir: Path = SAMPLES_DIR, force: bool = True) -> Path:
    """Write all sample files. Returns the samples directory."""
    samples_dir.mkdir(parents=True, exist_ok=True)
    index = {"generated_end_date": END_DATE, "tickers": {}}

    for seed, (ticker, profile) in enumerate(TICKERS.items(), start=1):
        tdir = samples_dir / ticker
        tdir.mkdir(parents=True, exist_ok=True)

        prices_path = tdir / "prices.csv"
        if force or not prices_path.exists():
            _price_series(profile, seed).to_csv(prices_path, index=False)

        (tdir / "fundamentals.json").write_text(
            json.dumps(_fundamentals(profile), indent=2), encoding="utf-8"
        )
        (tdir / "news.json").write_text(
            json.dumps(_news(ticker, profile), indent=2), encoding="utf-8"
        )
        (tdir / "filing_10k.txt").write_text(
            _filing_10k(ticker, profile), encoding="utf-8"
        )
        index["tickers"][ticker] = profile["company_name"]

    (samples_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return samples_dir


def main() -> None:
    out = generate_all()
    tickers = ", ".join(TICKERS)
    print(f"Wrote sample data for {tickers} to {out}")


if __name__ == "__main__":
    main()
