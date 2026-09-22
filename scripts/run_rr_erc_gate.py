"""Gate-first walk-forward run for regime-resilient ERC.

Gate-first grid: one Path A (stress_corr_overlay) + one Path B (loim_regime_parity)
trial on category_sleeves. Nulls: unconditional ERC (primary), EW, LW MinVar.
5 bps one-way, DSR + trial_count, monthly WF.

Registry enabled:false — research only; not investment advice.
Lead: Ielpo, Muhammetgulyyeva & Royer (2026) doi:10.3905/jpm.2026.030.
"""
import sys
from pathlib import Path

# Ensure package on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pandas as pd
from usa_etf_features.regime_resilient_erc import (
    RegimeResilientERCTrial,
    run_regime_resilient_erc_grid,
)

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "processed" / "rr_erc"
OUT_DIR.mkdir(parents=True, exist_ok=True)

UNIVERSE_CSV = Path(__file__).resolve().parents[1] / "data" / "raw" / "usa_universe_categorized.csv"
MONTHLY_CSV  = Path(__file__).resolve().parents[1] / "data" / "raw" / "usa_universe_panel_monthly_returns.csv"
COVERAGE_CSV = Path(__file__).resolve().parents[1] / "data" / "raw" / "usa_universe_panel_history_coverage.csv"

def main():
    monthly = pd.read_csv(MONTHLY_CSV, index_col=0, parse_dates=True).sort_index()
    monthly.columns = [str(c).upper() for c in monthly.columns]
    coverage = pd.read_csv(COVERAGE_CSV)

    # Gate-first grid: smallest meaningful run
    # Path A — stress/corr overlay, category sleeves, λ=0.25, 12-month stress window
    # Path B — LOIM parity, rolling-vol-split, historical-freq π, category sleeves
    trials = [
        RegimeResilientERCTrial(
            trial_id="rr_erc_pathA_stress_sw12_lam25_cat",
            construction="stress_corr_overlay",
            stress_window_months=12,
            mix_lambda=0.25,
            corr_breakdown_gate=False,
            cov_estimator="ledoit_wolf",
            apply_to="category_sleeves",
            min_names=5,           # sleeve count gate (not name-level)
            min_history_months=36,
            cost_bps_one_way=5.0,
            cash_ticker="BIL",
            long_only=True,
        ),
        RegimeResilientERCTrial(
            trial_id="rr_erc_pathB_loim_vols_histfreq_cat",
            construction="loim_regime_parity",
            regime_pool_rule="rolling_vol_split",
            n_regimes=2,
            pi_rule="historical_freq",
            min_obs_per_pool=24,
            cov_estimator="ledoit_wolf",
            apply_to="category_sleeves",
            min_names=5,
            min_history_months=36,
            cost_bps_one_way=5.0,
            cash_ticker="BIL",
            long_only=True,
        ),
    ]

    print(f"Running {len(trials)} trials on category_sleeves …")
    summary, weights, oos, diag, registry = run_regime_resilient_erc_grid(
        monthly,
        trials,
        universe_csv=UNIVERSE_CSV,
        coverage=coverage,
        bootstrap_samples=500,
    )

    if summary.empty:
        print("ERROR: no OOS rows produced", file=sys.stderr)
        sys.exit(1)

    def _write(df, name):
        p = OUT_DIR / name
        tmp = df.copy()
        for col in tmp.columns:
            if pd.api.types.is_datetime64_any_dtype(tmp[col]):
                tmp[col] = pd.to_datetime(tmp[col]).dt.strftime("%Y-%m-%d")
        tmp.to_csv(p, index=False)
        print(f"  wrote {len(tmp)} rows → {p}")

    _write(summary,  "rr_erc_oos_summary.csv")
    _write(weights,  "rr_erc_monthly_weights.csv")
    _write(oos,      "rr_erc_oos_returns.csv")
    _write(diag,     "rr_erc_construction_diag.csv")
    _write(registry, "rr_erc_trial_registry.csv")

    print("\n=== OOS Gate Table ===")
    cols = ["trial_id", "n_months", "start_date", "end_date",
            "AnnReturn", "AnnVol", "MaxDD", "Sharpe_rf0", "DSR", "trial_count",
            "NW_t_vs_null_a_uncond_ERC", "NW_t_vs_null_b_EW", "NW_t_vs_null_c_LW_MinVar",
            "AnnReturn_null_a_uncond_ERC", "Sharpe_null_a_uncond_ERC",
            "AnnReturn_null_b_EW", "Sharpe_null_b_EW",
            "AnnReturn_null_c_LW_MinVar", "Sharpe_null_c_LW_MinVar",
            "turnover_per_year"]
    avail = [c for c in cols if c in summary.columns]
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", "{:.4f}".format)
    print(summary[avail].T.to_string())

if __name__ == "__main__":
    main()
