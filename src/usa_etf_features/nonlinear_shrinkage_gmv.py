"""Research only: analytical nonlinear shrinkage global minimum variance.

CLEAN-ROOM implementation from published equations, Sections 2.1, 4.2–4.7,
eqs. (4.3)–(4.9); no reference code was copied.
Ledoit & Wolf (2020), AoS 48(5), 3043–3065, doi:10.1214/19-AOS1921;
Ledoit & Wolf (2017), RFS 30(12), 4349–4388, doi:10.1093/rfs/hhx052;
Ledoit & Wolf (2004), JMVA 88(2), 365–411.
Reference-code license check (2026-09-25): github.com/oledoit/covShrinkage,
MikeWolf007/covShrinkage and pald22/covShrinkage are MIT-licensed but do not contain
the 2020 analytical estimator (they ship QIS/LIS/GIS and linear estimators). The 2020
Matlab ZIP on Michael Wolf's UZH page could not be retrieved, so its license is
unverified and treated as unlicensed; nothing was copied or used as a fixture.
Snapshot universe/coverage filters introduce survivorship bias.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf

from .gate_metrics import filter_cash_like
from .spectral_risk_parity import long_only_minvar, normalize_cov, null_weights, read_returns
from .vol_target import sharpe_rf0, annualized_vol, newey_west_tstat, deflated_sharpe_approx

METHOD = "nonlinear_shrinkage_gmv"
PRIMARY = "minvar_lw_weekly"
REFERENCE = "minvar_lw_monthly_reference"
SPECTRAL_DIR = "data/processed/spectral_rp/name"
DSR_METHOD = "normal approximation; monthly Sharpe (repo deflated_sharpe_approx, Bailey & Lopez de Prado 2014)"
DISCLAIMER = "Research only. Registry enabled:false. No live-book wiring."
# Quant ruling on the v1 gate (PR #34), 2026-09-26 ET. Not PASS, not FAIL.
VERDICT = {
    "verdict": "VOID",
    "verdict_label": "VOID — cash-dominated, no evidence of estimator edge",
    "verdict_by": "Quant",
    "verdict_date": "2026-09-26",
    "verdict_reason": (
        "All criteria passed mechanically, but the test design was broken: the primary null (weekly LW MinVar) "
        "was ~68% in the cash-like category and the method ~81%, and Sharpe_rf0 rewards whichever holds more "
        "T-bills. NW t vs the null was +0.48 (156w) / +0.76 (260w): no evidence of a return edge. DSR at a low "
        "trial_count is effectively PSR vs zero and carries no weight."),
    "dsr_decisive": False,
    "cash_share_caveat": (
        "The 'US Treasuries / Govt / Cash-like' category used for the cash shares also contains duration "
        "(e.g. GOVT, IEF, TLT, SHY), while USFR sits in 'High Yield Credit'; quoted cash shares therefore mix "
        "in some duration and are not a pure T-bill share."),
    "follow_up": (
        "v2 re-spec (Quant ticket ENGINEERING_TICKET_nonlinear_shrinkage_gmv_v2_excash.md): ex-cash universe "
        "(cash_like tag excluded for the method and every null), Sharpe in excess of BIL (priced) with Sharpe_rf0 "
        "as legacy, realized-vol primary test; trial_count carries forward from 4."),
}
ROLES = {METHOD: "method", PRIMARY: "primary_null", "erc_weekly": "null",
         "equal_weight": "null", REFERENCE: "reference_only"}


_SQRT5 = np.sqrt(5.0)
# |x| at/above which the far-field series is used instead of the closed form.
_HILBERT_SERIES_FROM = 10.0
_HILBERT_SERIES_TERMS = 30


def epanechnikov_hilbert(x):
    """Hilbert transform of the unit-variance Epanechnikov kernel (paper Prop. 4.1).

    Paper convention (Definition 3.2): Hκ(x) = (1/π) PV ∫ κ(t)/(t − x) dt, i.e.
    Hκ(x) = −3x/(10π) + 3/(4√5π)(1 − x²/5) log|(√5 − x)/(√5 + x)|, with the log
    term set to zero at |x| = √5.

    Numerical note: for |x| ≫ √5 the two terms of the closed form cancel
    catastrophically in float64 (at |x| ~ 1e7 the result is wrong by orders of
    magnitude; this happens for the largest sample eigenvalues when the spectrum
    spans many decades, e.g. T-bill vs. crypto ETFs). For |x| ≥ 10 we therefore
    evaluate the same function through its exact convergent expansion in
    a = √5/x (obtained by expanding the log in the closed form):
        Hκ(x) = −(3/(√5π)) Σ_{m≥0} a^(2m+1) / ((2m+1)(2m+3)),
    whose leading term is the Cauchy tail −1/(πx). This is the same estimator,
    evaluated accurately; see tests for the quadrature cross-check.
    """
    x = np.asarray(x, dtype=float)
    out = np.empty_like(x)
    far = np.abs(x) >= _HILBERT_SERIES_FROM
    near = ~far
    xn = x[near]
    edge = np.abs(np.abs(xn) - _SQRT5) < 1e-12
    safe = np.where(edge, 0., xn)
    term = (1 - safe**2 / 5) * np.log(np.abs((_SQRT5 - safe) / (_SQRT5 + safe)))
    out[near] = -3 * xn / (10 * np.pi) + 3 / (4 * _SQRT5 * np.pi) * np.where(edge, 0., term)
    a = _SQRT5 / x[far]
    a2, power, total = a * a, a.copy(), np.zeros_like(a)
    for m in range(_HILBERT_SERIES_TERMS):
        total += power / ((2 * m + 1) * (2 * m + 3))
        power *= a2
    out[far] = -3 / (_SQRT5 * np.pi) * total
    return out if out.ndim else float(out)


def nonlinear_shrinkage_spectrum(R, *, demean=True) -> dict:
    R = np.asarray(R, dtype=float)
    if R.ndim != 2 or not np.isfinite(R).all():
        raise ValueError("returns must be a finite T by N array (no NaN)")
    T, p = R.shape
    n = T - int(demean)
    if p < 1 or p >= n:
        raise ValueError("require 1 <= N < effective sample size")
    Y = R - R.mean(axis=0) if demean else R
    S = Y.T @ Y / n
    lam, U = np.linalg.eigh((S + S.T) / 2)
    if lam[0] <= 0:
        raise ValueError("singular window: sample eigenvalues must be positive")
    c, h = p / n, n**(-1 / 3)
    bandwidth = lam * h
    x = (lam[:, None] - lam[None, :]) / bandwidth[None, :]
    f = (3 / (4 * np.sqrt(5) * bandwidth) * np.maximum(0, 1 - x**2 / 5)).mean(axis=1)
    Hf = (epanechnikov_hilbert(x) / bandwidth).mean(axis=1)
    d = lam / ((np.pi * c * lam * f)**2 + (1 - c - np.pi * c * lam * Hf)**2)
    return dict(sample_eigenvalues=lam, shrunk_eigenvalues=d, eigenvectors=U, c=c, n_eff=n, h=h)


def nonlinear_shrinkage_cov(R, *, demean=True) -> np.ndarray:
    spectrum = nonlinear_shrinkage_spectrum(R, demean=demean)
    U = spectrum["eigenvectors"]
    cov = (U * spectrum["shrunk_eigenvalues"]) @ U.T
    return (cov + cov.T) / 2


def nls_gmv_weights(window: pd.DataFrame) -> np.ndarray:
    return long_only_minvar(normalize_cov(nonlinear_shrinkage_cov(window.to_numpy())))


@dataclass(frozen=True)
class NLSGMVTrial:
    window_weeks: int = 156
    min_names: int = 100
    adv_min: float = 0.0
    include_thin: bool = False
    thin_min_months: int = 60
    exclude_categories: tuple[str, ...] = ("Defined Outcome / Buffer / Structured", "Specialty / Other")
    cost_bps: float = 5.0
    oos_start: str = "2021-04-30"
    oos_end: str = "2026-08-31"
    # Shared gate helper flag (gate_metrics.filter_cash_like). False reproduces the archived
    # v1 (VOID) run byte-for-byte; the v2 re-spec sets it True.
    exclude_cash_like: bool = False


PREREGISTERED_TRIALS = (NLSGMVTrial(156), NLSGMVTrial(260))
# Runs of the SAME pre-registered configurations that were invalidated by a code
# bug. Per the Quant ruling they COUNT toward trial_count (2 configs -> +2).
DISCLOSED_RUNS = (
    {"run": "2026-09-25 ~23:49 ET: first full walk-forward of the two pre-registered configs (156w, 260w)",
     "status": "invalid (numerical bug), superseded",
     "n_configs": 2,
     "bug": ("closed-form Epanechnikov Hilbert transform cancelled catastrophically in float64 for |x| >> sqrt(5) "
             "(wrong by orders of magnitude at |x| ~ 1e7, wrong sign at 1e8); with sample eigenvalues spanning ~7 "
             "decades the largest eigenvalues were shrunk to ~1e-9 of their sample values, so 'GMV' loaded on the "
             "highest-variance ETFs"),
     "fix": "exact far-field series for |x| >= 10 (same function; quadrature-verified to 1e-9 relative); regression tests added",
     "invalid_method_numbers": "156w Sharpe 0.796 / AnnVol 14.54% / MaxDD -23.02%; 260w Sharpe 0.733 / AnnVol 14.46% / MaxDD -22.88%",
     "nulls_affected": "no (EW, weekly LW MinVar, ERC do not use the estimator)"},
)

# Pre-registered configs (2) + invalidated first run counted by Quant (2).
# Any extra preview must be appended to the reported previews and increments this count.
TRIAL_COUNT = 4


def run_nls_gmv_trial(weekly, monthly, universe, coverage, trial=NLSGMVTrial()) -> dict[str, pd.DataFrame]:
    if trial.window_weeks < 3 or trial.min_names < 1 or trial.cost_bps < 0 or trial.thin_min_months < 0:
        raise ValueError("invalid window, minimum names/history or cost")
    monthly = monthly.sort_index().copy()
    months = monthly.index.to_period("M")
    if months.has_duplicates or (np.diff(months.asi8) != 1).any():
        raise ValueError("returns must contain exactly one row per consecutive calendar month")
    if not weekly.index.is_unique or not weekly.index.is_monotonic_increasing:
        raise ValueError("weekly index must be unique and increasing")
    for panel in (monthly, weekly):
        if panel.index.hasnans or panel.columns.has_duplicates:
            raise ValueError("invalid dates or duplicate names")
        if np.isinf(panel.to_numpy()).any() or (panel < -1).any().any():
            raise ValueError("invalid simple returns")
    uni = universe.set_index("Ticker")
    names = monthly.columns.intersection(uni.index).intersection(weekly.columns).tolist()
    names = [t for t in names if uni.loc[t, "Category"] not in trial.exclude_categories]
    # One eligible list feeds the method and every null, so the exclusion applies to all.
    names = filter_cash_like(names, universe, trial.exclude_cash_like)
    if coverage is not None:
        cov = coverage.set_index("ticker").reindex(names)
        if not trial.include_thin:
            thin = cov.thin_lt5y.astype(str).str.lower().ne("false")
            names = [t for t in names if not thin[t]]
        if trial.adv_min:
            names = [t for t in names if cov.loc[t, "adv_proxy"] >= trial.adv_min]
    elif trial.adv_min:
        raise ValueError("ADV filtering requires coverage")
    calendar = [i for i in range(len(monthly) - 1)
                if pd.Timestamp(trial.oos_start) <= monthly.index[i + 1] <= pd.Timestamp(trial.oos_end)]
    if not calendar:
        raise ValueError("empty OOS evaluation calendar")
    rows, weights, diagnostics, previous = [], [], [], {}
    for i in calendar:
        decision, evaluation = monthly.index[i:i + 2]
        win = weekly.loc[:decision, names].tail(trial.window_weeks)
        if len(win) < trial.window_weeks:
            raise ValueError(f"insufficient weekly history at {decision}")
        live = win.columns[win.notna().all() & (win.std() > 1e-10)].tolist()
        if not trial.include_thin:
            live = [t for t in live if monthly.iloc[:i + 1][t].count() >= trial.thin_min_months]
        if len(live) < trial.min_names:
            raise ValueError(f"eligible N={len(live)} below required N>={trial.min_names} at {decision}")
        win = win[live]
        observed = monthly.loc[evaluation, live]
        if observed.isna().any():
            raise ValueError(f"missing OOS return at {evaluation}; explicit data repair required")
        nulls = null_weights(win)
        allocations = {METHOD: nls_gmv_weights(win), PRIMARY: nulls["minvar_lw"],
                       "erc_weekly": nulls["erc"], "equal_weight": nulls["equal_weight"]}
        meta = dict(decision_date=decision, feature_end=win.index[-1], date=evaluation,
                    label_start=decision + pd.Timedelta(days=1), window_weeks=trial.window_weeks, n_names=len(live))
        sp = nonlinear_shrinkage_spectrum(win)
        lam, d = sp["sample_eigenvalues"], sp["shrunk_eigenvalues"]
        diagnostics.append({**meta, **{k: sp[k] for k in ("n_eff", "c", "h")},
                            "lambda_min": lam.min(), "lambda_max": lam.max(), "d_min": d.min(), "d_max": d.max(),
                            "sample_condition_number": lam.max() / lam.min(),
                            "nls_condition_number": d.max() / d.min(),
                            "lw_shrinkage_intensity": LedoitWolf().fit(win).shrinkage_})
        for sid, allocation in allocations.items():
            w = pd.Series(allocation, index=live)
            turnover = .5 * w.subtract(previous.get(sid, pd.Series(dtype=float)), fill_value=0).abs().sum()
            gross = float(w @ observed)
            cost = turnover * trial.cost_bps / 10000
            rows.append({**meta, "strategy_id": sid, "gross_return": gross, "turnover": turnover,
                         "cost_return": cost, "return": gross - cost})
            weights.extend(dict(decision_date=decision, date=evaluation, window_weeks=trial.window_weeks,
                                strategy_id=sid, ticker=t, weight=v) for t, v in w.items())
            previous[sid] = w
    return dict(oos_returns=pd.DataFrame(rows), weights=pd.DataFrame(weights), shrinkage_diagnostics=pd.DataFrame(diagnostics))


def summarize_gate(oos, weights, trial_count, primary_null=PRIMARY) -> pd.DataFrame:
    rows = []
    for (window, sid), sub in oos.groupby(["window_weeks", "strategy_id"]):
        sub = sub.sort_values("date")
        r = sub.set_index("date")["return"]
        base = oos.loc[(oos.window_weeks == window) & (oos.strategy_id == primary_null)].set_index("date")["return"]
        aligned = pd.concat([r, base], axis=1, join="inner").dropna()
        w = weights.loc[(weights.window_weeks == window) & (weights.strategy_id == sid)]
        hhi = w.assign(square=w.weight**2).groupby("date").square.sum()
        wealth = np.r_[1., (1 + r).cumprod().to_numpy()]
        sr, vol = sharpe_rf0(r), annualized_vol(r)
        rows.append(dict(window_weeks=window, strategy_id=sid, n_months=len(r), start=r.index.min(), end=r.index.max(),
                         AnnReturn=float((1 + r).prod()**(12 / len(r)) - 1), Sharpe_rf0=sr, AnnVol=vol,
                         OOS_var_monthly=r.var(ddof=1), OOS_var_ann=vol**2,
                         MaxDD=float(np.min(wealth / np.maximum.accumulate(wealth) - 1)),
                         turnover_per_year=sub.turnover.mean() * 12, HHI_mean=hhi.mean(), eff_N_mean=(1 / hhi).mean(),
                         avg_N_eligible=sub.n_names.mean(),
                         NW_t_vs_minvar_lw_weekly=np.nan if sid == primary_null else newey_west_tstat(aligned.iloc[:, 0] - aligned.iloc[:, 1], lags=3),
                         DSR=deflated_sharpe_approx(sr / np.sqrt(12), len(r), trial_count), trial_count=trial_count, dsr_method=DSR_METHOD))
    return pd.DataFrame(rows)


def monthly_lw_reference(spectral_dir=SPECTRAL_DIR):
    """Committed monthly LW MinVar is reference only, never a gate null."""
    frames = []
    for name in ("oos_returns", "weights"):
        frame = pd.read_csv(Path(spectral_dir) / f"{name}.csv")
        frame = frame.loc[frame.strategy_id.eq("minvar_lw__0")].copy()
        if frame.empty:
            raise ValueError(f"missing monthly LW reference only rows in {name}")
        frame["strategy_id"] = REFERENCE
        frame["role"] = "reference_only"
        for column in ("decision_date", "feature_end", "date", "label_start"):
            if column in frame:
                frame[column] = pd.to_datetime(frame[column])
        frames.append(frame)
    return tuple(frames)


CASH_LIKE_CATEGORY = "US Treasuries / Govt / Cash-like"


def composition_table(weights: pd.DataFrame, universe: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    """Descriptive holdings mix per config/strategy (average over rebalances)."""
    category = universe.set_index("Ticker")["Category"]
    rows = []
    for (window, sid), sub in weights.groupby(["window_weeks", "strategy_id"]):
        n = sub.date.nunique()
        by_ticker = (sub.groupby("ticker").weight.sum() / n).sort_values(ascending=False)
        by_cat = sub.assign(cat=sub.ticker.map(category)).groupby("cat").weight.sum() / n
        rows.append(dict(window_weeks=window, strategy_id=sid,
                         cash_like_category_weight=float(by_cat.get(CASH_LIKE_CATEGORY, 0.)),
                         top_holdings_avg="; ".join(f"{t} {v:.1%}" for t, v in by_ticker.head(top).items()),
                         top_categories_avg="; ".join(f"{c} {v:.1%}" for c, v in by_cat.sort_values(ascending=False).head(3).items())))
    return pd.DataFrame(rows)


def run_nls_gmv_gate(weekly, monthly, universe, coverage, trials=PREREGISTERED_TRIALS,
                     spectral_dir=SPECTRAL_DIR, extra_previews: list[str] = (),
                     disclosed_runs=DISCLOSED_RUNS) -> dict:
    trials = tuple(trials)
    if not trials or len({t.window_weeks for t in trials}) != len(trials):
        raise ValueError("provide nonempty trials with unique window_weeks")
    counted_invalid = sum(int(r.get("n_configs", 1)) for r in disclosed_runs)
    count = len(trials) + len(extra_previews) + counted_invalid
    runs = [run_nls_gmv_trial(weekly, monthly, universe, coverage, t) for t in trials]
    output = {key: pd.concat([r[key] for r in runs], ignore_index=True) for key in runs[0]}
    ref_oos, ref_weights = monthly_lw_reference(spectral_dir)
    registry = []
    for trial, run in zip(trials, runs):
        dates = run["oos_returns"].date.unique()
        for key, frame in (("oos_returns", ref_oos), ("weights", ref_weights)):
            selected = frame.loc[frame.date.isin(dates)].copy()
            if set(pd.to_datetime(dates)) - set(selected.date):
                raise ValueError("monthly reference only rows must cover every OOS evaluation date")
            selected["window_weeks"] = trial.window_weeks
            output[key] = pd.concat([output[key], selected], ignore_index=True)
        for sid, role in ROLES.items():
            registry.append({**asdict(trial), "strategy_id": sid, "role": role,
                             "trial_id": f"nls_gmv_w{trial.window_weeks}" if sid == METHOD else f"{sid}_w{trial.window_weeks}",
                             "preregistered": sid == METHOD and trial in PREREGISTERED_TRIALS, "trial_count": count})
    summary = summarize_gate(output["oos_returns"], output["weights"], count)
    summary["role"] = summary.strategy_id.map(ROLES)
    summary["DSR_decisive"] = False
    comparisons, checks = [], {}
    for trial in trials:
        window = trial.window_weeks
        table = summary.loc[summary.window_weeks.eq(window)].set_index("strategy_id")
        method, primary, reference = (table.loc[s] for s in (METHOD, PRIMARY, REFERENCE))
        checks[f"w{window}"] = dict(
            vol_lower_than_primary_null=bool(method.AnnVol < primary.AnnVol),
            sharpe_ge_primary_null=bool(method.Sharpe_rf0 >= primary.Sharpe_rf0),
            maxdd_no_worse_than_primary_null=bool(method.MaxDD >= primary.MaxDD),
            dsr_ge_0p95=bool(method.DSR >= .95),
            sharpe_gt_ew=bool(method.Sharpe_rf0 > table.loc["equal_weight", "Sharpe_rf0"]),
            sharpe_gt_erc=bool(method.Sharpe_rf0 > table.loc["erc_weekly", "Sharpe_rf0"]))
        oos = output["oos_returns"]
        pair = oos.loc[oos.window_weeks.eq(window) & oos.strategy_id.isin([PRIMARY, REFERENCE])].pivot(
            index="date", columns="strategy_id", values="return").dropna()
        comparison = dict(window_weeks=window, role="reference_only", n_common_months=len(pair),
                          NW_t_weekly_minus_monthly=newey_west_tstat(pair[PRIMARY] - pair[REFERENCE], lags=3))
        for metric in ("Sharpe_rf0", "AnnVol", "MaxDD"):
            comparison.update({f"weekly_{metric}": primary[metric], f"monthly_reference_{metric}": reference[metric],
                               f"difference_{metric}": primary[metric] - reference[metric]})
        comparisons.append(comparison)
    checks["w260_points_same_way"] = None
    if {156, 260}.issubset({t.window_weeks for t in trials}):
        diffs = {}
        for window in (156, 260):
            table = summary.loc[summary.window_weeks.eq(window)].set_index("strategy_id")
            diffs[window] = table.loc[METHOD, "Sharpe_rf0"] - table.loc[PRIMARY, "Sharpe_rf0"]
        checks["w260_points_same_way"] = bool(checks["w260"]["vol_lower_than_primary_null"] and
                                             np.sign(diffs[260]) == np.sign(diffs[156]))
    composition = composition_table(output["weights"], universe)
    output.update(summary=summary, null_comparison=summary.copy(), trial_registry=pd.DataFrame(registry), composition=composition,
                  weekly_vs_monthly_lw=pd.DataFrame(comparisons), gate_checks=checks, trial_count=count,
                  trials=[asdict(t) for t in trials], extra_previews=list(extra_previews),
                  disclosed_runs=[dict(r) for r in disclosed_runs], trial_count_breakdown=dict(
                      preregistered_configs=len(trials), extra_previews=len(extra_previews),
                      invalidated_run_configs=counted_invalid),
                  metadata={
                      "ticket_path": "/workspace/investments/justina_shortlist/ENGINEERING_TICKET_nonlinear_shrinkage_gmv.md",
                      "teaching_note_path": "/workspace/investments/methods/allocation_alpha_nonlinear_shrinkage_gmv.html",
                      "data_files": {"weekly": "data/raw/usa_universe_panel_weekly_returns.csv",
                                     "monthly": "data/raw/usa_universe_panel_monthly_returns.csv",
                                     "universe": "data/raw/usa_universe_categorized.csv",
                                     "coverage": "data/raw/usa_universe_panel_history_coverage.csv",
                                     "spectral_dir": str(spectral_dir)},
                      "universe": "Monthly/universe/weekly intersection; excluded categories, static coverage and ADV filters; dynamic monthly history and complete weekly windows. Snapshot filters imply survivorship bias.",
                      "calendar": "Monthly decisions, next observed monthly evaluation within inclusive trial OOS bounds; weekly dates <= decision; no warm-up skipping.",
                      "cost": "Half L1 change from previous target weights, including initial entry; turnover times trial cost_bps / 10000.",
                      "solver": "Covariance divided by mean diagonal; SLSQP, equal initial weights, bounds (0,1), sum=1, maxiter=1000, ftol=1e-12; shared spectral nulls.",
                      "reference": "Committed monthly LW MinVar is reference only; its original universe, turnover and costs are retained.",
                      "universe_note": ("Mirrors the committed Spectral RP name gate (data/processed/spectral_rp/name/trial_registry.csv: "
                                        "adv_min 0.0, include_thin false, min_names 100, same excluded categories, 5 bp). "
                                        "An ADV >= $10M snapshot filter is NOT applied: it would leave 98 non-thin names (< 100), "
                                        "and the archived gate did not apply it. Eligible N per rebalance matches the archived gate (101-120)."),
                      "estimator_note": ("Clean-room Ledoit-Wolf (2020) analytical nonlinear shrinkage, p < n case; demeaned inside each "
                                         "window, effective n = T - 1 (paper Remark 2.1), c = N/n, h = n^(-1/3), h_j = lambda_j h; "
                                         "Hilbert transform far field (|x| >= 10) via exact series for float64 stability."),
                      "input_provenance": "DataFrame inputs; default file paths are nominal unless supplied by the CLI."})
    return output


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_gate_artifacts(result, out_dir="data/processed/nonlinear_shrinkage_gmv"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tables = ("oos_returns", "weights", "summary", "null_comparison", "trial_registry",
              "shrinkage_diagnostics", "weekly_vs_monthly_lw", "composition")
    for name in tables:
        result[name].to_csv(out / f"{name}.csv", index=False, date_format="%Y-%m-%d")
    report = dict(VERDICT)
    report.update({k: result[k] for k in ("metadata", "trial_count", "trial_count_breakdown", "trials",
                                          "extra_previews", "disclosed_runs")})
    report["mechanical_gate_checks_superseded_by_verdict"] = result["gate_checks"]
    report.update(statement=DISCLAIMER, summary=result["summary"].to_dict("records"),
                  weekly_vs_monthly_lw=result["weekly_vs_monthly_lw"].to_dict("records"),
                  composition=result["composition"].to_dict("records"))
    (out / "gate_report.json").write_text(json.dumps(_json_safe(report), indent=2, allow_nan=False) + "\n")
    meta = result["metadata"]
    first = result["summary"].loc[result["summary"].strategy_id.eq(METHOD)].iloc[0]
    lines = ["# Analytical nonlinear shrinkage GMV (Bet 1) — gate report", "",
             f"**Verdict: {VERDICT['verdict_label']}** ({VERDICT['verdict_by']}, {VERDICT['verdict_date']}). "
             "Not PASS, not FAIL.", "", VERDICT["verdict_reason"], "",
             f"**Follow-up:** {VERDICT['follow_up']}", "", f"**Cash-share caveat:** {VERDICT['cash_share_caveat']}", "",
             DISCLAIMER, "",
             f"- Ticket: `{meta['ticket_path']}`", f"- Teaching note: `{meta['teaching_note_path']}`",
             f"- OOS window: {pd.Timestamp(first.start):%Y-%m-%d} → {pd.Timestamp(first.end):%Y-%m-%d} ({int(first.n_months)} monthly evaluations)",
             "- Primary null: LW (2004) linear-shrinkage long-only MinVar re-estimated on the SAME weekly returns and window.",
             "- Monthly LW MinVar (Archive, Spectral RP gate) appears only as a labeled reference row.", "",
             "## Geometry", "", meta["universe"], "", meta["universe_note"], "", meta["calendar"], "",
             meta["cost"], "", meta["solver"], "", meta["estimator_note"], ""]
    labels = {METHOD: "method", PRIMARY: "weekly LW MinVar (primary null)", "equal_weight": "EW",
              "erc_weekly": "ERC", REFERENCE: "monthly LW MinVar (reference only)"}
    columns = [("Sharpe_rf0", "Sharpe_rf0", ".3f"), ("AnnVol", "AnnVol", ".2%"),
               ("OOS var (ann.)", "OOS_var_ann", ".2%"), ("MaxDD", "MaxDD", ".2%"),
               ("turnover/yr", "turnover_per_year", ".2%"), ("HHI", "HHI_mean", ".4f"),
               ("eff N", "eff_N_mean", ".2f"), ("avg N", "avg_N_eligible", ".2f"),
               ("NW t vs weekly LW", "NW_t_vs_minvar_lw_weekly", ".2f"), ("DSR", "DSR", ".4f")]
    for window, group in result["summary"].groupby("window_weeks"):
        lines += [f"## {window}-week configuration", "", "| Strategy | " + " | ".join(c[0] for c in columns) + " |",
                  "|---|" + "---|" * len(columns)]
        table = group.set_index("strategy_id")
        for sid, label in labels.items():
            row = table.loc[sid]
            values = [format(row[key], fmt) if pd.notna(row[key]) else "—" for _, key, fmt in columns]
            lines.append("| " + label + " | " + " | ".join(values) + " |")
        lines.append("")
    lines += ["## Holdings composition (descriptive)", "",
              "Average over rebalances. Sharpe_rf0 uses rf = 0, so for portfolios dominated by T-bill / "
              "cash-like ETFs it largely reflects the cash yield over the OOS window, not excess return.", "",
              "| Config | Strategy | Cash-like category weight | Top holdings (avg) |", "|---|---|---|---|"]
    for row in result["composition"].itertuples():
        lines.append(f"| {row.window_weeks}w | {labels.get(row.strategy_id, row.strategy_id)} | "
                     f"{row.cash_like_category_weight:.1%} | {row.top_holdings_avg} |")
    lines += ["", f"Cash-like = universe Category \"{CASH_LIKE_CATEGORY}\" (usa_universe_categorized.csv). "
              "That category also contains duration (e.g. GOVT, IEF, TLT, SHY) and misses USFR (labelled High Yield "
              "Credit), so these shares mix in some duration and are not a pure T-bill share.", ""]
    b = result["trial_count_breakdown"]
    lines += ["## DSR and trial_count", "",
              f"trial_count = {result['trial_count']} ({b['preregistered_configs']} pre-registered configs + "
              f"{b['invalidated_run_configs']} configs from the invalidated first run, counted per Quant + "
              f"{b['extra_previews']} extra previews). {DSR_METHOD}.", "",
              "**DSR is non-decisive.** Sharpe_rf0 is the repo convention (compound annual return / annualized vol, "
              "as in the Spectral RP gate) and rewards cash carry; DSR input is Sharpe_rf0/sqrt(12). At this low "
              "trial_count the expected-max-noise term is small, so DSR is effectively a PSR vs zero without "
              "skew/kurtosis adjustment and carries no weight in the verdict.", "",
              "All extra previews count: " + (", ".join(result["extra_previews"]) or "none") + ".", "",
              "Pre-registered trials: " + ", ".join(f"{t['window_weeks']}w" for t in result["trials"]) + ".", ""]
    if result["disclosed_runs"]:
        lines += ["### Invalidated first run (same configs; counted in trial_count)", ""]
        for run in result["disclosed_runs"]:
            lines += [f"- **{run['run']}** — {run['status']}.", f"  - Bug: {run['bug']}.", f"  - Fix: {run['fix']}.",
                      f"  - Invalid method numbers (do not use): {run['invalid_method_numbers']}.",
                      f"  - Nulls affected: {run['nulls_affected']}."]
        lines += ["", "Counted in trial_count per the Quant ruling.", ""]
    lines += [
              "## Weekly versus monthly LW (reference only)", "",
              "This frequency comparison is separate from the estimator gate checks. The committed monthly allocation is reference only.", ""]
    for row in result["weekly_vs_monthly_lw"].to_dict("records"):
        lines += [f"{row['window_weeks']} weeks: {row['n_common_months']} common months; NW t (weekly − monthly) {row['NW_t_weekly_minus_monthly']:.2f}.", "",
                  "| Metric | Weekly LW | Monthly LW (reference only) | Difference |", "|---|---|---|---|"]
        for metric, fmt in (("Sharpe_rf0", ".3f"), ("AnnVol", ".2%"), ("MaxDD", ".2%")):
            lines.append(f"| {metric} | {row['weekly_' + metric]:{fmt}} | {row['monthly_reference_' + metric]:{fmt}} | {row['difference_' + metric]:{fmt}} |")
        lines.append("")
    lines += ["## Mechanical gate checks (superseded by the VOID verdict)", "",
              "All v1 criteria passed mechanically, but the design was broken (cash-dominated method and null, "
              "Sharpe_rf0), so these checks carry no weight.", "", "```json",
              json.dumps(_json_safe(result["gate_checks"]), indent=2), "```", "",
              f"Verdict: {VERDICT['verdict_label']}. Follow-up: v2 ex-cash re-spec.", ""]
    (out / "gate_report.md").write_text("\n".join(lines))
