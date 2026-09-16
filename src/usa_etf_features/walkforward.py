"""Walk-forward information coefficient (IC) — no same-period label leakage.

At each month-end decision date T_{k-1}:
  - Features / scores use prices only through T_{k-1}.
  - Labels = next-month excess return on (T_{k-1}, T_k] (the subsequent month-end return).
Forbidden: using same-month or future returns inside features for that decision date.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .features import compute_raw_features
from .portfolio import (
    TURNOVER_COST_BPS,
    build_optimized_portfolio,
    optimizer_strategy_registry,
)
from .rotation import compute_rotation_signals, month_end_trading_dates
from .scores import composite_scores, load_feature_weights
from .universe import assert_eligible, load_universe_config, load_universe_csv


def next_month_excess(
    me_ret: pd.DataFrame,
    decision_date: pd.Timestamp,
    tickers: list[str],
    benchmark: str = "VOO",
) -> pd.Series:
    """Excess monthly return of tickers vs benchmark over the month AFTER decision_date."""
    idx = me_ret.index
    if decision_date not in idx:
        # align to nearest prior ME in index
        prior = idx[idx <= decision_date]
        if len(prior) == 0:
            return pd.Series(dtype=float)
        decision_date = prior[-1]
    pos = idx.get_loc(decision_date)
    if isinstance(pos, slice):
        pos = pos.start
    if isinstance(pos, (np.ndarray, list)):
        pos = int(np.asarray(pos).ravel()[0])
    if pos + 1 >= len(idx):
        return pd.Series(dtype=float)
    nxt = idx[pos + 1]
    # Label uses next month only — not the decision month
    out = {}
    for t in tickers:
        if t not in me_ret.columns or benchmark not in me_ret.columns:
            out[t] = np.nan
            continue
        ri = me_ret.loc[nxt, t]
        rb = me_ret.loc[nxt, benchmark]
        out[t] = float(ri - rb) if pd.notna(ri) and pd.notna(rb) else np.nan
    return pd.Series(out, dtype=float)


def spearman_ic(scores: pd.Series, labels: pd.Series) -> float:
    """Cross-sectional Spearman correlation; NaN if < 3 overlapping finite pairs.

    Implemented via Pearson of ranks (no scipy dependency).
    """
    df = pd.concat([scores.rename("s"), labels.rename("y")], axis=1).dropna()
    if len(df) < 3:
        return float("nan")
    rs = df["s"].rank()
    ry = df["y"].rank()
    return float(rs.corr(ry, method="pearson"))


def walkforward_ic_table(
    prices: pd.DataFrame,
    categories: pd.Series | dict[str, str],
    *,
    tickers: list[str] | None = None,
    benchmark: str = "VOO",
    weights_cfg: dict | None = None,
    min_history_months: int = 13,
) -> pd.DataFrame:
    """
    For each decision month-end with enough history, score using data ≤ T,
    correlate with next-month excess. Returns date, IC, n_names, mean_IC running.
    """
    cols = list(tickers) if tickers else list(prices.columns)
    need = list(dict.fromkeys([*cols, benchmark]))
    px = prices[need].copy()
    me_dates = month_end_trading_dates(px)
    me_px = px.loc[me_dates]
    me_ret = me_px.pct_change()
    cfg = weights_cfg or load_feature_weights()

    if isinstance(categories, dict):
        cat = pd.Series(categories)
    else:
        cat = categories

    rows = []
    for i, d in enumerate(me_dates):
        if i < min_history_months:
            continue
        if i + 1 >= len(me_dates):
            break
        # PIT features through d only (include benchmark column even if not scored)
        feat_cols = list(dict.fromkeys([*cols, benchmark]))
        # Need enough benchmark history for Quality IR
        if px.loc[:d, benchmark].dropna().shape[0] < 60:
            continue
        raw = compute_raw_features(px.loc[:d, feat_cols], benchmark=benchmark)
        raw = raw.loc[[t for t in cols if t in raw.index]]
        scored = composite_scores(raw, cat.reindex(raw.index).fillna("Unknown"), cfg)
        labels = next_month_excess(me_ret, d, list(scored.index), benchmark=benchmark)
        ic = spearman_ic(scored["S_i"], labels)
        n = int(pd.concat([scored["S_i"], labels], axis=1).dropna().shape[0])
        rows.append({"date": d, "IC": ic, "n_names": n, "decision_month_end": d.date().isoformat()})
    out = pd.DataFrame(rows)
    if not out.empty:
        out["IC_mean_expanding"] = out["IC"].expanding().mean()
        valid = out["IC"].dropna()
        ir = float(valid.mean() / valid.std(ddof=1)) if len(valid) > 1 and valid.std(ddof=1) > 0 else np.nan
        out.attrs["IR_IC"] = ir
        out.attrs["mean_IC"] = float(valid.mean()) if len(valid) else np.nan
    return out


def rotation_on_off_next_month_table(
    prices: pd.DataFrame,
    ticker: str = "XSD",
    benchmark: str = "VOO",
    use_vol_gate: bool = True,
    hysteresis_months: int = 0,
) -> pd.DataFrame:
    """
    Regime-style table: avg next-month excess (ticker − bench) when gate ON vs OFF.
    Signal at decision ME uses data through that ME only; label is strictly next month.
    """
    sig = compute_rotation_signals(
        prices,
        [ticker],
        benchmark=benchmark,
        use_vol_gate=use_vol_gate,
        hysteresis_months=hysteresis_months,
    )
    me_dates = month_end_trading_dates(prices[[ticker, benchmark]])
    me_ret = prices.loc[me_dates, [ticker, benchmark]].pct_change()

    records = []
    sub = sig[sig["ticker"] == ticker].set_index("date").sort_index()
    for d in sub.index:
        labels = next_month_excess(me_ret, d, [ticker], benchmark=benchmark)
        if labels.empty or pd.isna(labels.get(ticker, np.nan)):
            continue
        if pd.isna(sub.loc[d, "mom12_1"]) or pd.isna(sub.loc[d, "mom12_1_bench"]):
            continue
        records.append(
            {
                "date": d,
                "on": bool(sub.loc[d, "on"]),
                "next_month_excess": float(labels[ticker]),
            }
        )
    df = pd.DataFrame(records)
    if df.empty:
        return pd.DataFrame(columns=["GateState", "AvgNextMonth_Excess", "HitRate_ExcessPos", "N_Months"])
    rows = []
    for label, mask in [("ON", df["on"]), ("OFF", ~df["on"])]:
        n = int(mask.sum())
        ex = df.loc[mask, "next_month_excess"]
        rows.append(
            {
                "GateState": label,
                "AvgNextMonth_Excess": float(ex.mean()) if n else np.nan,
                "HitRate_ExcessPos": float((ex > 0).mean()) if n else np.nan,
                "N_Months": n,
                "Note": "walk-forward; label = next month only (no same-month leakage)",
            }
        )
    return pd.DataFrame(rows)


def assert_no_same_period_leakage(
    decision_date: pd.Timestamp,
    feature_end: pd.Timestamp,
    label_start: pd.Timestamp,
    label_end: pd.Timestamp,
) -> None:
    """
    Test helper: features must end at/before decision; labels must start strictly after decision.
    """
    if feature_end > decision_date:
        raise AssertionError(
            f"feature window ends {feature_end} after decision {decision_date} (lookahead)"
        )
    if label_start <= decision_date:
        raise AssertionError(
            f"label window starts {label_start} on/before decision {decision_date} (same-period leak)"
        )
    if label_end < label_start:
        raise AssertionError("empty label window")


def write_ic_csv(ic_df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = ic_df.copy()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)
    return path


def walkforward_optimization_tables(
    prices: pd.DataFrame,
    categories: pd.Series | dict[str, str],
    *,
    tickers: list[str],
    universe_csv: str | Path | None = None,
    benchmark: str = "VOO",
    weights_cfg: dict | None = None,
    constraints: dict | None = None,
    optimizer: str = "P2",
    window_months: int = 36,
    min_history_months: int = 36,
    top_n: int = 6,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Walk-forward optimizer artifacts.

    Decision at t computes features/scores/weights using data <= t only.
    Evaluation return is the next month (t, t+1], with 5 bps one-way turnover cost.
    """
    cols = list(dict.fromkeys([*tickers, benchmark]))
    px = prices[[c for c in cols if c in prices.columns]].copy()
    if universe_csv is not None:
        uni_df = load_universe_csv(universe_csv)
        assert_eligible(list(px.columns), uni_df, load_universe_config())
    me_dates = month_end_trading_dates(px)
    me_px = px.loc[me_dates]
    me_ret = me_px.pct_change()
    cfg = weights_cfg or load_feature_weights()
    cat = pd.Series(categories) if isinstance(categories, dict) else categories

    weight_rows: list[dict] = []
    ic_rows: list[dict] = []
    prev_w: pd.Series | None = None
    family = optimizer.upper()
    strategy = (
        f"P1_MaxSharpe_roll{window_months}_t25"
        if family == "P1"
        else f"P2_CoreRotate_roll{window_months}_t25"
        if family == "P2"
        else f"P3_RiskParity_top{top_n}_roll{window_months}"
    )

    for i, d in enumerate(me_dates):
        if i < min_history_months or i + 1 >= len(me_dates):
            continue
        hist_px = px.loc[:d]
        live = [t for t in tickers if t in hist_px.columns and hist_px[t].dropna().shape[0] > 260]
        if len(live) < 3 or benchmark not in hist_px.columns:
            continue
        raw = compute_raw_features(hist_px[list(dict.fromkeys([*live, benchmark]))], benchmark=benchmark)
        raw = raw.loc[[t for t in live if t in raw.index]]
        scored = composite_scores(raw, cat.reindex(raw.index).fillna("Unknown"), cfg)
        labels = next_month_excess(me_ret, d, list(scored.index), benchmark=benchmark)
        ic = spearman_ic(scored["S_i"], labels)
        n_ic = int(pd.concat([scored["S_i"], labels], axis=1).dropna().shape[0])
        nxt = me_dates[i + 1]
        ic_rows.append({"date": d, "next_date": nxt, "IC": ic, "n": n_ic})

        try:
            weights = build_optimized_portfolio(
                scored,
                hist_px,
                optimizer=family,
                constraints=constraints,
                asof=d,
                universe_csv=universe_csv,
                window_months=window_months,
                benchmark=benchmark,
                top_n=top_n,
                w_prev=prev_w,
            )
        except Exception:
            continue
        w = weights.set_index("ticker")["weight"].astype(float)
        tick_cols = [t for t in w.index if t in me_ret.columns]
        gross = float((w.reindex(tick_cols).fillna(0.0) * me_ret.loc[nxt, tick_cols]).sum())
        turnover = 0.5 * float((w.subtract(prev_w, fill_value=0.0).abs()).sum()) if prev_w is not None else 0.5 * float(w.abs().sum())
        cost = turnover * (TURNOVER_COST_BPS / 10000.0)
        net = gross - cost
        row = {
            "date": d,
            "eval_date": nxt,
            "strategy": strategy,
            "gross_return": gross,
            "turnover": turnover,
            "turnover_cost_bps_one_way": TURNOVER_COST_BPS,
            "cost_return": cost,
            "net_return": net,
        }
        for t, val in w.items():
            row[f"w_{t}"] = float(val)
        for t, val in scored["S_i"].items():
            row[f"S_{t}"] = float(val)
        weight_rows.append(row)
        prev_w = w

    weights_df = pd.DataFrame(weight_rows)
    ic_df = pd.DataFrame(ic_rows)
    registry = optimizer_strategy_registry()
    registry = registry[registry["family"].eq(family) | registry["strategy"].str.contains(family, regex=False)]
    return weights_df, ic_df, registry.reset_index(drop=True)


def write_strategy_registry(path: str | Path, registry: pd.DataFrame | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = registry if registry is not None else optimizer_strategy_registry()
    out.to_csv(path, index=False)
    return path
