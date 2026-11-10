"""Daily price loading and data-quality checks.

Prices are read from CSV files (``<data_dir>/<TICKER>.csv`` with ``date`` and
``close`` columns) until the Supabase prices table exists. The daily job (FR7)
will use ``validate`` to refuse bad data before it overwrites good data.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

SUPPORTED_TICKERS = ("META", "PLTR")
BENCHMARK_TICKERS = ("SPY",)

EARLIEST_DATES: dict[str, date] = {
    "META": date(2012, 5, 18),  # IPO
    "PLTR": date(2020, 9, 30),  # direct listing
    "SPY": date(1993, 1, 29),
}

MAX_CALENDAR_GAP_DAYS = 5
"""Longer than any weekend plus market holiday, so a bigger gap means missing data."""
MAX_DAILY_MOVE = 0.75
"""A one-day move bigger than this is far more likely bad data than a real move."""

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "prices"


class PriceData:
    def __init__(self, ticker: str, data_dir: Path | str = DEFAULT_DATA_DIR) -> None:
        ticker = ticker.upper()
        if ticker not in SUPPORTED_TICKERS + BENCHMARK_TICKERS:
            raise ValueError(f"Unsupported ticker: {ticker}")
        self.ticker = ticker
        self.data_dir = Path(data_dir)
        self.frame: pd.DataFrame | None = None

    def load(self, start: date | None = None, end: date | None = None) -> pd.DataFrame:
        path = self.data_dir / f"{self.ticker}.csv"
        if not path.exists():
            raise FileNotFoundError(f"No price file for {self.ticker} at {path}")
        frame = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
        if start is not None:
            frame = frame[frame.index >= pd.Timestamp(start)]
        if end is not None:
            frame = frame[frame.index <= pd.Timestamp(end)]
        self.frame = frame
        return frame

    def closes(self) -> pd.Series:
        if self.frame is None:
            raise RuntimeError("Call load() first")
        return self.frame["close"].astype(float)

    def validate(self) -> list[str]:
        """Return a list of human-readable problems; empty means the data passed."""
        if self.frame is None:
            raise RuntimeError("Call load() first")
        return validate_prices(self.frame)


def validate_prices(frame: pd.DataFrame) -> list[str]:
    problems: list[str] = []
    if frame.empty:
        return ["No price rows"]
    if "close" not in frame.columns:
        return ["Missing 'close' column"]

    dupes = frame.index[frame.index.duplicated()].unique()
    if len(dupes):
        problems.append(f"Duplicate dates: {', '.join(d.strftime('%Y-%m-%d') for d in dupes[:5])}")

    close = frame["close"]
    if close.isna().any():
        problems.append(f"{int(close.isna().sum())} missing close prices")
    if (close <= 0).any():
        problems.append(f"{int((close <= 0).sum())} non-positive close prices")

    unique_index = frame.index[~frame.index.duplicated()].sort_values()
    gaps = pd.Series(unique_index[1:] - unique_index[:-1], index=unique_index[1:])
    long_gaps = gaps[gaps > pd.Timedelta(days=MAX_CALENDAR_GAP_DAYS)]
    for when, gap in long_gaps.head(5).items():
        problems.append(f"Missing days: {gap.days}-day gap ending {when:%Y-%m-%d}")

    moves = close[~frame.index.duplicated()].sort_index().pct_change().abs()
    for when in moves[moves > MAX_DAILY_MOVE].index[:5]:
        problems.append(f"Suspicious price jump on {when:%Y-%m-%d}")

    return problems
