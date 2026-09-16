"""Thematic rotation signals (v1.1 ScoreSimple) — research only, not advice.

Primary: ON iff Mom12_1(i) > Mom12_1(VOO).
ScoreSimple (+ vol gate): ON iff (z(Mom12_1_i)>0 OR excess Mom>0)
  AND vol_63 ≤ expanding Q90(vol_63) through t-1 only (no peeking).
Optional hysteresis: stay ON until raw signal fails hysteresis_months consecutive MEs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml

from .features import mom12_1, vol_63
from .prices import daily_returns
from .universe import UniverseGateError, assert_eligible, load_universe_config, load_universe_csv


OFF_LIST_SEMIS = frozenset({"SMH", "SOXX", "SOXL", "PSI"})


def load_portfolio_constraints(path: str | Path | None = None) -> dict:
    if path is None:
        candidates = [
            Path("config/portfolio_constraints.yaml"),
            Path(__file__).resolve().parents[2] / "config" / "portfolio_constraints.yaml",
        ]
        for c in candidates:
            if c.exists():
                path = c
                break
        else:
            return {
                "thematic_rotate_eligible": ["XSD"],
                "thematic_tickers": ["XSD", "XBI", "LOUP", "GTEK", "GINN", "BBC"],
                "thematic_cap": 0.25,
                "single_name_cap_thematic": 0.15,
                "rotate_on_weight": 0.10,
                "hysteresis_months": 2,
                "vol_gate_quantile": 0.90,
                "vol_gate_min_periods": 21,
                "core_when_thematic_off": {"VOO": 0.70, "QQQM": 0.20, "IJR": 0.10},
                "rotate_benchmark": "VOO",
                "rotate_thematic_default": False,
            }
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def month_end_trading_dates(prices: pd.DataFrame) -> pd.DatetimeIndex:
    """Actual last trading day per calendar month (matches xsd_rotation_backtest)."""
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise TypeError("prices index must be DatetimeIndex")
    me = prices.groupby(prices.index.to_period("M")).apply(lambda x: x.index.max())
    return pd.DatetimeIndex(me.values).sort_values()


def mom12_1_series(monthly_returns: pd.Series) -> pd.Series:
    """Product of monthly returns lag 12..lag 2 (skip lag 1), minus 1 — full series."""
    log_sum = sum(np.log1p(monthly_returns.shift(k)) for k in range(2, 13))
    return np.expm1(log_sum)


def expanding_z(s: pd.Series, min_periods: int = 12) -> pd.Series:
    """Expanding z using mean/std through prior observation only (shift 1)."""
    mu = s.expanding(min_periods=min_periods).mean().shift(1)
    sd = s.expanding(min_periods=min_periods).std(ddof=1).shift(1)
    return (s - mu) / sd


def vol63_at_month_ends(prices: pd.Series, me_dates: pd.DatetimeIndex) -> pd.Series:
    """Annualized 63d vol on daily returns, sampled at month-end trading dates."""
    r = daily_returns(prices.to_frame("_")).iloc[:, 0]
    vol = r.rolling(63, min_periods=63).std(ddof=1) * np.sqrt(252)
    return vol.reindex(me_dates).ffill()


def expanding_vol_ok(
    vol_me: pd.Series,
    quantile: float = 0.90,
    min_periods: int = 21,
) -> pd.Series:
    """True when vol ≤ expanding quantile through t-1 only."""
    thr = vol_me.expanding(min_periods=min_periods).quantile(quantile).shift(1)
    return vol_me <= thr


def apply_hysteresis(raw_on: pd.Series, hysteresis_months: int = 2) -> pd.Series:
    """
    Stay ON until raw signal fails for `hysteresis_months` consecutive month-ends.
    Turning ON is immediate when raw_on becomes True.
    """
    if hysteresis_months is None or hysteresis_months <= 1:
        return raw_on.astype(bool)

    out = []
    state = False
    fail_streak = 0
    for val in raw_on.fillna(False).astype(bool):
        if val:
            state = True
            fail_streak = 0
        else:
            if state:
                fail_streak += 1
                if fail_streak >= hysteresis_months:
                    state = False
                    fail_streak = 0
            else:
                fail_streak = 0
        out.append(state)
    return pd.Series(out, index=raw_on.index, dtype=bool)


def assert_rotate_tickers_eligible(
    tickers: Iterable[str],
    universe_df: pd.DataFrame | None = None,
    universe_config: dict | None = None,
) -> None:
    """Hard-fail SMH/SOXX/SOXL/PSI (and any non-eligible) under rotate path."""
    tickers = [str(t).strip().upper() for t in tickers]
    for t in tickers:
        if t in OFF_LIST_SEMIS:
            raise UniverseGateError(
                f"Ticker {t} is not eligible (off-list hard deny). "
                "SMH/SOXX/SOXL/PSI must never be injected under --rotate-thematic."
            )
    if universe_df is not None:
        assert_eligible(tickers, universe_df, universe_config or load_universe_config())


def score_simple_raw_on(
    mom_i: pd.Series,
    mom_bench: pd.Series,
    vol_ok: pd.Series,
    use_vol_gate: bool = True,
) -> pd.Series:
    """
    ScoreSimple-style raw ON series (before hysteresis).
    Without vol gate: Mom_i > Mom_bench.
    With vol gate: (z(Mom_i)>0 OR excess>0) AND vol_ok  (expanding z through t-1).
    """
    excess = mom_i - mom_bench
    if not use_vol_gate:
        return (excess > 0).fillna(False)

    z = expanding_z(mom_i)
    mom_ok = (z > 0) | (excess > 0)
    # If z or vol_ok NaN → OFF (insufficient history), matching backtest
    raw = mom_ok & vol_ok.fillna(False)
    raw = raw.where(z.notna() & vol_ok.notna(), False)
    return raw.fillna(False).astype(bool)


def compute_rotation_signals(
    prices: pd.DataFrame,
    tickers: list[str],
    benchmark: str = "VOO",
    use_vol_gate: bool = True,
    hysteresis_months: int = 0,
    vol_quantile: float = 0.90,
    vol_min_periods: int = 21,
    asof: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """
    Month-end rotation diagnostics + ON flags for each thematic ticker.

    Columns per ticker prefix or long format rows:
      date, ticker, mom12_1, mom12_1_bench, excess_mom, z_mom, vol63, vol_ok,
      raw_on, on
    """
    px = prices.copy()
    if asof is not None:
        px = px.loc[:asof]
    need = list(dict.fromkeys([*tickers, benchmark]))
    missing = [t for t in need if t not in px.columns]
    if missing:
        raise ValueError(f"Missing price columns for rotation: {missing}")

    me_dates = month_end_trading_dates(px[need])
    me_px = px.loc[me_dates, need]
    me_ret = me_px.pct_change()
    mom_bench = mom12_1_series(me_ret[benchmark])

    rows = []
    for t in tickers:
        mom_i = mom12_1_series(me_ret[t])
        vol_me = vol63_at_month_ends(px[t], me_dates)
        vok = expanding_vol_ok(vol_me, quantile=vol_quantile, min_periods=vol_min_periods)
        raw = score_simple_raw_on(mom_i, mom_bench, vok, use_vol_gate=use_vol_gate)
        on = apply_hysteresis(raw, hysteresis_months=hysteresis_months) if hysteresis_months else raw
        z = expanding_z(mom_i)
        for d in me_dates:
            rows.append(
                {
                    "date": d,
                    "ticker": t,
                    "mom12_1": float(mom_i.loc[d]) if pd.notna(mom_i.loc[d]) else np.nan,
                    "mom12_1_bench": float(mom_bench.loc[d]) if pd.notna(mom_bench.loc[d]) else np.nan,
                    "excess_mom": (
                        float(mom_i.loc[d] - mom_bench.loc[d])
                        if pd.notna(mom_i.loc[d]) and pd.notna(mom_bench.loc[d])
                        else np.nan
                    ),
                    "z_mom": float(z.loc[d]) if pd.notna(z.loc[d]) else np.nan,
                    "vol63": float(vol_me.loc[d]) if pd.notna(vol_me.loc[d]) else np.nan,
                    "vol_ok": bool(vok.loc[d]) if pd.notna(vok.loc[d]) else False,
                    "raw_on": bool(raw.loc[d]),
                    "on": bool(on.loc[d]),
                }
            )
    return pd.DataFrame(rows)


def signal_on_asof(
    prices: pd.DataFrame,
    ticker: str,
    asof: pd.Timestamp | None = None,
    benchmark: str = "VOO",
    use_vol_gate: bool = True,
    hysteresis_months: int = 0,
    vol_quantile: float = 0.90,
    vol_min_periods: int = 21,
) -> bool:
    """Boolean ON for a single ticker at the latest month-end ≤ asof (or last available)."""
    sig = compute_rotation_signals(
        prices,
        [ticker],
        benchmark=benchmark,
        use_vol_gate=use_vol_gate,
        hysteresis_months=hysteresis_months,
        vol_quantile=vol_quantile,
        vol_min_periods=vol_min_periods,
        asof=asof,
    )
    if sig.empty:
        return False
    # Drop rows without enough Mom history
    sub = sig.dropna(subset=["mom12_1", "mom12_1_bench"])
    if sub.empty:
        return False
    return bool(sub.iloc[-1]["on"])


def point_in_time_mom_on(
    prices_i: pd.Series,
    prices_bench: pd.Series,
    decision_date: pd.Timestamp,
) -> bool:
    """
    Point-in-time Mom12_1(i) > Mom12_1(bench) using only data through decision_date.
    Used by unit tests to prove no lookahead on the decision date.
    """
    m_i = mom12_1(prices_i.loc[:decision_date])
    m_b = mom12_1(prices_bench.loc[:decision_date])
    if np.isnan(m_i) or np.isnan(m_b):
        return False
    return bool(m_i > m_b)
