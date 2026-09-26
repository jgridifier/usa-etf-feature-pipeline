"""Shared gate helper: cash-like tagging and excess-of-BIL Sharpe.

Part A of the NLS GMV v2 ticket (cash-null audit follow-up). Pure functions, no I/O
side effects beyond reading the committed CSVs they are pointed at.

* ``cash_like`` / ``short_duration`` tags live as boolean columns in
  ``data/raw/usa_universe_categorized.csv``. ``cash_like`` names (T-bill / floating-rate /
  ultrashort, duration <= ~1y) can be removed from the eligible set with
  :func:`filter_cash_like`. Runners call it ONCE on the shared eligible list, so the
  exclusion applies to the method and every null by construction. The flag defaults to
  ``True`` for new gates; archived trial dataclasses pin ``exclude_cash_like=False`` so
  their committed outputs are unchanged.
* Risk-free rate: BIL's priced monthly total return from the committed monthly panel from
  BIL's first full month on; before that, FRED ``TB3MS`` / 1200 (``data/raw/fred_tb3ms.csv``).
  :func:`window_rf_coverage` reports the share of a window that uses the fallback.
* ``Sharpe_exBIL = mean(r - rf) * 12 / (std(r - rf, ddof=1) * sqrt(12))`` (arithmetic,
  monthly). ``Sharpe_rf0`` stays the repo's legacy CAGR / vol (``vol_target.sharpe_rf0``)
  and is labelled "legacy (rf = 0)" wherever it is shown.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from .vol_target import annualized_vol, max_drawdown, sharpe_rf0

MONTHS_PER_YEAR = 12
CASH_LIKE = frozenset({"BIL", "SGOV", "SHV", "GBIL", "USFR", "GSST", "GUMI"})
SHORT_DURATION = frozenset({"SHY", "SPTS", "BSV", "STIP"})
CASH_LIKE_COLUMN = "cash_like"
SHORT_DURATION_COLUMN = "short_duration"
RF_TICKER = "BIL"
SHARPE_RF0_LABEL = "legacy (rf = 0)"
SHARPE_EXBIL_LABEL = "excess of BIL"

_REPO = Path(__file__).resolve().parents[2]
DEFAULT_PANEL = _REPO / "data" / "raw" / "usa_universe_panel_monthly_returns.csv"
DEFAULT_TB3MS = _REPO / "data" / "raw" / "fred_tb3ms.csv"


# --------------------------------------------------------------------------- tags
def _bool_col(universe: pd.DataFrame, col: str) -> pd.Series:
    if col not in universe.columns:
        raise KeyError(f"universe is missing the '{col}' tag column")
    s = universe[col]
    if s.dtype != bool:
        s = s.astype(str).str.strip().str.lower().map({"true": True, "false": False, "1": True, "0": False})
        if s.isna().any():
            raise ValueError(f"non-boolean values in '{col}'")
    return s.astype(bool)


def tagged_tickers(universe: pd.DataFrame, col: str) -> frozenset[str]:
    tick = universe["Ticker"].astype(str).str.strip().str.upper()
    return frozenset(tick[_bool_col(universe, col).to_numpy()])


def cash_like_tickers(universe: pd.DataFrame) -> frozenset[str]:
    return tagged_tickers(universe, CASH_LIKE_COLUMN)


def short_duration_tickers(universe: pd.DataFrame) -> frozenset[str]:
    return tagged_tickers(universe, SHORT_DURATION_COLUMN)


def is_cash_like(ticker: str, universe: pd.DataFrame) -> bool:
    return str(ticker).strip().upper() in cash_like_tickers(universe)


def filter_cash_like(names: Iterable[str], universe: pd.DataFrame,
                     exclude_cash_like: bool = True) -> list[str]:
    """Return ``names`` (order kept) without cash-like tickers when the flag is on.

    Call this once on the eligible list that feeds the method AND every null.
    """
    names = list(names)
    if not exclude_cash_like:
        return names
    cash = cash_like_tickers(universe)
    return [t for t in names if str(t).upper() not in cash]


def apply_gate_universe(panel: pd.DataFrame, universe: pd.DataFrame,
                        exclude_cash_like: bool = True) -> pd.DataFrame:
    """Drop cash-like columns from a returns panel shared by all strategies of a gate."""
    return panel.loc[:, filter_cash_like(panel.columns, universe, exclude_cash_like)]


def run_gate_strategies(panel: pd.DataFrame, universe: pd.DataFrame,
                        strategies: Mapping[str, "callable"],
                        exclude_cash_like: bool = True) -> dict[str, pd.Series]:
    """Evaluate every strategy (method and nulls) on the SAME filtered eligible panel.

    Each strategy is ``f(panel) -> weights Series`` indexed by ticker. Raises if any
    strategy returns weight on a name outside the eligible set.
    """
    eligible = apply_gate_universe(panel, universe, exclude_cash_like)
    allowed = set(eligible.columns)
    out = {}
    for name, fn in strategies.items():
        w = pd.Series(fn(eligible), dtype=float)
        bad = sorted(set(w.index[w.abs() > 0]) - allowed)
        if bad:
            raise ValueError(f"strategy {name!r} holds names outside the gate universe: {bad}")
        out[name] = w
    return out


# ------------------------------------------------------------------ risk-free rate
def load_tb3ms(path: str | Path = DEFAULT_TB3MS) -> pd.Series:
    """FRED TB3MS (percent, annualised, discount basis) -> monthly decimal rate TB3MS/1200."""
    df = pd.read_csv(path)
    date_col = "observation_date" if "observation_date" in df.columns else df.columns[0]
    s = pd.to_numeric(df["TB3MS"], errors="coerce")
    out = pd.Series(s.to_numpy() / 1200.0, index=pd.PeriodIndex(pd.to_datetime(df[date_col]), freq="M"),
                    name="tb3ms_monthly")
    if out.index.has_duplicates:
        raise ValueError("duplicate TB3MS months")
    return out.dropna().sort_index()


def load_bil_monthly(panel_path: str | Path = DEFAULT_PANEL) -> pd.Series:
    panel = pd.read_csv(panel_path, index_col=0, parse_dates=True)
    s = panel[RF_TICKER].astype(float)
    s.index = pd.PeriodIndex(s.index, freq="M")
    if s.index.has_duplicates:
        raise ValueError("duplicate months in the monthly panel")
    return s.sort_index()


def bil_first_full_month(bil: pd.Series) -> pd.Period:
    """First month with a priced BIL monthly return.

    Panel returns are month-end close to month-end close, so the inception month (no prior
    month-end price) is NaN and the first non-NaN month is BIL's first full month
    (2007-06 on the committed panel; BIL listed 2007-05-30).
    """
    first = bil.first_valid_index()
    if first is None:
        raise ValueError("BIL has no priced monthly return")
    if bil.loc[first:].isna().any():
        raise ValueError("BIL monthly return has gaps after its first full month")
    return first


def risk_free_monthly(bil: pd.Series | None = None, tb3ms: pd.Series | None = None) -> pd.DataFrame:
    """Monthly rf with its source: TB3MS/1200 before BIL's first full month, BIL after."""
    bil = load_bil_monthly() if bil is None else bil
    tb3ms = load_tb3ms() if tb3ms is None else tb3ms
    first = bil_first_full_month(bil)
    pre = tb3ms.loc[tb3ms.index < first]
    post = bil.loc[first:]
    rf = pd.concat([pd.DataFrame({"rf": pre, "source": "TB3MS"}),
                    pd.DataFrame({"rf": post, "source": "BIL"})])
    rf.index.name = "month"
    return rf.sort_index()


def _months(dates: Sequence) -> pd.PeriodIndex:
    idx = pd.Index(dates)
    if isinstance(idx, pd.PeriodIndex):
        return idx.asfreq("M")
    return pd.PeriodIndex(pd.to_datetime(idx), freq="M")


def align_rf(dates: Sequence, rf: pd.DataFrame) -> pd.DataFrame:
    months = _months(dates)
    missing = months.difference(rf.index)
    if len(missing):
        raise ValueError(f"no risk-free rate for months {list(missing.astype(str))[:5]}")
    return rf.loc[months]


def window_rf_coverage(dates: Sequence, rf: pd.DataFrame) -> dict:
    a = align_rf(dates, rf)
    n = len(a)
    fb = int((a["source"] == "TB3MS").sum())
    months = _months(dates)
    return {"start": str(months.min()), "end": str(months.max()), "n_months": n,
            "fallback_months": fb, "fallback_share": fb / n if n else float("nan"),
            "bil_share": (n - fb) / n if n else float("nan")}


# ------------------------------------------------------------------------- metrics
def sharpe_excess(returns: Sequence[float], rf: Sequence[float]) -> float:
    """Arithmetic annualised mean excess return / annualised std of excess returns."""
    ex = np.asarray(returns, float) - np.asarray(rf, float)
    if ex.size < 2 or not np.isfinite(ex).all():
        return float("nan")
    sd = ex.std(ddof=1)
    if sd <= 1e-15:
        # Holding exactly the risk-free asset: no excess return and no excess risk -> 0.
        return 0.0 if abs(ex.mean()) <= 1e-15 else float("nan")
    return float(ex.mean() * MONTHS_PER_YEAR / (sd * np.sqrt(MONTHS_PER_YEAR)))


def sharpe_exbil(returns: pd.Series, rf: pd.DataFrame | None = None) -> float:
    """Sharpe in excess of BIL (TB3MS fallback) for a date-indexed monthly return series."""
    r = pd.Series(returns, dtype=float).dropna()
    rf = risk_free_monthly() if rf is None else rf
    return sharpe_excess(r.to_numpy(), align_rf(r.index, rf)["rf"].to_numpy())


def gate_sharpe_table(series: Mapping[str, pd.Series] | pd.DataFrame,
                      rf: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per strategy: Sharpe_exBIL (headline), Sharpe_rf0 (legacy), vol, MaxDD, rf coverage.

    All series must share one date index (the gate window).
    """
    rf = risk_free_monthly() if rf is None else rf
    frame = pd.DataFrame(series) if not isinstance(series, pd.DataFrame) else series
    if frame.isna().any().any():
        raise ValueError("gate series must be complete on a common window")
    cov = window_rf_coverage(frame.index, rf)
    rfv = align_rf(frame.index, rf)["rf"].to_numpy()
    rows = []
    for name in frame.columns:
        r = frame[name].astype(float)
        rows.append({"strategy": name, "n_months": len(r), "start": cov["start"], "end": cov["end"],
                     "Sharpe_exBIL": sharpe_excess(r.to_numpy(), rfv),
                     "Sharpe_rf0_legacy": sharpe_rf0(r), "AnnVol": annualized_vol(r),
                     "MaxDD": max_drawdown(r), "rf_fallback_share": cov["fallback_share"],
                     "rf_bil_share": cov["bil_share"]})
    return pd.DataFrame(rows).set_index("strategy")
