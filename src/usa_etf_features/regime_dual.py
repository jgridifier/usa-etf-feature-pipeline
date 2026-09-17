"""Regime-conditioned category research; not investment advice or a paper replication.

K=2 KMeans is a transparent approximation to the cited architecture. Categories
come from a static research universe (survivorship bias remains). Membership uses
history known before each sleeve return, never final coverage counts. Missing
held returns invalidate that month's portfolio return; they are not zero-filled.
"""
from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.covariance import LedoitWolf
from threadpoolctl import threadpool_limits

from .portfolio import risk_parity_weights
from .vol_target import annualized_return, deflated_sharpe_approx, max_drawdown, sharpe_rf0

# Deliberate, editable economic classification; unknown and leveraged categories
# are excluded from conditional policies. Nulls include every available sleeve.
# Value and metals are defensive candidates, not guaranteed crisis hedges. Credit
# is calm-only by default. Structured products are calm-only; crypto is opt-in.
REGIME_ELIGIBILITY = {
    "stress": (
        "US Treasuries / Govt / Cash-like", "Core / Aggregate Bonds",
        "TIPS / Inflation-Linked", "Municipal Bonds", "Commodities / Metals",
        "US Large Value",
    ),
    "calm": (
        "US Large / Broad Blend", "US Large Growth / Tech-tilt", "US Large Value",
        "US Mid Blend", "US Mid Growth", "US Mid Value", "US Small Blend",
        "US Small Growth", "US Small Value", "International Developed Equity",
        "International EM Equity", "Global Equity (incl US)", "Specialty / Other",
        "Defined Outcome / Buffer / Structured", "Sector / Factor / Thematic",
        "High Yield Credit", "Investment Grade Credit", "REITs / Real Estate",
        "Multi-Asset / Allocation", "Preferred / Hybrid Income", "EM Debt",
        "Other Fixed Income",
    ),
}
# Frozen before evaluation: 1 K x 2 feature sets x 2 allocators = 4 trials.
TRIAL_GRID = tuple(product((2,), ("vol_corr", "vol_corr_spread"), ("erc", "ew")))
DEFAULT_DATA_DIR = Path("/workspace/investments")
DISCLAIMER = "Research only; not investment advice."


def build_category_sleeves(
    panel: pd.DataFrame, categorized: pd.DataFrame, min_name_months: int = 12,
) -> pd.DataFrame:
    """EW among names qualified through t-1; skip missing returns and empty months."""
    if min_name_months < 1:
        raise ValueError("min_name_months must be positive")
    cats = categorized[["Ticker", "Category"]].drop_duplicates("Ticker").set_index("Ticker")["Category"]
    panel = panel.sort_index().astype(float)
    eligible = panel.notna().cumsum().shift(1, fill_value=0).ge(min_name_months)
    qualified = panel.where(eligible)
    return pd.DataFrame({cat: qualified[names].mean(axis=1) for cat in cats.unique()
                         if (names := [n for n in cats.index[cats.eq(cat)] if n in panel])})


def regime_features(
    sleeves: pd.DataFrame, *, vol_window: int = 6, corr_window: int = 12,
    eligibility: dict | None = None,
) -> pd.DataFrame:
    """Trailing features at t, for use only in allocations effective after t."""
    if min(vol_window, corr_window) < 2:
        raise ValueError("feature windows must be at least two months")
    eligibility = eligibility or REGIME_ELIGIBILITY
    market = sleeves.mean(axis=1)
    vol = market.rolling(vol_window).std() * np.sqrt(12)
    corr = []
    for i in range(len(sleeves)):
        window = sleeves.iloc[max(0, i + 1 - corr_window):i + 1]
        matrix = window.corr(min_periods=corr_window).to_numpy()
        pairs = matrix[np.triu_indices_from(matrix, k=1)]
        corr.append(float(np.nanmean(pairs)) if np.isfinite(pairs).any() else np.nan)
    defensive = sleeves.reindex(columns=[c for c in eligibility["stress"] if c in sleeves]).mean(axis=1)
    cyclical = sleeves.reindex(columns=[c for c in eligibility["calm"] if c in sleeves]).mean(axis=1)
    spread = (defensive - cyclical).rolling(vol_window).mean()
    return pd.DataFrame({"vol": vol, "corr": corr, "spread": spread}, index=sleeves.index)


def fit_regime(history: pd.DataFrame, decision_date: pd.Timestamp) -> str:
    """Fit and standardize exclusively on the supplied past; anchor stress by vol."""
    if history.index.max() > decision_date:
        raise ValueError("regime training window extends beyond decision")
    scale = history.std().replace(0, 1).fillna(1)
    x = (history - history.mean()) / scale
    if len(x.drop_duplicates()) < 2:
        return "calm"
    with threadpool_limits(limits=1):
        model = KMeans(n_clusters=2, n_init=5, random_state=42).fit(x.to_numpy())
        label = model.predict(x.iloc[[-1]].to_numpy())[0]
    stress = history["vol"].groupby(model.labels_).mean().idxmax()
    return "stress" if label == stress else "calm"


def allocation(history: pd.DataFrame, names: list[str], allocator: str) -> pd.Series:
    if not names:
        raise ValueError("no eligible sleeves with enough history")
    if allocator == "ew":
        return pd.Series(1 / len(names), index=names)
    # Mean imputation is restricted to estimation history; never fill OOS returns.
    x = history[names].fillna(history[names].mean())
    cov = LedoitWolf().fit(x.to_numpy()).covariance_
    # Normalize covariance scale because the shared optimizer has absolute tolerance.
    cov = cov / max(float(np.diag(cov).mean()), 1e-12) + np.eye(len(names)) * 1e-8
    return risk_parity_weights(pd.DataFrame(cov, index=names, columns=names), names, max_weight=1.0)


def run_regime_dual(
    sleeves: pd.DataFrame, *, k: int = 2, fit_mode: str = "expanding",
    min_history_months: int = 36, rolling_window: int = 60,
    vol_window: int = 6, corr_window: int = 12, cov_window: int = 36,
    eligibility: dict | None = None, crypto_calm: bool = False,
) -> dict[str, pd.DataFrame]:
    """Run the predeclared grid and three nulls on identical decision dates.

    Always-calm uses ERC. DSR uses monthly Sharpe, matching monthly observation
    count; displayed Sharpe is annualized. Nulls receive the same trial penalty.
    Turnover is half L1 versus drifted prior holdings; returns are gross of costs.
    Ex-post stress (bottom market-return quintile) is diagnostics only.
    """
    if k != 2 or fit_mode not in {"expanding", "rolling"}:
        raise ValueError("only K=2 and expanding/rolling fits are registered")
    if (min_history_months < 2 or cov_window < 2
            or (fit_mode == "rolling" and rolling_window < min_history_months)):
        raise ValueError("invalid history or rolling/covariance window")
    sleeves = sleeves.sort_index().astype(float)
    if not isinstance(sleeves.index, pd.DatetimeIndex) or sleeves.index.has_duplicates:
        raise ValueError("sleeves require unique datetime index")
    if sleeves.index.to_period("M").duplicated().any():
        raise ValueError("sleeves require one row per month")
    if np.isinf(sleeves.to_numpy()).any():
        raise ValueError("infinite returns are invalid")
    eligibility = {s: tuple(v) for s, v in (eligibility or REGIME_ELIGIBILITY).items()}
    if crypto_calm:
        eligibility["calm"] += ("Crypto / Digital Assets",)
    features = regime_features(sleeves, vol_window=vol_window, corr_window=corr_window, eligibility=eligibility)
    trials = [(f"k{k}_{f}_{a}", f, a, "dual") for k, f, a in TRIAL_GRID]
    trials += [("unconditional_erc", "vol_corr_spread", "erc", "all"),
               ("unconditional_ew", "vol_corr_spread", "ew", "all"),
               ("always_calm", "vol_corr_spread", "erc", "calm")]
    weights, returns, states = [], [], []
    previous: dict[str, pd.Series] = {}
    for i, decision in enumerate(sleeves.index[:-1]):
        nxt = sleeves.index[i + 1]
        if nxt.to_period("M") != decision.to_period("M") + 1:
            continue
        past = features.loc[:decision].dropna()
        if fit_mode == "rolling":
            past = features.loc[:decision].tail(rolling_window).dropna()
        if len(past) < min_history_months or past.index[-1] != decision:
            continue
        history = sleeves.loc[:decision].tail(cov_window)
        available = history.columns[history.count().ge(min(12, cov_window)) & history.iloc[-1].notna()].tolist()
        selected = {s: [c for c in available if c in eligibility[s]] for s in ("calm", "stress")}
        if not all(selected.values()):
            continue
        labels = {}
        for f in ("vol_corr", "vol_corr_spread"):
            cols = ["vol", "corr"] + (["spread"] if f.endswith("spread") else [])
            labels[f] = fit_regime(past[cols], decision)
            states.append(dict(decision_date=decision, feature_end=decision, date=nxt,
                               feature_set=f, regime=labels[f], fit_start=past.index[0], fit_end=past.index[-1]))
        cache = {}
        for trial_id, f, allocator, policy in trials:
            regime = labels[f] if policy == "dual" else policy
            names = available if policy == "all" else selected[regime]
            key = (tuple(names), allocator)
            if key not in cache:
                cache[key] = allocation(history, names, allocator)
            w = cache[key]
            turnover = 0.5 * w.subtract(previous.get(trial_id, pd.Series(dtype=float)), fill_value=0).abs().sum()
            realized = sleeves.loc[nxt, names]
            r = float((w * realized).sum()) if realized.notna().all() else np.nan
            meta = dict(trial_id=trial_id, decision_date=decision, feature_end=decision, date=nxt, regime=regime)
            returns.append(dict(**meta, **{"return": r}, turnover=turnover,
                                missing_held_returns=int(realized.isna().sum())))
            weights.extend(dict(**meta, asset=n, weight=float(v)) for n, v in w.items())
            previous[trial_id] = w * (1 + realized) / (1 + r) if np.isfinite(r) and r > -1 else w
    if not returns:
        raise ValueError("no OOS decisions; require more history and both eligible category sets")
    ret = pd.DataFrame(returns)
    market = sleeves.mean(axis=1).reindex(ret.date.unique())
    stress_dates = market.index[market.le(market.quantile(0.2))]
    ret["ex_post_stress"] = ret.date.isin(stress_dates)
    summary = []
    for trial_id, f, allocator, policy in trials:
        sub = ret.loc[ret.trial_id.eq(trial_id)]
        r = sub["return"].dropna()
        stress_r = sub.loc[sub.ex_post_stress, "return"].dropna()
        sr = sharpe_rf0(r)
        summary.append(dict(trial_id=trial_id, K=k, feature_set=f, allocator=allocator,
                            fit_mode=fit_mode, policy=policy, trial_count=len(TRIAL_GRID),
                            DSR=deflated_sharpe_approx(sr / np.sqrt(12), len(r), len(TRIAL_GRID)),
                            Sharpe=sr, AnnReturn=annualized_return(r), MaxDD=max_drawdown(r),
                            n_months=len(r), missing_months=int(sub["return"].isna().sum()),
                            stress_months=len(stress_r), stress_Sharpe=sharpe_rf0(stress_r),
                            stress_mean_return=stress_r.mean(), stress_total_return=(1 + stress_r).prod() - 1,
                            turnover_per_year=sub.turnover.mean() * 12))
    state = pd.DataFrame(states)
    diag = []
    for f, sub in state.groupby("feature_set"):
        counts = pd.crosstab(sub.regime.shift(), sub.regime).reindex(index=["calm", "stress"], columns=["calm", "stress"], fill_value=0)
        for origin, dest in product(("calm", "stress"), repeat=2):
            total = counts.loc[origin].sum()
            diag.append(dict(feature_set=f, state=origin, next_state=dest,
                             occupancy=float(sub.regime.eq(origin).mean()),
                             transition_count=int(counts.loc[origin, dest]),
                             transition_probability=counts.loc[origin, dest] / total if total else np.nan))
    result = {"monthly_weights": pd.DataFrame(weights), "oos_returns": ret,
              "summary": pd.DataFrame(summary), "trial_registry": pd.DataFrame(summary).iloc[:len(TRIAL_GRID)].copy(),
              "states": state, "diagnostics": pd.DataFrame(diag)}
    for frame in result.values():
        frame["research_disclaimer"] = DISCLAIMER
    return result


def load_and_run(params: dict[str, Any], asof: pd.Timestamp | None = None) -> dict[str, pd.DataFrame]:
    """Read external inputs; snapshot coverage flags are diagnostics only."""
    if params.get("name_level", False):
        raise ValueError("name_level is not implemented; this research uses category sleeves")
    def path(key: str, filename: str) -> Path:
        return Path(params.get(key, DEFAULT_DATA_DIR / filename))
    panel = pd.read_csv(path("panel_returns_path", "usa_universe_panel_monthly_returns.csv"), index_col=0, parse_dates=True)
    # The source uses final trading dates and may end with an incomplete month.
    complete = ((panel.index.to_period("M") < panel.index.max().to_period("M"))
                | panel.index.is_month_end
                | (panel.index + pd.offsets.BMonthEnd(0) == panel.index))
    panel = panel.loc[complete]
    panel.index = panel.index.to_period("M").to_timestamp("M")
    if asof is not None:
        panel = panel.loc[:asof]
    categorized = pd.read_csv(path("categorized_path", "usa_universe_categorized.csv"), usecols=["Ticker", "Category"])
    coverage = pd.read_csv(path("coverage_path", "usa_universe_panel_history_coverage.csv"), usecols=["ticker", "thin_lt5y"])
    sleeves = build_category_sleeves(panel, categorized, int(params.get("min_name_months", 12)))
    keys = ("k", "fit_mode", "min_history_months", "rolling_window", "vol_window", "corr_window", "cov_window", "eligibility", "crypto_calm")
    result = run_regime_dual(sleeves, **{key: params[key] for key in keys if key in params})
    thin = coverage.thin_lt5y.astype(str).str.lower().eq("true")
    result["diagnostics"]["thin_history_tickers"] = ",".join(sorted(set(coverage.loc[thin, "ticker"]) & set(panel.columns)))
    result["diagnostics"]["coverage_note"] = "Snapshot flags only; not used for historical selection"
    return result
