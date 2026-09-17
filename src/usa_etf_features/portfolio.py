"""Growth-mode portfolio construction, rotation sleeve, and M3 optimizers.

Research tooling only — not investment advice.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import optimize
from sklearn.covariance import LedoitWolf

from .rotation import (
    assert_rotate_tickers_eligible,
    compute_rotation_signals,
    load_portfolio_constraints,
    month_end_trading_dates,
    signal_on_asof,
)
from .universe import UniverseGateError, assert_eligible, load_universe_config, load_universe_csv


CORE_TICKERS = ["VOO", "QQQM", "IJR"]
DEFAULT_THEMATIC_TICKERS = ["XSD", "XBI", "LOUP", "GTEK", "GINN", "BBC", "GVIP"]
DEFAULT_FACTOR_TICKERS = ["QUAL", "USMV", "VLUE", "GSEW"]
DEFAULT_SIZE_GROWTH_TICKERS = ["IWP", "IWO", "IJK", "IJT", "VIOG", "VXF"]
DEFAULT_SATELLITE_TICKERS = (
    DEFAULT_FACTOR_TICKERS
    + DEFAULT_SIZE_GROWTH_TICKERS
    + DEFAULT_THEMATIC_TICKERS
    + ["IWM", "VTI", "QQQ", "VEA", "EEM"]
)
TURNOVER_COST_BPS = 5.0


def proportional_core_trim(
    core: dict[str, float],
    thematic_weights: dict[str, float],
) -> dict[str, float]:
    """
    Fund thematic sleeve by trimming core proportionally:
      w_i^core = CORE_i * (1 - sum w_thematic)
    Raises if thematic sum exceeds 1 or individual caps are violated by caller.
    """
    thematic_sum = float(sum(thematic_weights.values()))
    if thematic_sum < -1e-12:
        raise ValueError("thematic weights must be non-negative")
    if thematic_sum > 1.0 + 1e-9:
        raise ValueError(f"thematic sum {thematic_sum} exceeds 1.0")
    scale = 1.0 - thematic_sum
    out = {k: float(v) * scale for k, v in core.items()}
    for t, w in thematic_weights.items():
        out[t] = out.get(t, 0.0) + float(w)
    return out


def enforce_thematic_caps(
    thematic_weights: dict[str, float],
    thematic_cap: float = 0.25,
    single_cap: float = 0.15,
) -> dict[str, float]:
    """Clip single-name thematic weights and rescale sleeve to thematic_cap if needed."""
    w = {k: max(0.0, float(v)) for k, v in thematic_weights.items()}
    for k in list(w):
        if w[k] > single_cap + 1e-12:
            w[k] = single_cap
    s = sum(w.values())
    if s > thematic_cap + 1e-12 and s > 0:
        scale = thematic_cap / s
        w = {k: v * scale for k, v in w.items()}
    return w


def validate_weights(
    weights: dict[str, float],
    thematic_tickers: set[str],
    thematic_cap: float = 0.25,
    single_thematic_cap: float = 0.15,
    tol: float = 1e-8,
) -> None:
    s = sum(weights.values())
    if abs(s - 1.0) > tol:
        raise ValueError(f"weights must sum to 1 (±{tol}), got {s}")
    for t, w in weights.items():
        if w < -tol:
            raise ValueError(f"negative weight for {t}: {w}")
        if t.upper() in thematic_tickers and w > single_thematic_cap + tol:
            raise ValueError(f"thematic single-name cap {single_thematic_cap} breached by {t}={w}")
    them_sum = sum(w for t, w in weights.items() if t.upper() in thematic_tickers)
    if them_sum > thematic_cap + tol:
        raise ValueError(f"thematic sleeve cap {thematic_cap} breached: {them_sum}")


def build_rotated_portfolio(
    prices: pd.DataFrame,
    *,
    constraints: dict | None = None,
    asof: pd.Timestamp | None = None,
    use_vol_gate: bool = True,
    hysteresis_months: int | None = None,
    universe_df: pd.DataFrame | None = None,
    universe_config: dict | None = None,
    rotate_eligible: list[str] | None = None,
) -> pd.DataFrame:
    """
    Option-A core + rotate-in thematic sleeve (default eligible: XSD).

    When all thematic OFF → core_when_thematic_off.
    When ON → proportional core trim funding rotate_on_weight (capped).
    """
    cfg = constraints or load_portfolio_constraints()
    core = {k.upper(): float(v) for k, v in cfg.get("core_when_thematic_off", {}).items()}
    if abs(sum(core.values()) - 1.0) > 1e-8:
        raise ValueError("core_when_thematic_off must sum to 1")

    eligible = [t.upper() for t in (rotate_eligible or cfg.get("thematic_rotate_eligible", ["XSD"]))]
    assert_rotate_tickers_eligible(eligible, universe_df, universe_config)

    thematic_set = {t.upper() for t in cfg.get("thematic_tickers", eligible)}
    thematic_cap = float(cfg.get("thematic_cap", 0.25))
    single_cap = float(cfg.get("single_name_cap_thematic", 0.15))
    on_w = min(float(cfg.get("rotate_on_weight", 0.10)), single_cap)
    bench = str(cfg.get("rotate_benchmark", "VOO")).upper()
    hyst = cfg.get("hysteresis_months", 2) if hysteresis_months is None else hysteresis_months
    vol_q = float(cfg.get("vol_gate_quantile", 0.90))
    vol_mp = int(cfg.get("vol_gate_min_periods", 21))

    thematic_w: dict[str, float] = {}
    signal_rows: list[dict[str, Any]] = []
    for t in eligible:
        on = signal_on_asof(
            prices,
            t,
            asof=asof,
            benchmark=bench,
            use_vol_gate=use_vol_gate,
            hysteresis_months=int(hyst or 0),
            vol_quantile=vol_q,
            vol_min_periods=vol_mp,
        )
        thematic_w[t] = on_w if on else 0.0
        signal_rows.append({"ticker": t, "rotate_on": bool(on), "target_weight": thematic_w[t]})

    thematic_w = enforce_thematic_caps(thematic_w, thematic_cap=thematic_cap, single_cap=single_cap)
    # Zero out tiny remnants
    thematic_w = {k: v for k, v in thematic_w.items() if v > 1e-12}

    weights = proportional_core_trim(core, thematic_w)
    validate_weights(weights, thematic_set, thematic_cap=thematic_cap, single_thematic_cap=single_cap)

    rows = []
    on_map = {r["ticker"]: r["rotate_on"] for r in signal_rows}
    for t, w in weights.items():
        role = "thematic" if t in thematic_set else "core"
        rows.append(
            {
                "ticker": t,
                "weight": w,
                "role": role,
                "rotate_on": on_map.get(t, False) if role == "thematic" else False,
                "thesis_tag": "rotate_thematic" if role == "thematic" and w > 0 else (
                    "core_option_a" if role == "core" else "thematic_off"
                ),
                "mode": "growth_rotate",
            }
        )
    # Include eligible thematics at 0 for auditability when OFF
    present = {r["ticker"] for r in rows}
    for t in eligible:
        if t not in present:
            rows.append(
                {
                    "ticker": t,
                    "weight": 0.0,
                    "role": "thematic",
                    "rotate_on": on_map.get(t, False),
                    "thesis_tag": "thematic_off",
                    "mode": "growth_rotate",
                }
            )
    out = pd.DataFrame(rows).sort_values(["role", "weight"], ascending=[True, False]).reset_index(drop=True)
    return out


def build_static_from_scores(
    scores: pd.DataFrame,
    *,
    constraints: dict | None = None,
    n_holdings: int | None = None,
) -> pd.DataFrame:
    """
    Simple static growth sleeve from ranked scores (no rotate).
    Takes top-N by S_i with thematic/single caps; renormalizes to 1.
    """
    cfg = constraints or load_portfolio_constraints()
    thematic_set = {t.upper() for t in cfg.get("thematic_tickers", [])}
    thematic_cap = float(cfg.get("thematic_cap", 0.25))
    single_them = float(cfg.get("single_name_cap_thematic", 0.15))
    single_core = float(cfg.get("single_name_cap_core", 0.40))
    card_min = int(cfg.get("cardinality_min", 4))
    card_max = int(cfg.get("cardinality_max", 8))
    n = n_holdings or card_max
    n = max(card_min, min(n, card_max))

    df = scores.copy()
    if "ticker" not in df.columns:
        df = df.reset_index().rename(columns={"index": "ticker"})
    df["ticker"] = df["ticker"].astype(str).str.upper()
    if "S_i" not in df.columns:
        raise ValueError("scores must include S_i")
    df = df.sort_values("S_i", ascending=False)

    picked: list[str] = []
    them_w = 0.0
    for _, row in df.iterrows():
        if len(picked) >= n:
            break
        t = row["ticker"]
        is_them = t in thematic_set
        if is_them and them_w >= thematic_cap - 1e-12:
            continue
        picked.append(t)
        if is_them:
            # equal-weight later; reserve room
            them_w += single_them  # provisional

    if not picked:
        raise ValueError("no holdings selected from scores")

    # Equal weight then clip caps and renormalize
    w = {t: 1.0 / len(picked) for t in picked}
    for _ in range(8):
        for t in list(w):
            cap = single_them if t in thematic_set else single_core
            if w[t] > cap:
                w[t] = cap
        them_sum = sum(v for t, v in w.items() if t in thematic_set)
        if them_sum > thematic_cap:
            scale = thematic_cap / them_sum
            for t in list(w):
                if t in thematic_set:
                    w[t] *= scale
        s = sum(w.values())
        if s <= 0:
            raise ValueError("weights collapsed")
        w = {t: v / s for t, v in w.items()}
        # Check feasibility
        ok = all(
            (w[t] <= (single_them if t in thematic_set else single_core) + 1e-9) for t in w
        ) and sum(v for t, v in w.items() if t in thematic_set) <= thematic_cap + 1e-9
        if ok and abs(sum(w.values()) - 1.0) < 1e-8:
            break

    # Final hard clip for float residue then renorm
    for t in list(w):
        cap = single_them if t in thematic_set else single_core
        w[t] = min(w[t], cap)
    them_sum = sum(v for t, v in w.items() if t in thematic_set)
    if them_sum > thematic_cap:
        scale = thematic_cap / them_sum
        for t in list(w):
            if t in thematic_set:
                w[t] *= scale
    s = sum(w.values())
    w = {t: v / s for t, v in w.items()}
    validate_weights(w, thematic_set, thematic_cap=thematic_cap, single_thematic_cap=single_them)
    rows = [
        {
            "ticker": t,
            "weight": w[t],
            "role": "thematic" if t in thematic_set else "core",
            "rotate_on": False,
            "thesis_tag": "score_rank_static",
            "mode": "growth_static",
            "S_i": float(df.set_index("ticker").loc[t, "S_i"]) if t in set(df["ticker"]) else float("nan"),
        }
        for t in w
    ]
    return pd.DataFrame(rows).sort_values("weight", ascending=False).reset_index(drop=True)


def monthly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Month-end simple returns using actual last trading day in each calendar month."""
    me = month_end_trading_dates(prices)
    return prices.loc[me].pct_change()


def james_stein_means(sample_means: pd.Series, grand_mean: float | None = None) -> pd.Series:
    """Simple James-Stein shrink of cross-sectional means toward their grand mean."""
    x = sample_means.dropna().astype(float)
    out = sample_means.copy().astype(float)
    if len(x) < 3:
        return out
    grand = float(x.mean() if grand_mean is None else grand_mean)
    s2 = float(x.var(ddof=1))
    denom = float(((x - grand) ** 2).sum())
    if not np.isfinite(s2) or s2 < 1e-16 or denom < 1e-16:
        return out
    shrink = max(0.0, 1.0 - (len(x) - 2) * s2 / denom)
    out.loc[x.index] = grand + shrink * (x - grand)
    return out


def score_to_mu(scores: pd.Series, hist_excess_mean: float, scale: float = 0.015) -> pd.Series:
    """Map score rank percentiles to monthly expected excess returns around history."""
    s = scores.dropna().astype(float)
    out = pd.Series(np.nan, index=scores.index, dtype=float)
    if s.empty:
        return out
    zish = (s.rank(pct=True) - 0.5) * 2.0
    out.loc[s.index] = float(hist_excess_mean) + scale * zish
    return out


def blended_expected_returns(
    window_returns: pd.DataFrame,
    scores: pd.Series,
    names: list[str],
    benchmark: str = "VOO",
) -> pd.Series:
    """Primary M3 μ̂: 0.5 James-Stein historical excess + 0.5 score map."""
    hist = {}
    for t in names:
        if t not in window_returns.columns:
            continue
        if benchmark in window_returns.columns:
            ex = window_returns[t] - window_returns[benchmark]
            hist[t] = float(ex.mean())
        else:
            hist[t] = float(window_returns[t].mean())
    hist_ex = pd.Series(hist, dtype=float).reindex(names)
    grand = float(hist_ex.dropna().mean()) if hist_ex.notna().any() else 0.0
    mu_js = james_stein_means(hist_ex, grand)
    mu_score = score_to_mu(scores.reindex(names), grand)
    return 0.5 * mu_js.fillna(grand) + 0.5 * mu_score.fillna(grand)


def ledoit_wolf_cov(returns: pd.DataFrame, *, force_shrinkage: bool = False) -> pd.DataFrame:
    """Ledoit-Wolf shrinkage covariance, with a tiny-ridge fallback for short panels."""
    clean = returns.dropna(how="any")
    cols = list(returns.columns)
    if len(clean) >= (2 if force_shrinkage else max(12, len(cols) + 2)):
        lw = LedoitWolf().fit(clean.values)
        return pd.DataFrame(lw.covariance_, index=clean.columns, columns=clean.columns)
    cov = returns.cov().reindex(index=cols, columns=cols).fillna(0.0)
    return cov + np.eye(len(cols)) * 1e-6


def _renormalize_with_caps(
    weights: pd.Series,
    caps: dict[str, float],
    thematic: set[str],
    thematic_cap: float,
) -> pd.Series:
    w = weights.fillna(0.0).clip(lower=0.0).astype(float)
    if w.sum() <= 0:
        return w
    w = w / w.sum()
    for _ in range(20):
        before = w.copy()
        for t in w.index:
            w.loc[t] = min(float(w.loc[t]), float(caps.get(t, 0.40)))
        them = [t for t in w.index if t in thematic]
        them_sum = float(w.reindex(them).sum()) if them else 0.0
        if them_sum > thematic_cap and them_sum > 0:
            w.loc[them] *= thematic_cap / them_sum
        rem = 1.0 - float(w.sum())
        if abs(rem) < 1e-10:
            break
        room = pd.Series({t: max(0.0, caps.get(t, 0.40) - float(w.loc[t])) for t in w.index})
        if room.sum() <= 1e-12:
            break
        w += rem * room / room.sum()
        if np.allclose(before.values, w.values, atol=1e-12):
            break
    if w.sum() > 0:
        w = w / w.sum()
    return w


def solve_mv(
    mu: pd.Series,
    sigma: pd.DataFrame,
    caps: dict[str, float],
    thematic: set[str],
    thematic_cap: float,
    *,
    w_prev: pd.Series | None = None,
    gamma_turn: float = 0.0,
    lam: float = 1.0,
) -> pd.Series:
    """Long-only constrained MV: max μ'w - λw'Σw - γ||w-w_prev||1."""
    names = list(mu.dropna().index)
    if not names:
        return pd.Series(dtype=float)
    n = len(names)
    mu_v = mu.reindex(names).astype(float).values
    sig = sigma.reindex(index=names, columns=names).fillna(0.0).values + np.eye(n) * 1e-8
    theme_idx = [i for i, t in enumerate(names) if t in thematic]
    prev = None if w_prev is None else w_prev.reindex(names).fillna(0.0).values

    def obj(w: np.ndarray) -> float:
        val = -(float(mu_v @ w) - float(lam) * float(w @ sig @ w))
        if prev is not None and gamma_turn > 0:
            val += float(gamma_turn) * float(np.abs(w - prev).sum())
        return val

    bounds = [(0.0, float(caps.get(t, 0.40))) for t in names]
    cons: list[dict[str, Any]] = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    if theme_idx:
        cons.append({"type": "ineq", "fun": lambda w, idx=theme_idx: thematic_cap - np.sum(w[idx])})
    w0 = np.ones(n) / n
    w0 = np.minimum(w0, np.array([b[1] for b in bounds]))
    w0 = w0 / w0.sum()
    res = optimize.minimize(
        obj,
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=cons,
        options={"maxiter": 500, "ftol": 1e-10, "disp": False},
    )
    raw = pd.Series(res.x if res.success else w0, index=names)
    return _renormalize_with_caps(raw, caps, thematic, thematic_cap)


def risk_parity_weights(sigma: pd.DataFrame, names: list[str], max_weight: float = 0.40) -> pd.Series:
    """Equal-risk-contribution weights, initialized by inverse volatility."""
    sig = sigma.reindex(index=names, columns=names).fillna(0.0).values + np.eye(len(names)) * 1e-8
    vols = np.sqrt(np.clip(np.diag(sig), 1e-12, None))
    w0 = 1.0 / vols
    w0 = w0 / w0.sum()

    def obj(w: np.ndarray) -> float:
        mrc = sig @ w
        rc = w * mrc
        return float(((rc - rc.mean()) ** 2).sum())

    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = [(0.0, max_weight)] * len(names)
    res = optimize.minimize(obj, w0, method="SLSQP", bounds=bounds, constraints=cons)
    w = pd.Series(res.x if res.success else w0, index=names)
    return w.clip(lower=0) / w.clip(lower=0).sum()


def _scores_series(scores: pd.DataFrame | pd.Series) -> pd.Series:
    if isinstance(scores, pd.Series):
        out = scores.copy()
        out.index = out.index.astype(str).str.upper()
        return out.astype(float)
    df = scores.copy()
    if "ticker" in df.columns:
        df["ticker"] = df["ticker"].astype(str).str.upper()
        df = df.set_index("ticker")
    if "S_i" not in df.columns:
        raise ValueError("scores must include S_i")
    return df["S_i"].astype(float)


def _eligible_optimizer_names(
    names: list[str],
    *,
    universe_df: pd.DataFrame | None,
    universe_config: dict | None,
) -> list[str]:
    out = list(dict.fromkeys(str(t).upper() for t in names))
    assert_rotate_tickers_eligible(out, universe_df, universe_config)
    if universe_df is not None:
        assert_eligible(out, universe_df, universe_config or load_universe_config())
    return out


def thematic_gate_map(
    prices: pd.DataFrame,
    thematic: list[str],
    *,
    asof: pd.Timestamp | None = None,
    benchmark: str = "VOO",
) -> dict[str, bool]:
    """ScoreSimple gate for thematics; data is truncated at asof inside rotation code."""
    live = [t for t in thematic if t in prices.columns]
    if not live:
        return {}
    assert_rotate_tickers_eligible(live)
    sig = compute_rotation_signals(
        prices,
        live,
        benchmark=benchmark,
        use_vol_gate=True,
        hysteresis_months=0,
        asof=asof,
    )
    out = {t: False for t in live}
    if sig.empty:
        return out
    for t, sub in sig.dropna(subset=["mom12_1", "mom12_1_bench"]).groupby("ticker"):
        if not sub.empty:
            out[str(t).upper()] = bool(sub.sort_values("date").iloc[-1]["on"])
    return out


def _format_optimized_rows(
    weights: pd.Series,
    *,
    optimizer: str,
    scores: pd.Series,
    thematic: set[str],
    gate: dict[str, bool] | None = None,
    include_zero_thematics: list[str] | None = None,
) -> pd.DataFrame:
    gate = gate or {}
    rows = []
    all_names = list(weights.index)
    for t in include_zero_thematics or []:
        if t not in all_names:
            all_names.append(t)
    for t in all_names:
        w = float(weights.get(t, 0.0))
        role = "thematic" if t in thematic else ("core" if t in CORE_TICKERS else "satellite")
        rows.append(
            {
                "ticker": t,
                "weight": w,
                "role": role,
                "rotate_on": bool(gate.get(t, False)) if role == "thematic" else False,
                "thesis_tag": (
                    "scoresimple_gated_thematic_on"
                    if role == "thematic" and w > 0
                    else "scoresimple_gated_thematic_off"
                    if role == "thematic"
                    else f"{optimizer.lower()}_optimized"
                ),
                "mode": "growth_optimize",
                "optimizer": optimizer,
                "S_i": float(scores.get(t, np.nan)),
            }
        )
    return pd.DataFrame(rows).sort_values(["weight", "ticker"], ascending=[False, True]).reset_index(drop=True)


def build_optimized_portfolio(
    scores: pd.DataFrame | pd.Series,
    prices: pd.DataFrame,
    *,
    optimizer: str = "P2",
    constraints: dict | None = None,
    asof: pd.Timestamp | None = None,
    universe_csv: str | Path | None = None,
    universe_config: dict | None = None,
    window_months: int = 36,
    benchmark: str = "VOO",
    top_n: int = 6,
    lam: float = 1.0,
    gamma_turn: float = 0.05,
    w_prev: pd.Series | None = None,
) -> pd.DataFrame:
    """Build P1/P2/P3 optimized research portfolio for one decision date."""
    cfg = constraints or load_portfolio_constraints()
    opt = optimizer.upper()
    if opt not in {"P1", "P2", "P3"}:
        raise ValueError("optimizer must be P1, P2, or P3")
    uni_df = load_universe_csv(universe_csv) if universe_csv is not None else None
    uni_cfg = universe_config or load_universe_config()
    sc = _scores_series(scores)
    px = prices.copy()
    px.columns = [str(c).upper() for c in px.columns]
    if asof is not None:
        px = px.loc[:asof]
    if px.empty:
        raise ValueError("prices are empty through asof")

    thematic = set(str(t).upper() for t in cfg.get("thematic_tickers", DEFAULT_THEMATIC_TICKERS))
    thematic.update(t for t in DEFAULT_THEMATIC_TICKERS if t in px.columns)
    assert_rotate_tickers_eligible(thematic)
    thematic_cap = float(cfg.get("thematic_cap", 0.25))
    single_them = float(cfg.get("single_name_cap_thematic", 0.15))
    single_core = float(cfg.get("single_name_cap_core", 0.40))
    core_base = pd.Series({k.upper(): float(v) for k, v in cfg.get("core_when_thematic_off", {}).items()})
    if core_base.empty:
        core_base = pd.Series({"VOO": 0.70, "QQQM": 0.20, "IJR": 0.10})

    ret = monthly_returns(px)
    if len(ret.dropna(how="all")) < 12:
        raise ValueError("need at least 12 monthly returns for optimization")
    win = ret.iloc[-window_months:] if window_months and len(ret) > window_months else ret
    live = [t for t in px.columns if t in sc.index or t in core_base.index or t == benchmark]
    live = [t for t in live if t in ret.columns and ret[t].dropna().shape[0] >= 12]
    live = _eligible_optimizer_names(live, universe_df=uni_df, universe_config=uni_cfg)
    caps = {t: (single_them if t in thematic else single_core) for t in live}

    gate = thematic_gate_map(px, sorted(thematic), asof=asof, benchmark=benchmark)
    zero_thematics = sorted(t for t in thematic if t in px.columns and not gate.get(t, False))

    if opt == "P1":
        names = [t for t in live if t in win.columns and t != benchmark or t == benchmark]
        names = [t for t in names if t in win.columns]
        mu = blended_expected_returns(win[names], sc, names, benchmark=benchmark)
        sigma = ledoit_wolf_cov(win[names])
        w = solve_mv(mu, sigma, caps, thematic, thematic_cap, w_prev=w_prev, gamma_turn=gamma_turn, lam=lam)
        return _format_optimized_rows(w[w > 1e-10], optimizer=opt, scores=sc, thematic=thematic, gate=gate)

    if opt == "P2":
        core_live = [t for t in core_base.index if t in live and t in px.columns]
        if len(core_live) < 2:
            raise ValueError("P2 requires at least two live core tickers")
        core_w = core_base.reindex(core_live).fillna(0.0)
        core_w = core_w / core_w.sum()
        sat_budget = 0.40
        sat_pool = [t for t in DEFAULT_SATELLITE_TICKERS if t in live and t not in core_live]
        sat_names = []
        for t in sat_pool:
            if t in thematic:
                if gate.get(t, False):
                    sat_names.append(t)
            elif pd.notna(sc.get(t, np.nan)) and sc.get(t) >= sc.reindex(sat_pool).median():
                sat_names.append(t)
        if not sat_names:
            w = core_w
        else:
            sat_scores = sc.reindex(sat_names).fillna(sc.median())
            if len(sat_names) >= 2 and win.reindex(columns=sat_names).dropna(how="any").shape[0] >= 12:
                mu = blended_expected_returns(win[sat_names], sat_scores, sat_names, benchmark=benchmark)
                sigma = ledoit_wolf_cov(win[sat_names])
                sat_caps = {
                    t: (single_them / sat_budget if t in thematic else single_core / sat_budget)
                    for t in sat_names
                }
                w_sat = solve_mv(
                    mu,
                    sigma,
                    sat_caps,
                    thematic,
                    thematic_cap / sat_budget,
                    lam=lam,
                )
            else:
                positive = (sat_scores - sat_scores.median()).clip(lower=0.0)
                w_sat = positive / positive.sum() if positive.sum() > 0 else pd.Series(1 / len(sat_names), index=sat_names)
            w = core_w * (1.0 - sat_budget)
            for t, wt in w_sat.items():
                w.loc[t] = w.get(t, 0.0) + sat_budget * float(wt)
            w = _renormalize_with_caps(w, caps, thematic, thematic_cap)
            core_sum = float(w.reindex(core_live).fillna(0.0).sum())
            if core_sum < 0.60:
                sats = [t for t in w.index if t not in core_live]
                sat_sum = float(w.reindex(sats).sum()) if sats else 0.0
                if sat_sum > 0:
                    scale = (1.0 - 0.60) / sat_sum
                    w.loc[sats] *= scale
                    w.loc[core_live] = 0.60 * core_w
                    w = w / w.sum()
        return _format_optimized_rows(
            w[w > 1e-10],
            optimizer=opt,
            scores=sc,
            thematic=thematic,
            gate=gate,
            include_zero_thematics=zero_thematics,
        )

    ranked = sc.reindex(live).dropna().sort_values(ascending=False)
    names = list(ranked.head(top_n).index)
    if len(names) < 3:
        raise ValueError("P3 requires at least three scored live tickers")
    sigma = ledoit_wolf_cov(win[names])
    w = risk_parity_weights(sigma, names, max_weight=single_core)
    w = _renormalize_with_caps(w, caps, thematic, thematic_cap)
    return _format_optimized_rows(w[w > 1e-10], optimizer=opt, scores=sc, thematic=thematic, gate=gate)


def optimizer_strategy_registry() -> pd.DataFrame:
    """Registry of M3 strategy families for multiple-testing honesty."""
    rows = [
        ("P1", "P1_MaxSharpe_roll36_t25", "rolling36", 0.25, 1.0, 0.05, np.nan, "constrained MV; mu=0.5 JS + 0.5 score map; Sigma=Ledoit-Wolf"),
        ("P2", "P2_CoreRotate_roll36_t25", "rolling36", 0.25, 1.0, 0.05, np.nan, "hierarchical core>=60%; ScoreSimple-gated thematics can go to 0"),
        ("P3", "P3_RiskParity_top6_roll36", "rolling36", 0.25, 1.0, 0.05, 6, "risk parity among top-N by S_i"),
        ("P3", "P3_RiskParity_top8_roll36", "rolling36", 0.25, 1.0, 0.05, 8, "risk parity among top-N by S_i"),
    ]
    return pd.DataFrame(
        [
            {
                "trial_id": i,
                "strategy": name,
                "family": fam,
                "window": window,
                "thematic_cap": cap,
                "lam": lam,
                "gamma_turn": gamma,
                "top_n": top_n,
                "turnover_cost_bps_one_way": TURNOVER_COST_BPS,
                "multiple_testing_family": "wf_optimization_m3",
                "notes": notes,
            }
            for i, (fam, name, window, cap, lam, gamma, top_n, notes) in enumerate(rows, start=1)
        ]
    )


def build_portfolio(
    scores: pd.DataFrame | None = None,
    prices: pd.DataFrame | None = None,
    *,
    rotate_thematic: bool = False,
    optimize: bool = False,
    optimizer: str = "P2",
    use_vol_gate: bool = False,
    hysteresis_months: int | None = None,
    constraints: dict | None = None,
    asof: pd.Timestamp | None = None,
    universe_csv: str | Path | None = None,
    universe_config: dict | None = None,
) -> pd.DataFrame:
    """Dispatch static vs rotate portfolio construction."""
    cfg = constraints or load_portfolio_constraints()
    uni_df = None
    uni_cfg = universe_config or load_universe_config()
    if universe_csv is not None:
        uni_df = load_universe_csv(universe_csv)

    if rotate_thematic:
        if prices is None:
            raise ValueError("--rotate-thematic requires prices panel")
        eligible = [t.upper() for t in cfg.get("thematic_rotate_eligible", ["XSD"])]
        if uni_df is not None:
            assert_eligible(eligible, uni_df, uni_cfg)
        else:
            assert_rotate_tickers_eligible(eligible)
        return build_rotated_portfolio(
            prices,
            constraints=cfg,
            asof=asof,
            use_vol_gate=use_vol_gate,
            hysteresis_months=hysteresis_months,
            universe_df=uni_df,
            universe_config=uni_cfg,
            rotate_eligible=eligible,
        )

    if optimize:
        if scores is None or prices is None:
            raise ValueError("--optimize requires scores and prices")
        return build_optimized_portfolio(
            scores,
            prices,
            optimizer=optimizer,
            constraints=cfg,
            asof=asof,
            universe_csv=universe_csv,
            universe_config=universe_config,
        )

    if scores is None:
        raise ValueError("scores required when rotate_thematic is False")
    return build_static_from_scores(scores, constraints=cfg)


# Back-compat stub name from M1
def build_portfolio_stub(scores: pd.DataFrame, *_args, **_kwargs) -> pd.DataFrame:
    return build_portfolio(scores=scores, rotate_thematic=False)
