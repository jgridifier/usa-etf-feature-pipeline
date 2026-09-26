"""Reconcile the shared gate helper against Quant's cash-null audit (2026-09-26).

Recomputes Sharpe in excess of BIL (TB3MS fallback before BIL's first full month) and the
legacy Sharpe_rf0 (CAGR / vol) on the committed monthly OOS returns of every archived gate
and the live books, and compares them with the numbers in the audit memo.

The memo figures (``MEMO``) are the values as printed in the memo; ``AUDIT_EXACT`` are the
4-decimal values from the audit script's stats file for the headline rows. A figure
reproduces when it matches the printed value to the printed precision (half a unit in the
last printed digit) and, where an exact value exists, to 1e-4.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .gate_metrics import gate_sharpe_table, risk_free_monthly, window_rf_coverage
from .vol_target import newey_west_tstat

_REPO = Path(__file__).resolve().parents[2]
PROCESSED = _REPO / "data" / "processed"

# The memo's VCFC row is trial L126_C12_g0p25 (65 months): the first trial alphabetically, NOT the
# headline trial. The Archive card / Methods table headline is the best Sharpe trial L21_C12_g0p5 (70 months).
VCFC_RECON_TRIAL = "VCFC_option_a_vt_L126_C12_g0p25_mkt_vol"
VCFC_GATE = "#13 VCFC (trial L126_C12_g0p25, 65 months; first alphabetically, not the headline trial)"

# (gate, strategy) -> (printed Sharpe_rf0 or None, printed Sharpe_exBIL or None)
MEMO: dict[tuple[str, str], tuple[str | None, str | None]] = {
    ("Spectral RP (name)", "Spectral RP"): ("1.06", "0.30"),
    ("Spectral RP (name)", "ERC"): ("0.98", "0.31"),
    ("Spectral RP (name)", "LW MinVar"): ("1.60", "-0.25"),
    ("Spectral RP (name)", "EW"): ("0.83", "0.55"),
    ("Regime-Aware dual", "best conditional (k2_vol_corr_spread_ew)"): ("0.53", "0.44"),
    ("Regime-Aware dual", "uncond ERC"): ("0.74", "0.54"),
    ("Regime-Aware dual", "uncond EW"): (None, "0.60"),
    (VCFC_GATE, "method"): ("0.78", "0.51"),
    (VCFC_GATE, "Book-2 VT"): ("0.87", "0.67"),
    ("#4 FT-MED", "method"): ("0.36", "0.36"),
    ("#4 FT-MED", "EW"): ("0.61", "0.52"),
    ("#4 FT-MED", "LW MinVar"): ("0.60", "0.37"),
    ("#4 FT-MED", "ERC"): ("0.69", "0.52"),
    ("#4 FT-MED", "LW MVO"): ("0.69", "0.56"),
    ("#3 RR-ERC Path B", "Path B"): ("0.869", "0.665"),
    ("#3 RR-ERC Path B", "uncond ERC"): ("0.866", "0.662"),
    ("#3 RR-ERC Path B", "LW MinVar"): ("0.944", "0.642"),
    ("#6 skew gate-first (live Book 2)", "VT x gate-first"): ("1.280", "0.966"),
    ("#6 skew gate-first (live Book 2)", "Book-2 VT (BIL priced)"): ("1.059", "0.839"),
    ("#6 skew gate-first (live Book 2)", "Option A static"): (None, "0.75"),
    ("#6 skew gate-first (live Book 2)", "MinVar"): ("1.03", "0.13"),
    ("Book-2 VT committed run (cash = 0 proxy)", "Book-2 VT"): (None, "0.83"),
    ("Book-2 VT committed run (cash = 0 proxy)", "Option A static"): (None, "0.75"),
}
# 4-decimal Sharpe_exBIL from the audit script's stats file (headline rows).
AUDIT_EXACT: dict[tuple[str, str], float] = {
    ("Spectral RP (name)", "Spectral RP"): 0.2965,
    ("Spectral RP (name)", "ERC"): 0.3075,
    ("Spectral RP (name)", "LW MinVar"): -0.2462,
    ("Spectral RP (name)", "EW"): 0.5497,
    ("Regime-Aware dual", "best conditional (k2_vol_corr_spread_ew)"): 0.4421,
    ("Regime-Aware dual", "uncond ERC"): 0.5428,
    ("Regime-Aware dual", "uncond EW"): 0.5965,
    (VCFC_GATE, "method"): 0.5107,
    (VCFC_GATE, "Book-2 VT"): 0.6736,
    ("#4 FT-MED", "method"): 0.3584,
    ("#4 FT-MED", "EW"): 0.5240,
    ("#4 FT-MED", "LW MinVar"): 0.3663,
    ("#4 FT-MED", "ERC"): 0.5217,
    ("#4 FT-MED", "LW MVO"): 0.5574,
    ("#3 RR-ERC Path B", "Path B"): 0.6647,
    ("#3 RR-ERC Path B", "uncond ERC"): 0.6618,
    ("#3 RR-ERC Path B", "LW MinVar"): 0.6424,
    ("#6 skew gate-first (live Book 2)", "VT x gate-first"): 0.9664,
    ("#6 skew gate-first (live Book 2)", "Book-2 VT (BIL priced)"): 0.8394,
    ("#6 skew gate-first (live Book 2)", "Option A static"): 0.7509,
    ("#6 skew gate-first (live Book 2)", "MinVar"): 0.1304,
    ("Book-2 VT committed run (cash = 0 proxy)", "Book-2 VT"): 0.8274,
    ("Book-2 VT committed run (cash = 0 proxy)", "Option A static"): 0.7509,
}
# Printed memo figures that do not reproduce, with the explanation. Nothing is forced.
KNOWN_DIFFS: dict[tuple[str, str], str] = {}
# Notes on rows that do reproduce.
NOTES: dict[tuple[str, str], str] = {
    (VCFC_GATE, "Book-2 VT"): (
        "memo now rounds the legacy Sharpe_rf0 0.8747 to 0.87, matching the audit script's stats "
        "and this helper; an earlier memo draft printed 0.88"),
}
# Memo rf coverage by BIL (rest TB3MS), printed as whole percent.
MEMO_BIL_SHARE = {"Spectral RP (name)": 100, "Regime-Aware dual": 88, VCFC_GATE: 100,
                  "#4 FT-MED": 80, "#3 RR-ERC Path B": 83, "#6 skew gate-first (live Book 2)": 100,
                  "Book-2 VT committed run (cash = 0 proxy)": 100}
# Memo count statements.
MEMO_COUNTS = {"vcfc_trials_losing_exbil": "12/12", "vcfc_trials_losing_rf0": "12/12",
               "vcfc_nw_t_range": "-1.4 to -3.1", "skew_grid_beat_vt_exbil": "48/72",
               "skew_grid_beat_vt_rf0": "54/72", "skew_grid_milder_maxdd": "72/72"}


def _read(rel: str, processed: Path) -> pd.DataFrame:
    return pd.read_csv(processed / rel, parse_dates=["date"])


def _wide(df: pd.DataFrame, trial: str | None, cols: dict[str, str]) -> pd.DataFrame:
    if trial is not None:
        df = df[df["trial_id"] == trial]
    return df.set_index("date")[list(cols)].rename(columns=cols).astype(float)


def gate_frames(processed: Path = PROCESSED) -> dict[str, pd.DataFrame]:
    """Committed OOS return series per gate, one common window per gate."""
    g: dict[str, pd.DataFrame] = {}
    srp = _read("spectral_rp/name/oos_returns.csv", processed)
    srp = srp.pivot(index="date", columns="strategy_id", values="return")
    g["Spectral RP (name)"] = srp[["spectral_risk_parity__0", "erc__0", "minvar_lw__0", "equal_weight__0"]].rename(
        columns={"spectral_risk_parity__0": "Spectral RP", "erc__0": "ERC", "minvar_lw__0": "LW MinVar",
                 "equal_weight__0": "EW"})
    rd = _read("regime_dual/regime_dual_oos_returns.csv", processed)
    rd = rd.pivot(index="date", columns="trial_id", values="return")
    rd = rd.loc[rd["unconditional_erc"].notna()].dropna(axis=1)
    g["Regime-Aware dual"] = rd.rename(columns={"k2_vol_corr_spread_ew": "best conditional (k2_vol_corr_spread_ew)",
                                                "unconditional_erc": "uncond ERC", "unconditional_ew": "uncond EW"})
    vc = _read("vol_cond_factor_corr/vol_cfc_oos_returns.csv", processed)
    assert sorted(vc["trial_id"].unique())[0] == VCFC_RECON_TRIAL
    g[VCFC_GATE] = _wide(vc, VCFC_RECON_TRIAL, {"r_method": "method", "r_null_a": "Book-2 VT",
                                                     "r_null_b": "Option A static", "r_null_c": "EW sleeves"})
    ft = _read("ft_med/ft_med_oos_returns.csv", processed)
    g["#4 FT-MED"] = _wide(ft, sorted(ft["trial_id"].unique())[0],
                           {"r_method": "method", "r_null_a": "EW", "r_null_b": "LW MinVar", "r_null_c": "ERC",
                            "r_null_d": "LW MVO"})
    rr = _read("rr_erc/rr_erc_oos_returns.csv", processed)
    path_b = [t for t in rr["trial_id"].unique() if "pathB" in t]
    g["#3 RR-ERC Path B"] = _wide(rr, path_b[0], {"r_method": "Path B", "r_null_a": "uncond ERC", "r_null_b": "EW",
                                                  "r_null_c": "LW MinVar"})
    sk = _read("skewness_managed/skew_managed_gatefirst_returns.csv", processed)
    g["#6 skew gate-first (live Book 2)"] = _wide(sk, None, {
        "r_method": "VT x gate-first", "r_null_a": "Book-2 VT (BIL priced)", "r_null_b": "Option A static",
        "r_null_c": "EW", "r_null_d": "MinVar", "r_null_e": "ERC"})
    vt = _read("vol_target_oos_returns.csv", processed)
    g["Book-2 VT committed run (cash = 0 proxy)"] = _wide(vt, None, {"r_vt": "Book-2 VT",
                                                                     "r_option_a": "Option A static"})
    return g


def _within(value: float, printed: str) -> bool:
    decimals = len(printed.split(".")[1]) if "." in printed else 0
    return abs(value - float(printed)) <= 0.5 * 10 ** (-decimals) + 1e-9


def reconciliation_table(processed: Path = PROCESSED, rf: pd.DataFrame | None = None) -> pd.DataFrame:
    rf = risk_free_monthly() if rf is None else rf
    rows = []
    for gate, frame in gate_frames(processed).items():
        tab = gate_sharpe_table(frame, rf)
        for strat, r in tab.iterrows():
            memo_rf0, memo_ex = MEMO.get((gate, strat), (None, None))
            exact = AUDIT_EXACT.get((gate, strat))
            ok = True
            if memo_ex is not None:
                ok &= _within(r.Sharpe_exBIL, memo_ex)
            if memo_rf0 is not None:
                ok &= _within(r.Sharpe_rf0_legacy, memo_rf0)
            if exact is not None:
                ok &= abs(r.Sharpe_exBIL - exact) <= 1e-4 + 1e-9
            rows.append({"gate": gate, "strategy": strat, "window": f"{r.start}..{r.end}", "n_months": r.n_months,
                         "rf_fallback_share": r.rf_fallback_share, "Sharpe_exBIL": r.Sharpe_exBIL,
                         "memo_exBIL": memo_ex, "audit_exact_exBIL": exact,
                         "Sharpe_rf0_legacy": r.Sharpe_rf0_legacy, "memo_rf0": memo_rf0,
                         "in_memo": memo_ex is not None or memo_rf0 is not None,
                         "reproduces": bool(ok) if (memo_ex or memo_rf0 or exact is not None) else None,
                         "note": KNOWN_DIFFS.get((gate, strat)) or NOTES.get((gate, strat), "")})
    return pd.DataFrame(rows)


def fallback_shares(processed: Path = PROCESSED, rf: pd.DataFrame | None = None) -> pd.DataFrame:
    rf = risk_free_monthly() if rf is None else rf
    rows = []
    for gate, frame in gate_frames(processed).items():
        c = window_rf_coverage(frame.index, rf)
        rows.append({"gate": gate, **c, "memo_bil_share_pct": MEMO_BIL_SHARE.get(gate)})
    return pd.DataFrame(rows)


def trial_counts(processed: Path = PROCESSED, rf: pd.DataFrame | None = None) -> dict:
    """VCFC 12-trial and #6 72-trial grid counts vs their primary null (r_null_a)."""
    rf = risk_free_monthly() if rf is None else rf
    out = {}
    vc = _read("vol_cond_factor_corr/vol_cfc_oos_returns.csv", processed)
    lose_ex = lose_rf0 = 0
    nwt = []
    trials = sorted(vc["trial_id"].unique())
    for t in trials:
        f = _wide(vc, t, {"r_method": "m", "r_null_a": "a"})
        tab = gate_sharpe_table(f, rf)
        lose_ex += tab.loc["m", "Sharpe_exBIL"] < tab.loc["a", "Sharpe_exBIL"]
        lose_rf0 += tab.loc["m", "Sharpe_rf0_legacy"] < tab.loc["a", "Sharpe_rf0_legacy"]
        nwt.append(newey_west_tstat(f["m"] - f["a"], lags=3))
    out["vcfc_trials_losing_exbil"] = f"{lose_ex}/{len(trials)}"
    out["vcfc_trials_losing_rf0"] = f"{lose_rf0}/{len(trials)}"
    out["vcfc_nw_t_range"] = f"{max(nwt):.1f} to {min(nwt):.1f}"
    sk = _read("skewness_managed/skew_managed_oos_returns.csv", processed)
    beat_ex = beat_rf0 = milder = 0
    trials = sorted(sk["trial_id"].unique())
    for t in trials:
        f = _wide(sk, t, {"r_method": "m", "r_null_a": "a"})
        tab = gate_sharpe_table(f, rf)
        beat_ex += tab.loc["m", "Sharpe_exBIL"] > tab.loc["a", "Sharpe_exBIL"]
        beat_rf0 += tab.loc["m", "Sharpe_rf0_legacy"] > tab.loc["a", "Sharpe_rf0_legacy"]
        milder += tab.loc["m", "MaxDD"] > tab.loc["a", "MaxDD"]
    out["skew_grid_beat_vt_exbil"] = f"{beat_ex}/{len(trials)}"
    out["skew_grid_beat_vt_rf0"] = f"{beat_rf0}/{len(trials)}"
    out["skew_grid_milder_maxdd"] = f"{milder}/{len(trials)}"
    return out


# ------------------------------------------------------------------ Pages figures
def _pair(r: pd.Series, rf: pd.DataFrame) -> dict:
    tab = gate_sharpe_table(pd.DataFrame({"x": r}), rf)
    return {"exbil": round(float(tab.loc["x", "Sharpe_exBIL"]), 4),
            "rf0_legacy": round(float(tab.loc["x", "Sharpe_rf0_legacy"]), 4),
            "n_months": int(tab.loc["x", "n_months"]), "window": f"{tab.loc['x', 'start']}..{tab.loc['x', 'end']}",
            "rf_fallback_share": round(float(tab.loc["x", "rf_fallback_share"]), 4)}


# Archive card rows -> (gate frame, column) or (file, trial, column).
ARCHIVE_ROWS = {
    "spectral_rp": {"Spectral RP": ("Spectral RP (name)", "Spectral RP"),
                    "LW MinVar (null)": ("Spectral RP (name)", "LW MinVar")},
    "regime_dual": {"Best dual (vol_corr_spread ERC)": ("Regime-Aware dual", "k2_vol_corr_spread_erc"),
                    "Uncond ERC (null)": ("Regime-Aware dual", "uncond ERC")},
    "vcfc": {"VCFC (best Sharpe trial)": ("vcfc:VCFC_option_a_vt_L21_C12_g0p5_mkt_vol", "r_method"),
             "Book-2 VT, VCFC run window (null)": ("vcfc:VCFC_option_a_vt_L21_C12_g0p5_mkt_vol", "r_null_a")},
    "ft_med": {"FT-MED (primary)": ("#4 FT-MED", "method"), "EW (null)": ("#4 FT-MED", "EW"),
               "LW MinVar (null)": ("#4 FT-MED", "LW MinVar"), "ERC (null)": ("#4 FT-MED", "ERC")},
    "rr_erc": {"Path A (stress overlay)": ("rrA", "r_method"), "Path B (LOIM parity)": ("#3 RR-ERC Path B", "Path B"),
               "Uncond ERC (primary null)": ("#3 RR-ERC Path B", "uncond ERC"),
               "LW MinVar (null)": ("#3 RR-ERC Path B", "LW MinVar")},
    "uncond_book2_vt": {"Uncond Book-2 VT": ("#6 skew gate-first (live Book 2)", "Book-2 VT (BIL priced)"),
                        "#6 overlay (measured)": ("#6 skew gate-first (live Book 2)", "VT x gate-first")},
    # v3 stocks-only NLS GMV (PR #40), 156w primary, full 2016-01..2026-09 window.
    "nls_gmv_v3": {"NLS GMV v3 (156w, method)": ("nlsv3:nonlinear_shrinkage_gmv", "return"),
                   "Weekly LW MinVar (primary null)": ("nlsv3:minvar_lw_weekly", "return"),
                   "USMV buy-and-hold (in-sample reference only)": ("nlsv3:buy_hold_usmv", "return")},
}
NLS_V3_RETURNS = "nonlinear_shrinkage_gmv_v3/oos_returns.csv"


def site_sharpe_figures(processed: Path = PROCESSED, rf: pd.DataFrame | None = None) -> dict:
    """Every Sharpe the Pages site shows: excess of BIL (headline) + legacy rf = 0."""
    rf = risk_free_monthly() if rf is None else rf
    frames = gate_frames(processed)
    six = frames["#6 skew gate-first (live Book 2)"]
    vc = _read("vol_cond_factor_corr/vol_cfc_oos_returns.csv", processed)
    rr = _read("rr_erc/rr_erc_oos_returns.csv", processed)
    path_a = [t for t in rr["trial_id"].unique() if "pathA" in t][0]

    def series(src: str, col: str) -> pd.Series:
        if src.startswith("vcfc:"):
            return _wide(vc, src[5:], {col: col})[col]
        if src == "rrA":
            return _wide(rr, path_a, {col: col})[col]
        if src.startswith("nlsv3:"):
            v3 = _read(NLS_V3_RETURNS, processed)
            v3 = v3.loc[v3["window_weeks"].eq(156) & v3["strategy_id"].eq(src[6:])]
            return v3.set_index("date")[col].astype(float)
        return frames[src][col]

    short = pd.read_csv(processed / "cash_null_audit" / "shortlist_strategy_returns.csv", parse_dates=["date"])
    short = short.pivot(index="date", columns="strategy_id", values="return")
    return {
        "note": ("Sharpe_exBIL = mean(r - rf)*12 / (std(r - rf)*sqrt(12)); rf = BIL priced monthly return from "
                 "2007-06, FRED TB3MS/1200 before. rf0_legacy = CAGR / vol (legacy, rf = 0). Generated by "
                 "scripts/reconcile_cash_null_audit.py from committed OOS returns."),
        "books": {
            "book1_static_core": _pair(six["Option A static"], rf),
            "book2_vt_x_gatefirst": _pair(six["VT x gate-first"], rf),
            "uncond_vt_audit_null": _pair(six["Book-2 VT (BIL priced)"], rf),
            "uncond_vt_committed_cash0": _pair(frames["Book-2 VT committed run (cash = 0 proxy)"]["Book-2 VT"], rf),
        },
        # docs/data/vol_target_oos_returns.csv (BIL priced) is identical to the #6 run's nulls a/b.
        "vol_target_run": {"vt": _pair(six["Book-2 VT (BIL priced)"], rf), "option_a": _pair(six["Option A static"], rf)},
        # run_latest strategy_comparison rows (vol_target_option_a there is the unconditional VT, BIL priced).
        "comparison": {
            "static_option_a": _pair(short["static_option_a"], rf),
            "vol_target_option_a": _pair(six["Book-2 VT (BIL priced)"], rf),
            "score_rotate_xsd": _pair(short["score_rotate_xsd"], rf),
            "m3_p2_core_rotate": _pair(short["m3_p2_core_rotate"], rf),
        },
        "archive": {cid: {label: _pair(series(*src), rf) for label, src in rows.items()}
                    for cid, rows in ARCHIVE_ROWS.items()},
        "skew_nulls": {k: _pair(six[k], rf) for k in ("EW", "MinVar", "ERC")},
    }
