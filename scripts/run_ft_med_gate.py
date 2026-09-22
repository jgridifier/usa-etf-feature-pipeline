"""Gate-first walk-forward run: forecast_tangency_med.

Single config: EF lookback=21m, VARX lookback=60m, mu=sample.
Primary: category_sleeves (multi-sleeve allocation, ~15-20 variables — fast).

Name-level N>=100 feasibility is already documented (310 eligible names
with >=24m history as of 2026-09); a separate name-level grid run can be
registered once the category-sleeve gate is reviewed by Quant.

Outputs → data/processed/ft_med/.

Research tooling only; not investment advice.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from usa_etf_features.universe import load_universe_config
from usa_etf_features.forecast_tangency_med import (
    ForecastTangencyMedTrial,
    run_forecast_tangency_med_trial,
)
from usa_etf_features.vol_target import (
    annualized_return,
    annualized_vol,
    max_drawdown,
    sharpe_rf0,
    newey_west_tstat,
    block_bootstrap_sharpe_ci,
    deflated_sharpe_approx,
    MONTHS_PER_YEAR,
)

UNIVERSE_CSV = ROOT / "data" / "raw" / "usa_universe_categorized.csv"
MONTHLY_CSV  = ROOT / "data" / "raw" / "usa_universe_panel_monthly_returns.csv"
COVERAGE_CSV = ROOT / "data" / "raw" / "usa_universe_panel_history_coverage.csv"
OUT_DIR      = ROOT / "data" / "processed" / "ft_med"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    tmp = df.copy()
    for col in tmp.columns:
        if pd.api.types.is_datetime64_any_dtype(tmp[col]):
            tmp[col] = pd.to_datetime(tmp[col]).dt.strftime("%Y-%m-%d")
    tmp.to_csv(path, index=False)
    print(f"  wrote {len(tmp):>6} rows → {path.relative_to(ROOT)}")


def build_summary_row(
    trial: ForecastTangencyMedTrial,
    oos: pd.DataFrame,
    trial_count: int,
) -> dict:
    sub = oos.copy()
    sub["date"] = pd.to_datetime(sub["date"])
    r_m = sub.set_index("date")["r_method"].dropna()
    if len(r_m) < 12:
        return {}
    sr = sharpe_rf0(r_m)
    dsr = deflated_sharpe_approx(sr / np.sqrt(MONTHS_PER_YEAR), len(r_m), trial_count)
    lo, hi = block_bootstrap_sharpe_ci(r_m, block_months=3, n_boot=500)
    to_yr = float(sub["turnover"].dropna().mean() * MONTHS_PER_YEAR) if "turnover" in sub.columns else float("nan")
    dist = float(sub["distance"].dropna().mean()) if "distance" in sub.columns else float("nan")

    row: dict = {
        "trial_id": trial.trial_id,
        "apply_to": trial.apply_to,
        "ef_lookback_months": trial.ef_lookback_months,
        "forecast_lookback_months": trial.forecast_lookback_months,
        "mu_estimator": trial.mu_estimator,
        "n_months": int(len(r_m)),
        "start_date": str(r_m.index.min().date()),
        "end_date": str(r_m.index.max().date()),
        "AnnReturn": annualized_return(r_m),
        "AnnVol": annualized_vol(r_m),
        "MaxDD": max_drawdown(r_m),
        "Sharpe_rf0": sr,
        "DSR": dsr,
        "trial_count": trial_count,
        "bootstrap_Sharpe_lo95": lo,
        "bootstrap_Sharpe_hi95": hi,
        "turnover_per_year": to_yr,
        "mean_distance": dist,
        "cost_bps_one_way": trial.cost_bps_one_way,
        "long_only": trial.long_only,
        "leverage_cap": trial.leverage_cap,
        "cash_ticker": trial.cash_ticker,
        "research_disclaimer": "Research-only; not investment advice; no trading or broker routing.",
    }

    for null_col, null_lbl in [
        ("r_null_a", "EW"),
        ("r_null_b", "LW_MinVar"),
        ("r_null_c", "ERC"),
        ("r_null_d", "LW_MVO"),
    ]:
        active = (sub["r_method"] - sub[null_col]).dropna()
        row[f"NW_t_vs_{null_lbl}"] = newey_west_tstat(active)
        rn = sub[null_col].dropna()
        row[f"AnnReturn_{null_lbl}"] = annualized_return(rn)
        row[f"AnnVol_{null_lbl}"] = annualized_vol(rn)
        row[f"MaxDD_{null_lbl}"] = max_drawdown(rn)
        row[f"Sharpe_{null_lbl}"] = sharpe_rf0(rn)
    return row


def print_one_screen(
    trial: ForecastTangencyMedTrial,
    oos: pd.DataFrame,
    trial_count: int,
) -> None:
    sub = oos.copy()
    sub["date"] = pd.to_datetime(sub["date"])
    r_m = sub.set_index("date")["r_method"].dropna()
    if len(r_m) < 12:
        print("  Insufficient OOS months.")
        return
    sr = sharpe_rf0(r_m)
    dsr = deflated_sharpe_approx(sr / np.sqrt(MONTHS_PER_YEAR), len(r_m), trial_count)
    lo, hi = block_bootstrap_sharpe_ci(r_m, block_months=3, n_boot=500)
    to_yr = float(sub["turnover"].dropna().mean() * MONTHS_PER_YEAR)
    dist = float(sub["distance"].dropna().mean()) if "distance" in sub.columns else float("nan")

    print(f"\n{'═'*62}")
    print(f"  {trial.trial_id}")
    print(f"  OOS: {r_m.index.min().date()} → {r_m.index.max().date()}  n={len(r_m)} months")
    print(f"{'─'*62}")
    print(f"  {'Portfolio':32s}  Sharpe_rf0  AnnRet   AnnVol   MaxDD")
    print(f"  {'FT-MED (primary)':32s}  {sr:+8.3f}  {annualized_return(r_m):+7.2%}  {annualized_vol(r_m):6.2%}  {max_drawdown(r_m):7.2%}")
    for null_col, null_lbl in [
        ("r_null_a", "(a) EW"),
        ("r_null_b", "(b) LW MinVar"),
        ("r_null_c", "(c) ERC"),
        ("r_null_d", "(d) LW MVO"),
    ]:
        rn = sub[null_col].dropna()
        if rn.empty:
            continue
        print(f"  {null_lbl:32s}  {sharpe_rf0(rn):+8.3f}  {annualized_return(rn):+7.2%}  {annualized_vol(rn):6.2%}  {max_drawdown(rn):7.2%}")
    print(f"{'─'*62}")
    print(f"  DSR: {dsr:.4f}   trial_count: {trial_count}")
    print(f"  Sharpe 95% CI: [{lo:.3f}, {hi:.3f}]")
    print(f"  Turnover/yr: {to_yr:.1%}   Mean EF dist: {dist:.5f}")
    print(f"{'─'*62}")
    for null_col, null_lbl in [
        ("r_null_a", "EW"),
        ("r_null_b", "LW MinVar"),
        ("r_null_c", "ERC"),
        ("r_null_d", "LW MVO"),
    ]:
        active = (sub["r_method"] - sub[null_col]).dropna()
        nw = newey_west_tstat(active)
        print(f"  NW t vs {null_lbl:<14}: {nw:+.3f}")
    print(f"{'═'*62}")


def main() -> None:
    monthly = pd.read_csv(MONTHLY_CSV, index_col=0, parse_dates=True).sort_index()
    monthly.columns = [c.upper() for c in monthly.columns]
    coverage = pd.read_csv(COVERAGE_CSV) if COVERAGE_CSV.exists() else None
    uni_cfg = load_universe_config()

    # Only one trial for the gate-first run (category_sleeves, N~15 variables, fast)
    TRIAL_COUNT = 1

    trial = ForecastTangencyMedTrial(
        trial_id="ft_med_ef21_fc60_sample_sleeves",
        ef_lookback_months=21,
        forecast_lookback_months=60,
        mu_estimator="sample",
        cov_estimator="ledoit_wolf",
        long_only=True,
        leverage_cap=1.0,
        cost_bps_one_way=5.0,
        cash_ticker="BIL",
        min_names=2,
        apply_to="category_sleeves",
        include_thin=False,
        min_history_months=24,
    )

    print(f"\n[Running] {trial.trial_id}")
    print(f"  apply_to=category_sleeves  ef_lb=21m  fc_lb=60m  mu=sample")
    print(f"  (N≥100 name-level feasibility confirmed: 310 eligible names")
    print(f"   with ≥24m history as of 2026-09; separate trial for later gate pass)")

    w, oos, reg = run_forecast_tangency_med_trial(
        monthly, trial,
        universe_csv=UNIVERSE_CSV,
        coverage=coverage,
        universe_config=uni_cfg,
    )
    print(f"  → {len(w)} weight rows, {len(oos)} OOS rows")

    if oos.empty:
        print("ERROR: empty OOS table.", file=sys.stderr)
        sys.exit(1)

    reg = reg.copy()
    reg["trial_count"] = TRIAL_COUNT
    reg["trial_num"] = 1

    print_one_screen(trial, oos, TRIAL_COUNT)

    summary_row = build_summary_row(trial, oos, TRIAL_COUNT)
    summary = pd.DataFrame([summary_row]) if summary_row else pd.DataFrame()

    print("\n[Writing outputs]")
    _write_csv(summary, OUT_DIR / "ft_med_oos_summary.csv")
    _write_csv(w, OUT_DIR / "ft_med_monthly_weights.csv")
    _write_csv(oos, OUT_DIR / "ft_med_oos_returns.csv")
    _write_csv(reg, OUT_DIR / "ft_med_trial_registry.csv")

    coef_cols = [c for c in oos.columns if c in {
        "date", "decision_date", "trial_id",
        "coef_r_mvp", "coef_sigma_mvp", "coef_u",
        "fc_r_mvp", "fc_sigma_mvp", "fc_u",
        "rhat_tp", "sigmahat_tp", "r_star", "distance",
    }]
    _write_csv(oos[coef_cols], OUT_DIR / "ft_med_coef_forecast.csv")

    print("\n[Done] Outputs → data/processed/ft_med/")


if __name__ == "__main__":
    main()
