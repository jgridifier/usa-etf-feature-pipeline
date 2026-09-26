"""Research only: ex-cash NLS GMV; snapshot universe implies survivorship bias.

Ledoit & Wolf (2020), AoS 48(5) 3043–3065 (unchanged estimator);
LW (2017), RFS 30(12) 4349–4388 (GMV judged on out-of-sample SD);
LW (2011), "Robust Performance Hypothesis Testing with the Variance",
Wilmott 2011(55) 86–89; LW (2008), JEF 15(5) 850–859 (HAC/bootstrap);
Andrews (1991), Econometrica 59(3) 817–858; Andrews & Monahan (1992),
Econometrica 60(4) 953–966; Politis & Romano (1992), circular block bootstrap.
Bandwidth equation: https://cowles.yale.edu/sites/default/files/2022-08/d0942.pdf
Bootstrap machinery: https://www.ledoit.net/Robust_Sharpe_2008.pdf
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

import numpy as np
import pandas as pd
from scipy.special import ndtr
from sklearn.covariance import LedoitWolf

from . import nonlinear_shrinkage_gmv as v1
from .gate_metrics import (filter_cash_like, cash_like_tickers, short_duration_tickers,
                           risk_free_monthly, sharpe_exbil, window_rf_coverage)
from .portfolio import ledoit_wolf_cov
from .spectral_risk_parity import null_weights, long_only_minvar, normalize_cov, read_returns
from .vol_target import annualized_vol, sharpe_rf0, newey_west_tstat, deflated_sharpe_approx

METHOD, PRIMARY, REFERENCE, ROLES = v1.METHOD, v1.PRIMARY, v1.REFERENCE, v1.ROLES
TICKET = "/workspace/investments/justina_shortlist/ENGINEERING_TICKET_nonlinear_shrinkage_gmv_v2_excash.md"
DECISION_RULE = ("Criterion 1: method AnnVol < weekly LW MinVar AnnVol and "
                 "p_gate = max(p_one_sided_hac, p_one_sided_boot) <= 0.10; "
                 "both LW2011 variants must pass.")
STATUS = "PENDING — Quant decides"
TRIAL_COUNT_V2 = 6


@dataclass(frozen=True)
class NLSGMVv2Trial:
    window_weeks: int = 156
    min_names: int = 95
    below_floor: str = "skip"
    adv_min: float = 0.0
    include_thin: bool = False
    thin_min_months: int = 60
    exclude_categories: tuple[str, ...] = ("Defined Outcome / Buffer / Structured", "Specialty / Other")
    exclude_cash_like: bool = True
    cost_bps: float = 5.0
    oos_start: str = "2021-04-30"
    oos_end: str = "2026-08-31"
    reference_lookback_months: int = 60


PREREGISTERED_V2 = (NLSGMVv2Trial(156), NLSGMVv2Trial(260))


def _moments(x):
    """Supports leading bootstrap batch dimensions; observations on axis -2."""
    mu = x.mean(axis=-2)
    gamma = (x*x).mean(axis=-2)
    var = gamma - mu*mu
    if np.any(var <= 0):
        raise ValueError("variance test requires positive variances")
    y = np.concatenate((x - mu[..., None, :], x*x - gamma[..., None, :]), axis=-1)
    g = np.stack((-2*mu[..., 0]/var[..., 0], 2*mu[..., 1]/var[..., 1],
                  1/var[..., 0], -1/var[..., 1]), axis=-1)
    return np.log(var[..., 0]) - np.log(var[..., 1]), y, g, var


def _qs_hac(y, prewhiten):
    T = len(y)
    A = np.zeros((4, 4))
    e = y
    if prewhiten:
        A = np.linalg.lstsq(y[:-1], y[1:], rcond=None)[0].T
        radius = np.max(np.abs(np.linalg.eigvals(A)))
        if radius >= .97:
            A *= .97 / radius
        e = y[1:] - y[:-1] @ A.T
    e = e - e.mean(axis=0)
    lag, nxt = e[:-1], e[1:]
    denom = (lag*lag).sum(axis=0)
    rho = np.divide((lag*nxt).sum(axis=0), denom, out=np.zeros(4), where=denom > 0)
    rho = np.clip(rho, -.97, .97)
    innovation_var = ((nxt - lag*rho)**2).mean(axis=0)
    denominator = np.sum(innovation_var**2 / (1-rho)**4)
    alpha = np.sum(4*rho**2 * innovation_var**2 / (1-rho)**8) / denominator if denominator else 0.
    bandwidth = 1.3221 * (len(e)*alpha)**.2
    psi = e.T @ e / len(e)
    if bandwidth > 1e-12:
        for k in range(1, len(e)):
            z = 6*np.pi*(k/bandwidth)/5
            kernel = 3*(np.sin(z)/z - np.cos(z))/(z*z)
            cov = e[k:].T @ e[:-k] / len(e)
            psi += kernel*(cov + cov.T)
    recolor = np.linalg.inv(np.eye(4)-A)
    return recolor @ psi @ recolor.T * T/(T-4), float(bandwidth)


def _natural_se(y, g, block_size):
    """LW (2008) natural block standard error of the log-variance difference.

    Psi = (1/l) sum_j zeta_j zeta_j' with zeta_j = b^(-1/2) * (block-j sum of y); blocks of size b
    are tiled over the T observations (original sample) or are the resampled circular blocks
    (bootstrap), truncated to exactly T observations, so the final block may be partial.
    """
    T = y.shape[-2]
    l = (T + block_size-1)//block_size
    influence = np.einsum('...ti,...i->...t', y, g)
    padded = np.pad(influence, [(0, 0)]*(influence.ndim-1) + [(0, l*block_size-T)])
    sums = padded.reshape(*influence.shape[:-1], l, block_size).sum(axis=-1)
    return np.sqrt((sums*sums).mean(axis=-1) / block_size / T)


def _z(delta, se):
    if se <= 1e-14:
        return 0. if abs(delta) <= 1e-14 else float(np.copysign(np.inf, delta))
    return float(delta/se)


def lw2011_variance_test(a, b, *, hac=True, prewhiten=True, bootstrap_reps=4999,
                         block_size=4, seed=20260926):
    """One-sided H1: variance(a) < variance(b), with paired circular blocks.

    A common RMS return unit is removed before fitting the moment VAR and the
    equal-weight AR bandwidth selector, making inference invariant to return
    units. This is a common scalar (not separate scaling of the two portfolios).
    IID inference uses the unmodified sample moment covariance (ddof=1).
    bootstrap_reps=0 skips bootstrap for simulation diagnostics only.
    """
    pair = pd.concat([pd.Series(a), pd.Series(b)], axis=1, join="inner").dropna()
    T = len(pair)
    if T < 12:
        raise ValueError("variance test requires at least 12 aligned observations")
    if not np.isfinite(pair.to_numpy()).all():
        raise ValueError("returns must be finite")
    if int(block_size) != block_size or not 1 <= block_size <= T or int(bootstrap_reps) != bootstrap_reps or bootstrap_reps < 0:
        raise ValueError("invalid block_size or bootstrap_reps")
    raw = pair.to_numpy(dtype=float)
    delta, y, g, var = _moments(raw)
    scale = np.sqrt(np.mean(raw*raw))
    x = raw / scale
    _, ys, gs, _ = _moments(x)
    if hac:
        psi, bandwidth = _qs_hac(ys, prewhiten)
        se = np.sqrt(max(0., float(gs @ psi @ gs))/T)
    else:
        bandwidth = 0.
        se = np.sqrt(max(0., float(g @ np.cov(y, rowvar=False, ddof=1) @ g))/T)
    # Exact identical samples have a degenerate, zero difference.
    if np.array_equal(raw[:, 0], raw[:, 1]):
        se = 0.
    z = _z(delta, se)
    nat = float(_natural_se(ys, gs, block_size))
    z_boot = _z(delta, nat)
    one = two = np.nan
    if bootstrap_reps:
        rng = np.random.default_rng(seed)
        l = (T + block_size-1)//block_size
        n_one = n_two = 0
        for start in range(0, bootstrap_reps, 256):
            m = min(256, bootstrap_reps-start)
            starts = rng.integers(T, size=(m, l))
            indices = ((starts[..., None] + np.arange(block_size)) % T).reshape(m, -1)[:, :T]
            ds, yy, gg, _ = _moments(x[indices])
            ses = _natural_se(yy, gg, block_size)
            centered = ds - delta
            zs = np.divide(centered, ses, out=np.zeros_like(ds), where=ses > 1e-14)
            degenerate = (ses <= 1e-14) & (np.abs(centered) > 1e-14)
            zs[degenerate] = np.copysign(np.inf, centered[degenerate])
            n_one += np.count_nonzero(zs <= z_boot)
            n_two += np.count_nonzero(np.abs(zs) >= abs(z_boot))
        one, two = (1+n_one)/(bootstrap_reps+1), (1+n_two)/(bootstrap_reps+1)
    return dict(n=T, var_a_ann=float(var[0]*12), var_b_ann=float(var[1]*12),
                vol_a_ann=float(np.sqrt(var[0]*12)), vol_b_ann=float(np.sqrt(var[1]*12)),
                delta_log_var=float(delta), se_hac=float(se), z_hac=z,
                p_one_sided_hac=float(ndtr(z)), p_two_sided_hac=float(2*ndtr(-abs(z))),
                bandwidth=bandwidth, se_boot_nat=nat, p_one_sided_boot=one,
                p_two_sided_boot=two, block_size=block_size, bootstrap_reps=bootstrap_reps, seed=seed)


def run_nls_gmv_v2_trial(weekly, monthly, universe, coverage, trial=NLSGMVv2Trial()) -> dict[str, pd.DataFrame]:
    if trial.window_weeks < 3 or trial.min_names < 1 or trial.cost_bps < 0 or trial.thin_min_months < 0:
        raise ValueError("invalid window, minimum names/history or cost")
    if trial.below_floor != "skip" or trial.reference_lookback_months < 2:
        raise ValueError("below_floor must be skip; reference lookback must be >= 2")
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
    rows, weights, diagnostics, previous, counts = [], [], [], {}, []
    for i in calendar:
        decision, evaluation = monthly.index[i:i + 2]
        win = weekly.loc[:decision, names].tail(trial.window_weeks)
        if len(win) < trial.window_weeks:
            raise ValueError(f"insufficient weekly history at {decision}")
        live = win.columns[win.notna().all() & (win.std() > 1e-10)].tolist()
        if not trial.include_thin:
            live = [t for t in live if monthly.iloc[:i + 1][t].count() >= trial.thin_min_months]
        skipped = len(live) < trial.min_names
        counts.append(dict(decision_date=decision, date=evaluation, window_weeks=trial.window_weeks,
                           n_eligible=len(live), below_100=len(live) < 100, skipped=skipped))
        if skipped:
            continue
        win = win[live]
        observed = monthly.loc[evaluation, live]
        if observed.isna().any():
            raise ValueError(f"missing OOS return at {evaluation}; explicit data repair required")
        nulls = null_weights(win)
        allocations = {METHOD: v1.nls_gmv_weights(win), PRIMARY: nulls["minvar_lw"],
                       "erc_weekly": nulls["erc"], "equal_weight": nulls["equal_weight"]}
        meta = dict(decision_date=decision, feature_end=win.index[-1], date=evaluation,
                    label_start=decision + pd.Timedelta(days=1), window_weeks=trial.window_weeks, n_names=len(live))
        sp = v1.nonlinear_shrinkage_spectrum(win)
        lam, d = sp["sample_eigenvalues"], sp["shrunk_eigenvalues"]
        diagnostics.append({**meta, **{k: sp[k] for k in ("n_eff", "c", "h")},
                            "lambda_min": lam.min(), "lambda_max": lam.max(), "d_min": d.min(), "d_max": d.max(),
                            "sample_condition_number": lam.max() / lam.min(),
                            "nls_condition_number": d.max() / d.min(),
                            "lw_shrinkage_intensity": LedoitWolf().fit(win).shrinkage_})
        monthly_win = monthly.iloc[max(0, i+1-trial.reference_lookback_months):i+1][live].dropna(axis=1)
        if len(monthly_win) < trial.reference_lookback_months or monthly_win.shape[1] == 0:
            raise ValueError(f"insufficient monthly reference history at {decision}")
        reference = long_only_minvar(normalize_cov(ledoit_wolf_cov(monthly_win, force_shrinkage=True).to_numpy()))
        allocations[REFERENCE] = reference
        for sid, allocation in allocations.items():
            w = pd.Series(allocation, index=monthly_win.columns if sid == REFERENCE else live)
            turnover = .5 * w.subtract(previous.get(sid, pd.Series(dtype=float)), fill_value=0).abs().sum()
            gross = float(w @ observed.reindex(w.index))
            cost = turnover * trial.cost_bps / 10000
            rows.append({**meta, "n_names": len(w), "strategy_id": sid, "gross_return": gross, "turnover": turnover,
                         "cost_return": cost, "return": gross - cost})
            weights.extend(dict(decision_date=decision, date=evaluation, window_weeks=trial.window_weeks,
                                strategy_id=sid, ticker=t, weight=v) for t, v in w.items())
            previous[sid] = w
    if not rows:
        raise ValueError("every rebalance is skipped below the name floor")
    return dict(name_counts=pd.DataFrame(counts), oos_returns=pd.DataFrame(rows), weights=pd.DataFrame(weights), shrinkage_diagnostics=pd.DataFrame(diagnostics))



def composition_table(weights, universe):
    categories = universe.set_index("Ticker").Category
    short, cash = short_duration_tickers(universe), cash_like_tickers(universe)
    rows = []
    for (window, sid), w in weights.groupby(["window_weeks", "strategy_id"]):
        n = w.date.nunique()
        holdings = (w.groupby("ticker").weight.sum()/n).sort_values(ascending=False)
        cats = (w.assign(category=w.ticker.map(categories)).groupby("category").weight.sum()/n).sort_values(ascending=False)
        cash_share = float(w.loc[w.ticker.isin(cash), "weight"].sum()/n)
        assert cash_share == 0., "v2 gate must have zero cash-like holdings for every strategy"
        rows.append(dict(window_weeks=window, strategy_id=sid,
                         short_duration_share_mean=float(w.loc[w.ticker.isin(short), "weight"].sum()/n),
                         cash_like_share_mean=cash_share, largest_category=cats.index[0],
                         largest_category_share=float(cats.iloc[0]),
                         top_categories_avg="; ".join(f"{k} {v:.2%}" for k, v in cats.head(3).items()),
                         top_holdings_avg="; ".join(f"{k} {v:.2%}" for k, v in holdings.head(5).items())))
    return pd.DataFrame(rows)


def summarize_v2(oos, weights, name_counts, universe, trial_count, *, rf=None, bootstrap_reps=4999):
    rf = risk_free_monthly() if rf is None else rf
    composition = composition_table(weights, universe)
    rows, tests = [], []
    for (window, sid), sub in oos.groupby(["window_weeks", "strategy_id"]):
        sub = sub.sort_values("date")
        r = sub.set_index("date")["return"]
        base = oos.loc[oos.window_weeks.eq(window) & oos.strategy_id.eq(PRIMARY)].set_index("date")["return"]
        aligned = pd.concat([r, base], axis=1, join="inner").dropna()
        w = weights.loc[weights.window_weeks.eq(window) & weights.strategy_id.eq(sid)]
        hhi = w.assign(square=w.weight**2).groupby("date").square.sum()
        held = w.assign(held=w.weight > 1e-4).groupby("date").held.sum()
        wealth = np.r_[1., (1+r).cumprod().to_numpy()]
        sr, sr0, vol = sharpe_exbil(r, rf), sharpe_rf0(r), annualized_vol(r)
        test = {k: np.nan for k in ("p_one_sided_hac", "p_one_sided_boot", "delta_log_var")}
        if sid != PRIMARY:
            test = lw2011_variance_test(r, base, bootstrap_reps=bootstrap_reps)
            tests.append(dict(window_weeks=window, strategy_id=sid, primary_null=PRIMARY, **test))
        gate = float(np.maximum(test["p_one_sided_hac"], test["p_one_sided_boot"]))
        rows.append(dict(window_weeks=window, strategy_id=sid, n_months=len(r), start=r.index.min(), end=r.index.max(),
                         AnnReturn=float((1+r).prod()**(12/len(r))-1), AnnVol=vol, OOS_var_ann=vol**2,
                         Sharpe_exBIL=sr, Sharpe_rf0_legacy=sr0,
                         rf_fallback_share=window_rf_coverage(r.index, rf)["fallback_share"],
                         MaxDD=float(np.min(wealth/np.maximum.accumulate(wealth)-1)),
                         turnover_per_year=sub.turnover.mean()*12, HHI_mean=hhi.mean(), eff_N_mean=(1/hhi).mean(),
                         names_held_mean=held.mean(),
                         avg_N_eligible=name_counts.loc[name_counts.window_weeks.eq(window), "n_eligible"].mean(),
                         NW_t_vs_primary=np.nan if sid == PRIMARY else newey_west_tstat(aligned.iloc[:, 0]-aligned.iloc[:, 1], lags=3),
                         **{k: test[k] for k in ("p_one_sided_hac", "p_one_sided_boot", "delta_log_var")}, p_gate=gate,
                         DSR_exBIL=deflated_sharpe_approx(sr/np.sqrt(12), len(r), trial_count),
                         DSR_rf0_legacy=deflated_sharpe_approx(sr0/np.sqrt(12), len(r), trial_count),
                         trial_count=trial_count, role=ROLES[sid], DSR_decisive=False))
    return pd.DataFrame(rows).merge(composition, on=["window_weeks", "strategy_id"]), pd.DataFrame(tests), composition


def mechanical_reading(summary, windows=(156, 260)):
    """Mechanical criteria only; the research report remains pending Quant."""
    checks = {}
    tripwires = ("void_method_short_duration", "void_method_effN",
                 "void_primary_short_duration", "void_primary_effN")
    for window in windows:
        table = summary.loc[summary.window_weeks.eq(window)].set_index("strategy_id")
        if not {METHOD, PRIMARY, "erc_weekly"}.issubset(table.index):
            raise ValueError(f"missing gate strategies for window {window}")
        m, p, e = (table.loc[s] for s in (METHOD, PRIMARY, "erc_weekly"))
        checks[f"w{window}"] = dict(
            c1_vol_lower_and_p_le_0p10=bool(m.AnnVol < p.AnnVol and m.p_gate <= .10),
            c1_vol_lower=bool(m.AnnVol < p.AnnVol),
            c2_sharpe_exbil_ge_primary=bool(m.Sharpe_exBIL >= p.Sharpe_exBIL),
            c2_sharpe_exbil_gt_erc=bool(m.Sharpe_exBIL > e.Sharpe_exBIL),
            c2=bool(m.Sharpe_exBIL >= p.Sharpe_exBIL and m.Sharpe_exBIL > e.Sharpe_exBIL),
            c3_maxdd_no_worse=bool(m.MaxDD >= p.MaxDD),
            void_method_short_duration=bool(m.short_duration_share_mean > .50),
            void_method_effN=bool(m.eff_N_mean < 5),
            void_primary_short_duration=bool(p.short_duration_share_mean > .50),
            void_primary_effN=bool(p.eff_N_mean < 5),
            raw={"method": m.to_dict(), "primary": p.to_dict(), "erc": e.to_dict()})
    # Custom preview windows may be summarized, but cannot stand in for the registered gate.
    primary, sensitivity = checks.get("w156"), checks.get("w260")
    c4 = bool(sensitivity and sensitivity["c1_vol_lower"] and sensitivity["c2"])
    void = [k for k in tripwires if primary and primary[k]]
    notes = [k for k in tripwires if sensitivity and sensitivity[k]]
    fail = [name for name, passed in (
        ("c1", primary and primary["c1_vol_lower_and_p_le_0p10"]),
        ("c2", primary and primary["c2"]), ("c3", primary and primary["c3_maxdd_no_worse"]), ("c4", c4)) if not passed]
    return dict(windows=checks, c4_260w_same_way=c4, void_tripwires=void,
                sensitivity_260w_tripwires=notes, sensitivity_note="260w tripwires are information only; do not void the 156w gate",
                failing_criteria=fail, overall="VOID" if void else "FAIL" if fail else "PASS")


def run_nls_gmv_v2_gate(weekly, monthly, universe, coverage, trials=PREREGISTERED_V2,
                       extra_previews=(), *, rf=None):
    trials, extra_previews = tuple(trials), tuple(extra_previews)
    if not trials or len({t.window_weeks for t in trials}) != len(trials):
        raise ValueError("provide nonempty trials with unique window_weeks")
    count = v1.TRIAL_COUNT + len(trials) + len(extra_previews)
    if trials == PREREGISTERED_V2 and not extra_previews:
        assert count == TRIAL_COUNT_V2
    runs = [run_nls_gmv_v2_trial(weekly, monthly, universe, coverage, t) for t in trials]
    result = {k: pd.concat([run[k] for run in runs], ignore_index=True) for k in runs[0]}
    summary, tests, composition = summarize_v2(result["oos_returns"], result["weights"], result["name_counts"], universe, count, rf=rf)
    registry = [{**asdict(t), "trial_id": f"nls_gmv_v2_w{t.window_weeks}",
                 "role": "primary" if t.window_weeks == 156 else "sensitivity" if t.window_weeks == 260 else "preview",
                 "preregistered": t in PREREGISTERED_V2, "trial_count": count} for t in trials]
    result.update(summary=summary, variance_tests=tests, composition=composition, trial_registry=pd.DataFrame(registry),
                  status=STATUS, decision_rule=DECISION_RULE, ticket=TICKET, trials=[asdict(t) for t in trials],
                  trial_count=count, extra_previews=list(extra_previews),
                  trial_count_breakdown=dict(v1_carried=v1.TRIAL_COUNT, v2_configs=len(trials), extra_previews=len(extra_previews)),
                  mechanical_reading=mechanical_reading(summary, windows=tuple(t.window_weeks for t in trials)))
    return result


def _json_safe(value):
    if isinstance(value, pd.DataFrame):
        return _json_safe(value.to_dict("records"))
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


def write_v2_artifacts(result, out_dir="data/processed/nonlinear_shrinkage_gmv_v2"):
    out = Path(out_dir)
    # Never overwrite an archived processed artifact, even through a custom CLI path.
    processed = Path(__file__).resolve().parents[2] / "data" / "processed"
    tables = ("oos_returns", "weights", "summary", "variance_tests", "name_counts", "shrinkage_diagnostics", "composition", "trial_registry")
    targets = [out/f"{k}.csv" for k in tables] + [out/"gate_report.json", out/"gate_report.md"]
    if out.resolve().is_relative_to(processed.resolve()) and any(p.exists() for p in targets):
        raise FileExistsError("refusing to overwrite existing processed artifacts; choose a new output directory")
    out.mkdir(parents=True, exist_ok=True)
    for key in tables:
        result[key].to_csv(out/f"{key}.csv", index=False, date_format="%Y-%m-%d")
    report = {k: result[k] for k in ("status", "decision_rule", "ticket", "trials", "trial_count", "extra_previews",
                                     "trial_count_breakdown", "mechanical_reading", "summary", "variance_tests",
                                     "composition", "name_counts")}
    report["statement"] = "Research only. Registry enabled:false. No live-book wiring. Quant decides the gate."
    report["dsr_decisive"] = False
    (out/"gate_report.json").write_text(json.dumps(_json_safe(report), indent=2, allow_nan=False)+"\n")
    labels = {METHOD: "NLS GMV (method)", PRIMARY: "Weekly LW MinVar (primary null)",
              "equal_weight": "EW", "erc_weekly": "ERC", REFERENCE: "Monthly LW MinVar (reference only)"}
    lines = ["# NLS GMV v2 ex-cash research gate", "", STATUS, "",
             "Research only. Registry enabled:false. Snapshot universe implies survivorship bias. No live-book wiring.",
             "", f"Ticket: `{TICKET}`", "", DECISION_RULE, "",
             "Spectral RP name settings plus exclude_cash_like=True; pre-registered floor 95, skip-and-list.",
             "Weekly windows end at the decision month; next-month evaluation, half-L1 turnover including initial entry, 5 bp costs.",
             "Previous weights carry across skipped months. Monthly LW MinVar is reference only.", ""]
    for trial in result["trials"]:
        lines += [f"Configuration: `{json.dumps(_json_safe(trial), sort_keys=True)}`", ""]
    for window, counts in result["name_counts"].groupby("window_weeks"):
        skipped = counts.loc[counts.skipped, "date"]
        listed = ", ".join(pd.Timestamp(d).strftime("%Y-%m-%d") for d in skipped) or "none"
        lines += [f"{window}w eligible N per rebalance: min {counts.n_eligible.min()}, mean {counts.n_eligible.mean():.2f}, "
                  f"max {counts.n_eligible.max()}; months under 100: {int(counts.below_100.sum())}; skipped months: {listed}.", ""]
    columns = [("AnnVol", "AnnVol", ".2%"), ("Sharpe ex-BIL", "Sharpe_exBIL", ".3f"),
               ("Sharpe legacy (rf = 0)", "Sharpe_rf0_legacy", ".3f"), ("MaxDD", "MaxDD", ".2%"),
               ("short_duration share", "short_duration_share_mean", ".2%"), ("eff N", "eff_N_mean", ".2f"),
               ("names held", "names_held_mean", ".2f"), ("turnover/yr", "turnover_per_year", ".2%"),
               ("NW t vs primary", "NW_t_vs_primary", ".2f"), ("DSR (ex-BIL)", "DSR_exBIL", ".4f")]
    def fmt(v, spec):
        return format(v, spec) if pd.notna(v) else "—"
    for window, group in result["summary"].groupby("window_weeks"):
        lines += [f"## {window}-week configuration", "",
                  "| Strategy | " + " | ".join(c[0] for c in columns) + " | LW2011 p (one-sided, HAC / boot / gate) | largest category (share) |",
                  "|---|" + "---|"*(len(columns)+2)]
        table = group.set_index("strategy_id")
        for sid, label in labels.items():
            row = table.loc[sid]
            values = [fmt(row[k], spec) for _, k, spec in columns]
            values += [" / ".join(fmt(row[k], ".3f") for k in ("p_one_sided_hac", "p_one_sided_boot", "p_gate")),
                       f"{row.largest_category} ({row.largest_category_share:.2%})"]
            lines.append("| " + label + " | " + " | ".join(values) + " |")
        lines.append("")
    reading = result["mechanical_reading"]
    lines += ["## Mechanical reading of criteria 1–5 (not a verdict)", "", f"Mechanical overall: {reading['overall']}.", ""]
    for window, check in reading["windows"].items():
        m, p, e = (check["raw"][key] for key in ("method", "primary", "erc"))
        lines += [f"{window}:",
                  f"- c1: {check['c1_vol_lower_and_p_le_0p10']}; vol {m['AnnVol']:.2%} vs {p['AnnVol']:.2%}; "
                  f"p_gate {m['p_gate']:.3f} <= 0.100 (direction: {check['c1_vol_lower']}).",
                  f"- c2: {check['c2']}; Sharpe ex-BIL {m['Sharpe_exBIL']:.3f} >= primary {p['Sharpe_exBIL']:.3f} "
                  f"and > ERC {e['Sharpe_exBIL']:.3f}.",
                  f"- c3: {check['c3_maxdd_no_worse']}; MaxDD {m['MaxDD']:.2%} vs {p['MaxDD']:.2%}.",
                  f"- c5 VOID tripwires: method short_duration {m['short_duration_share_mean']:.2%}, eff N {m['eff_N_mean']:.2f}; "
                  f"primary short_duration {p['short_duration_share_mean']:.2%}, eff N {p['eff_N_mean']:.2f}. "
                  "Thresholds: share > 50.00% or eff N < 5.00.", ""]
    b = result["trial_count_breakdown"]
    lines += [f"c4: 260w same way on volatility direction and criterion 2: {reading['c4_260w_same_way']}.", "",
              "156w VOID tripwires: " + (", ".join(reading["void_tripwires"]) or "none") + ".",
              "Failing criteria: " + (", ".join(reading["failing_criteria"]) or "none") + ".",
              "260w informational tripwires: " + (", ".join(reading["sensitivity_260w_tripwires"]) or "none") + ".",
              reading["sensitivity_note"], "",
              f"DSR is non-decisive; trial_count {result['trial_count']}: {b['v1_carried']} carried from v1 incl. the invalidated run "
              f"+ {b['v2_configs']} v2 configs + {b['extra_previews']} extra previews. DSR uses monthly Sharpe = annual Sharpe / sqrt(12).",
              "Extra previews: " + (", ".join(result["extra_previews"]) or "none") + ".", "",
              "LW2011: 4999 paired circular bootstrap replicates; block size 4 months; seed 20260926. "
              "VAR(1) prewhitening, spectral radius capped at 0.97, Andrews automatic QS bandwidth, T/(T−4) correction. "
              "Common RMS return units are removed before the equal-weight moment bandwidth fits; final partial bootstrap blocks are truncated.",
              "Sharpe ex-BIL uses priced BIL monthly returns with TB3MS fallback; fallback shares are in summary.csv.", "",
              "Monthly LW MinVar is reference only. Quant decides.", ""]
    (out/"gate_report.md").write_text("\n".join(lines))
