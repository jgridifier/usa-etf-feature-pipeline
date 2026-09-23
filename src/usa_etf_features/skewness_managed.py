"""Skewness-Managed Book-2 Overlay — Justina CIO shortlist #6.

Walk-forward Book-2 vol-target with skewness / left-tail gate (Gong–Lynch–Ogden).

Primary path: keep Book-2 f_t = clip(σ*/σ̂_t, f_min, f_max);
gate g_t ∈ [g_min, 1] from skewness / left-tail diagnostics ≤ t;
effective equity scale f̃_t = f_t · g_t; residual → BIL.

Registry: enabled=false until Quant gate PASS.

Nulls:
  (a) Unconditional Book-2 VT (PRIMARY)     — must clear on Sharpe AND MaxDD/left-tail
  (b) Static Option A core                  — buy-and-hold context
  (c) Equal-weight (name-level panel)
  (d) LW MinVar                             — CIO gate set
  (e) ERC                                   — CIO gate set

Research tooling only; not investment advice.
No same-month leakage: σ̂_t, skew diagnostics, gate, and weights at month-end t
are invariant to mutations of returns after t (unit test in tests/test_skewness_managed.py).

Lead citation:
  Gong, Rui, John Lynch, and Richard Ogden. "Skewness Managed Portfolios."
  Working paper (author PDF Jan 2025; practitioner coverage Jun–Jul 2026).
  https://richardeogden.github.io/Skewness_Managed_Portfolios.pdf

Backbone:
  Moreira, Alan, and Tyler Muir. 2017. "Volatility-Managed Portfolios."
  Journal of Finance 72(4):1611–1644. doi:10.1111/jofi.12513

Skewness measurement:
  Amaya, Diego, Peter Christoffersen, Kris Jacobs, and Aurelio Vasquez. 2015.
  "Does Realized Skewness Predict the Cross-Section of Equity Returns?"
  Journal of Financial Economics 118:135–167.

  Boyer, Brian, Todd Mitton, and Keith Vorkink. 2010.
  "Expected Idiosyncratic Skewness."
  Review of Financial Studies 23(1):169–202.

Inference:
  Bailey, David H., and Marcos López de Prado. 2014.
  "The Deflated Sharpe Ratio." Journal of Portfolio Management 40(5):94–107.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import optimize, stats

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

CITATION = (
    "Gong, Rui, John Lynch, and Richard Ogden. 'Skewness Managed Portfolios.' "
    "Working paper (author PDF Jan 2025; Justina Jul 2026 coverage). "
    "https://richardeogden.github.io/Skewness_Managed_Portfolios.pdf; "
    "Moreira & Muir 2017 Book-2 backbone doi:10.1111/jofi.12513; "
    "Amaya et al. 2015 JFE 118:135-167; Boyer, Mitton & Vorkink 2010 RFS 23(1):169-202; "
    "Bailey & Lopez de Prado 2014 DSR."
)

_DEFAULT_EXCLUDE_CATEGORIES = (
    "Defined Outcome / Buffer / Structured",
    "Specialty / Other",
)

TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# Trial dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SkewnessManagedTrial:
    trial_id: str
    core: str = "option_a"
    lookback: int = 63
    f_min: float = 0.25
    f_max: float = 1.0
    g_min: float = 0.5
    sigma_star: str | float = "expanding_annvol"
    skew_estimator: str = "realized_amaya"   # realized_amaya | expected_bmv_lite
    left_tail_rule: str = "cvar_5"           # cvar_5 | adverse_rs | pct_lt_neg_k_sigma
    k_sigma: float = 1.0                     # threshold for pct_lt_neg_k_sigma rule
    apply_to: str = "option_a_vt"            # option_a_vt | category_sleeves
    cash_ticker: str = "BIL"
    cost_bps_one_way: float = 5.0
    skew_lookback_months: int = 63           # monthly lookback for CVaR / tail score
    min_names: int = 100
    include_thin: bool = False
    cov_lookback_months: int = 36            # for LW MinVar / ERC nulls


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_skewness_managed_config(path: str | Path | None = None) -> dict:
    if path is None:
        candidates = [
            Path("config/skewness_managed.yaml"),
            Path(__file__).resolve().parents[2] / "config" / "skewness_managed.yaml",
        ]
        for c in candidates:
            if c.exists():
                path = c
                break
    if path is None:
        return {
            "skewness_managed": {
                "lookbacks": [21, 63, 126],
                "f_min": 0.25,
                "f_max": 1.0,
                "g_min": [0.25, 0.5],
                "skew_estimator": ["realized_amaya", "expected_bmv_lite"],
                "left_tail_rule": ["cvar_5", "adverse_rs", "pct_lt_neg_k_sigma"],
                "apply_to": ["option_a_vt"],
                "cost_bps_one_way": 5,
                "min_names": 100,
                "enabled": False,
                "cash_ticker": "BIL",
                "sigma_star": "expanding_annvol",
                "skew_lookback_months": 63,
                "cov_lookback_months": 36,
                "bootstrap_samples": 500,
                "bootstrap_block_months": 3,
            }
        }
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Skewness diagnostics
# ---------------------------------------------------------------------------

def realized_skewness_amaya(daily_r: np.ndarray) -> float:
    """Amaya et al. (2015) realized skewness from daily returns.

    RS = sqrt(N) * sum(r^3) / RV^(3/2)
    where RV = sum(r^2) (realized variance, not annualised).

    Returns NaN if fewer than 3 observations or RV is zero.
    """
    r = np.asarray(daily_r, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    if n < 3:
        return float("nan")
    rv = float(np.sum(r ** 2))
    if rv < 1e-20:
        return float("nan")
    return float(np.sqrt(n) * np.sum(r ** 3) / rv ** 1.5)


def realized_skewness_at_month_ends(
    core_daily: pd.Series,
    me_dates: pd.DatetimeIndex,
) -> pd.Series:
    """Amaya realized skewness for each decision month-end.

    Uses only daily returns within the calendar month ≤ t (no leakage).
    """
    r = core_daily.dropna().sort_index()
    out: dict = {}
    for t in me_dates:
        # daily returns in the same calendar month as t
        month_start = t.replace(day=1)
        window = r.loc[(r.index >= month_start) & (r.index <= t)]
        out[t] = realized_skewness_amaya(window.to_numpy())
    return pd.Series(out, name="realized_skew")


def expected_skewness_bmv_lite(
    rs_series: pd.Series,
    me_dates: pd.DatetimeIndex,
) -> pd.Series:
    """Boyer–Mitton–Vorkink-lite expected skewness (expanding OLS on lagged rs).

    At each date t, fits an expanding AR(1)-style OLS on realized skewness
    using data strictly ≤ t to forecast next-period rs. Only data ≤ t is used
    to avoid leakage. Returns the in-sample fitted value at t as E[rs_{t+1}].
    Falls back to lagged rs when OLS cannot be fitted.
    """
    rs = rs_series.dropna().sort_index()
    out: dict = {}
    for t in me_dates:
        hist = rs.loc[rs.index <= t].dropna()
        if len(hist) < 5:
            # not enough history; fall back to most recent rs
            out[t] = float(hist.iloc[-1]) if len(hist) >= 1 else float("nan")
            continue
        y = hist.iloc[1:].to_numpy(dtype=float)
        x = hist.iloc[:-1].to_numpy(dtype=float)
        valid = np.isfinite(x) & np.isfinite(y)
        if valid.sum() < 3:
            out[t] = float(hist.iloc[-1])
            continue
        x_v, y_v = x[valid], y[valid]
        # simple OLS: y = a + b*x
        x_mat = np.column_stack([np.ones(len(x_v)), x_v])
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                coef, *_ = np.linalg.lstsq(x_mat, y_v, rcond=None)
            last_rs = float(hist.iloc[-1])
            if np.isfinite(last_rs) and np.all(np.isfinite(coef)):
                out[t] = float(coef[0] + coef[1] * last_rs)
            else:
                out[t] = float(hist.iloc[-1])
        except Exception:
            out[t] = float(hist.iloc[-1])
    return pd.Series(out, name="expected_skew")


def skewness_at_month_ends(
    core_daily: pd.Series,
    me_dates: pd.DatetimeIndex,
    skew_estimator: str,
) -> pd.Series:
    """Dispatch to the requested skewness estimator."""
    rs_realized = realized_skewness_at_month_ends(core_daily, me_dates)
    if skew_estimator == "realized_amaya":
        return rs_realized
    if skew_estimator == "expected_bmv_lite":
        return expected_skewness_bmv_lite(rs_realized, me_dates)
    raise ValueError(f"unknown skew_estimator {skew_estimator!r}; "
                     "expected realized_amaya or expected_bmv_lite")


# ---------------------------------------------------------------------------
# Left-tail scores
# ---------------------------------------------------------------------------

def cvar_at_level(monthly_returns: pd.Series, level: float = 0.05) -> float:
    """Rolling CVaR (expected shortfall) at given level from a return series.

    Returns the mean of returns in the bottom `level` quantile.
    Sign convention: positive value = adverse (large losses → high CVaR).
    """
    vals = pd.Series(monthly_returns, dtype=float).dropna().to_numpy()
    if len(vals) < 3:
        return float("nan")
    threshold = float(np.quantile(vals, level))
    tail = vals[vals <= threshold]
    if tail.size == 0:
        return float("nan")
    return float(-np.mean(tail))  # positive = bad (more negative mean = higher CVaR)


def pct_below_minus_k_sigma(monthly_returns: pd.Series, k: float = 1.0) -> float:
    """Fraction of months where r < -k * sigma_monthly (sample std)."""
    vals = pd.Series(monthly_returns, dtype=float).dropna().to_numpy()
    if len(vals) < 3:
        return float("nan")
    sigma = float(np.std(vals, ddof=1))
    if sigma < 1e-12:
        return float("nan")
    return float(np.mean(vals < -k * sigma))


def left_tail_score_at_month_ends(
    monthly_r: pd.Series,
    me_dates: pd.DatetimeIndex,
    rs_series: pd.Series,
    *,
    rule: str,
    lookback_months: int,
    k_sigma: float = 1.0,
) -> pd.Series:
    """Rolling left-tail score at each decision month-end using data ≤ t only.

    rule:
      cvar_5              — rolling CVaR at 5% on portfolio monthly returns
      adverse_rs          — max(0, −rs_t); adverse skew direction
      pct_lt_neg_k_sigma  — % monthly returns below −k·σ_monthly
    """
    if rule not in {"cvar_5", "adverse_rs", "pct_lt_neg_k_sigma"}:
        raise ValueError(f"unknown left_tail_rule {rule!r}; "
                         "expected cvar_5, adverse_rs, or pct_lt_neg_k_sigma")

    mr = monthly_r.dropna().sort_index()
    out: dict = {}
    for t in me_dates:
        if rule == "adverse_rs":
            rs = rs_series.get(t, float("nan"))
            if not np.isfinite(rs):
                out[t] = float("nan")
            else:
                out[t] = float(max(0.0, -rs))
        else:
            hist = mr.loc[mr.index <= t]
            if len(hist) >= lookback_months:
                window = hist.iloc[-lookback_months:]
            else:
                window = hist
            if rule == "cvar_5":
                out[t] = cvar_at_level(window)
            else:  # pct_lt_neg_k_sigma
                out[t] = pct_below_minus_k_sigma(window, k=k_sigma)
    return pd.Series(out, name="left_tail_score")


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------

def expanding_median_prior(series: pd.Series) -> pd.Series:
    """Expanding median of values strictly before each date (no leakage)."""
    s = series.astype(float)
    vals: list[float] = []
    hist: list[float] = []
    for idx in s.index:
        vals.append(float(np.nanmedian(hist)) if hist else float("nan"))
        v = s.loc[idx]
        if np.isfinite(v):
            hist.append(float(v))
    return pd.Series(vals, index=s.index, name=f"{s.name}_med_prior")


def skewness_gate(
    left_tail: float,
    lt_median: float,
    *,
    g_min: float,
) -> tuple[float, bool]:
    """Gate g_t ∈ [g_min, 1]: bind when left-tail score exceeds expanding median.

    Returns (g, binding).
    Binding when left_tail > lt_median (adverse left-tail is above historical norm).
    Open (g=1) when left-tail is calm or favorable.
    """
    if not (np.isfinite(left_tail) and np.isfinite(lt_median)):
        return (1.0, False)
    binding = bool(left_tail > lt_median)
    return (float(g_min) if binding else 1.0, binding)


# ---------------------------------------------------------------------------
# Null portfolio helpers (EW, LW MinVar, ERC) — computed from monthly panel
# ---------------------------------------------------------------------------

def _ledoit_wolf_cov(returns: np.ndarray) -> np.ndarray:
    """Ledoit–Wolf shrinkage covariance for a (T x N) returns array."""
    from sklearn.covariance import LedoitWolf
    lw = LedoitWolf(assume_centered=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        lw.fit(returns)
    return lw.covariance_


def _sample_cov(returns: np.ndarray) -> np.ndarray:
    return np.cov(returns.T, ddof=1)


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
    """Equal-risk-contribution portfolio (long-only) via log-barrier (Maillard et al. 2010)."""
    w0 = np.ones(n) / n

    def _obj(w: np.ndarray) -> float:
        val = 0.5 * float(w @ cov @ w)
        if np.any(w <= 0):
            return 1e20
        val -= float(np.sum(np.log(w))) / n
        return val

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


def _port_ret_from_weights(monthly_returns_row: pd.Series, weights: np.ndarray, tickers: list[str]) -> float:
    vals = []
    for t, wt in zip(tickers, weights):
        r = monthly_returns_row.get(t, float("nan"))
        if pd.isna(r):
            return float("nan")
        vals.append(float(wt) * float(r))
    return float(np.sum(vals)) if vals else float("nan")


def _ew_weights(tickers: list[str]) -> np.ndarray:
    n = len(tickers)
    return np.ones(n) / n if n > 0 else np.array([])


# ---------------------------------------------------------------------------
# Monthly panel helpers
# ---------------------------------------------------------------------------

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


def _monthly_price_returns(
    prices: pd.DataFrame,
    me_dates: pd.DatetimeIndex,
    cash_ticker: str,
) -> pd.DataFrame:
    me_px = prices.reindex(me_dates)
    me_ret = me_px.pct_change()
    if cash_ticker not in me_ret.columns or me_ret[cash_ticker].isna().all():
        me_ret[cash_ticker] = 0.0
    return me_ret


# ---------------------------------------------------------------------------
# Main walk-forward trial
# ---------------------------------------------------------------------------

def run_skewness_managed_trial(
    prices: pd.DataFrame,
    trial: SkewnessManagedTrial,
    *,
    universe_csv: str | Path,
    monthly: pd.DataFrame | None = None,
    coverage: pd.DataFrame | None = None,
    universe_config: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Walk-forward skewness-managed Book-2 overlay.

    Returns (weights, oos_returns, registry).

    Nulls in oos_returns:
      r_null_a  — unconditional Book-2 VT (PRIMARY)
      r_null_b  — static Option A (fully invested)
      r_null_c  — equal-weight name-level (no cash)
      r_null_d  — LW MinVar (no cash)
      r_null_e  — ERC (no cash)
    """
    cash = trial.cash_ticker.upper()
    apply_to = str(trial.apply_to).strip().lower()
    if apply_to not in {"option_a_vt", "category_sleeves"}:
        raise ValueError(f"apply_to must be option_a_vt or category_sleeves, got {trial.apply_to!r}")

    uni_df = load_universe_csv(universe_csv)
    cfg = universe_config or load_universe_config()
    base = core_weights(trial.core)
    assert_eligible([*base.keys(), cash], uni_df, cfg)
    eligible = eligible_tickers(uni_df, cfg)

    px = prices.copy()
    missing_core = [t for t in base if t not in px.columns]
    if missing_core:
        raise ValueError(f"missing price columns for core: {missing_core}")
    cash_price_missing = cash not in px.columns
    if cash_price_missing:
        px[cash] = np.nan

    need_cols = list(dict.fromkeys([*base.keys(), cash]))
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

    # Skewness / left-tail diagnostics
    skew_series = skewness_at_month_ends(core_daily, me_dates, trial.skew_estimator)

    # Monthly portfolio returns for left-tail (used by CVaR / pct-below rules)
    # Build Option A monthly return series from me_ret (data ≤ t, sampled on me_dates)
    option_w = pd.Series({**base, cash: 0.0}, dtype=float)
    portfolio_monthly_r = pd.Series(
        {
            eval_d: portfolio_month_return(me_ret, eval_d, option_w)
            for eval_d in me_dates
        },
        name="r_core_monthly",
    ).dropna()

    left_tail = left_tail_score_at_month_ends(
        portfolio_monthly_r,
        me_dates,
        skew_series,
        rule=trial.left_tail_rule,
        lookback_months=trial.skew_lookback_months,
        k_sigma=trial.k_sigma,
    )
    lt_median = expanding_median_prior(left_tail)

    # Monthly panel for EW / MinVar / ERC nulls
    if monthly is None:
        me_all = month_end_trading_dates(px)
        monthly_panel = px.reindex(me_all).pct_change()
    else:
        monthly_panel = monthly.sort_index().copy()
        monthly_panel.columns = [str(c).upper() for c in monthly_panel.columns]

    thin_flags = _thin_flags_from_coverage(coverage)
    if thin_flags is None:
        thin_set = thin_history_set(cfg)
        thin_flags = pd.Series({t: True for t in thin_set}, dtype=bool)

    eligible_names = sorted(
        t for t in monthly_panel.columns
        if t in eligible
        and t != cash
        and t not in {c.upper() for c in base}  # exclude core tickers from null
    ) if not trial.include_thin else sorted(
        t for t in monthly_panel.columns
        if t in eligible and t != cash
    )
    # But for null portfolios include all eligible names (including core tickers):
    eligible_names_null = sorted(
        t for t in monthly_panel.columns
        if t in eligible and t != cash
        and (trial.include_thin or not bool(thin_flags.get(t, False)))
    )

    thin = thin_history_set(cfg)
    qqqm_first_valid = px["QQQM"].first_valid_index() if "QQQM" in px.columns else pd.NaT
    n_panel_eligible = len([t for t in monthly_panel.columns if t in eligible])

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

        lt = float(left_tail.get(decision_date, float("nan")))
        lt_med = float(lt_median.get(decision_date, float("nan")))
        skew_val = float(skew_series.get(decision_date, float("nan")))
        g, binding = skewness_gate(lt, lt_med, g_min=trial.g_min)
        f_tilde = float(f) * float(g)

        w = target_weights(base, cash, f_tilde)
        w_book2 = target_weights(base, cash, f)

        gross = portfolio_month_return(me_ret, eval_date, w)
        if not np.isfinite(gross):
            continue
        book2_gross = portfolio_month_return(me_ret, eval_date, w_book2)
        option_a = portfolio_month_return(me_ret, eval_date, pd.Series({**base, cash: 0.0}, dtype=float))

        # EW / MinVar / ERC nulls from monthly panel
        hist = monthly_panel.loc[monthly_panel.index <= decision_date]
        # tickers with full non-NaN history in the available window
        cov_lb = min(trial.cov_lookback_months, len(hist))
        win = hist.iloc[-cov_lb:] if cov_lb > 0 else hist
        tickers_null = [
            t for t in eligible_names_null
            if t in win.columns
            and win[t].notna().sum() >= max(3, cov_lb // 2)
        ]
        n_null = len(tickers_null)

        r_ew = float("nan")
        r_minvar = float("nan")
        r_erc = float("nan")

        if n_null >= trial.min_names or n_null >= 3:
            ret_row = monthly_panel.loc[eval_date] if eval_date in monthly_panel.index else None
            if ret_row is not None:
                w_ew_arr = _ew_weights(tickers_null)
                r_ew_raw = _port_ret_from_weights(ret_row, w_ew_arr, tickers_null)
                r_ew = r_ew_raw if np.isfinite(r_ew_raw) else float("nan")

                if n_null >= 3:
                    win_sub = win[tickers_null].dropna(how="any")
                    if len(win_sub) >= max(3, n_null):
                        try:
                            cov_mat = _ledoit_wolf_cov(win_sub.to_numpy())
                            w_mv = _lw_minvar(cov_mat, n_null)
                            r_minvar = _port_ret_from_weights(ret_row, w_mv, tickers_null)
                        except Exception:
                            r_minvar = float("nan")
                        try:
                            if not np.isfinite(r_minvar):
                                cov_mat_e = _sample_cov(win_sub.to_numpy())
                            else:
                                cov_mat_e = cov_mat  # reuse
                            w_erc_arr = _erc(cov_mat_e, n_null)
                            r_erc = _port_ret_from_weights(ret_row, w_erc_arr, tickers_null)
                        except Exception:
                            r_erc = float("nan")

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
            "left_tail_score": lt,
            "lt_median": lt_med,
            "skew": skew_val,
            "skew_estimator": trial.skew_estimator,
            "left_tail_rule": trial.left_tail_rule,
            "sigma_hat": float(sh),
            "sigma_star": float(ss),
            "lookback": trial.lookback,
            "skew_lookback_months": trial.skew_lookback_months,
            "g_min": trial.g_min,
            "f_min": trial.f_min,
            "f_max": trial.f_max,
            "cash_ticker": cash,
            "cash_price_source": "prices" if not cash_price_missing else "zero_return_proxy_rf0",
            "thin_history_tickers": ",".join(sorted(set(base) & thin)),
            "n_panel_names_eligible": n_panel_eligible,
            "n_null_names": n_null,
            "qqqm_first_valid": qqqm_first_valid.date().isoformat() if pd.notna(qqqm_first_valid) else "",
            "turnover": turnover,
            "cost_return": cost,
        }
        for t, val in w.items():
            row[f"w_{t}"] = float(val)
        weight_rows.append(row)

        return_rows.append({
            "date": eval_date,
            "decision_date": decision_date,
            "trial_id": trial.trial_id,
            "r_method": net,
            "r_method_gross": gross,
            "cost_return": cost,
            "r_null_a": net_b2,          # unconditional Book-2 VT (PRIMARY)
            "r_null_b": option_a,         # static Option A
            "r_null_c": r_ew,             # EW
            "r_null_d": r_minvar,         # LW MinVar
            "r_null_e": r_erc,            # ERC
            "r_active_vs_a": net - net_b2,
            "r_active_vs_b": net - option_a,
            "r_active_vs_c": net - r_ew if np.isfinite(r_ew) else float("nan"),
            "r_active_vs_d": net - r_minvar if np.isfinite(r_minvar) else float("nan"),
            "r_active_vs_e": net - r_erc if np.isfinite(r_erc) else float("nan"),
            "turnover": turnover,
            "f": float(f),
            "g": float(g),
            "f_tilde": float(f_tilde),
            "gate_binding": bool(binding),
            "left_tail_score": lt,
            "skew": skew_val,
        })
        prev_w = w
        prev_w_book2 = w_book2

    registry = pd.DataFrame([{
        "trial_id": trial.trial_id,
        "method": "skewness_managed",
        "citation": CITATION,
        "core": trial.core,
        "apply_to": apply_to,
        "lookback": trial.lookback,
        "skew_lookback_months": trial.skew_lookback_months,
        "skew_estimator": trial.skew_estimator,
        "left_tail_rule": trial.left_tail_rule,
        "k_sigma": trial.k_sigma,
        "f_min": trial.f_min,
        "f_max": trial.f_max,
        "g_min": trial.g_min,
        "sigma_star": sigma_star_label,
        "cash_ticker": cash,
        "cost_bps_one_way": trial.cost_bps_one_way,
        "min_names": trial.min_names,
        "include_thin": trial.include_thin,
        "cov_lookback_months": trial.cov_lookback_months,
        "cash_price_source": "prices" if not cash_price_missing else "zero_return_proxy_rf0",
        "not_investment_advice": True,
        "enabled": False,
    }])
    return pd.DataFrame(weight_rows), pd.DataFrame(return_rows), registry


# ---------------------------------------------------------------------------
# Summary and state tables
# ---------------------------------------------------------------------------

def summarize_skew_managed(
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

        def _safe_nw(col: str) -> float:
            if col not in r.columns:
                return float("nan")
            return newey_west_tstat(r[col].dropna())

        # Portfolio skewness from OOS monthly returns
        oos_vals = r_m.dropna().to_numpy()
        oos_skew = float(stats.skew(oos_vals)) if len(oos_vals) >= 3 else float("nan")
        # CVaR_5 on OOS returns
        oos_cvar5 = cvar_at_level(r_m) if len(oos_vals) >= 3 else float("nan")
        # % months < 0
        pct_neg = float(np.mean(oos_vals < 0)) if len(oos_vals) >= 3 else float("nan")

        row = {
            **reg,
            "n_months": int(r_m.dropna().shape[0]),
            "start_date": r["date"].min(),
            "end_date": r["date"].max(),
            "AnnReturn": annualized_return(r_m),
            "AnnVol": annualized_vol(r_m),
            "MaxDD": max_drawdown(r_m),
            "Sharpe_rf0": sharpe,
            "OOS_skewness": oos_skew,
            "OOS_CVaR5": oos_cvar5,
            "OOS_pct_neg_months": pct_neg,
            # Book-2 VT (null_a, PRIMARY)
            "Book2_AnnReturn": annualized_return(r["r_null_a"]),
            "Book2_AnnVol": annualized_vol(r["r_null_a"]),
            "Book2_MaxDD": max_drawdown(r["r_null_a"]),
            "Book2_Sharpe_rf0": sharpe_rf0(r["r_null_a"]),
            # Static Option A (null_b)
            "OptionA_AnnReturn": annualized_return(r["r_null_b"]),
            "OptionA_AnnVol": annualized_vol(r["r_null_b"]),
            "OptionA_MaxDD": max_drawdown(r["r_null_b"]),
            "OptionA_Sharpe_rf0": sharpe_rf0(r["r_null_b"]),
            # EW (null_c)
            "EW_AnnReturn": annualized_return(r["r_null_c"]) if "r_null_c" in r.columns else float("nan"),
            "EW_Sharpe_rf0": sharpe_rf0(r["r_null_c"]) if "r_null_c" in r.columns else float("nan"),
            # LW MinVar (null_d)
            "MinVar_AnnReturn": annualized_return(r["r_null_d"]) if "r_null_d" in r.columns else float("nan"),
            "MinVar_Sharpe_rf0": sharpe_rf0(r["r_null_d"]) if "r_null_d" in r.columns else float("nan"),
            # ERC (null_e)
            "ERC_AnnReturn": annualized_return(r["r_null_e"]) if "r_null_e" in r.columns else float("nan"),
            "ERC_Sharpe_rf0": sharpe_rf0(r["r_null_e"]) if "r_null_e" in r.columns else float("nan"),
            # NW t-stats
            "NW_t_vs_Book2": _safe_nw("r_active_vs_a"),
            "NW_t_vs_OptionA": _safe_nw("r_active_vs_b"),
            "NW_t_vs_EW": _safe_nw("r_active_vs_c"),
            "NW_t_vs_MinVar": _safe_nw("r_active_vs_d"),
            "NW_t_vs_ERC": _safe_nw("r_active_vs_e"),
            "Sharpe_CI_L": ci_lo,
            "Sharpe_CI_U": ci_hi,
            "turnover_per_year": float(r["turnover"].mean() * MONTHS_PER_YEAR) if len(r) else float("nan"),
            "mean_f": float(w["f"].mean()) if not w.empty else float("nan"),
            "mean_g": float(w["g"].mean()) if not w.empty else float("nan"),
            "mean_f_tilde": float(w["f_tilde"].mean()) if not w.empty else float("nan"),
            "pct_months_gate_binding": float(w["gate_binding"].mean()) if not w.empty else float("nan"),
            "mean_left_tail_score": float(w["left_tail_score"].mean()) if "left_tail_score" in w.columns else float("nan"),
            "mean_skew": float(w["skew"].mean()) if "skew" in w.columns else float("nan"),
            "trial_count": n_trials,
            "DSR": deflated_sharpe_approx(sharpe, int(r_m.dropna().shape[0]), n_trials),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def state_table_skew(returns: pd.DataFrame) -> pd.DataFrame:
    """Gate state table: avg next-month active vs Book-2 when gate binding vs open."""
    if returns.empty or "trial_id" not in returns.columns:
        return pd.DataFrame()
    rows = []
    for trial_id, r in returns.groupby("trial_id"):
        gate_col = "gate_binding"
        if gate_col not in r.columns:
            continue
        active_col = "r_active_vs_a" if "r_active_vs_a" in r.columns else "r_method"
        for label, mask in [
            ("gate_binding", r[gate_col].astype(bool)),
            ("gate_open", ~r[gate_col].astype(bool)),
        ]:
            sub = r.loc[mask, active_col]
            rows.append({
                "trial_id": trial_id,
                "state": label,
                "avg_next_month_active_vs_book2": float(sub.mean()) if len(sub) else float("nan"),
                "hit_rate_active_positive": float((sub > 0).mean()) if len(sub) else float("nan"),
                "n_months": int(len(sub)),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Trial factory
# ---------------------------------------------------------------------------

def make_skew_managed_trials(
    *,
    lookbacks: Iterable[int],
    g_mins: Iterable[float],
    skew_estimators: Iterable[str],
    left_tail_rules: Iterable[str],
    apply_tos: Iterable[str],
    f_min: float,
    f_max: float,
    sigma_star: str | float,
    cash_ticker: str,
    cost_bps_one_way: float,
    skew_lookback_months: Iterable[int] | None = None,
    include_thin: bool = False,
    min_names: int = 100,
    core: str = "option_a",
    cov_lookback_months: int = 36,
) -> list[SkewnessManagedTrial]:
    trials: list[SkewnessManagedTrial] = []
    skew_lbs = list(skew_lookback_months) if skew_lookback_months is not None else [63]
    for lookback in lookbacks:
        for skew_lb in skew_lbs:
            for g_min in g_mins:
                for skew_est in skew_estimators:
                    for lt_rule in left_tail_rules:
                        for apply_to in apply_tos:
                            g_lab = str(g_min).replace(".", "p")
                            se_lab = skew_est.replace("_", "")
                            lt_lab = lt_rule.replace("_", "")
                            trial_id = (
                                f"SM_{apply_to}_L{int(lookback)}_SL{int(skew_lb)}_"
                                f"g{g_lab}_{se_lab}_{lt_lab}"
                            )
                            trials.append(
                                SkewnessManagedTrial(
                                    trial_id=trial_id,
                                    core=core,
                                    lookback=int(lookback),
                                    f_min=float(f_min),
                                    f_max=float(f_max),
                                    g_min=float(g_min),
                                    sigma_star=sigma_star,
                                    skew_estimator=str(skew_est),
                                    left_tail_rule=str(lt_rule),
                                    apply_to=str(apply_to),
                                    cash_ticker=cash_ticker.upper(),
                                    cost_bps_one_way=float(cost_bps_one_way),
                                    skew_lookback_months=int(skew_lb),
                                    include_thin=bool(include_thin),
                                    min_names=int(min_names),
                                    cov_lookback_months=int(cov_lookback_months),
                                )
                            )
    return trials


# ---------------------------------------------------------------------------
# Grid runner
# ---------------------------------------------------------------------------

def run_skewness_managed_grid(
    prices: pd.DataFrame,
    trials: list[SkewnessManagedTrial],
    *,
    universe_csv: str | Path,
    monthly: pd.DataFrame | None = None,
    coverage: pd.DataFrame | None = None,
    universe_config: dict | None = None,
    bootstrap_samples: int = 500,
    bootstrap_block_months: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    weight_parts: list[pd.DataFrame] = []
    return_parts: list[pd.DataFrame] = []
    registry_parts: list[pd.DataFrame] = []
    for trial in trials:
        w, r, reg = run_skewness_managed_trial(
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
    summary = summarize_skew_managed(
        returns,
        weights,
        registry,
        n_trials=len(trials),
        bootstrap_samples=bootstrap_samples,
        bootstrap_block_months=bootstrap_block_months,
    )
    states = state_table_skew(returns)
    return summary, weights, returns, registry, states
