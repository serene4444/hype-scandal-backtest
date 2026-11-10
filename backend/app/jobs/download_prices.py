"""Download daily closing prices into the prices table.

Run from the backend folder:

    python -m app.jobs.download_prices            # META, PLTR and SPY
    python -m app.jobs.download_prices PLTR       # just one

Prices are split- and dividend-adjusted closes from Yahoo Finance (yfinance).
Each download is checked with ``validate_prices`` first, and a ticker is only
replaced when the new data passes, so bad data never replaces good data. The
rows go to Supabase when DATABASE_URL is set, otherwise to the local SQLite
file. The daily GitHub Action (FR7) will run this same module.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

import pandas as pd

from app import store
from app.core.prices import BENCHMARK_TICKERS, EARLIEST_DATES, SUPPORTED_TICKERS, validate_prices
from app.db import database_url

ALL_TICKERS = SUPPORTED_TICKERS + BENCHMARK_TICKERS


def fetch_closes(ticker: str) -> pd.DataFrame:
    import yfinance as yf  # only needed by this job, not by the API

    history = yf.Ticker(ticker).history(
        start=EARLIEST_DATES[ticker].isoformat(),
        end=(date.today() + timedelta(days=1)).isoformat(),
        auto_adjust=True,
        actions=False,
    )
    if history.empty:
        raise RuntimeError(f"Yahoo Finance returned no rows for {ticker}")
    frame = pd.DataFrame(
        {"close": history["Close"].round(4).to_numpy()},
        index=pd.DatetimeIndex(history.index.tz_localize(None).normalize(), name="date"),
    )
    return frame.dropna()


def save(ticker: str, frame: pd.DataFrame) -> int:
    problems = validate_prices(frame)
    if problems:
        raise ValueError(f"{ticker}: refusing to save, data checks failed: {'; '.join(problems)}")
    return store.save_prices(ticker, frame)


def main(tickers: list[str]) -> int:
    target = "Postgres (DATABASE_URL)" if database_url().startswith("postgresql") else "local SQLite"
    print(f"Saving to {target}")
    failed = 0
    for ticker in tickers:
        ticker = ticker.upper()
        if ticker not in ALL_TICKERS:
            print(f"{ticker}: not supported (choose from {', '.join(ALL_TICKERS)})")
            failed += 1
            continue
        try:
            frame = fetch_closes(ticker)
            save(ticker, frame)
        except Exception as exc:  # report every ticker, then fail at the end
            print(f"{ticker}: FAILED - {exc}")
            failed += 1
            continue
        print(f"{ticker}: {len(frame)} days, {frame.index[0]:%Y-%m-%d} to {frame.index[-1]:%Y-%m-%d} saved")
    return 1 if failed else 0


if __name__ == "__main__":
    from app.settings import load_env

    load_env()  # picks up DATABASE_URL from backend/.env
    sys.exit(main(sys.argv[1:] or list(ALL_TICKERS)))
