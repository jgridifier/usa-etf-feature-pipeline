"""Experimental spectral/eigenrisk mapping; not a verbatim ADIA solver.

Snapshot universe/coverage filters introduce survivorship bias. All fitted quantities
and dynamic history gates use only the decision window. Missing held returns fail
explicitly, rather than silently dropping assets or renormalizing ex post.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .portfolio import ledoit_wolf_cov
from .vol_target import annualized_vol, sharpe_rf0, deflated_sharpe_approx


@dataclass(frozen=True)
class SpectralTrial:
    lookback: int = 60
    gamma: float = 1.0
    mp_rule: str = "unit"
    mode: str = "name"
    include_thin: bool = False
    min_names: int = 100
    adv_min: float = 0.0
    exclude_categories: tuple[str, ...] = (
        "Defined Outcome / Buffer / Structured", "Specialty / Other",
    )
    cost_bps: float = 5.0


def read_returns(path: str | Path) -> pd.DataFrame:
    panel = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    # Source panel dates are actual trading dates; exclude a partial final month.
    last = panel.index[-1]
    if last < last + pd.offsets.BMonthEnd(0):
        panel = panel.iloc[:-1]
    return panel


def spectral_weights(window: pd.DataFrame, gamma: float = 1.0) -> tuple[np.ndarray, dict]:
    """Equal pre-projection signal-PC risk, then penalize noise after projection.

    Eigenvectors have deterministic signs (positive sum, largest loading tie-break).
    Correlation-space holdings are converted to capital weights using asset vols.
    Long-only projection breaks exact PC parity; realized contributions are reported.
    The quadratic noise penalty acts on projected exposures (penalizing the original
    signal-only vector would be identically zero).
    """
    vol = window.std().to_numpy()
    corr = window.corr().to_numpy()
    values, vectors = np.linalg.eigh(corr)
    values = np.maximum(values, 0)
    signs = np.sign(vectors.sum(axis=0))
    for k in np.flatnonzero(np.abs(vectors.sum(axis=0)) < 1e-12):
        signs[k] = np.sign(vectors[np.argmax(np.abs(vectors[:, k])), k])
    vectors *= np.where(signs == 0, 1, signs)
    edge = (1 + np.sqrt(window.shape[1] / len(window))) ** 2
    signal = values > edge
    signal[-1] = True
    target = vectors[:, signal] @ (1 / np.sqrt(values[signal]))
    noise = vectors[:, ~signal]
    x = np.maximum(target, 0)
    # Projected gradient solves 1/2||x-target||² + gamma/2||U_noise' x||².
    for _ in range(300):
        nxt = np.maximum(x - (x - target + gamma * (noise @ (noise.T @ x))) / (1 + gamma), 0)
        if np.max(np.abs(nxt - x)) < 1e-11:
            break
        x = nxt
    w = nxt / vol
    w /= w.sum()
    exposure = vectors.T @ (vol * w)
    risk = values * exposure ** 2
    return w, {
        "n_signal_modes": int(signal.sum()), "pct_var_signal": float(values[signal].sum() / values.sum()),
        "noise_penalty": float(gamma * np.sum(exposure[~signal] ** 2)),
        "signal_risk_fraction": float(risk[signal].sum() / risk.sum()),
        "eigen_risk_contributions": json.dumps((risk / risk.sum()).tolist()), "mp_upper_edge": edge,
    }


def null_weights(window: pd.DataFrame) -> dict[str, np.ndarray]:
    cov = ledoit_wolf_cov(window, force_shrinkage=True).to_numpy()
    cov = cov / np.mean(np.diag(cov))
    n = len(cov)
    # Convex risk-budget objective; normalizing its solution yields asset ERC.
    result = minimize(lambda x: .5 * x @ cov @ x - np.log(x).sum(),
                      np.ones(n), jac=lambda x: cov @ x - 1 / x,
                      bounds=[(1e-10, None)] * n, method="L-BFGS-B",
                      options={"maxiter": 2000, "ftol": 1e-13, "gtol": 1e-8})
    if not result.success:
        raise ValueError(f"ERC solver failed: {result.message}")
    erc = result.x / result.x.sum()
    result = minimize(lambda x: .5 * x @ cov @ x, np.full(n, 1 / n),
                      jac=lambda x: cov @ x, bounds=[(0, 1)] * n,
                      constraints={"type": "eq", "fun": lambda x: x.sum() - 1,
                                   "jac": lambda x: np.ones(n)}, method="SLSQP",
                      options={"maxiter": 1000, "ftol": 1e-12})
    if not result.success:
        raise ValueError(f"MinVar solver failed: {result.message}")
    return {"erc": erc, "minvar_lw": result.x / result.x.sum(), "equal_weight": np.full(n, 1 / n)}


def run_spectral_trial(returns: pd.DataFrame, universe: pd.DataFrame,
                       coverage: pd.DataFrame | None = None,
                       trial: SpectralTrial = SpectralTrial()) -> dict[str, pd.DataFrame]:
    if trial.mode not in {"name", "sleeve"} or trial.mp_rule != "unit":
        raise ValueError("mode must be name/sleeve; supported mp_rule is unit")
    if trial.lookback < 3 or trial.gamma < 0 or trial.cost_bps < 0 or trial.min_names < 1:
        raise ValueError("invalid lookback, gamma, cost or minimum names")
    panel = returns.sort_index().copy()
    months = panel.index.to_period("M")
    if months.has_duplicates or (np.diff(months.asi8) != 1).any():
        raise ValueError("returns must contain exactly one row per consecutive calendar month")
    if np.isinf(panel.to_numpy()).any() or (panel < -1).any().any():
        raise ValueError("invalid simple returns")
    uni = universe.set_index("Ticker")
    names = panel.columns.intersection(uni.index).tolist()
    if trial.mode == "name":
        names = [t for t in names if uni.loc[t, "Category"] not in trial.exclude_categories]
    thin = pd.Series(False, index=names)
    if coverage is not None:
        cov = coverage.set_index("ticker").reindex(names)
        thin = cov["thin_lt5y"].astype(str).str.lower().ne("false")
        if not trial.include_thin:
            names = [t for t in names if not thin[t]]
        if trial.adv_min:
            names = [t for t in names if cov.loc[t, "adv_proxy"] >= trial.adv_min]
    elif trial.adv_min:
        raise ValueError("ADV filtering requires coverage")
    minimum = trial.min_names if trial.mode == "name" else 1
    if len(names) < minimum:
        raise ValueError(f"eligible N={len(names)} below required N>={minimum}")
    weights, rows, diagnostics = [], [], []
    previous: dict[str, pd.Series] = {}
    started = False
    for i in range(trial.lookback - 1, len(panel) - 1):
        decision, evaluation = panel.index[i:i + 2]
        window = panel.iloc[i - trial.lookback + 1:i + 1][names]
        live = window.columns[window.notna().all() & (window.std() > 1e-10)].tolist()
        if not trial.include_thin:
            live = [t for t in live if panel.iloc[:i + 1][t].count() >= 60]
        if len(live) < minimum:
            if started:
                raise ValueError(f"eligible N={len(live)} below required N>={minimum} at {decision}")
            continue  # inception warm-up, determined only by past history
        started = True
        window = window[live]
        groups = {t: [t] for t in live}
        if trial.mode == "sleeve":
            groups = {}
            for t in live:
                groups.setdefault(str(uni.loc[t, "Category"]), []).append(t)
            window = pd.DataFrame({c: window[ts].mean(axis=1) for c, ts in groups.items()})
        sw, diag = spectral_weights(window, trial.gamma)
        allocations = {"spectral_risk_parity": sw, **null_weights(window)}
        meta = {"decision_date": decision, "feature_end": decision,
                "date": evaluation, "label_start": decision + pd.Timedelta(days=1),
                "n_names": len(live), "n_sleeves": len(groups),
                "include_thin": trial.include_thin, "n_thin": int(thin.reindex(live).sum())}
        diagnostics.append({**meta, **diag})
        observed = panel.loc[evaluation, live]
        if observed.isna().any():
            raise ValueError(f"missing OOS return at {evaluation}; explicit data repair required")
        for strategy, allocation in allocations.items():
            # Expand sleeves to actual assets for turnover, including member changes.
            w = pd.Series({t: allocation[k] / len(ts)
                           for k, ts in enumerate(groups.values()) for t in ts})
            turnover = .5 * w.subtract(previous.get(strategy, pd.Series(dtype=float)), fill_value=0).abs().sum()
            gross = float(w @ observed.reindex(w.index))
            cost = turnover * trial.cost_bps / 10000
            rows.append({**meta, "strategy_id": strategy, "gross_return": gross,
                         "turnover": turnover, "cost_return": cost, "return": gross - cost})
            weights.extend({**meta, "strategy_id": strategy, "ticker": t,
                            "weight": v, "thin_lt5y": bool(thin[t])} for t, v in w.items())
            previous[strategy] = w
    if not rows:
        raise ValueError(f"no eligible OOS windows: require N>={minimum}, lookback={trial.lookback}")
    oos = pd.DataFrame(rows)
    registry = pd.DataFrame([{**asdict(trial), "strategy_id": s, "trial_id": s,
                             "dsr_method": "normal approximation; monthly Sharpe"} for s in allocations])
    summary = summarize(oos, len(registry))
    return {"oos_returns": oos, "weights": pd.DataFrame(weights), "summary": summary,
            "eigen_diagnostics": pd.DataFrame(diagnostics), "trial_registry": registry,
            "null_comparison": summary.copy()}


def summarize(oos: pd.DataFrame, n_trials: int) -> pd.DataFrame:
    rows = []
    for sid, sub in oos.groupby("strategy_id"):
        r = sub["return"]
        wealth = np.r_[1., (1 + r).cumprod().to_numpy()]
        sr = sharpe_rf0(r)
        rows.append({"strategy_id": sid, "Sharpe_rf0": sr, "AnnVol": annualized_vol(r),
                     "MaxDD": float(np.min(wealth / np.maximum.accumulate(wealth) - 1)),
                     "DSR": deflated_sharpe_approx(sr / np.sqrt(12), len(r), n_trials),
                     "n_trials": n_trials, "n_months": len(r),
                     "turnover_per_year": sub.turnover.mean() * 12,
                     "include_thin": bool(sub.include_thin.iloc[0])})
    return pd.DataFrame(rows)


def write_artifacts(result: dict[str, pd.DataFrame], out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in result.items():
        frame.to_csv(out / f"{name}.csv", index=False)


def run_spectral_grid(returns: pd.DataFrame, universe: pd.DataFrame,
                      coverage: pd.DataFrame | None, trials: list[SpectralTrial]) -> dict[str, pd.DataFrame]:
    """Register every executed configuration and null; compare on shared OOS dates."""
    if not trials or len({str(asdict(t)) for t in trials}) != len(trials):
        raise ValueError("provide nonempty, unique trials")
    runs = []
    for i, trial in enumerate(trials):
        result = run_spectral_trial(returns, universe, coverage, trial)
        for frame in result.values():
            frame["configuration_id"] = i
            if "strategy_id" in frame:
                frame["strategy_id"] = frame["strategy_id"] + f"__{i}"
        result["trial_registry"]["trial_id"] = result["trial_registry"]["strategy_id"]
        runs.append(result)
    output = {key: pd.concat([r[key] for r in runs], ignore_index=True) for key in runs[0]}
    oos = output["oos_returns"]
    calendars = [set(g.date) for _, g in oos.groupby("strategy_id")]
    common = set.intersection(*calendars)
    if not common:
        raise ValueError("grid has no shared OOS calendar")
    for key in ["oos_returns", "weights", "eigen_diagnostics"]:
        output[key] = output[key][output[key].date.isin(common)].reset_index(drop=True)
    output["summary"] = summarize(output["oos_returns"], len(output["trial_registry"]))
    output["null_comparison"] = output["summary"].copy()
    return output
