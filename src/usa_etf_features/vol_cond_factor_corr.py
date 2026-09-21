"""Vol-managed Book-2 upgrade: conditional factor-correlation gate.

Research tooling only; not investment advice.

Primary path (CoS-friendly): keep Book-2 f_t, multiply by g_t in [g_min, 1]
when high market vol coincides with elevated mean pairwise |corr| across
category sleeves (DeMiguel–Martín-Utrera–Uppal JF mapping on ETF sleeves).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml

from .prices import daily_returns
from .rotation import month_end_trading_dates
from .universe import (
    assert_eligible,
    eligible_tickers,
    load_universe_config,
    load_universe_csv,
    thin_history_set,
)
from .vol_target import (
    MONTHS_PER_YEAR,
    annualized_return,
    annualized_vol,
    block_bootstrap_sharpe_ci,
    core_weights,
    deflated_sharpe_approx,
    expanding_sigma_star_at_month_ends,
    half_turnover,
    max_drawdown,
    newey_west_tstat,
    option_core_daily_returns,
    parse_sigma_star,
    portfolio_month_return,
    realized_ann_vol_at_month_ends,
    scale_factor,
    sharpe_rf0,
    target_weights,
    turnover_cost_return,
)

DEFAULT_EXCLUDE_CATEGORIES = (
    "Defined Outcome / Buffer / Structured",
    "Specialty / Other",
)


@dataclass(frozen=True)
class VolCondFactorCorrTrial:
    trial_id: str
    core: str = "option_a"
    lookback: int = 63
    f_min: float = 0.25
    f_max: float = 1.0
    g_min: float = 0.5
    sigma_star: str | float = "expanding_annvol"
    z_rule: str = "mkt_vol"  # or inv_mkt_vol
    corr_estimator: str = "rolling_pairwise_abs_mean"
    apply_to: str = "option_a_vt"
    cash_ticker: str = "BIL"
    cost_bps_one_way: float = 5.0
    corr_lookback_months: int = 12
    min_sleeve_names: int = 2
    min_names: int = 100
    include_thin: bool = False
    mkt_ticker: str = "VOO"


def load_vol_cond_factor_corr_config(path: str | Path | None = None) -> dict:
    if path is None:
        candidates = [
            Path("config/vol_cond_factor_corr.yaml"),
            Path(__file__).resolve().parents[2] / "config" / "vol_cond_factor_corr.yaml",
        ]
        for c in candidates:
            if c.exists():
                path = c
                break
    if path is None:
        return {
            "vol_cond_factor_corr": {
                "lookbacks": [21, 63, 126],
                "f_min": 0.25,
                "f_max": 1.0,
                "g_min": [0.25, 0.5],
                "z_rule": "mkt_vol",
                "corr_estimator": "rolling_pairwise_abs_mean",
                "apply_to": ["option_a_vt"],
                "cost_bps_one_way": 5,
                "min_names": 100,
                "corr_lookback_months": [6, 12],
                "include_thin": False,
                "cash_ticker": "BIL",
                "sigma_star": "expanding_annvol",
            }
        }
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def corr_lookback_from_daily(lookback_days: int) -> int:
    """Map daily vol lookback to a monthly corr window (min 6 months)."""
    return max(6, int(round(lookback_days / 21.0)))


def build_category_sleeve_returns(
    monthly: pd.DataFrame,
    universe: pd.DataFrame,
    *,
    exclude_categories: Iterable[str] = DEFAULT_EXCLUDE_CATEGORIES,
    thin_flags: pd.Series | None = None,
    include_thin: bool = False,
    min_sleeve_names: int = 2,
    eligible: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Equal-weight category sleeves from name-level monthly returns.

    Returns (sleeve_returns, sleeve_meta) where sleeve_meta has columns
    category, n_names, thin_sleeve.
    """
    uni = universe.copy()
    uni["Ticker"] = uni["Ticker"].astype(str).str.upper()
    if "Category" not in uni.columns:
        raise ValueError("universe CSV requires Category column for sleeve corr")
    cat_map = uni.set_index("Ticker")["Category"].astype(str)
    names = [c for c in monthly.columns if c in cat_map.index]
    if eligible is not None:
        names = [c for c in names if c in eligible]
    if thin_flags is not None and not include_thin:
        thin_set = set(thin_flags.index[thin_flags.astype(bool)])
        names = [c for c in names if c not in thin_set]
    exclude = {str(x) for x in exclude_categories}
    groups: dict[str, list[str]] = {}
    for t in names:
        cat = str(cat_map.loc[t])
        if cat in exclude:
            continue
        groups.setdefault(cat, []).append(t)
    groups = {c: ts for c, ts in groups.items() if len(ts) >= min_sleeve_names}
    if not groups:
        raise ValueError("no category sleeves available after filters")
    sleeve = pd.DataFrame(
        {cat: monthly[ts].mean(axis=1, skipna=True) for cat, ts in groups.items()},
        index=monthly.index,
    )
    meta_rows = []
    for cat, ts in groups.items():
        n_thin = 0
        if thin_flags is not None:
            n_thin = int(sum(1 for t in ts if bool(thin_flags.get(t, False))))
        meta_rows.append(
            {
                "category": cat,
                "n_names": len(ts),
                "thin_sleeve": n_thin >= max(1, len(ts) // 2),
                "n_thin_names": n_thin,
                "tickers": ",".join(sorted(ts)),
            }
        )
    return sleeve, pd.DataFrame(meta_rows)


def mean_pairwise_abs_corr(window: pd.DataFrame) -> float:
    """Mean of upper-triangle absolute pairwise correlations."""
    cols = [c for c in window.columns if window[c].notna().sum() >= 3 and window[c].std(ddof=1) > 1e-12]
    if len(cols) < 2:
        return float("nan")
    sub = window[cols].dropna(how="any")
    if len(sub) < 3:
        # pairwise with pairwise-complete observations
        corr = window[cols].corr()
    else:
        corr = sub.corr()
    vals = corr.to_numpy(dtype=float)
    n = vals.shape[0]
    if n < 2:
        return float("nan")
    iu = np.triu_indices(n, k=1)
    tri = np.abs(vals[iu])
    tri = tri[np.isfinite(tri)]
    if tri.size == 0:
        return float("nan")
    return float(np.mean(tri))


def rolling_mean_pairwise_abs_corr(
    sleeve_returns: pd.DataFrame,
    me_dates: pd.DatetimeIndex,
    lookback_months: int,
) -> pd.Series:
    """At each month-end decision date t, corr uses sleeve returns with index <= t only."""
    # Align sleeve index to month-ends via asof / reindex to calendar months of me_dates
    sleeve = sleeve_returns.sort_index()
    out = {}
    for t in me_dates:
        hist = sleeve.loc[sleeve.index <= t]
        if len(hist) < lookback_months:
            out[t] = np.nan
            continue
        window = hist.iloc[-lookback_months:]
        out[t] = mean_pairwise_abs_corr(window)
    return pd.Series(out, name="mean_abs_corr")


def market_vol_at_month_ends(
    prices: pd.DataFrame,
    me_dates: pd.DatetimeIndex,
    lookback: int,
    mkt_ticker: str = "VOO",
) -> pd.Series:
    if mkt_ticker not in prices.columns:
        raise ValueError(f"missing market ticker {mkt_ticker} in prices")
    r = daily_returns(prices[[mkt_ticker]])[mkt_ticker]
    return realized_ann_vol_at_month_ends(r, me_dates, lookback).rename("z_raw")


def conditioning_z(z_raw: pd.Series, z_rule: str) -> pd.Series:
    rule = str(z_rule).strip().lower()
    if rule == "mkt_vol":
        return z_raw.rename("z")
    if rule in {"inv_mkt_vol", "inv_vol"}:
        return (1.0 / z_raw.replace(0.0, np.nan)).rename("z")
    raise ValueError(f"unknown z_rule {z_rule!r}")


def expanding_median_prior(series: pd.Series) -> pd.Series:
    """Expanding median of values strictly before each date (no same-day threshold leakage)."""
    s = series.astype(float)
    vals = []
    hist: list[float] = []
    for idx in s.index:
        if len(hist) == 0:
            vals.append(np.nan)
        else:
            vals.append(float(np.nanmedian(hist)))
        v = s.loc[idx]
        if np.isfinite(v):
            hist.append(float(v))
    return pd.Series(vals, index=s.index, name=f"{s.name}_med_prior")


def correlation_gate(
    mean_abs_corr: float,
    z: float,
    corr_med: float,
    z_med: float,
    *,
    g_min: float,
    z_rule: str,
) -> tuple[float, bool, bool, bool]:
    """Return (g, gate_binding, corr_elevated, z_elevated).

    For mkt_vol: elevated when z > prior median (high vol).
    For inv_mkt_vol: elevated when z < prior median (since z=1/vol, low inv-vol = high vol).
    Gate binds when both corr and z-state are elevated.
    """
    if not (np.isfinite(mean_abs_corr) and np.isfinite(z) and np.isfinite(corr_med) and np.isfinite(z_med)):
        return (1.0, False, False, False)
    corr_hi = mean_abs_corr > corr_med
    rule = str(z_rule).strip().lower()
    if rule == "mkt_vol":
        z_hi = z > z_med
    else:
        # inv_mkt_vol: stress when inverse-vol is low vs history
        z_hi = z < z_med
    binding = bool(corr_hi and z_hi)
    g = float(g_min) if binding else 1.0
    return (g, binding, bool(corr_hi), bool(z_hi))


def _monthly_price_returns(prices: pd.DataFrame, me_dates: pd.DatetimeIndex, cash_ticker: str) -> pd.DataFrame:
    me_px = prices.reindex(me_dates)
    me_ret = me_px.pct_change()
    if cash_ticker not in me_ret.columns or me_ret[cash_ticker].isna().all():
        me_ret[cash_ticker] = 0.0
    return me_ret


def _thin_flags_from_coverage(coverage: pd.DataFrame | None) -> pd.Series | None:
    if coverage is None:
        return None
    cov = coverage.copy()
    ticker_col = "ticker" if "ticker" in cov.columns else ("Ticker" if "Ticker" in cov.columns else None)
    if ticker_col is None or "thin_lt5y" not in cov.columns:
        return None
    cov[ticker_col] = cov[ticker_col].astype(str).str.upper()
    flags = cov.set_index(ticker_col)["thin_lt5y"]
    return flags.astype(str).str.lower().isin({"true", "1", "yes"})


def ew_sleeve_month_return(sleeve_returns: pd.DataFrame, eval_date: pd.Timestamp) -> float:
    if eval_date not in sleeve_returns.index:
        # try asof within month
        prior = sleeve_returns.loc[sleeve_returns.index <= eval_date]
        if prior.empty:
            return float("nan")
        row = prior.iloc[-1]
    else:
        row = sleeve_returns.loc[eval_date]
    vals = row.dropna()
    if vals.empty:
        return float("nan")
    return float(vals.mean())


def run_vol_cond_factor_corr_trial(
    prices: pd.DataFrame,
    trial: VolCondFactorCorrTrial,
    *,
    universe_csv: str | Path,
    monthly: pd.DataFrame | None = None,
    coverage: pd.DataFrame | None = None,
    universe_config: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Walk-forward conditional gate on Book-2 vol-target (or sleeve apply_to).

    Returns weights, OOS returns (vs Book-2 VT + static A + optional EW sleeves), registry.
    """
    cash = trial.cash_ticker.upper()
    apply_to = str(trial.apply_to).strip().lower()
    if apply_to not in {"option_a_vt", "category_sleeves"}:
        raise ValueError(f"apply_to must be option_a_vt or category_sleeves, got {trial.apply_to!r}")
    if trial.corr_estimator != "rolling_pairwise_abs_mean":
        raise ValueError(f"unsupported corr_estimator {trial.corr_estimator!r}")

    uni_df = load_universe_csv(universe_csv)
    cfg = universe_config or load_universe_config()
    base = core_weights(trial.core)
    assert_eligible([*base.keys(), cash, trial.mkt_ticker.upper()], uni_df, cfg)
    eligible = eligible_tickers(uni_df, cfg)

    px = prices.copy()
    missing_core = [t for t in base if t not in px.columns]
    if missing_core:
        raise ValueError(f"missing price columns for core: {missing_core}")
    cash_price_missing = cash not in px.columns
    if cash_price_missing:
        px[cash] = np.nan
    if trial.mkt_ticker.upper() not in px.columns:
        raise ValueError(f"missing market ticker {trial.mkt_ticker}")

    need_cols = list(dict.fromkeys([*base.keys(), cash, trial.mkt_ticker.upper()]))
    me_dates = month_end_trading_dates(px[list(base)])
    me_ret = _monthly_price_returns(px[need_cols], me_dates, cash)

    # Book-2 f_t inputs
    core_daily = option_core_daily_returns(px, base)
    sigma_hat = realized_ann_vol_at_month_ends(core_daily, me_dates, trial.lookback)
    sigma_star_spec = parse_sigma_star(trial.sigma_star)
    if sigma_star_spec == "expanding_annvol":
        sigma_star_series = expanding_sigma_star_at_month_ends(core_daily, me_dates, trial.lookback)
        sigma_star_label = "expanding_annvol"
    else:
        sigma_star_series = pd.Series(float(sigma_star_spec), index=me_dates, name="sigma_star")
        sigma_star_label = f"{float(sigma_star_spec):.4f}"

    z_raw = market_vol_at_month_ends(px, me_dates, trial.lookback, trial.mkt_ticker.upper())
    z = conditioning_z(z_raw, trial.z_rule)
    z_med = expanding_median_prior(z)

    # Sleeve correlations
    if monthly is None:
        # Build monthly from prices for tickers present
        me_all = month_end_trading_dates(px)
        monthly_panel = px.reindex(me_all).pct_change()
    else:
        monthly_panel = monthly.sort_index().copy()
        monthly_panel.columns = [str(c).upper() for c in monthly_panel.columns]

    thin_flags = _thin_flags_from_coverage(coverage)
    if thin_flags is None:
        thin_set = thin_history_set(cfg)
        thin_flags = pd.Series({t: True for t in thin_set}, dtype=bool)

    sleeve_rets, sleeve_meta = build_category_sleeve_returns(
        monthly_panel,
        uni_df,
        thin_flags=thin_flags,
        include_thin=trial.include_thin,
        min_sleeve_names=trial.min_sleeve_names,
        eligible=eligible,
    )
    n_live_names = int(
        sum(
            1
            for t in monthly_panel.columns
            if t in eligible and t in uni_df.set_index("Ticker")["Category"].index
        )
    )
    mean_abs = rolling_mean_pairwise_abs_corr(sleeve_rets, me_dates, trial.corr_lookback_months)
    corr_med = expanding_median_prior(mean_abs)

    thin = thin_history_set(cfg)
    qqqm_first_valid = px["QQQM"].first_valid_index() if "QQQM" in px.columns else pd.NaT

    weight_rows: list[dict] = []
    return_rows: list[dict] = []
    prev_w: pd.Series | None = None
    prev_w_book2: pd.Series | None = None

    for i, decision_date in enumerate(me_dates):
        if i + 1 >= len(me_dates):
            break
        eval_date = me_dates[i + 1]
        sh = sigma_hat.loc[decision_date]
        ss = sigma_star_series.loc[decision_date]
        f = scale_factor(sh, ss, f_min=trial.f_min, f_max=trial.f_max)
        if not np.isfinite(f):
            continue
        if me_ret.loc[eval_date, list(base)].isna().any():
            continue
        if cash in prices.columns and pd.isna(me_ret.loc[eval_date, cash]):
            continue

        mac = float(mean_abs.loc[decision_date]) if decision_date in mean_abs.index else float("nan")
        zz = float(z.loc[decision_date]) if decision_date in z.index else float("nan")
        cm = float(corr_med.loc[decision_date]) if decision_date in corr_med.index else float("nan")
        zm = float(z_med.loc[decision_date]) if decision_date in z_med.index else float("nan")
        g, binding, corr_hi, z_hi = correlation_gate(
            mac, zz, cm, zm, g_min=trial.g_min, z_rule=trial.z_rule
        )
        f_tilde = float(f) * float(g)

        if apply_to == "option_a_vt":
            w = target_weights(base, cash, f_tilde)
            w_book2 = target_weights(base, cash, f)
        else:
            # category_sleeves: scale an EW sleeve proxy held via cash residual;
            # map to Option A capital only as a Book-2-comparable sleeve overlay research path:
            # use f_tilde on equal cash split is not name-level; keep Option A weights as carrier
            # for capital, gated by sleeve corr state (documented research approximation).
            w = target_weights(base, cash, f_tilde)
            w_book2 = target_weights(base, cash, f)

        gross = portfolio_month_return(me_ret, eval_date, w)
        if not np.isfinite(gross):
            continue
        book2_gross = portfolio_month_return(me_ret, eval_date, w_book2)
        option_w = pd.Series({**base, cash: 0.0}, dtype=float)
        option_a = portfolio_month_return(me_ret, eval_date, option_w)
        # EW sleeves null (c): equal-weight category sleeves next-month return
        r_ew = ew_sleeve_month_return(sleeve_rets, eval_date)

        turnover = half_turnover(prev_w, w)
        cost = turnover_cost_return(turnover, trial.cost_bps_one_way)
        net = gross - cost
        to_b2 = half_turnover(prev_w_book2, w_book2)
        cost_b2 = turnover_cost_return(to_b2, trial.cost_bps_one_way)
        net_b2 = book2_gross - cost_b2

        row = {
            "date": decision_date,
            "eval_date": eval_date,
            "trial_id": trial.trial_id,
            "core": trial.core,
            "apply_to": apply_to,
            "f": float(f),
            "g": float(g),
            "f_tilde": float(f_tilde),
            "gate_binding": bool(binding),
            "corr_elevated": bool(corr_hi),
            "z_elevated": bool(z_hi),
            "mean_abs_corr": mac,
            "z": zz,
            "z_rule": trial.z_rule,
            "sigma_hat": float(sh),
            "sigma_star": float(ss),
            "lookback": trial.lookback,
            "corr_lookback_months": trial.corr_lookback_months,
            "f_min": trial.f_min,
            "f_max": trial.f_max,
            "g_min": trial.g_min,
            "cash_ticker": cash,
            "cash_price_source": "prices" if not cash_price_missing else "zero_return_proxy_rf0",
            "thin_history_tickers": ",".join(sorted(set(base) & thin)),
            "include_thin": trial.include_thin,
            "n_sleeves": int(sleeve_meta.shape[0]),
            "n_thin_sleeves": int(sleeve_meta["thin_sleeve"].sum()) if not sleeve_meta.empty else 0,
            "n_panel_names_eligible": n_live_names,
            "qqqm_first_valid": qqqm_first_valid.date().isoformat() if pd.notna(qqqm_first_valid) else "",
            "turnover": turnover,
            "cost_return": cost,
        }
        for t, val in w.items():
            row[f"w_{t}"] = float(val)
        weight_rows.append(row)
        return_rows.append(
            {
                "date": eval_date,
                "decision_date": decision_date,
                "trial_id": trial.trial_id,
                "r_method": net,
                "r_method_gross": gross,
                "cost_return": cost,
                "r_null_a": net_b2,  # unconditional Book-2 VT
                "r_null_b": option_a,  # static Option A
                "r_null_c": r_ew,  # EW category sleeves
                "r_active_vs_a": net - net_b2,
                "r_active_vs_b": net - option_a,
                "r_active_vs_c": net - r_ew if np.isfinite(r_ew) else np.nan,
                "turnover": turnover,
                "f": float(f),
                "g": float(g),
                "f_tilde": float(f_tilde),
                "gate_binding": bool(binding),
            }
        )
        prev_w = w
        prev_w_book2 = w_book2

    registry = pd.DataFrame(
        [
            {
                "trial_id": trial.trial_id,
                "method": "vol_cond_factor_corr",
                "citation": (
                    "DeMiguel, Martín-Utrera & Uppal, Journal of Finance (JOFI 13395), "
                    "doi:10.1111/jofi.13395; Moreira & Muir 2017 backbone"
                ),
                "core": trial.core,
                "apply_to": apply_to,
                "lookback": trial.lookback,
                "corr_lookback_months": trial.corr_lookback_months,
                "f_min": trial.f_min,
                "f_max": trial.f_max,
                "g_min": trial.g_min,
                "z_rule": trial.z_rule,
                "corr_estimator": trial.corr_estimator,
                "sigma_star": sigma_star_label,
                "cash_ticker": cash,
                "cost_bps_one_way": trial.cost_bps_one_way,
                "min_names": trial.min_names,
                "include_thin": trial.include_thin,
                "n_sleeves": int(sleeve_meta.shape[0]),
                "cash_price_source": "prices" if not cash_price_missing else "zero_return_proxy_rf0",
                "not_investment_advice": True,
            }
        ]
    )
    return pd.DataFrame(weight_rows), pd.DataFrame(return_rows), registry


def summarize_vol_cfc(
    returns: pd.DataFrame,
    weights: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    n_trials: int = 1,
    bootstrap_samples: int = 500,
    bootstrap_block_months: int = 3,
) -> pd.DataFrame:
    if returns.empty or "trial_id" not in returns.columns:
        return pd.DataFrame()
    rows = []
    for trial_id, r in returns.groupby("trial_id"):
        w = weights[weights["trial_id"].eq(trial_id)]
        reg = registry[registry["trial_id"].eq(trial_id)].iloc[0].to_dict()
        r_m = r["r_method"]
        sharpe = sharpe_rf0(r_m)
        ci_lo, ci_hi = block_bootstrap_sharpe_ci(
            r_m, block_months=bootstrap_block_months, n_boot=bootstrap_samples
        )
        row = {
            **reg,
            "n_months": int(r_m.dropna().shape[0]),
            "start_date": r["date"].min(),
            "end_date": r["date"].max(),
            "AnnReturn": annualized_return(r_m),
            "AnnVol": annualized_vol(r_m),
            "MaxDD": max_drawdown(r_m),
            "Sharpe_rf0": sharpe,
            "Book2_AnnReturn": annualized_return(r["r_null_a"]),
            "Book2_AnnVol": annualized_vol(r["r_null_a"]),
            "Book2_MaxDD": max_drawdown(r["r_null_a"]),
            "Book2_Sharpe_rf0": sharpe_rf0(r["r_null_a"]),
            "OptionA_AnnReturn": annualized_return(r["r_null_b"]),
            "OptionA_AnnVol": annualized_vol(r["r_null_b"]),
            "OptionA_MaxDD": max_drawdown(r["r_null_b"]),
            "OptionA_Sharpe_rf0": sharpe_rf0(r["r_null_b"]),
            "EWSleeve_AnnReturn": annualized_return(r["r_null_c"]),
            "EWSleeve_Sharpe_rf0": sharpe_rf0(r["r_null_c"]),
            "NW_t_vs_Book2": newey_west_tstat(r["r_active_vs_a"]),
            "NW_t_vs_OptionA": newey_west_tstat(r["r_active_vs_b"]),
            "NW_t_vs_EWSleeve": newey_west_tstat(r["r_active_vs_c"]),
            "Sharpe_CI_L": ci_lo,
            "Sharpe_CI_U": ci_hi,
            "turnover_per_year": float(r["turnover"].mean() * MONTHS_PER_YEAR) if len(r) else np.nan,
            "mean_f": float(w["f"].mean()) if not w.empty else np.nan,
            "mean_g": float(w["g"].mean()) if not w.empty else np.nan,
            "mean_f_tilde": float(w["f_tilde"].mean()) if not w.empty else np.nan,
            "pct_months_gate_binding": float(w["gate_binding"].mean()) if not w.empty else np.nan,
            "trial_count": n_trials,
            "DSR": deflated_sharpe_approx(sharpe, int(r_m.dropna().shape[0]), n_trials),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def state_table(returns: pd.DataFrame) -> pd.DataFrame:
    if returns.empty or "trial_id" not in returns.columns:
        return pd.DataFrame()
    rows = []
    for trial_id, r in returns.groupby("trial_id"):
        for label, mask in [
            ("gate_binding", r["gate_binding"].astype(bool)),
            ("gate_open", ~r["gate_binding"].astype(bool)),
        ]:
            sub = r.loc[mask, "r_active_vs_a"]
            rows.append(
                {
                    "trial_id": trial_id,
                    "state": label,
                    "avg_next_month_active_vs_book2": float(sub.mean()) if len(sub) else np.nan,
                    "hit_rate_active_positive": float((sub > 0).mean()) if len(sub) else np.nan,
                    "n_months": int(len(sub)),
                }
            )
    return pd.DataFrame(rows)


def make_vol_cfc_trials(
    *,
    lookbacks: Iterable[int],
    g_mins: Iterable[float],
    z_rules: Iterable[str],
    apply_tos: Iterable[str],
    f_min: float,
    f_max: float,
    sigma_star: str | float,
    cash_ticker: str,
    cost_bps_one_way: float,
    corr_lookback_months: Iterable[int] | None = None,
    include_thin: bool = False,
    min_names: int = 100,
    core: str = "option_a",
) -> list[VolCondFactorCorrTrial]:
    trials: list[VolCondFactorCorrTrial] = []
    for lookback in lookbacks:
        corr_lbs = list(corr_lookback_months) if corr_lookback_months is not None else [corr_lookback_from_daily(int(lookback))]
        for corr_lb in corr_lbs:
            for g_min in g_mins:
                for z_rule in z_rules:
                    for apply_to in apply_tos:
                        g_lab = str(g_min).replace(".", "p")
                        trial_id = (
                            f"VCFC_{apply_to}_L{int(lookback)}_C{int(corr_lb)}_"
                            f"g{g_lab}_{z_rule}"
                        )
                        trials.append(
                            VolCondFactorCorrTrial(
                                trial_id=trial_id,
                                core=core,
                                lookback=int(lookback),
                                f_min=float(f_min),
                                f_max=float(f_max),
                                g_min=float(g_min),
                                sigma_star=sigma_star,
                                z_rule=str(z_rule),
                                apply_to=str(apply_to),
                                cash_ticker=cash_ticker.upper(),
                                cost_bps_one_way=float(cost_bps_one_way),
                                corr_lookback_months=int(corr_lb),
                                include_thin=bool(include_thin),
                                min_names=int(min_names),
                            )
                        )
    return trials


def run_vol_cond_factor_corr_grid(
    prices: pd.DataFrame,
    trials: list[VolCondFactorCorrTrial],
    *,
    universe_csv: str | Path,
    monthly: pd.DataFrame | None = None,
    coverage: pd.DataFrame | None = None,
    universe_config: dict | None = None,
    bootstrap_samples: int = 500,
    bootstrap_block_months: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    weight_parts = []
    return_parts = []
    registry_parts = []
    for trial in trials:
        w, r, reg = run_vol_cond_factor_corr_trial(
            prices,
            trial,
            universe_csv=universe_csv,
            monthly=monthly,
            coverage=coverage,
            universe_config=universe_config,
        )
        weight_parts.append(w)
        return_parts.append(r)
        registry_parts.append(reg)
    weights = pd.concat(weight_parts, ignore_index=True) if weight_parts else pd.DataFrame()
    returns = pd.concat(return_parts, ignore_index=True) if return_parts else pd.DataFrame()
    registry = pd.concat(registry_parts, ignore_index=True) if registry_parts else pd.DataFrame()
    summary = summarize_vol_cfc(
        returns,
        weights,
        registry,
        n_trials=len(trials),
        bootstrap_samples=bootstrap_samples,
        bootstrap_block_months=bootstrap_block_months,
    )
    states = state_table(returns)
    return summary, weights, returns, registry, states
