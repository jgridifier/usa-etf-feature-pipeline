"""Price loaders (local CSV; yfinance stub for later)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_adj_close_csv(path: str | Path) -> pd.DataFrame:
    """Load wide adj-close panel: Date index, ticker columns."""
    df = pd.read_csv(path)
    date_col = None
    for c in df.columns:
        if str(c).lower() in {"date", "datetime", "timestamp"}:
            date_col = c
            break
    if date_col is None:
        date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df.apply(pd.to_numeric, errors="coerce")


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change()


def month_end_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Last available price in each calendar month (month-end proxy)."""
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise TypeError("prices index must be DatetimeIndex")
    return prices.resample("ME").last().dropna(how="all")


def history_years(prices: pd.Series) -> float:
    s = prices.dropna()
    if len(s) < 2:
        return 0.0
    days = (s.index.max() - s.index.min()).days
    return days / 365.25
