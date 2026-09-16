"""Volatility-managed Option A research path.

Research tooling only; not investment advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml
from scipy import stats

from .prices import daily_returns
from .rotation import month_end_trading_dates
from .universe import assert_eligible, load_universe_config, load_universe_csv, thin_history_set

TRADING_DAYS_PER_YEAR = 252
MONTHS_PER_YEAR = 12
OPTION_A_WEIGHTS = {"VOO": 0.70, "QQQM": 0.20, "IJR": 0.10}
G1_WEIGHTS = {"VOO": 0.55, "QQQM": 0.20, "QUAL": 0.15, "IJR": 0.10}
CORE_WEIGHTS = {"option_a": OPTION_A_WEIGHTS, "g1": G1_WEIGHTS}


@dataclass(frozen=True)
class VolTargetTrial:
    trial_id: str
    core: str = "option_a"
    lookback: int = 63
    f_min: float = 0.25
    f_max: float = 1.0
    sigma_star: str | float = "expanding_annvol"
    cash_ticker: str = "BIL"
    cost_bps_one_way: float = 5.0


def load_vol_target_config(path: str | Path | None = None) -> dict:
    if path is None:
        candidates = [
            Path("config/vol_target.yaml"),
            Path(__file__).resolve().parents[2] / "config" / "vol_target.yaml",
        ]
        for c in candidates:
            if c.exists():
                path = c
                break
    if path is None:
        return {
            "vol_target": {
                "lookbacks": [21, 63, 252],
                "f_min": 0.25,
                "f_max": 1.0,
                "sigma_star": "expanding_annvol",
                "cash_ticker": "BIL",
                "cost_bps_one_way": 5,
            }
        }
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def core_weights(core: str) -> dict[str, float]:
    key = core.strip().lower()
    if key not in CORE_WEIGHTS:
        raise ValueError(f"unknown core {core!r}; expected one of {sorted(CORE_WEIGHTS)}")
    return dict(CORE_WEIGHTS[key])


def option_core_daily_returns(prices: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    missing = [t for t in weights if t not in prices.columns]
    if missing:
        raise ValueError(f"missing price columns for core: {missing}")
    rets = daily_returns(prices[list(weights)]).dropna(how="all")
    weighted = rets.mul(pd.Series(weights), axis=1).sum(axis=1, min_count=len(weights))
    return weighted.rename("r_core")


def realized_ann_vol_at_month_ends(
    core_daily_returns: pd.Series,
    me_dates: pd.DatetimeIndex,
    lookback: int,
) -> pd.Series:
    """Annualized rolling vol sampled at decision month-ends, using returns <= t only."""
    vol = core_daily_returns.rolling(lookback, min_periods=lookback).std(ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR)
    return vol.reindex(me_dates).ffill().rename("sigma_hat")


def expanding_sigma_star_at_month_ends(
    core_daily_returns: pd.Series,
    me_dates: pd.DatetimeIndex,
    min_periods: int,
) -> pd.Series:
    """Expanding annualized vol through t-1, sampled at month-end t."""
    exp = core_daily_returns.expanding(min_periods=min_periods).std(ddof=1).shift(1) * np.sqrt(TRADING_DAYS_PER_YEAR)
    return exp.reindex(me_dates).ffill().rename("sigma_star")


def parse_sigma_star(value: str | float | int) -> str | float:
    if isinstance(value, (float, int)):
        return float(value)
    text = str(value).strip().lower()
    if text in {"expanding", "expanding_annvol"}:
        return "expanding_annvol"
    return float(text)


def scale_factor(
    sigma_hat: float,
    sigma_star: float,
    *,
    f_min: float = 0.25,
    f_max: float = 1.0,
) -> float:
    if not np.isfinite(sigma_hat) or sigma_hat <= 0 or not np.isfinite(sigma_star) or sigma_star <= 0:
        return float("nan")
    return float(np.clip(sigma_star / sigma_hat, f_min, f_max))


def target_weights(base_weights: dict[str, float], cash_ticker: str, f: float) -> pd.Series:
    w = {t: float(v) * float(f) for t, v in base_weights.items()}
    w[cash_ticker.upper()] = max(0.0, 1.0 - float(f))
    out = pd.Series(w, dtype=float)
    total = float(out.sum())
    if not np.isfinite(total) or abs(total - 1.0) > 1e-8:
        raise ValueError(f"target weights must sum to 1, got {total}")
    return out


def half_turnover(prev_w: pd.Series | None, current_w: pd.Series) -> float:
    if prev_w is None:
        return 0.0
    return 0.5 * float(current_w.subtract(prev_w, fill_value=0.0).abs().sum())


def turnover_cost_return(turnover: float, cost_bps_one_way: float) -> float:
    return float(turnover) * float(cost_bps_one_way) / 10000.0


def portfolio_month_return(me_ret: pd.DataFrame, eval_date: pd.Timestamp, weights: pd.Series) -> float:
    vals = []
    for ticker, weight in weights.items():
        if ticker not in me_ret.columns:
            if abs(weight) > 1e-12:
                raise ValueError(f"missing monthly return for nonzero weight {ticker}")
            continue
        r = me_ret.loc[eval_date, ticker]
        if pd.isna(r):
            return float("nan")
        vals.append(float(weight) * float(r))
    return float(np.sum(vals))


def max_drawdown(returns: pd.Series) -> float:
    r = pd.Series(returns, dtype=float).dropna()
    if r.empty:
        return float("nan")
    curve = (1.0 + r).cumprod()
    dd = curve / curve.cummax() - 1.0
    return float(dd.min())


def annualized_return(returns: pd.Series) -> float:
    r = pd.Series(returns, dtype=float).dropna()
    if r.empty:
        return float("nan")
    total = float((1.0 + r).prod())
    return total ** (MONTHS_PER_YEAR / len(r)) - 1.0


def annualized_vol(returns: pd.Series) -> float:
    r = pd.Series(returns, dtype=float).dropna()
    if len(r) < 2:
        return float("nan")
    return float(r.std(ddof=1) * np.sqrt(MONTHS_PER_YEAR))


def sharpe_rf0(returns: pd.Series) -> float:
    vol = annualized_vol(returns)
    if not np.isfinite(vol) or vol <= 0:
        return float("nan")
    return float(annualized_return(returns) / vol)


def newey_west_tstat(x: pd.Series, lags: int = 3) -> float:
    vals = pd.Series(x, dtype=float).dropna().to_numpy()
    n = len(vals)
    if n < 3:
        return float("nan")
    demeaned = vals - vals.mean()
    gamma0 = float(np.dot(demeaned, demeaned) / n)
    var = gamma0
    for lag in range(1, min(lags, n - 1) + 1):
        gamma = float(np.dot(demeaned[lag:], demeaned[:-lag]) / n)
        var += 2.0 * (1.0 - lag / (lags + 1.0)) * gamma
    se = np.sqrt(max(var, 0.0) / n)
    return float(vals.mean() / se) if se > 0 else float("nan")


def block_bootstrap_sharpe_ci(
    returns: pd.Series,
    *,
    block_months: int = 3,
    n_boot: int = 1000,
    seed: int = 7,
) -> tuple[float, float]:
    vals = pd.Series(returns, dtype=float).dropna().to_numpy()
    n = len(vals)
    if n < max(4, block_months) or n_boot <= 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    starts = np.arange(0, n)
    sharpes = []
    for _ in range(n_boot):
        sampled: list[float] = []
        while len(sampled) < n:
            start = int(rng.choice(starts))
            block = vals[start : min(start + block_months, n)]
            if len(block) < block_months:
                block = np.concatenate([block, vals[: block_months - len(block)]])
            sampled.extend(block.tolist())
        sharpes.append(sharpe_rf0(pd.Series(sampled[:n])))
    lo, hi = np.nanpercentile(sharpes, [2.5, 97.5])
    return (float(lo), float(hi))


def deflated_sharpe_approx(sharpe: float, n_obs: int, n_trials: int) -> float:
    if not np.isfinite(sharpe) or n_obs < 3 or n_trials <= 1:
        return float("nan")
    expected_max_noise = stats.norm.ppf(1.0 - 1.0 / max(n_trials, 2)) / np.sqrt(max(n_obs - 1, 1))
    z = (sharpe - expected_max_noise) * np.sqrt(max(n_obs - 1, 1))
    return float(stats.norm.cdf(z))


def _monthly_price_returns(prices: pd.DataFrame, me_dates: pd.DatetimeIndex, cash_ticker: str) -> pd.DataFrame:
    me_px = prices.reindex(me_dates)
    me_ret = me_px.pct_change()
    if cash_ticker not in me_ret.columns or me_ret[cash_ticker].isna().all():
        me_ret[cash_ticker] = 0.0
    return me_ret


def _assert_trial_eligible(
    trial: VolTargetTrial,
    weights: dict[str, float],
    universe_csv: str | Path,
    universe_config: dict | None = None,
) -> None:
    uni_df = load_universe_csv(universe_csv)
    cfg = universe_config or load_universe_config()
    assert_eligible([*weights.keys(), trial.cash_ticker], uni_df, cfg)


def run_vol_target_trial(
    prices: pd.DataFrame,
    trial: VolTargetTrial,
    *,
    universe_csv: str | Path,
    universe_config: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return monthly weights, OOS returns, and one-row registry for a trial."""
    cash = trial.cash_ticker.upper()
    base = core_weights(trial.core)
    _assert_trial_eligible(trial, base, universe_csv, universe_config)

    need_cols = list(dict.fromkeys([*base.keys(), cash]))
    px = prices.copy()
    missing_core = [t for t in base if t not in px.columns]
    if missing_core:
        raise ValueError(f"missing price columns for core: {missing_core}")
    cash_price_missing = cash not in px.columns
    if cash_price_missing:
        px[cash] = np.nan

    me_dates = month_end_trading_dates(px[list(base)])
    me_ret = _monthly_price_returns(px[need_cols], me_dates, cash)
    core_daily = option_core_daily_returns(px, base)
    sigma_hat = realized_ann_vol_at_month_ends(core_daily, me_dates, trial.lookback)
    sigma_star_spec = parse_sigma_star(trial.sigma_star)
    if sigma_star_spec == "expanding_annvol":
        sigma_star_series = expanding_sigma_star_at_month_ends(core_daily, me_dates, trial.lookback)
        sigma_star_label = "expanding_annvol"
    else:
        sigma_star_series = pd.Series(float(sigma_star_spec), index=me_dates, name="sigma_star")
        sigma_star_label = f"{float(sigma_star_spec):.4f}"

    weight_rows: list[dict] = []
    return_rows: list[dict] = []
    prev_w: pd.Series | None = None
    thin = thin_history_set(universe_config)
    qqqm_first_valid = px["QQQM"].first_valid_index() if "QQQM" in px.columns else pd.NaT

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

        w = target_weights(base, cash, f)
        gross = portfolio_month_return(me_ret, eval_date, w)
        if not np.isfinite(gross):
            continue
        option_w = pd.Series({**base, cash: 0.0}, dtype=float)
        option_a = portfolio_month_return(me_ret, eval_date, option_w)
        turnover = half_turnover(prev_w, w)
        cost = turnover_cost_return(turnover, trial.cost_bps_one_way)
        net = gross - cost

        row = {
            "date": decision_date,
            "eval_date": eval_date,
            "trial_id": trial.trial_id,
            "core": trial.core,
            "f": f,
            "sigma_hat": float(sh),
            "sigma_star": float(ss),
            "lookback": trial.lookback,
            "f_min": trial.f_min,
            "f_max": trial.f_max,
            "cash_ticker": cash,
            "cash_price_source": "prices" if not cash_price_missing else "zero_return_proxy_rf0",
            "thin_history_tickers": ",".join(sorted(set(base) & thin)),
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
                "r_vt_gross": gross,
                "cost_return": cost,
                "r_vt": net,
                "r_option_a": option_a,
                "r_active": net - option_a,
                "turnover": turnover,
                "f": f,
            }
        )
        prev_w = w

    registry = pd.DataFrame(
        [
            {
                "trial_id": trial.trial_id,
                "core": trial.core,
                "lookback": trial.lookback,
                "f_min": trial.f_min,
                "f_max": trial.f_max,
                "sigma_star": sigma_star_label,
                "cash_ticker": cash,
                "cost_bps_one_way": trial.cost_bps_one_way,
                "cash_price_source": "prices" if not cash_price_missing else "zero_return_proxy_rf0",
                "method": "target_vol_scale_down",
                "not_investment_advice": True,
            }
        ]
    )
    return pd.DataFrame(weight_rows), pd.DataFrame(return_rows), registry


def summarize_trial(
    returns: pd.DataFrame,
    weights: pd.DataFrame,
    registry: pd.DataFrame,
    *,
    n_trials: int = 1,
    bootstrap_samples: int = 1000,
    bootstrap_block_months: int = 3,
) -> pd.DataFrame:
    if returns.empty or "trial_id" not in returns.columns:
        return pd.DataFrame()
    rows = []
    for trial_id, r in returns.groupby("trial_id"):
        w = weights[weights["trial_id"].eq(trial_id)]
        reg = registry[registry["trial_id"].eq(trial_id)].iloc[0].to_dict()
        r_vt = r["r_vt"]
        r_b = r["r_option_a"]
        ci_lo, ci_hi = block_bootstrap_sharpe_ci(
            r_vt,
            block_months=bootstrap_block_months,
            n_boot=bootstrap_samples,
        )
        sharpe = sharpe_rf0(r_vt)
        row = {
            **reg,
            "n_months": int(r_vt.dropna().shape[0]),
            "start_date": r["date"].min(),
            "end_date": r["date"].max(),
            "AnnReturn": annualized_return(r_vt),
            "AnnVol": annualized_vol(r_vt),
            "MaxDD": max_drawdown(r_vt),
            "Sharpe_rf0": sharpe,
            "OptionA_AnnReturn": annualized_return(r_b),
            "OptionA_AnnVol": annualized_vol(r_b),
            "OptionA_MaxDD": max_drawdown(r_b),
            "OptionA_Sharpe_rf0": sharpe_rf0(r_b),
            "NW_t_vs_OptionA": newey_west_tstat(r["r_active"]),
            "Sharpe_CI_L": ci_lo,
            "Sharpe_CI_U": ci_hi,
            "turnover_per_year": float(r["turnover"].mean() * MONTHS_PER_YEAR) if len(r) else np.nan,
            "mean_f": float(w["f"].mean()) if not w.empty else np.nan,
            "pct_months_f_lt_1": float((w["f"] < 1.0 - 1e-12).mean()) if not w.empty else np.nan,
            "trial_count": n_trials,
            "DSR": deflated_sharpe_approx(sharpe, int(r_vt.dropna().shape[0]), n_trials),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def regime_table(returns: pd.DataFrame) -> pd.DataFrame:
    if returns.empty or "trial_id" not in returns.columns:
        return pd.DataFrame()
    rows = []
    for trial_id, r in returns.groupby("trial_id"):
        for label, mask in [("f_lt_1", r["f"] < 1.0 - 1e-12), ("f_eq_1", r["f"] >= 1.0 - 1e-12)]:
            sub = r.loc[mask, "r_active"]
            rows.append(
                {
                    "trial_id": trial_id,
                    "regime": label,
                    "avg_next_month_active_return": float(sub.mean()) if len(sub) else np.nan,
                    "hit_rate_active_positive": float((sub > 0).mean()) if len(sub) else np.nan,
                    "n_months": int(len(sub)),
                }
            )
    return pd.DataFrame(rows)


def make_trials(
    *,
    cores: Iterable[str],
    lookbacks: Iterable[int],
    sigma_stars: Iterable[str | float],
    f_min: float,
    f_max: float,
    cash_ticker: str,
    cost_bps_one_way: float,
) -> list[VolTargetTrial]:
    trials = []
    for core in cores:
        for lookback in lookbacks:
            for sigma_star in sigma_stars:
                label = str(sigma_star).replace("expanding_annvol", "expanding").replace(".", "p")
                trial_id = f"VT_{core}_L{int(lookback)}_sig{label}_fmax{str(f_max).replace('.', 'p')}"
                trials.append(
                    VolTargetTrial(
                        trial_id=trial_id,
                        core=core,
                        lookback=int(lookback),
                        f_min=float(f_min),
                        f_max=float(f_max),
                        sigma_star=sigma_star,
                        cash_ticker=cash_ticker.upper(),
                        cost_bps_one_way=float(cost_bps_one_way),
                    )
                )
    return trials


def run_vol_target_grid(
    prices: pd.DataFrame,
    trials: list[VolTargetTrial],
    *,
    universe_csv: str | Path,
    universe_config: dict | None = None,
    bootstrap_samples: int = 1000,
    bootstrap_block_months: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    weight_parts = []
    return_parts = []
    registry_parts = []
    for trial in trials:
        w, r, reg = run_vol_target_trial(prices, trial, universe_csv=universe_csv, universe_config=universe_config)
        weight_parts.append(w)
        return_parts.append(r)
        registry_parts.append(reg)
    weights = pd.concat(weight_parts, ignore_index=True) if weight_parts else pd.DataFrame()
    returns = pd.concat(return_parts, ignore_index=True) if return_parts else pd.DataFrame()
    registry = pd.concat(registry_parts, ignore_index=True) if registry_parts else pd.DataFrame()
    summary = summarize_trial(
        returns,
        weights,
        registry,
        n_trials=len(trials),
        bootstrap_samples=bootstrap_samples,
        bootstrap_block_months=bootstrap_block_months,
    )
    regimes = regime_table(returns)
    return summary, weights, returns, registry, regimes
