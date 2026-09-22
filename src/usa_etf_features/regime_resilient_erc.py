"""Regime-Resilient ERC Portfolio Construction (LOIM Regime Parity).

Walk-forward ERC construction using stress / corr-breakdown overlays (Path A)
and/or LOIM regime-parity risk inputs (Path B) that change how ERC weights are
built.  This is CONSTRUCTION resilience — not dual-regime asset selection.

Construction paths (not selection — every month still emits an ERC family):
  Path A — Stress / corr-breakdown overlays (Diversification-Under-Stress):
      Diagnostics ≤ t: stress-window Σ̂_stress, avg pairwise |corr|, sync score.
      Σ̂_resilient,t = (1−λ) Σ̂_uncond,t + λ Σ̂_stress,t   (registered λ)
      w*_t = ERC(Σ̂_resilient,t)   # long-only; residual → BIL

  Path B — LOIM regime-parity construction (NOT current-regime selection):
      Historical regime pools m=1…M built from data ≤ t (NBER lag or rolling-vol
      split); each pool provides a local Σ̂_m,t and a local ERC solution:
          w*_m,t = ERC(Σ̂_m,t)
          π̂_m,t = historical frequency / Markov steady-state ≤ t
          w*_t   = Σ_m π̂_m,t · w*_m,t   ← π-weighted blend of local ERCs
      FORBIDDEN: classify current regime m̂_t → hold only w*_m̂_t (archived #2).

  Both paths can be registered as separate trials and swept.

Lead citation:
  Ielpo, Florian, Selbi Muhammetgulyyeva, and Julien Royer. 2026.
  "Building a Regime-Resilient ERC Portfolio." Journal of Portfolio
  Management 52(9):189–213. doi:10.3905/jpm.2026.030.
  https://www.pm-research.com/content/iijpormgmt/52/9/189

Practitioner precursor:
  Ielpo, Florian, Julien Royer, and Selbi Muhammetgulyyeva. 2023.
  "Building a regime-resistant, long-run allocation in multi asset."
  LOIM MARS / Investment Viewpoints, 7 December 2023.
  https://am.lombardodier.com/contents/news/investment-viewpoints/2023/december/1148-MAC-mars-long-run.html

Classical ERC:
  Maillard, Sébastien, Thierry Roncalli, and Jérôme Teiletche. 2010.
  "The Properties of Equally Weighted Risk Contribution Portfolios."
  Journal of Portfolio Management 36(4):60–70.

DSR / inference:
  Bailey, David H., and Marcos López de Prado. 2014. "The Deflated
  Sharpe Ratio." Journal of Portfolio Management 40(5):94–107.
  doi:10.3905/jpm.2014.40.5.094.

Primary null: unconditional ERC (same names / same category sleeves;
single Σ̂; no stress/corr overlay; no regime-parity blend).
Additional nulls: Equal-weight (null_b), LW MinVar (null_c).
Optional null: Book-2 vol-target (null_d, if supplied).

Hard rules:
  - Walk-forward monthly; weights for t+1 use data ≤ t only (no same-month leakage).
  - N ≥ 100 eligible names on name-level run and/or category sleeves.
  - Thin-history flags; fallback to unconditional ERC when pool is thin.
  - 5 bps one-way turnover costs on OOS curve.
  - DSR + trial_count mandatory on every OOS Sharpe claim.
  - Registry enabled:false until Quant gate PASS.
  - Long-only + BIL cash residual (Appendix 3 deny honored).
  - External regime labels (NBER): documented publication lag; used only as
    construction inputs to pool data for local Σ̂_m — not as a current-regime
    selector.

Research tooling only; not investment advice.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import optimize

from .universe import (
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
    "Research-only; not investment advice; no trading or broker routing. "
    "Construction overlays only — not dual-regime asset selection (archived #2). "
    "Registry enabled:false until Quant gate PASS."
)

CITATION_LEAD = (
    "Ielpo, Florian, Selbi Muhammetgulyyeva, and Julien Royer. 2026. "
    "'Building a Regime-Resilient ERC Portfolio.' "
    "Journal of Portfolio Management 52(9):189-213. "
    "doi:10.3905/jpm.2026.030."
)

CITATION_PRECURSOR = (
    "Ielpo, Florian, Julien Royer, and Selbi Muhammetgulyyeva. 2023. "
    "'Building a regime-resistant, long-run allocation in multi asset.' "
    "LOIM MARS / Investment Viewpoints, 7 December 2023. "
    "https://am.lombardodier.com/contents/news/investment-viewpoints/"
    "2023/december/1148-MAC-mars-long-run.html"
)

CITATION_ERC = (
    "Maillard, Sebastien, Thierry Roncalli, and Jerome Teiletche. 2010. "
    "'The Properties of Equally Weighted Risk Contribution Portfolios.' "
    "Journal of Portfolio Management 36(4):60-70."
)

CITATION_DSR = (
    "Bailey, David H., and Marcos Lopez de Prado. 2014. "
    "'The Deflated Sharpe Ratio.' Journal of Portfolio Management "
    "40(5):94-107. doi:10.3905/jpm.2014.40.5.094."
)

CASH_FALLBACKS = ("BIL", "SGOV", "GBIL", "SHV")

_DEFAULT_EXCLUDE_CATEGORIES = (
    "Defined Outcome / Buffer / Structured",
    "Specialty / Other",
)

# ---------------------------------------------------------------------------
# NBER Business Cycle dates with publication-lag documentation
# ---------------------------------------------------------------------------
# Source: NBER Business Cycle Dating Committee (BCDC).
# Publication-lag rule: a month is treated as "recession" at time t only if
# the NBER had announced the relevant trough date before t (conservative lag).
# Pairs: (peak_ym, trough_ym, trough_announce_date) — inclusive on both ends.
# Peak months are included in the recession regime.
# We require the *trough* announcement (when the full episode is known) before
# using a month as "recession" in any pool.
_NBER_RECESSION_EPISODES: list[tuple[str, str, str]] = [
    # (peak_month, trough_month, nber_trough_announcement_date)
    # All dates in YYYY-MM format.
    ("1990-07", "1991-03", "1992-12-22"),  # announced Dec 1992 (NBER BCDC)
    ("2001-03", "2001-11", "2003-07-17"),  # announced Jul 2003 (NBER BCDC)
    ("2007-12", "2009-06", "2010-09-20"),  # announced Sep 2010 (NBER BCDC)
    ("2020-02", "2020-04", "2021-07-19"),  # announced Jul 2021 (NBER BCDC)
]


def _nber_recession_months(as_of: pd.Timestamp) -> frozenset[pd.Period]:
    """Return set of month periods classified as NBER recession as of `as_of`.

    Only includes recession months where the NBER BCDC had announced the
    trough (end of episode) before `as_of`, enforcing publication lag.
    External labels used as construction pool inputs only — not as a
    current-regime selector.
    """
    recession: set[pd.Period] = set()
    for peak_ym, trough_ym, announce_str in _NBER_RECESSION_EPISODES:
        announce_dt = pd.Timestamp(announce_str)
        if announce_dt >= as_of:
            continue
        peak_p = pd.Period(peak_ym, freq="M")
        trough_p = pd.Period(trough_ym, freq="M")
        p = peak_p
        while p <= trough_p:
            recession.add(p)
            p += 1
    return frozenset(recession)


# ---------------------------------------------------------------------------
# Trial dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegimeResilientERCTrial:
    """Configuration for one walk-forward regime-resilient ERC trial.

    construction:
        "stress_corr_overlay"  — Path A: blend unconditional + stress Σ̂
        "loim_regime_parity"   — Path B: π-weighted blend of local ERC solutions

    Both paths change ERC *inputs* / blends.  Neither selects assets based on
    the current-regime classification (archived dual-regime pattern).
    """
    trial_id: str

    # Which construction path
    construction: str = "stress_corr_overlay"   # "stress_corr_overlay" | "loim_regime_parity"

    # Path A: stress / corr-breakdown overlay
    stress_window_months: int = 12     # length of high-vol/left-tail stress window
    mix_lambda: float = 0.25           # λ weight on Σ̂_stress in blend (0 = unconditional ERC)
    corr_breakdown_gate: bool = False  # if True: additional soft cash residual on high avg|corr|
    corr_breakdown_threshold: float = 0.60  # avg pairwise |corr| above which gate activates

    # Path B: LOIM regime-parity
    regime_pool_rule: str = "rolling_vol_split"  # "rolling_vol_split" | "nber_lag"
    n_regimes: int = 2
    pi_rule: str = "historical_freq"             # "historical_freq" | "markov_steady"
    min_obs_per_pool: int = 24

    # Shared
    cov_estimator: str = "ledoit_wolf"           # "ledoit_wolf" | "sample"
    long_only: bool = True
    cost_bps_one_way: float = 5.0
    cash_ticker: str = "BIL"
    min_names: int = 100
    apply_to: str = "name_level"                 # "name_level" | "category_sleeves"
    include_thin: bool = False
    min_history_months: int = 36

    def trial_count_contribution(self) -> int:
        return 1


def load_regime_resilient_erc_config(path: str | Path | None = None) -> dict:
    """Load YAML config or return defaults."""
    if path is None:
        candidates = [
            Path("config/regime_resilient_erc.yaml"),
            Path(__file__).resolve().parents[2] / "config" / "regime_resilient_erc.yaml",
        ]
        for c in candidates:
            if c.exists():
                path = c
                break
    if path is None:
        return {
            "regime_resilient_erc": {
                "construction": ["stress_corr_overlay", "loim_regime_parity"],
                "stress_window_months": [12, 24],
                "mix_lambda": [0.25, 0.5],
                "corr_breakdown_gate": [False],
                "regime_pool_rule": ["rolling_vol_split", "nber_lag"],
                "n_regimes": [2],
                "pi_rule": ["historical_freq"],
                "cov_estimator": ["ledoit_wolf"],
                "min_obs_per_pool": [24, 36],
                "cost_bps_one_way": 5,
                "min_names": 100,
                "apply_to": ["name_level", "category_sleeves"],
                "include_thin": False,
                "min_history_months": 36,
                "cash_ticker": "BIL",
                "enabled": False,
            }
        }
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_rr_erc_trials(
    constructions: list[str] | None = None,
    stress_window_months: list[int] | None = None,
    mix_lambdas: list[float] | None = None,
    corr_breakdown_gates: list[bool] | None = None,
    regime_pool_rules: list[str] | None = None,
    pi_rules: list[str] | None = None,
    cov_estimators: list[str] | None = None,
    min_obs_per_pools: list[int] | None = None,
    apply_tos: list[str] | None = None,
    cost_bps_one_way: float = 5.0,
    cash_ticker: str = "BIL",
    min_names: int = 100,
    include_thin: bool = False,
    min_history_months: int = 36,
) -> list[RegimeResilientERCTrial]:
    """Build a grid of trials for the regime-resilient ERC sweep."""
    constructions = constructions or ["stress_corr_overlay"]
    stress_window_months = stress_window_months or [12]
    mix_lambdas = mix_lambdas or [0.25]
    corr_breakdown_gates = corr_breakdown_gates or [False]
    regime_pool_rules = regime_pool_rules or ["rolling_vol_split"]
    pi_rules = pi_rules or ["historical_freq"]
    cov_estimators = cov_estimators or ["ledoit_wolf"]
    min_obs_per_pools = min_obs_per_pools or [24]
    apply_tos = apply_tos or ["name_level"]

    trials: list[RegimeResilientERCTrial] = []
    seen: set[str] = set()

    for construction in constructions:
        for apply_to in apply_tos:
            for cov_est in cov_estimators:
                if construction == "stress_corr_overlay":
                    for sw_months in stress_window_months:
                        for lam in mix_lambdas:
                            for corr_gate in corr_breakdown_gates:
                                gate_str = "corrgate" if corr_gate else "nocorrgate"
                                tid = (
                                    f"rr_erc_stress_sw{sw_months}_lam{int(lam*100)}"
                                    f"_{gate_str}_{cov_est}_{apply_to}"
                                )
                                if tid in seen:
                                    continue
                                seen.add(tid)
                                trials.append(RegimeResilientERCTrial(
                                    trial_id=tid,
                                    construction="stress_corr_overlay",
                                    stress_window_months=sw_months,
                                    mix_lambda=lam,
                                    corr_breakdown_gate=corr_gate,
                                    cov_estimator=cov_est,
                                    cost_bps_one_way=cost_bps_one_way,
                                    cash_ticker=cash_ticker,
                                    min_names=min_names,
                                    apply_to=apply_to,
                                    include_thin=include_thin,
                                    min_history_months=min_history_months,
                                ))
                elif construction == "loim_regime_parity":
                    for pool_rule in regime_pool_rules:
                        for pi_rule in pi_rules:
                            for min_obs in min_obs_per_pools:
                                tid = (
                                    f"rr_erc_loim_{pool_rule}_{pi_rule}"
                                    f"_minobs{min_obs}_{cov_est}_{apply_to}"
                                )
                                if tid in seen:
                                    continue
                                seen.add(tid)
                                trials.append(RegimeResilientERCTrial(
                                    trial_id=tid,
                                    construction="loim_regime_parity",
                                    regime_pool_rule=pool_rule,
                                    n_regimes=2,
                                    pi_rule=pi_rule,
                                    min_obs_per_pool=min_obs,
                                    cov_estimator=cov_est,
                                    cost_bps_one_way=cost_bps_one_way,
                                    cash_ticker=cash_ticker,
                                    min_names=min_names,
                                    apply_to=apply_to,
                                    include_thin=include_thin,
                                    min_history_months=min_history_months,
                                ))
    return trials


# ---------------------------------------------------------------------------
# Covariance estimators
# ---------------------------------------------------------------------------

def _lw_cov(returns: np.ndarray) -> np.ndarray:
    """Ledoit-Wolf shrunk covariance (T × N array)."""
    from sklearn.covariance import LedoitWolf
    lw = LedoitWolf(assume_centered=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        lw.fit(returns)
    return lw.covariance_


def _sample_cov(returns: np.ndarray) -> np.ndarray:
    return np.cov(returns.T, ddof=1)


def _estimate_cov(returns: np.ndarray, estimator: str = "ledoit_wolf") -> np.ndarray:
    n = returns.shape[1]
    if n == 1:
        return np.array([[float(np.var(returns[:, 0], ddof=1))]])
    if estimator == "ledoit_wolf":
        return _lw_cov(returns)
    return _sample_cov(returns)


# ---------------------------------------------------------------------------
# ERC solver (Maillard-Roncalli-Teïletche log-barrier)
# ---------------------------------------------------------------------------

def _erc(cov: np.ndarray, n: int) -> np.ndarray:
    """Equal-risk-contribution portfolio (long-only) via log-barrier.

    Maillard-Roncalli-Teïletche (2010): ERC minimizes
        1/2 w'Σw − (1/N) Σ_i log(w_i)  s.t. w > 0
    then renormalize.  L-BFGS-B with analytical gradient.
    """
    w0 = np.ones(n) / n
    d = np.sqrt(np.diag(cov)) + 1e-8
    scale = d / np.mean(d)

    def _obj(w: np.ndarray) -> float:
        if np.any(w <= 0):
            return 1e20
        return 0.5 * float(w @ cov @ w) - float(np.sum(np.log(w))) / n

    def _grad(w: np.ndarray) -> np.ndarray:
        return (cov @ w) - 1.0 / (n * w)

    result = optimize.minimize(
        fun=_obj,
        jac=_grad,
        x0=w0,
        method="L-BFGS-B",
        bounds=[(1e-10, None)] * n,
        options={"ftol": 1e-14, "gtol": 1e-8, "maxiter": 2000},
    )
    w = np.clip(result.x, 0.0, None)
    s = w.sum()
    return w / s if s > 1e-12 else w0


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


# ---------------------------------------------------------------------------
# Stress / corr-breakdown diagnostics  (Path A helpers)
# ---------------------------------------------------------------------------

def _identify_stress_months(
    returns_df: pd.DataFrame,
    stress_window_months: int,
) -> pd.DatetimeIndex:
    """Identify the stress (high-vol/left-tail) months from the panel ≤ t.

    Strategy: compute trailing 12-month equal-weight portfolio vol for each
    month, then flag months in the top `stress_window_months` by vol level.
    Returns a DatetimeIndex of months classified as stress.

    All data is already ≤ t (caller guarantees this — no leakage).
    """
    if returns_df.empty or len(returns_df) < 2:
        return pd.DatetimeIndex([])
    ew_ret = returns_df.mean(axis=1)
    # Trailing 12-month realized vol for each month (annualized)
    trail_vol = ew_ret.rolling(window=12, min_periods=3).std() * np.sqrt(12)
    trail_vol = trail_vol.dropna()
    if trail_vol.empty:
        return pd.DatetimeIndex([])
    # Select top `stress_window_months` months by vol
    n_stress = min(stress_window_months, len(trail_vol))
    stress_idx = trail_vol.nlargest(n_stress).index
    return pd.DatetimeIndex(stress_idx)


def _avg_pairwise_abs_corr(returns_df: pd.DataFrame, lookback: int | None = None) -> float:
    """Average pairwise absolute correlation across columns.

    Used as a Diversification-Under-Stress diagnostic.  Returns NaN if
    fewer than 2 columns or too little data.
    """
    sub = returns_df.iloc[-lookback:] if lookback is not None else returns_df
    sub = sub.dropna(how="any", axis=0)
    if sub.shape[0] < 6 or sub.shape[1] < 2:
        return float("nan")
    corr = sub.corr().to_numpy(dtype=float)
    n = corr.shape[0]
    if n < 2:
        return float("nan")
    upper = corr[np.triu_indices(n, k=1)]
    return float(np.mean(np.abs(upper)))


def _sync_score(returns_df: pd.DataFrame, lookback: int | None = None) -> float:
    """Synchronisation score: fraction of assets with same sign as equal-weight portfolio.

    Rises during corr-breakdown / stress (most assets move together).
    """
    sub = returns_df.iloc[-lookback:] if lookback is not None else returns_df
    sub = sub.dropna(how="any", axis=0)
    if sub.shape[0] < 3 or sub.shape[1] < 2:
        return float("nan")
    ew = sub.mean(axis=1)
    same_sign = (sub.mul(ew, axis=0) > 0).mean(axis=1)
    return float(same_sign.mean())


def _stress_cov(
    returns_df: pd.DataFrame,
    stress_months: pd.DatetimeIndex,
    estimator: str,
    min_obs: int = 6,
) -> np.ndarray | None:
    """Estimate covariance on stress-window months only.

    Returns None if insufficient observations.
    """
    if len(stress_months) < min_obs:
        return None
    mask = returns_df.index.isin(stress_months)
    stress_sub = returns_df.loc[mask].dropna(how="any", axis=0)
    if len(stress_sub) < min_obs or stress_sub.shape[1] < 2:
        return None
    return _estimate_cov(stress_sub.to_numpy(dtype=float), estimator)


# ---------------------------------------------------------------------------
# LOIM regime-parity helpers  (Path B helpers)
# ---------------------------------------------------------------------------

def _rolling_vol_regime_labels(
    returns_df: pd.DataFrame,
    vol_lookback: int = 6,
) -> pd.Series:
    """Assign each month a regime label {0=low-vol, 1=high-vol} based on
    trailing equal-weight portfolio vol, split at the expanding median ≤ t.

    Labels are computed using only expanding-window history, enforcing
    leakage-free regime pools.  The expanding median is recomputed at each
    step so that regimes for month m are determined by the data through m
    (not through t; final labeling is called once with panel ≤ t).
    """
    if returns_df.empty or len(returns_df) < vol_lookback + 1:
        return pd.Series(dtype=int)
    ew_ret = returns_df.mean(axis=1)
    trail_vol = ew_ret.rolling(window=vol_lookback, min_periods=2).std() * np.sqrt(12)
    trail_vol = trail_vol.dropna()
    if trail_vol.empty:
        return pd.Series(dtype=int)
    # Expanding median as of each month
    exp_median = trail_vol.expanding(min_periods=2).median()
    labels = (trail_vol >= exp_median).astype(int)   # 1 = high-vol regime
    return labels


def _nber_regime_labels(
    returns_df: pd.DataFrame,
    as_of: pd.Timestamp,
) -> pd.Series:
    """Assign each month a regime label {0=expansion, 1=recession} using NBER
    dates with documented publication lag (see _nber_recession_months).

    Only months where the NBER had announced the end of the recession before
    `as_of` are labeled as recession.  External labels used as construction
    pool inputs only — not as a current-regime selector.
    """
    recession_set = _nber_recession_months(as_of)
    idx = returns_df.index
    periods = idx.to_period("M")
    labels = pd.Series(
        [1 if p in recession_set else 0 for p in periods],
        index=idx,
    )
    return labels


def _compute_pi_historical(labels: pd.Series, n_regimes: int) -> np.ndarray:
    """Historical frequency π̂_m from labels series."""
    total = len(labels)
    if total == 0:
        return np.ones(n_regimes) / n_regimes
    pi = np.array([float((labels == m).sum()) / total for m in range(n_regimes)])
    # Clip: avoid zero-weight regimes (fall back to uniform if degenerate)
    pi = np.clip(pi, 1e-6, None)
    return pi / pi.sum()


def _markov_steady_state(labels: pd.Series, n_regimes: int) -> np.ndarray:
    """Steady-state distribution from first-order empirical Markov chain.

    Transition matrix P[i,j] = P(t+1=j | t=i), estimated empirically ≤ t.
    Steady-state: π = π P  → left eigenvector.  Falls back to historical
    frequencies on any failure.
    """
    if len(labels) < 4:
        return _compute_pi_historical(labels, n_regimes)
    counts = np.zeros((n_regimes, n_regimes))
    for i in range(len(labels) - 1):
        r_from = int(labels.iloc[i])
        r_to = int(labels.iloc[i + 1])
        if 0 <= r_from < n_regimes and 0 <= r_to < n_regimes:
            counts[r_from, r_to] += 1
    row_sums = counts.sum(axis=1, keepdims=True)
    row_sums = np.where(row_sums == 0, 1.0, row_sums)
    P = counts / row_sums
    # Steady state: solve π(P - I) = 0, Σ π = 1
    A = (P.T - np.eye(n_regimes))
    A = np.vstack([A, np.ones(n_regimes)])
    b = np.zeros(n_regimes + 1)
    b[-1] = 1.0
    try:
        pi, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
        pi = np.clip(pi, 1e-6, None)
        return pi / pi.sum()
    except Exception:
        return _compute_pi_historical(labels, n_regimes)


# ---------------------------------------------------------------------------
# Month-end index helper
# ---------------------------------------------------------------------------

def _month_ends_in_index(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Return month-end dates (last obs per calendar month) from idx."""
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
    """Slice panel to tickers with ≥ min_history_months through `through`."""
    cols = [t for t in tickers if t in monthly.columns]
    sub = monthly.loc[:through, cols]
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
    min_history_months: int = 36,
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
            "thin_sleeve": any(t in (thin_set or set()) for t in ts) if thin_set else False,
        }
        for cat, ts in groups.items()
    ]
    return sleeve, pd.DataFrame(meta_rows)


# ---------------------------------------------------------------------------
# Core walk-forward loop
# ---------------------------------------------------------------------------

def run_regime_resilient_erc_trial(
    monthly: pd.DataFrame,
    trial: RegimeResilientERCTrial,
    *,
    universe_csv: str | Path,
    coverage: pd.DataFrame | None = None,
    universe_config: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run one walk-forward regime-resilient ERC trial.

    Construction (not selection):
    - Path A (stress_corr_overlay): Σ̂_resilient = (1−λ)Σ̂_uncond + λΣ̂_stress → ERC
    - Path B (loim_regime_parity): w* = Σ_m π̂_m · ERC(Σ̂_m)

    Returns
    -------
    monthly_weights : pd.DataFrame
        One row per decision month: decision_date, eval_date, trial_id,
        construction_tag, cash_pct, turnover, w_<TICKER>... (≤ 1 total).
    oos_returns : pd.DataFrame
        date, decision_date, trial_id, r_method, r_null_a (uncond ERC),
        r_null_b (EW), r_null_c (LW MinVar), r_active_vs_a, turnover.
    construction_diag : pd.DataFrame
        date, trial_id, construction_tag, mix_lambda, avg_abs_corr, sync_score,
        pi_hat_0, pi_hat_1, n_obs_pool_0, n_obs_pool_1, w_vs_uncond_erc_norm,
        stress_months_used, fallback_flag.
    registry : pd.DataFrame
        One row with trial parameters and citations.

    No same-month leakage: all inputs, regime pools, Σ̂, π̂, and weights at t
    are invariant to returns after t.
    """
    uni_cfg = universe_config or load_universe_config()
    uni_df = load_universe_csv(universe_csv)

    cash = trial.cash_ticker.upper()
    cash_fallbacks = [c for c in CASH_FALLBACKS if c != cash]
    all_tickers_eligible = set(eligible_tickers(uni_df, uni_cfg))
    thin_set = thin_history_set(uni_cfg)

    if cash not in all_tickers_eligible:
        for fb in cash_fallbacks:
            if fb in all_tickers_eligible:
                cash = fb
                break

    monthly = monthly.copy()
    monthly.columns = [str(c).upper() for c in monthly.columns]
    monthly.index = pd.to_datetime(monthly.index)
    monthly = monthly.sort_index()

    me_dates = _month_ends_in_index(monthly.index)

    weight_rows: list[dict] = []
    return_rows: list[dict] = []
    diag_rows: list[dict] = []

    prev_w_method: pd.Series | None = None
    prev_w_null_a: pd.Series | None = None
    prev_w_null_b: pd.Series | None = None
    prev_w_null_c: pd.Series | None = None

    # sleeve→ticker map for eval_date return calculation
    sleeve_ticker_map: dict[str, list[str]] = {}

    for i, d in enumerate(me_dates):
        if i + 1 >= len(me_dates):
            break
        eval_date = me_dates[i + 1]

        # ----------------------------------------------------------------
        # 1. Build panel ≤ d (no leakage)
        # ----------------------------------------------------------------
        sleeve_ticker_map_d: dict[str, list[str]] = {}

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
            # Rebuild sleeve→tickers for eval_date return calculation
            uni_tmp = uni_df.copy()
            uni_tmp["Ticker"] = uni_tmp["Ticker"].astype(str).str.upper()
            if "Category" in uni_tmp.columns:
                cat_map_tmp = uni_tmp.set_index("Ticker")["Category"].astype(str)
                n_obs_through = monthly.loc[:d].notna().sum(axis=0)
                _excl = set(_DEFAULT_EXCLUDE_CATEGORIES)
                for cat in panel.columns:
                    members = [
                        t for t in monthly.columns
                        if (t in cat_map_tmp.index
                            and str(cat_map_tmp.loc[t]) == cat
                            and t in all_tickers_eligible
                            and (trial.include_thin or t not in thin_set)
                            and n_obs_through.get(t, 0) >= trial.min_history_months
                            and cat not in _excl)
                    ]
                    if members:
                        sleeve_ticker_map_d[cat] = members
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

        if trial.apply_to == "name_level" and panel.shape[1] < trial.min_names:
            continue

        tickers_t = list(panel.columns)
        N = len(tickers_t)

        # ----------------------------------------------------------------
        # 2. Unconditional Σ̂ (all history ≤ d) — used by Path A and as null
        # ----------------------------------------------------------------
        window_all = panel.dropna(how="any", axis=0)
        if len(window_all) < max(6, N + 1):
            window_all = panel.dropna(how="all", axis=0).dropna(axis=1)
            if window_all.shape[0] < 6 or window_all.shape[1] < 2:
                continue
            tickers_t = list(window_all.columns)
            N = len(tickers_t)

        try:
            cov_uncond = _estimate_cov(window_all.to_numpy(dtype=float), trial.cov_estimator)
            cov_uncond_reg = cov_uncond + 1e-8 * np.eye(N)
        except Exception:
            continue

        # ----------------------------------------------------------------
        # 3. Build risky weights for primary method
        # ----------------------------------------------------------------
        fallback_flag = False
        construction_tag = trial.construction
        mix_lambda_used = float("nan")
        avg_abs_corr = float("nan")
        sync_score_val = float("nan")
        stress_months_used = 0
        pi_hat = [float("nan")] * trial.n_regimes
        n_obs_pool = [0] * trial.n_regimes
        w_vs_erc_norm = float("nan")

        if trial.construction == "stress_corr_overlay":
            # Path A: blend unconditional and stress Σ̂
            stress_idx = _identify_stress_months(panel.loc[:d], trial.stress_window_months)
            stress_months_used = len(stress_idx)
            cov_stress = _stress_cov(
                panel.loc[:d, tickers_t],
                stress_idx,
                trial.cov_estimator,
                min_obs=max(6, N + 1),
            )
            if cov_stress is None:
                fallback_flag = True
                cov_resilient_reg = cov_uncond_reg.copy()
                mix_lambda_used = 0.0
            else:
                lam = trial.mix_lambda
                mix_lambda_used = lam
                cov_resilient = (1.0 - lam) * cov_uncond + lam * cov_stress
                cov_resilient_reg = cov_resilient + 1e-8 * np.eye(N)

            avg_abs_corr = _avg_pairwise_abs_corr(panel.loc[:d, tickers_t])
            sync_score_val = _sync_score(panel.loc[:d, tickers_t])

            try:
                w_risky_arr = _erc(cov_resilient_reg, N)
            except Exception:
                w_risky_arr = np.ones(N) / N
                fallback_flag = True

            # Corr-breakdown gate: increase cash residual when avg|corr| is elevated
            risky_scalar = 1.0
            if (trial.corr_breakdown_gate
                    and not np.isnan(avg_abs_corr)
                    and avg_abs_corr > trial.corr_breakdown_threshold):
                risky_scalar = max(0.5, 1.0 - (avg_abs_corr - trial.corr_breakdown_threshold))

            w_risky = pd.Series(dict(zip(tickers_t, w_risky_arr * risky_scalar)))

        elif trial.construction == "loim_regime_parity":
            # Path B: π-weighted blend of local ERC solutions
            # Build regime labels ≤ d (no leakage)
            panel_d = panel.loc[:d, tickers_t]

            if trial.regime_pool_rule == "nber_lag":
                regime_labels = _nber_regime_labels(panel_d, as_of=d)
            else:
                regime_labels = _rolling_vol_regime_labels(panel_d)

            # Compute per-regime Σ̂_m and ERC solutions
            local_ercs: list[np.ndarray] = []
            ok_regimes: list[int] = []
            for m in range(trial.n_regimes):
                mask = regime_labels == m
                # Align mask to panel_d index (rolling labels may be a subset)
                common_idx = panel_d.index.intersection(mask.index)
                if len(common_idx) == 0:
                    n_obs_pool[m] = 0
                    continue
                mask_aligned = mask.reindex(common_idx)
                sub_m = panel_d.loc[common_idx].loc[mask_aligned].dropna(how="any", axis=0)
                n_obs_pool[m] = len(sub_m)
                if n_obs_pool[m] < trial.min_obs_per_pool:
                    continue
                try:
                    cov_m = _estimate_cov(sub_m.to_numpy(dtype=float), trial.cov_estimator)
                    cov_m_reg = cov_m + 1e-8 * np.eye(N)
                    w_m = _erc(cov_m_reg, N)
                except Exception:
                    continue
                local_ercs.append(w_m)
                ok_regimes.append(m)

            if len(ok_regimes) == 0:
                fallback_flag = True
                w_risky_arr = _erc(cov_uncond_reg, N)
            elif len(ok_regimes) == 1:
                fallback_flag = True
                w_risky_arr = local_ercs[0]
            else:
                # Use only the common index between labels and panel_d for pi calculation
                common_idx = panel_d.index.intersection(regime_labels.index)
                labels_common = regime_labels.reindex(common_idx).dropna()
                labels_ok = labels_common[labels_common.isin(ok_regimes)]
                if trial.pi_rule == "markov_steady":
                    pi_all = _markov_steady_state(labels_ok, trial.n_regimes)
                else:
                    pi_all = _compute_pi_historical(labels_ok, trial.n_regimes)
                pi_sub = np.array([pi_all[m] for m in ok_regimes])
                pi_sub = pi_sub / pi_sub.sum()
                for m_idx, m in enumerate(ok_regimes):
                    pi_hat[m] = float(pi_sub[m_idx])
                w_risky_arr = sum(
                    pi_sub[j] * local_ercs[j] for j in range(len(ok_regimes))
                )

            w_risky = pd.Series(dict(zip(tickers_t, w_risky_arr)))

        else:
            w_risky = pd.Series(np.ones(N) / N, index=tickers_t)

        # Residual → cash
        risky_sum = float(w_risky.sum())
        cash_weight = max(0.0, 1.0 - risky_sum)
        w_method = w_risky.copy()
        w_method[cash] = w_method.get(cash, 0.0) + cash_weight

        # ----------------------------------------------------------------
        # 4. Construction diagnostics
        # ----------------------------------------------------------------
        # ‖w_method − w_uncond_ERC‖ (comparing risky portions)
        try:
            w_erc_uncond_arr = _erc(cov_uncond_reg, N)
            w_erc_uncond = pd.Series(dict(zip(tickers_t, w_erc_uncond_arr)))
            diff = w_method.reindex(tickers_t).fillna(0.0) - w_erc_uncond.reindex(tickers_t).fillna(0.0)
            w_vs_erc_norm = float(np.linalg.norm(diff.values))
        except Exception:
            w_vs_erc_norm = float("nan")

        # ----------------------------------------------------------------
        # 5. Null portfolios (all use data ≤ d — no leakage)
        # ----------------------------------------------------------------
        # (a) Unconditional ERC — PRIMARY CIO null
        try:
            w_null_a_arr = _erc(cov_uncond_reg, N)
        except Exception:
            w_null_a_arr = np.ones(N) / N
        w_null_a = pd.Series(dict(zip(tickers_t, w_null_a_arr)))

        # (b) Equal-weight
        w_null_b = pd.Series(1.0 / N, index=tickers_t)

        # (c) LW MinVar
        try:
            w_null_c_arr = _lw_minvar(cov_uncond_reg, N)
        except Exception:
            w_null_c_arr = np.ones(N) / N
        w_null_c = pd.Series(dict(zip(tickers_t, w_null_c_arr)))

        # ----------------------------------------------------------------
        # 6. Turnover costs
        # ----------------------------------------------------------------
        def _to(w_prev: pd.Series | None, w_new: pd.Series) -> float:
            return half_turnover(w_prev, w_new)

        to_method = _to(prev_w_method, w_method)
        to_a = _to(prev_w_null_a, w_null_a)
        to_b = _to(prev_w_null_b, w_null_b)
        to_c = _to(prev_w_null_c, w_null_c)

        cost_bps = trial.cost_bps_one_way / 10000.0
        cost_m = to_method * cost_bps
        cost_a = to_a * cost_bps
        cost_b = to_b * cost_bps
        cost_c = to_c * cost_bps

        prev_w_method = w_method.copy()
        prev_w_null_a = w_null_a.copy()
        prev_w_null_b = w_null_b.copy()
        prev_w_null_c = w_null_c.copy()

        # ----------------------------------------------------------------
        # 7. Evaluate t+1 returns (eval_date)
        # ----------------------------------------------------------------
        if eval_date not in monthly.index:
            continue

        eval_row = monthly.loc[eval_date]

        def _asset_ret(ticker: str) -> float:
            if ticker == cash:
                v = eval_row.get(cash, float("nan"))
                return float(v) if (v is not None and not pd.isna(v)) else 0.0
            if ticker in sleeve_ticker_map_d:
                members = sleeve_ticker_map_d[ticker]
                vals = [eval_row.get(m, float("nan")) for m in members if m in eval_row.index]
                valid = [v for v in vals if (v is not None and not np.isnan(v))]
                return float(np.mean(valid)) if valid else float("nan")
            rv = eval_row.get(ticker, float("nan"))
            return float(rv) if (rv is not None and not np.isnan(rv)) else float("nan")

        def _port_ret(w: pd.Series) -> float:
            r = 0.0
            for t_, wt_ in w.items():
                if abs(wt_) < 1e-12:
                    continue
                rv = _asset_ret(t_)
                if not np.isfinite(rv):
                    continue
                r += wt_ * rv
            return float(r)

        r_m = _port_ret(w_method) - cost_m
        r_a = _port_ret(w_null_a) - cost_a
        r_b = _port_ret(w_null_b) - cost_b
        r_c = _port_ret(w_null_c) - cost_c

        # ----------------------------------------------------------------
        # 8. Record rows
        # ----------------------------------------------------------------
        w_row: dict = {
            "date": d,
            "eval_date": eval_date,
            "trial_id": trial.trial_id,
            "construction_tag": construction_tag,
            "mix_lambda": mix_lambda_used if trial.construction == "stress_corr_overlay" else float("nan"),
            "turnover": to_method,
            "cash_pct": float(w_method.get(cash, 0.0)),
            "n_assets": N,
            "thin_flag": int(any(t in thin_set for t in tickers_t)),
            "fallback_flag": int(fallback_flag),
        }
        for t_, wt_ in w_method.items():
            if wt_ > 1e-12:
                w_row[f"w_{t_}"] = float(wt_)
        weight_rows.append(w_row)

        diag_row: dict = {
            "date": d,
            "trial_id": trial.trial_id,
            "construction_tag": construction_tag,
            "mix_lambda": mix_lambda_used if trial.construction == "stress_corr_overlay" else float("nan"),
            "avg_abs_corr": avg_abs_corr,
            "sync_score": sync_score_val,
            "stress_months_used": stress_months_used,
            "w_vs_uncond_erc_norm": w_vs_erc_norm,
            "fallback_flag": int(fallback_flag),
        }
        for m_idx in range(trial.n_regimes):
            diag_row[f"pi_hat_{m_idx}"] = pi_hat[m_idx] if m_idx < len(pi_hat) else float("nan")
            diag_row[f"n_obs_pool_{m_idx}"] = n_obs_pool[m_idx] if m_idx < len(n_obs_pool) else 0
        diag_rows.append(diag_row)

        return_rows.append({
            "date": eval_date,
            "decision_date": d,
            "trial_id": trial.trial_id,
            "construction_tag": construction_tag,
            "r_method": r_m,
            "r_null_a": r_a,   # unconditional ERC — PRIMARY CIO null
            "r_null_b": r_b,   # equal-weight
            "r_null_c": r_c,   # LW MinVar
            "r_active_vs_a": r_m - r_a,
            "turnover": to_method,
        })

    monthly_weights = pd.DataFrame(weight_rows)
    oos_returns = pd.DataFrame(return_rows)
    construction_diag = pd.DataFrame(diag_rows)
    registry = _make_registry(trial)
    return monthly_weights, oos_returns, construction_diag, registry


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def _summarize(
    oos: pd.DataFrame,
    trial_id: str,
    trial_count: int,
    bootstrap_samples: int = 500,
    bootstrap_block_months: int = 3,
) -> pd.DataFrame:
    if oos.empty or "r_method" not in oos.columns:
        return pd.DataFrame()
    # Use date column as index for proper date-aware operations
    if "date" in oos.columns:
        oos = oos.copy()
        oos["date"] = pd.to_datetime(oos["date"])
        oos_indexed = oos.set_index("date")
    else:
        oos_indexed = oos
    r_m = oos_indexed["r_method"].dropna()
    if len(r_m) < 12:
        return pd.DataFrame()

    ann_ret = annualized_return(r_m)
    ann_vol = annualized_vol(r_m)
    mdd = max_drawdown(r_m)
    sr = sharpe_rf0(r_m)
    dsr = deflated_sharpe_approx(sr / np.sqrt(MONTHS_PER_YEAR), len(r_m), trial_count)
    nw_vs_a = newey_west_tstat((oos_indexed["r_method"] - oos_indexed["r_null_a"]).dropna())
    nw_vs_b = newey_west_tstat((oos_indexed["r_method"] - oos_indexed["r_null_b"]).dropna())
    nw_vs_c = newey_west_tstat((oos_indexed["r_method"] - oos_indexed["r_null_c"]).dropna())
    lo, hi = block_bootstrap_sharpe_ci(r_m, block_months=bootstrap_block_months, n_boot=bootstrap_samples)
    to_yr = float(oos_indexed["turnover"].dropna().mean() * MONTHS_PER_YEAR) if "turnover" in oos_indexed.columns else float("nan")

    row: dict = {
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
        "NW_t_vs_null_a_uncond_ERC": nw_vs_a,
        "NW_t_vs_null_b_EW": nw_vs_b,
        "NW_t_vs_null_c_LW_MinVar": nw_vs_c,
        "bootstrap_Sharpe_lo95": lo,
        "bootstrap_Sharpe_hi95": hi,
        "turnover_per_year": to_yr,
        "research_disclaimer": RESEARCH_DISCLAIMER,
    }
    for null_col, null_label in [
        ("r_null_a", "null_a_uncond_ERC"),
        ("r_null_b", "null_b_EW"),
        ("r_null_c", "null_c_LW_MinVar"),
    ]:
        rn = oos_indexed[null_col].dropna()
        row[f"AnnReturn_{null_label}"] = annualized_return(rn)
        row[f"Sharpe_{null_label}"] = sharpe_rf0(rn)

    return pd.DataFrame([row])


def _make_registry(trial: RegimeResilientERCTrial) -> pd.DataFrame:
    return pd.DataFrame([{
        "trial_id": trial.trial_id,
        "method": "regime_resilient_erc",
        "construction": trial.construction,
        "stress_window_months": trial.stress_window_months,
        "mix_lambda": trial.mix_lambda,
        "corr_breakdown_gate": trial.corr_breakdown_gate,
        "corr_breakdown_threshold": trial.corr_breakdown_threshold,
        "regime_pool_rule": trial.regime_pool_rule,
        "n_regimes": trial.n_regimes,
        "pi_rule": trial.pi_rule,
        "min_obs_per_pool": trial.min_obs_per_pool,
        "cov_estimator": trial.cov_estimator,
        "long_only": trial.long_only,
        "cost_bps_one_way": trial.cost_bps_one_way,
        "cash_ticker": trial.cash_ticker,
        "min_names": trial.min_names,
        "apply_to": trial.apply_to,
        "include_thin": trial.include_thin,
        "min_history_months": trial.min_history_months,
        "trial_count": 1,
        "citation_lead": CITATION_LEAD,
        "citation_precursor": CITATION_PRECURSOR,
        "citation_erc": CITATION_ERC,
        "citation_dsr": CITATION_DSR,
        "enabled": False,
        "research_disclaimer": RESEARCH_DISCLAIMER,
    }])


# ---------------------------------------------------------------------------
# Grid runner
# ---------------------------------------------------------------------------

def run_regime_resilient_erc_grid(
    monthly: pd.DataFrame,
    trials: list[RegimeResilientERCTrial],
    *,
    universe_csv: str | Path,
    coverage: pd.DataFrame | None = None,
    universe_config: dict | None = None,
    bootstrap_samples: int = 500,
    bootstrap_block_months: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run a grid of regime-resilient ERC trials.

    Returns (summary, monthly_weights, oos_returns, construction_diag, registry).
    """
    all_weights: list[pd.DataFrame] = []
    all_returns: list[pd.DataFrame] = []
    all_diag: list[pd.DataFrame] = []
    all_registry: list[pd.DataFrame] = []

    for trial_num, trial in enumerate(trials, start=1):
        try:
            w, r, diag, reg = run_regime_resilient_erc_trial(
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
        all_diag.append(diag)
        all_registry.append(reg)

    if not all_returns:
        empty = pd.DataFrame()
        return empty, empty, empty, empty, empty

    monthly_weights = pd.concat(all_weights, ignore_index=True)
    oos_returns = pd.concat(all_returns, ignore_index=True)
    construction_diag = pd.concat(all_diag, ignore_index=True)
    registry = pd.concat(all_registry, ignore_index=True)
    trial_count_total = len(trials)
    registry["trial_count"] = trial_count_total

    summary_rows: list[pd.DataFrame] = []
    for trial, r_sub in zip(
        [t for t in trials if t.trial_id in set(registry["trial_id"].tolist())],
        all_returns,
    ):
        s = _summarize(
            r_sub,
            trial.trial_id,
            trial_count_total,
            bootstrap_samples,
            bootstrap_block_months,
        )
        summary_rows.append(s)

    summary = pd.concat(summary_rows, ignore_index=True) if summary_rows else pd.DataFrame()
    return summary, monthly_weights, oos_returns, construction_diag, registry
