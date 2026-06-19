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
        index["tickers"][ticker] = profile["company_name"]

    (samples_dir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return samples_dir


def main() -> None:
    out = generate_all()
    tickers = ", ".join(TICKERS)
    print(f"Wrote sample data for {tickers} to {out}")


if __name__ == "__main__":
    main()
