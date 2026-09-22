"""Forecast Tangency + Minimum Euclidean Distance Portfolio.

Walk-forward: EF coefficients (r_MVP, σ_MVP, u) → VARX(1) forecast →
forecasted tangency point → invest in minimum-Euclidean-distance portfolio
on the *current* frontier (Alexander & Scherer, Engineering Proceedings 2023).

Research tooling only; not investment advice.
No same-month leakage: weights for month t+1 use data ≤ t only.

Lead citation:
  Alexander, Nolan, and William Scherer. 2023. "Forecasting Tangency
  Portfolios and Investing in the Minimum Euclidean Distance Portfolio
  to Maximize Out-of-Sample Sharpe Ratios." Engineering Proceedings
  39(1):34. doi:10.3390/engproc2023039034. arXiv:2604.03948.

Inference:
  Bailey, David H., and Marcos López de Prado. 2014. "The Deflated
  Sharpe Ratio." Journal of Portfolio Management 40(5):94–107.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import optimize, stats

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
    deflated_sharpe_approx,
    half_turnover,
    max_drawdown,
    newey_west_tstat,
    sharpe_rf0,
)

RESEARCH_DISCLAIMER = (
    "Research-only; not investment advice; no trading or broker routing."
)
CITATION = (
    "Alexander, Nolan, and William Scherer. 2023. "
    "'Forecasting Tangency Portfolios and Investing in the Minimum "
    "Euclidean Distance Portfolio to Maximize Out-of-Sample Sharpe "
    "Ratios.' Engineering Proceedings 39(1):34. "
    "doi:10.3390/engproc2023039034. arXiv:2604.03948."
)
CITATION_DSR = (
    "Bailey, David H., and Marcos López de Prado. 2014. "
    "'The Deflated Sharpe Ratio.' Journal of Portfolio Management "
    "40(5):94-107. doi:10.3905/jpm.2014.40.5.094."
)
CASH_FALLBACKS = ("BIL", "SGOV", "GBIL", "SHV")

_DEFAULT_EXCLUDE_CATEGORIES = (
    "Defined Outcome / Buffer / Structured",
    "Specialty / Other",
)


# ---------------------------------------------------------------------------
# Trial dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ForecastTangencyMedTrial:
    trial_id: str
    ef_lookback_months: int = 21
    forecast_lookback_months: int = 60
    mu_estimator: str = "sample"       # "sample" or "james_stein"
    cov_estimator: str = "ledoit_wolf"
    long_only: bool = True
    leverage_cap: float = 1.0
    cost_bps_one_way: float = 5.0
    cash_ticker: str = "BIL"
    min_names: int = 100
    apply_to: str = "name_level"       # "name_level" or "category_sleeves"
    include_thin: bool = False
    min_history_months: int = 24


def load_forecast_tangency_med_config(path: str | Path | None = None) -> dict:
    """Load config from YAML or return sensible defaults."""
    if path is None:
        candidates = [
            Path("config/forecast_tangency_med.yaml"),
            Path(__file__).resolve().parents[2] / "config" / "forecast_tangency_med.yaml",
        ]
        for c in candidates:
            if c.exists():
                path = c
                break
    if path is None:
        return {
            "forecast_tangency_med": {
                "ef_lookbacks": [21, 63, 126],
                "forecast_lookbacks": [60],
                "mu_estimator": ["sample", "james_stein"],
                "cov_estimator": ["ledoit_wolf"],
                "long_only": True,
                "leverage_cap": 1.0,
                "cost_bps_one_way": 5,
                "min_names": 100,
                "apply_to": ["name_level", "category_sleeves"],
                "include_thin": False,
                "min_history_months": 24,
                "cash_ticker": "BIL",
            }
        }
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_ft_med_trials(
    ef_lookbacks: list[int] | None = None,
    forecast_lookbacks: list[int] | None = None,
    mu_estimators: list[str] | None = None,
    apply_tos: list[str] | None = None,
    cost_bps_one_way: float = 5.0,
    cash_ticker: str = "BIL",
    min_names: int = 100,
    include_thin: bool = False,
    min_history_months: int = 24,
) -> list[ForecastTangencyMedTrial]:
    ef_lookbacks = ef_lookbacks or [21]
    forecast_lookbacks = forecast_lookbacks or [60]
    mu_estimators = mu_estimators or ["sample"]
    apply_tos = apply_tos or ["name_level"]
    trials = []
    for ef_lb in ef_lookbacks:
        for fc_lb in forecast_lookbacks:
            for mu_est in mu_estimators:
                for apply_to in apply_tos:
                    tid = f"ft_med_ef{ef_lb}_fc{fc_lb}_{mu_est}_{apply_to}"
                    trials.append(
                        ForecastTangencyMedTrial(
                            trial_id=tid,
                            ef_lookback_months=ef_lb,
                            forecast_lookback_months=fc_lb,
                            mu_estimator=mu_est,
                            cov_estimator="ledoit_wolf",
                            long_only=True,
                            leverage_cap=1.0,
                            cost_bps_one_way=cost_bps_one_way,
                            cash_ticker=cash_ticker,
                            min_names=min_names,
                            apply_to=apply_to,
                            include_thin=include_thin,
                            min_history_months=min_history_months,
                        )
                    )
    return trials


# ---------------------------------------------------------------------------
# Mean / covariance estimation
# ---------------------------------------------------------------------------

def _lw_cov(returns: pd.DataFrame) -> np.ndarray:
    """Ledoit-Wolf shrunk covariance (monthly returns × columns)."""
    from sklearn.covariance import LedoitWolf
    arr = returns.to_numpy(dtype=float)
    lw = LedoitWolf(assume_centered=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        lw.fit(arr)
    return lw.covariance_


def _sample_mean(returns: pd.DataFrame) -> np.ndarray:
    return returns.mean(axis=0).to_numpy(dtype=float)


def _james_stein_mean(returns: pd.DataFrame) -> np.ndarray:
    """James-Stein estimator shrinking toward the grand mean.

    DeMiguel et al. (2009) variant: μ_JS = μ_grand + (1-c)(μ_sample - μ_grand)
    where c = ((N-2)/T) / ||μ_sample - μ_grand||² (clipped to [0,1]).
    """
    mu = _sample_mean(returns)
    N, T = returns.shape[1], returns.shape[0]
    mu_grand = float(np.mean(mu))
    excess = mu - mu_grand
    norm_sq = float(np.dot(excess, excess))
    if norm_sq < 1e-16 or T <= N + 2:
        return mu
    c = max(0.0, min(1.0, (N - 2) / (T * norm_sq)))
    return mu_grand + (1.0 - c) * excess


def _estimate_mu(returns: pd.DataFrame, estimator: str) -> np.ndarray:
    if estimator == "james_stein":
        return _james_stein_mean(returns)
    return _sample_mean(returns)


# ---------------------------------------------------------------------------
# EF coefficients
# ---------------------------------------------------------------------------

def ef_coefficients(mu: np.ndarray, sigma_inv: np.ndarray) -> tuple[float, float, float]:
    """Compute EF scalars (r_MVP, sigma_MVP, u) from Σ⁻¹ and μ̂.

    Reparameterization of Merton (1972) used by Alexander & Scherer (2023):
      A = 1'Σ⁻¹1,  B = μ'Σ⁻¹1,  C = μ'Σ⁻¹μ
      r_MVP = B/A,  σ_MVP = 1/√A,  u = (AC−B²)/A

    The EF in (σ², r) space: σ²(r) = σ_MVP² + (r − r_MVP)²/u.

    Returns:
        r_MVP : float — expected return of minimum-variance portfolio
        sigma_MVP : float — annualized volatility of MVP (monthly σ_MVP × √12)
        u : float — curvature parameter > 0
    """
    ones = np.ones(len(mu))
    A = float(ones @ sigma_inv @ ones)
    B = float(mu @ sigma_inv @ ones)
    C = float(mu @ sigma_inv @ mu)
    if A <= 0:
        raise ValueError("singular covariance: A ≤ 0")
    r_MVP = B / A
    sigma_MVP = 1.0 / np.sqrt(A)
    u_num = A * C - B * B
    if u_num <= 0:
        raise ValueError(f"EF curvature u={u_num/A:.4g} ≤ 0 (rank-deficient or near-flat frontier)")
    u = u_num / A
    return float(r_MVP), float(sigma_MVP), float(u)


def ef_sigma(r: float, r_MVP: float, sigma_MVP: float, u: float) -> float:
    """Frontier volatility at target return r (monthly scale)."""
    return float(np.sqrt(sigma_MVP**2 + (r - r_MVP) ** 2 / u))


def forecasted_tangency(
    r_MVP_hat: float, sigma_MVP_hat: float, u_hat: float, rf: float = 0.0
) -> tuple[float, float]:
    """Compute forecasted tangency point from forecasted EF coefficients.

    Paper Eq. 6 with rf (default 0 for Sharpe_rf0 parity):
      r̂_TP = (r̂_MVP² + û·σ̂_MVP² − r̂_MVP·rf) / (r̂_MVP − rf)
      σ̂_TP = σ(r̂_TP)  using forecasted frontier shape.

    Returns (r_hat_TP, sigma_hat_TP) on the *forecasted* frontier.
    """
    denom = r_MVP_hat - rf
    if abs(denom) < 1e-12:
        raise ValueError("r̂_MVP ≈ rf; tangency undefined")
    r_hat_TP = (r_MVP_hat**2 + u_hat * sigma_MVP_hat**2 - r_MVP_hat * rf) / denom
    sigma_hat_TP = ef_sigma(r_hat_TP, r_MVP_hat, sigma_MVP_hat, u_hat)
    return float(r_hat_TP), float(sigma_hat_TP)


# ---------------------------------------------------------------------------
# VARX(1) forecasting of EF coefficients
# ---------------------------------------------------------------------------

def _varx_forecast(
    coef_history: pd.DataFrame,
    forecast_lookback: int,
    current_idx: int,
) -> np.ndarray | None:
    """Lag-1 VAR forecast of (r_MVP, sigma_MVP, u) using OLS.

    Uses min(forecast_lookback, current_idx) observations through index
    current_idx-1. Returns (r_MVP_hat, sigma_MVP_hat, u_hat) or None
    if insufficient history.

    Fits each equation independently (OLS on lagged value + intercept).
    """
    # Need at least 12 obs for any reliable forecast; fall back to no-change otherwise
    min_obs = 12
    end = current_idx  # exclusive: use indices [start, end)
    start = max(0, end - forecast_lookback)
    if (end - start) < min_obs + 1:
        return None
    history = coef_history.iloc[start:end]
    X_lag = history.iloc[:-1].to_numpy(dtype=float)   # t-1 values
    Y = history.iloc[1:].to_numpy(dtype=float)         # t values (target)
    # Add intercept column
    Xb = np.column_stack([np.ones(len(X_lag)), X_lag])
    try:
        # lstsq with rcond=None
        coeffs, _, _, _ = np.linalg.lstsq(Xb, Y, rcond=None)
        # Forecast next step using last row of history as X_{t}
        x_last = history.iloc[-1].to_numpy(dtype=float)
        xb_last = np.array([1.0, *x_last])
        forecast = xb_last @ coeffs   # shape (3,)
        return forecast.astype(float)
    except np.linalg.LinAlgError:
        return None


# ---------------------------------------------------------------------------
# Portfolio solvers (long-only)
# ---------------------------------------------------------------------------

def _lw_minvar(cov: np.ndarray, n: int) -> np.ndarray:
    """Global minimum-variance portfolio (long-only) via SLSQP."""
    w0 = np.ones(n) / n
    result = optimize.minimize(
        fun=lambda w: float(w @ cov @ w),
        x0=w0,
        method="SLSQP",
        bounds=optimize.Bounds(0.0, 1.0),
        constraints={"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    if result.success or result.fun < float(w0 @ cov @ w0):
        w = np.clip(result.x, 0.0, None)
        s = w.sum()
        return w / s if s > 1e-12 else w0
    return w0


def _erc(cov: np.ndarray, n: int) -> np.ndarray:
    """Equal-risk-contribution portfolio (long-only) via SLSQP.

    Objective: minimize Σ_i Σ_j (RC_i − RC_j)²
    where RC_i = w_i (Σw)_i / (w'Σw) = marginal risk contribution.
    """
    w0 = np.ones(n) / n

    def _obj(w: np.ndarray) -> float:
        port_var = float(w @ cov @ w)
        if port_var < 1e-16:
            return 0.0
        mrc = (cov @ w) / port_var       # marginal risk contributions
        rc = w * mrc                      # total risk contributions
        # sum of squared pairwise differences (equivalent to ||rc - mean||^2 * n)
        diff = rc[:, None] - rc[None, :]
        return float(0.5 * np.sum(diff ** 2))

    def _grad(w: np.ndarray) -> np.ndarray:
        port_var = float(w @ cov @ w)
        if port_var < 1e-16:
            return np.zeros(n)
        Sw = cov @ w
        mrc = Sw / port_var
        rc = w * mrc
        rc_mean = np.mean(rc)
        # d(obj)/dw_k via chain rule — approximate with finite differences for simplicity
        # (SLSQP can handle numerical gradients via 2-point FD internally)
        return np.zeros(n)   # let SLSQP estimate gradient numerically

    result = optimize.minimize(
        fun=_obj,
        x0=w0,
        method="SLSQP",
        bounds=optimize.Bounds(0.0, 1.0),
        constraints={"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    if result.success or result.fun < _obj(w0):
        w = np.clip(result.x, 0.0, None)
        s = w.sum()
        return w / s if s > 1e-12 else w0
    return w0


def _lw_mvo_tangency(mu: np.ndarray, cov: np.ndarray, n: int) -> np.ndarray:
    """Long-only Ledoit-Wolf MVO tangency portfolio (rf=0 Sharpe max)."""
    # Maximize w'μ / √(w'Σw) ≡ minimize -w'μ s.t. w'Σw ≤ 1, w≥0, sum≤1
    # Equivalent: maximize SR = w'μ / sqrt(w'Σw) via SLSQP
    w0 = np.ones(n) / n

    def _neg_sharpe(w: np.ndarray) -> float:
        port_var = float(w @ cov @ w)
        port_ret = float(w @ mu)
        if port_var < 1e-16 or port_ret < 0:
            return 0.0
        return -port_ret / np.sqrt(port_var)

    result = optimize.minimize(
        fun=_neg_sharpe,
        x0=w0,
        method="SLSQP",
        bounds=optimize.Bounds(0.0, 1.0),
        constraints={"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    if result.success:
        w = np.clip(result.x, 0.0, None)
        s = w.sum()
        return w / s if s > 1e-12 else w0
    return w0


def _mvo_at_target_return(
    mu: np.ndarray,
    cov: np.ndarray,
    r_star: float,
    n: int,
    leverage_cap: float = 1.0,
) -> np.ndarray:
    """MVO portfolio at target return r* (long-only, leverage_cap ≤ 1.0).

    min w'Σw  s.t.  w'μ = r*,  1'w ≤ leverage_cap,  w ≥ 0.
    If the target return is infeasible, relaxes to maximize r within bounds.
    """
    r_min = float(np.min(mu))
    r_max = float(np.max(mu))
    if r_star < r_min:
        r_star = r_min
    if r_star > r_max:
        r_star = r_max

    w0 = np.ones(n) / n

    constraints = [
        {"type": "eq", "fun": lambda w: float(w @ mu) - r_star},
        {"type": "ineq", "fun": lambda w: leverage_cap - np.sum(w)},
    ]
    result = optimize.minimize(
        fun=lambda w: float(w @ cov @ w),
        x0=w0,
        method="SLSQP",
        bounds=optimize.Bounds(0.0, 1.0),
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 2000},
    )
    if result.success:
        w = np.clip(result.x, 0.0, None)
        s = w.sum()
        if s > leverage_cap + 1e-8:
            w = w * leverage_cap / s
        return w
    # Fallback to MinVar
    return _lw_minvar(cov, n)


# ---------------------------------------------------------------------------
# MED solve
# ---------------------------------------------------------------------------

def _med_solve(
    r_hat_TP: float,
    sigma_hat_TP: float,
    r_MVP_cur: float,
    sigma_MVP_cur: float,
    u_cur: float,
    mu_cur: np.ndarray,
) -> tuple[float, float]:
    """Find r* on the *current* frontier minimizing Euclidean distance to (r̂_TP, σ̂_TP).

    Returns (r_star, distance).
    The search is bounded to [r_MVP_cur, max(μ_cur)] for feasible long-only.
    """
    r_lo = r_MVP_cur
    r_hi = max(float(np.max(mu_cur)), r_MVP_cur + 1e-6)
    # also extend slightly above max(mu) in case forecasted tangency is above any asset
    r_hi = max(r_hi, r_hat_TP)

    def _dist_sq(r: float) -> float:
        sigma_cur = ef_sigma(r, r_MVP_cur, sigma_MVP_cur, u_cur)
        return (r - r_hat_TP) ** 2 + (sigma_cur - sigma_hat_TP) ** 2

    result = optimize.minimize_scalar(
        _dist_sq,
        bounds=(r_lo, r_hi),
        method="bounded",
        options={"xatol": 1e-10},
    )
    r_star = float(np.clip(result.x, r_lo, r_hi))
    distance = float(np.sqrt(max(0.0, _dist_sq(r_star))))
    return r_star, distance


# ---------------------------------------------------------------------------
# Month-end helper
# ---------------------------------------------------------------------------

def _month_ends_in_index(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Return month-end dates that appear in idx (last obs per calendar month)."""
    periods = idx.to_period("M")
    last_of_month = pd.Series(idx, index=periods).groupby(level=0).last()
    return pd.DatetimeIndex(last_of_month.values)


def _monthly_returns_panel(
    monthly: pd.DataFrame,
    tickers: list[str],
    *,
    min_history_months: int,
    through: pd.Timestamp,
) -> pd.DataFrame:
    """Slice panel to tickers with >= min_history_months of non-NaN data through `through`."""
    sub = monthly.loc[:through, [t for t in tickers if t in monthly.columns]]
    n_obs = sub.notna().sum(axis=0)
    ok = n_obs[n_obs >= min_history_months].index.tolist()
    return sub[ok].dropna(how="all")


def _sleeve_returns_at(
    monthly: pd.DataFrame,
    universe_df: pd.DataFrame,
    *,
    exclude_cats: Iterable[str] = _DEFAULT_EXCLUDE_CATEGORIES,
    eligible_set: set[str] | None = None,
    thin_set: set[str] | None = None,
    include_thin: bool = False,
    min_sleeve_names: int = 2,
    min_history_months: int = 24,
    through: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Equal-weight category-sleeve returns through `through`."""
    uni = universe_df.copy()
    uni["Ticker"] = uni["Ticker"].astype(str).str.upper()
    if "Category" not in uni.columns:
        raise ValueError("universe CSV needs Category column for category-sleeve mode")
    cat_map = uni.set_index("Ticker")["Category"].astype(str)
    names = [c for c in monthly.columns if c in cat_map.index]
    if eligible_set:
        names = [c for c in names if c in eligible_set]
    if thin_set and not include_thin:
        names = [c for c in names if c not in thin_set]
    exclude = set(exclude_cats)
    groups: dict[str, list[str]] = {}
    sub = monthly.loc[:through]
    n_obs = sub.notna().sum(axis=0)
    for t in names:
        if n_obs.get(t, 0) < min_history_months:
            continue
        cat = str(cat_map.loc[t])
        if cat in exclude:
            continue
        groups.setdefault(cat, []).append(t)
    groups = {c: ts for c, ts in groups.items() if len(ts) >= min_sleeve_names}
    if not groups:
        raise ValueError("no category sleeves available after filters")
    sleeve = pd.DataFrame(
        {cat: sub[[t for t in ts if t in sub.columns]].mean(axis=1, skipna=True)
         for cat, ts in groups.items()},
        index=sub.index,
    )
    meta_rows = [
        {
            "category": cat,
            "n_names": len(ts),
            "tickers": ",".join(sorted(ts)),
            "thin_sleeve": (
                any(t in (thin_set or set()) for t in ts)
                if thin_set else False
            ),
        }
        for cat, ts in groups.items()
    ]
    return sleeve, pd.DataFrame(meta_rows)


# ---------------------------------------------------------------------------
# Core walk-forward loop
# ---------------------------------------------------------------------------

def run_forecast_tangency_med_trial(
    monthly: pd.DataFrame,
    trial: ForecastTangencyMedTrial,
    *,
    universe_csv: str | Path,
    coverage: pd.DataFrame | None = None,
    universe_config: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run one walk-forward FT-MED trial.

    Returns
    -------
    monthly_weights : pd.DataFrame
        One row per decision month. Columns include decision_date,
        eval_date (return horizon), trial_id, cash_pct, r_star,
        distance, w_<TICKER>... (weights sum ≤ 1; residual → cash).
    oos_returns : pd.DataFrame
        Columns: date (eval month), decision_date, trial_id,
        r_method, r_null_a (EW), r_null_b (LW MinVar), r_null_c (ERC),
        r_null_d (LW MVO), r_active_vs_a,
        coef_r_mvp, coef_sigma_mvp, coef_u,
        fc_r_mvp, fc_sigma_mvp, fc_u,
        rhat_tp, sigmahat_tp, r_star, distance, turnover.
    registry : pd.DataFrame
        One row with trial parameters and citation.
    """
    uni_cfg = universe_config or load_universe_config()
    uni_df = load_universe_csv(universe_csv)

    cash = trial.cash_ticker.upper()
    cash_fallbacks = [c for c in CASH_FALLBACKS if c != cash]
    all_tickers_eligible = set(eligible_tickers(uni_df, uni_cfg))
    thin_set = thin_history_set(uni_cfg)

    # Ensure cash is on the approved list (Appendix 3 deny already handled by eligible check)
    if cash not in all_tickers_eligible:
        for fb in cash_fallbacks:
            if fb in all_tickers_eligible:
                cash = fb
                break

    # Get monthly returns columns that are eligible
    monthly = monthly.copy()
    monthly.columns = [str(c).upper() for c in monthly.columns]
    monthly.index = pd.to_datetime(monthly.index)
    monthly = monthly.sort_index()

    me_dates = _month_ends_in_index(monthly.index)

    # Need at least ef_lookback + forecast_lookback + 2 for a first decision
    min_startup = trial.ef_lookback_months + max(12, trial.forecast_lookback_months // 4)

    coef_history: list[dict] = []
    weight_rows: list[dict] = []
    return_rows: list[dict] = []

    prev_w_method: pd.Series | None = None
    prev_w_null_a: pd.Series | None = None
    prev_w_null_b: pd.Series | None = None
    prev_w_null_c: pd.Series | None = None
    prev_w_null_d: pd.Series | None = None

    for i, d in enumerate(me_dates):
        if i + 1 >= len(me_dates):
            break
        eval_date = me_dates[i + 1]

        # ----------------------------------------------------------------
        # 1. Filter eligible names (data ≤ d only — no leakage)
        # ----------------------------------------------------------------
        if trial.apply_to == "category_sleeves":
            try:
                panel, _sleeve_meta = _sleeve_returns_at(
                    monthly,
                    uni_df,
                    eligible_set=all_tickers_eligible,
                    thin_set=thin_set,
                    include_thin=trial.include_thin,
                    min_history_months=trial.min_history_months,
                    through=d,
                )
            except ValueError:
                continue
            panel = panel.loc[:d]
        else:
            eligible_names = [
                t for t in monthly.columns
                if t in all_tickers_eligible
                and (trial.include_thin or t not in thin_set)
                and t != cash
            ]
            panel = _monthly_returns_panel(
                monthly,
                eligible_names,
                min_history_months=trial.min_history_months,
                through=d,
            )

        if panel.empty or panel.shape[1] < 2:
            continue

        # Check min_names gate
        if panel.shape[1] < trial.min_names and trial.apply_to == "name_level":
            # not enough names; still proceed for category sleeves (min is effectively per-sleeve)
            if trial.apply_to != "category_sleeves":
                continue

        # ----------------------------------------------------------------
        # 2. Estimate μ̂_t, Σ̂_t (data ≤ d)
        # ----------------------------------------------------------------
        window = panel.iloc[-trial.ef_lookback_months:].dropna(how="any", axis=0)
        if len(window) < max(6, panel.shape[1] + 1):
            # Insufficient observations; need more rows than columns for Σ
            window = panel.dropna(how="any", axis=0)
        if len(window) < 6 or window.shape[1] < 2:
            continue

        tickers_t = list(window.columns)
        N = len(tickers_t)

        try:
            mu_t = _estimate_mu(window, trial.mu_estimator)
            cov_t = _lw_cov(window)
            cov_t_reg = cov_t + 1e-8 * np.eye(N)
            sigma_inv_t = np.linalg.solve(cov_t_reg, np.eye(N))
        except (np.linalg.LinAlgError, ValueError):
            continue

        # ----------------------------------------------------------------
        # 3. EF coefficients at t
        # ----------------------------------------------------------------
        try:
            r_mvp_t, sigma_mvp_t, u_t = ef_coefficients(mu_t, sigma_inv_t)
        except ValueError:
            continue

        coef_history.append({"date": d, "r_mvp": r_mvp_t, "sigma_mvp": sigma_mvp_t, "u": u_t})

        if len(coef_history) < 2:
            continue

        coef_df = pd.DataFrame(coef_history).set_index("date")[["r_mvp", "sigma_mvp", "u"]]

        # ----------------------------------------------------------------
        # 4. VARX(1) forecast of EF coefficients
        # ----------------------------------------------------------------
        forecast = _varx_forecast(
            coef_df,
            trial.forecast_lookback_months,
            len(coef_df),
        )
        if forecast is None:
            # No-change fallback
            fc_r_mvp, fc_sigma_mvp, fc_u = r_mvp_t, sigma_mvp_t, u_t
        else:
            fc_r_mvp, fc_sigma_mvp, fc_u = float(forecast[0]), float(forecast[1]), float(forecast[2])
            # Validate forecasted coefs are sensible
            if not (np.isfinite(fc_r_mvp) and np.isfinite(fc_sigma_mvp) and np.isfinite(fc_u)):
                fc_r_mvp, fc_sigma_mvp, fc_u = r_mvp_t, sigma_mvp_t, u_t
            fc_sigma_mvp = max(fc_sigma_mvp, 1e-6)
            fc_u = max(fc_u, 1e-8)

        # ----------------------------------------------------------------
        # 5. Forecasted tangency point (rf=0)
        # ----------------------------------------------------------------
        try:
            r_hat_TP, sigma_hat_TP = forecasted_tangency(fc_r_mvp, fc_sigma_mvp, fc_u, rf=0.0)
        except ValueError:
            r_hat_TP = fc_r_mvp + fc_u * fc_sigma_mvp**2 / max(abs(fc_r_mvp), 1e-6)
            sigma_hat_TP = ef_sigma(r_hat_TP, fc_r_mvp, fc_sigma_mvp, fc_u)

        # ----------------------------------------------------------------
        # 6. MED solve on current frontier
        # ----------------------------------------------------------------
        try:
            r_star, distance = _med_solve(
                r_hat_TP, sigma_hat_TP,
                r_mvp_t, sigma_mvp_t, u_t,
                mu_t,
            )
        except Exception:
            r_star = r_mvp_t
            distance = float("nan")

        # ----------------------------------------------------------------
        # 7. MVO portfolio at r* (long-only; residual → cash)
        # ----------------------------------------------------------------
        try:
            w_risky = _mvo_at_target_return(mu_t, cov_t_reg, r_star, N, trial.leverage_cap)
        except Exception:
            w_risky = np.ones(N) / N

        risky_total = float(w_risky.sum())
        cash_weight = max(0.0, trial.leverage_cap - risky_total)

        w_method = pd.Series(dict(zip(tickers_t, w_risky)))
        w_method[cash] = w_method.get(cash, 0.0) + cash_weight

        # ----------------------------------------------------------------
        # 8. Null portfolios (all use data ≤ d; no leakage)
        # ----------------------------------------------------------------
        # (a) Equal-weight
        w_null_a = pd.Series(1.0 / N, index=tickers_t)

        # (b) LW MinVar
        try:
            w_b = _lw_minvar(cov_t_reg, N)
        except Exception:
            w_b = np.ones(N) / N
        w_null_b = pd.Series(dict(zip(tickers_t, w_b)))

        # (c) ERC
        try:
            w_c = _erc(cov_t_reg, N)
        except Exception:
            w_c = np.ones(N) / N
        w_null_c = pd.Series(dict(zip(tickers_t, w_c)))

        # (d) LW MVO tangency (rf=0, long-only)
        try:
            w_d = _lw_mvo_tangency(mu_t, cov_t_reg, N)
        except Exception:
            w_d = np.ones(N) / N
        w_null_d = pd.Series(dict(zip(tickers_t, w_d)))

        # ----------------------------------------------------------------
        # 9. Compute turnover costs (one-way, 5 bps default)
        # ----------------------------------------------------------------
        def _to(w_prev: pd.Series | None, w_new: pd.Series) -> float:
            return half_turnover(w_prev, w_new)

        to_method = _to(prev_w_method, w_method)
        cost_method = to_method * trial.cost_bps_one_way / 10000.0

        to_a = _to(prev_w_null_a, w_null_a)
        cost_a = to_a * trial.cost_bps_one_way / 10000.0

        to_b = _to(prev_w_null_b, w_null_b)
        cost_b = to_b * trial.cost_bps_one_way / 10000.0

        to_c = _to(prev_w_null_c, w_null_c)
        cost_c = to_c * trial.cost_bps_one_way / 10000.0

        to_d = _to(prev_w_null_d, w_null_d)
        cost_d = to_d * trial.cost_bps_one_way / 10000.0

        prev_w_method = w_method.copy()
        prev_w_null_a = w_null_a.copy()
        prev_w_null_b = w_null_b.copy()
        prev_w_null_c = w_null_c.copy()
        prev_w_null_d = w_null_d.copy()

        # ----------------------------------------------------------------
        # 10. Evaluate t+1 returns (eval_date)
        # ----------------------------------------------------------------
        if eval_date not in monthly.index:
            continue

        def _port_ret(w: pd.Series, eval_d: pd.Timestamp) -> float:
            r = 0.0
            tot_w = 0.0
            for t, wt in w.items():
                if abs(wt) < 1e-12:
                    continue
                if t not in monthly.columns:
                    continue
                rv = monthly.loc[eval_d, t]
                if pd.isna(rv):
                    continue
                r += wt * rv
                tot_w += wt
            return float(r)

        r_m = _port_ret(w_method, eval_date) - cost_method
        r_a = _port_ret(w_null_a, eval_date) - cost_a
        r_b = _port_ret(w_null_b, eval_date) - cost_b
        r_c = _port_ret(w_null_c, eval_date) - cost_c
        r_d = _port_ret(w_null_d, eval_date) - cost_d

        # ----------------------------------------------------------------
        # Record weight row
        # ----------------------------------------------------------------
        w_row: dict = {
            "date": d,
            "eval_date": eval_date,
            "trial_id": trial.trial_id,
            "r_star": r_star,
            "distance": distance,
            "turnover": to_method,
            "cash_pct": float(w_method.get(cash, 0.0)),
            "n_assets": N,
            "thin_flag": int(any(t in thin_set for t in tickers_t)),
        }
        for t_, wt_ in w_method.items():
            if wt_ > 1e-12:
                w_row[f"w_{t_}"] = float(wt_)
        weight_rows.append(w_row)

        return_rows.append({
            "date": eval_date,
            "decision_date": d,
            "trial_id": trial.trial_id,
            "r_method": r_m,
            "r_null_a": r_a,
            "r_null_b": r_b,
            "r_null_c": r_c,
            "r_null_d": r_d,
            "r_active_vs_a": r_m - r_a,
            "coef_r_mvp": r_mvp_t,
            "coef_sigma_mvp": sigma_mvp_t,
            "coef_u": u_t,
            "fc_r_mvp": fc_r_mvp,
            "fc_sigma_mvp": fc_sigma_mvp,
            "fc_u": fc_u,
            "rhat_tp": r_hat_TP,
            "sigmahat_tp": sigma_hat_TP,
            "r_star": r_star,
            "distance": distance,
            "turnover": to_method,
        })

    monthly_weights = pd.DataFrame(weight_rows)
    oos_returns = pd.DataFrame(return_rows)

    registry = _make_registry(trial)
    return monthly_weights, oos_returns, registry


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------

def _summarize(
    oos: pd.DataFrame,
    trial_id: str,
    trial_count: int,
    bootstrap_samples: int = 500,
    bootstrap_block_months: int = 3,
) -> pd.DataFrame:
    """Build summary stats row for one trial."""
    if oos.empty or "r_method" not in oos.columns:
        return pd.DataFrame()
    r_m = oos["r_method"].dropna()
    if len(r_m) < 12:
        return pd.DataFrame()

    # Annualized metrics
    ann_ret = annualized_return(r_m)
    ann_vol = annualized_vol(r_m)
    mdd = max_drawdown(r_m)
    sr = sharpe_rf0(r_m)
    dsr = deflated_sharpe_approx(sr / np.sqrt(MONTHS_PER_YEAR), len(r_m), trial_count)
    nw_vs_a = newey_west_tstat((oos["r_method"] - oos["r_null_a"]).dropna())
    nw_vs_b = newey_west_tstat((oos["r_method"] - oos["r_null_b"]).dropna())
    nw_vs_c = newey_west_tstat((oos["r_method"] - oos["r_null_c"]).dropna())
    nw_vs_d = newey_west_tstat((oos["r_method"] - oos["r_null_d"]).dropna())

    lo, hi = block_bootstrap_sharpe_ci(r_m, n_samples=bootstrap_samples, block_months=bootstrap_block_months)

    to_yr = float(oos["turnover"].dropna().mean() * MONTHS_PER_YEAR) if "turnover" in oos.columns else float("nan")
    mean_dist = float(oos["distance"].dropna().mean()) if "distance" in oos.columns else float("nan")
    cash_pct = float(oos["r_null_a"].shape[0])  # placeholder; actual in weight rows

    row = {
        "trial_id": trial_id,
        "n_months": int(len(r_m)),
        "start_date": str(r_m.index.min().date()) if not r_m.empty else "",
        "end_date": str(r_m.index.max().date()) if not r_m.empty else "",
        "AnnReturn": ann_ret,
        "AnnVol": ann_vol,
        "MaxDD": mdd,
        "Sharpe_rf0": sr,
        "DSR": dsr,
        "trial_count": trial_count,
        "NW_t_vs_null_a_EW": nw_vs_a,
        "NW_t_vs_null_b_MinVar": nw_vs_b,
        "NW_t_vs_null_c_ERC": nw_vs_c,
        "NW_t_vs_null_d_MVO": nw_vs_d,
        "bootstrap_Sharpe_lo95": lo,
        "bootstrap_Sharpe_hi95": hi,
        "turnover_per_year": to_yr,
        "mean_distance": mean_dist,
        "research_disclaimer": RESEARCH_DISCLAIMER,
    }
    # Null summaries
    for null_col, null_label in [
        ("r_null_a", "null_a_EW"),
        ("r_null_b", "null_b_MinVar"),
        ("r_null_c", "null_c_ERC"),
        ("r_null_d", "null_d_MVO"),
    ]:
        rn = oos[null_col].dropna()
        row[f"AnnReturn_{null_label}"] = annualized_return(rn)
        row[f"Sharpe_{null_label}"] = sharpe_rf0(rn)
    return pd.DataFrame([row])


def _make_registry(trial: ForecastTangencyMedTrial) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trial_id": trial.trial_id,
                "method": "forecast_tangency_med",
                "ef_lookback_months": trial.ef_lookback_months,
                "forecast_lookback_months": trial.forecast_lookback_months,
                "mu_estimator": trial.mu_estimator,
                "cov_estimator": trial.cov_estimator,
                "long_only": trial.long_only,
                "leverage_cap": trial.leverage_cap,
                "cost_bps_one_way": trial.cost_bps_one_way,
                "cash_ticker": trial.cash_ticker,
                "min_names": trial.min_names,
                "apply_to": trial.apply_to,
                "include_thin": trial.include_thin,
                "min_history_months": trial.min_history_months,
                "trial_count": 1,
                "citation": CITATION,
                "citation_dsr": CITATION_DSR,
                "research_disclaimer": RESEARCH_DISCLAIMER,
            }
        ]
    )


# ---------------------------------------------------------------------------
# Grid runner
# ---------------------------------------------------------------------------

def run_forecast_tangency_med_grid(
    monthly: pd.DataFrame,
    trials: list[ForecastTangencyMedTrial],
    *,
    universe_csv: str | Path,
    coverage: pd.DataFrame | None = None,
    universe_config: dict | None = None,
    bootstrap_samples: int = 500,
    bootstrap_block_months: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run a grid of FT-MED trials.

    Returns (summary, monthly_weights, oos_returns, registry).
    """
    all_weights: list[pd.DataFrame] = []
    all_returns: list[pd.DataFrame] = []
    all_registry: list[pd.DataFrame] = []

    for trial_num, trial in enumerate(trials, start=1):
        try:
            w, r, reg = run_forecast_tangency_med_trial(
                monthly,
                trial,
                universe_csv=universe_csv,
                coverage=coverage,
                universe_config=universe_config,
            )
        except Exception as exc:
            import sys
            print(f"warning: trial {trial.trial_id} failed: {exc}", file=sys.stderr)
            continue

        reg = reg.copy()
        reg["trial_count"] = trial_num
        reg["trial_num"] = trial_num

        all_weights.append(w)
        all_returns.append(r)
        all_registry.append(reg)

    if not all_returns:
        empty = pd.DataFrame()
        return empty, empty, empty, empty

    monthly_weights = pd.concat(all_weights, ignore_index=True)
    oos_returns = pd.concat(all_returns, ignore_index=True)
    registry = pd.concat(all_registry, ignore_index=True)
    registry["trial_count"] = len(trials)
    for row in registry.itertuples():
        registry.loc[registry.index[row.Index], "trial_count"] = len(trials)

    trial_count_total = len(trials)
    summary_rows: list[pd.DataFrame] = []
    for trial, r_sub in zip(trials, all_returns):
        s = _summarize(
            r_sub,
            trial.trial_id,
            trial_count_total,
            bootstrap_samples,
            bootstrap_block_months,
        )
        summary_rows.append(s)

    summary = pd.concat(summary_rows, ignore_index=True)
    return summary, monthly_weights, oos_returns, registry
