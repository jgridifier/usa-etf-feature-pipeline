"""Feature formulas matching feature_pipeline_spec.md (Milestone 1)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .prices import daily_returns, history_years, month_end_prices


def mom12_1(prices: pd.Series | pd.DataFrame, asof: pd.Timestamp | None = None) -> float | pd.Series:
    """
    Momentum 12–1: product of monthly returns from lag 12 through lag 2
    (inclusive), minus 1 — skip lag 1 (most recent month).

    With month-end prices ending at t, lag k is the k-th prior monthly return
    R at iloc[-k]. Product k=2..12 equals P_{t-1}/P_{t-12} - 1 (classic 12-1).
    """
    if isinstance(prices, pd.Series):
        return _mom12_1_one(prices, asof)
    out = {}
    for col in prices.columns:
        out[col] = _mom12_1_one(prices[col], asof)
    return pd.Series(out, dtype=float)


def _mom12_1_one(prices: pd.Series, asof: pd.Timestamp | None) -> float:
    s = prices.dropna()
    if asof is not None:
        s = s.loc[:asof]
    me = month_end_prices(s.to_frame("_")).iloc[:, 0].dropna()
    # Need >= 13 month-end prices → 12 monthly returns
    if len(me) < 13:
        return float("nan")
    rets = me.pct_change()
    vals = []
    for k in range(2, 13):
        r = rets.iloc[-k]
        if pd.isna(r):
            return float("nan")
        vals.append(float(r))
    prod = 1.0
    for r in vals:
        prod *= 1.0 + r
    return prod - 1.0


def volatility(returns: pd.Series, window: int = 252, ddof: int = 1, ann: int = 252) -> float:
    """Annualized vol: sqrt(252) * sample std (ddof=1) over trailing window."""
    r = returns.dropna()
    if len(r) < max(2, ddof + 1):
        return float("nan")
    if len(r) >= window:
        r = r.iloc[-window:]
    return float(np.sqrt(ann) * r.std(ddof=ddof))


def vol_63(returns: pd.Series) -> float:
    return volatility(returns, window=63)


def vol_252(returns: pd.Series) -> float:
    return volatility(returns, window=252)


def maxdd_252(prices: pd.Series, lookback: int = 252) -> float:
    """
    Max drawdown over trailing `lookback` prices (default 252 ≈ t-251..t).
    MaxDD = min_u (P_u / max_{s in [start,u]} P_s - 1).
    """
    s = prices.dropna()
    if len(s) < 2:
        return float("nan")
    w = s.iloc[-lookback:] if len(s) >= lookback else s
    peak = w.cummax()
    dd = w / peak - 1.0
    return float(dd.min())


def quality_ir_er(
    asset_returns: pd.Series,
    bench_returns: pd.Series,
    er: float | None = None,
    lambda_er: float = 1.0,
    lookback: int = 252,
) -> tuple[float, bool]:
    """
    Q_v1 = IR - lambda_er * ER.
    IR = sqrt(252) * mean(e) / std(e), e = r_i - r_b over trailing lookback.
    If ER missing → 0 penalty and er_missing=True.
    """
    a = asset_returns.dropna()
    b = bench_returns.dropna()
    aligned = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    er_missing = bool(er is None or (isinstance(er, float) and np.isnan(er)))
    if aligned.empty or len(aligned) < 3:
        return float("nan"), bool(er_missing)
    if len(aligned) >= lookback:
        aligned = aligned.iloc[-lookback:]
    e = aligned["a"] - aligned["b"]
    std = float(e.std(ddof=1))
    if std == 0 or np.isnan(std):
        return float("nan"), bool(er_missing)
    ir = float(np.sqrt(252) * e.mean() / std)
    penalty = 0.0 if er_missing else float(er)
    return ir - lambda_er * penalty, bool(er_missing)


def liquidity_adv(
    prices: pd.Series,
    volume: pd.Series | None = None,
    lookback: int = 21,
) -> tuple[float, bool]:
    """ADV$ over L sessions. If volume absent → (NaN, liquidity_missing=True)."""
    if volume is None:
        return float("nan"), True
    df = pd.concat([prices.rename("p"), volume.rename("v")], axis=1).dropna()
    if len(df) < 1:
        return float("nan"), True
    df = df.iloc[-lookback:] if len(df) >= lookback else df
    return float((df["v"] * df["p"]).mean()), False


def compute_raw_features(
    prices: pd.DataFrame,
    volumes: pd.DataFrame | None = None,
    expense_ratios: dict[str, float] | None = None,
    benchmark: str = "VOO",
    fallback_benchmark: str = "VTI",
    asof: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Compute raw feature panel for all columns in prices."""
    px = prices.copy()
    if asof is not None:
        px = px.loc[:asof]
    rets = daily_returns(px)

    if benchmark in px.columns and px[benchmark].dropna().shape[0] > 50:
        bench_name = benchmark
    elif fallback_benchmark in px.columns:
        bench_name = fallback_benchmark
    else:
        raise ValueError(f"Benchmark {benchmark}/{fallback_benchmark} not in prices")
    bench_r = rets[bench_name]

    rows = []
    er_map = {k.upper(): v for k, v in (expense_ratios or {}).items()}
    for ticker in px.columns:
        p = px[ticker]
        r = rets[ticker]
        er = er_map.get(str(ticker).upper())
        q, er_miss = quality_ir_er(r, bench_r, er=er)
        vol = None
        if volumes is not None and ticker in volumes.columns:
            vol = volumes[ticker]
        adv, liq_miss = liquidity_adv(p, vol)
        rows.append(
            {
                "ticker": ticker,
                "mom12_1": float(mom12_1(p)),
                "vol_63": vol_63(r),
                "vol_252": vol_252(r),
                "maxdd_252": maxdd_252(p),
                "quality_v1": q,
                "er_missing": er_miss,
                "liquidity_adv": adv,
                "liquidity_missing": liq_miss,
                "history_years": history_years(p),
                "benchmark_used": bench_name,
            }
        )
    return pd.DataFrame(rows).set_index("ticker")
