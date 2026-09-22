"""Config-driven strategy registry runner.

Research tooling only; not investment advice.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from .features import compute_raw_features
from .portfolio import (
    build_optimized_portfolio,
    build_rotated_portfolio,
    monthly_returns,
)
from .rotation import (
    assert_rotate_tickers_eligible,
    compute_rotation_signals,
    load_portfolio_constraints,
    month_end_trading_dates,
)
from .scores import composite_scores, load_feature_weights
from .universe import assert_eligible, category_map, eligible_tickers, load_universe_config, load_universe_csv, thin_history_set
from .vol_target import (
    VolTargetTrial,
    annualized_return,
    annualized_vol,
    deflated_sharpe_approx,
    max_drawdown,
    newey_west_tstat,
    run_vol_target_trial,
    sharpe_rf0,
)
from .walkforward import walkforward_optimization_tables

RESEARCH_DISCLAIMER = "Research-only; not investment advice; no trading or broker routing."
REGIME_DUAL_ENTRYPOINT = "usa_etf_features.strategy_registry:regime_aware_dual_regime"
STATIC_ENTRYPOINT = "usa_etf_features.strategy_registry:static_option_a"
VOL_TARGET_ENTRYPOINT = "usa_etf_features.strategy_registry:vol_target_option_a"
VOL_CFC_ENTRYPOINT = "usa_etf_features.strategy_registry:vol_cond_factor_corr"
ROTATE_ENTRYPOINT = "usa_etf_features.strategy_registry:score_rotate_xsd"
M3_P2_ENTRYPOINT = "usa_etf_features.strategy_registry:m3_p2_core_rotate"
FT_MED_ENTRYPOINT = "usa_etf_features.strategy_registry:forecast_tangency_med"


@dataclass(frozen=True)
class StrategySpec:
    id: str
    display_name: str
    method_citation_id: str
    method_citation: str
    entrypoint: str
    default_params: dict[str, Any]
    enabled: bool = True


@dataclass
class StrategyResult:
    weights: pd.DataFrame
    diagnostics: pd.DataFrame
    returns: pd.DataFrame


def load_strategy_registry(path: str | Path) -> list[StrategySpec]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    specs = []
    for item in raw.get("strategies", []):
        specs.append(
            StrategySpec(
                id=str(item["id"]),
                display_name=str(item.get("display_name", item["id"])),
                method_citation_id=str(item.get("method_citation_id", "")),
                method_citation=str(item.get("method_citation", "")),
                entrypoint=str(item["entrypoint"]),
                default_params=dict(item.get("default_params") or {}),
                enabled=bool(item.get("enabled", True)),
            )
        )
    return specs


def enabled_strategies(specs: list[StrategySpec]) -> list[StrategySpec]:
    return [s for s in specs if s.enabled]


def params_hash(params: dict[str, Any]) -> str:
    payload = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _git_commit() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL)
        return out.strip()
    except Exception:
        return ""


def registry_used_frame(specs: list[StrategySpec]) -> pd.DataFrame:
    git_commit = _git_commit()
    rows = []
    for s in specs:
        rows.append(
            {
                "strategy_id": s.id,
                "display_name": s.display_name,
                "method_citation_id": s.method_citation_id,
                "method_citation": s.method_citation,
                "entrypoint": s.entrypoint,
                "enabled": s.enabled,
                "params_json": json.dumps(s.default_params, sort_keys=True),
                "params_hash": params_hash(s.default_params),
                "git_commit": git_commit,
                "research_disclaimer": RESEARCH_DISCLAIMER,
            }
        )
    return pd.DataFrame(rows)


def _asof_date(prices: pd.DataFrame, asof: pd.Timestamp | None) -> pd.Timestamp:
    px = prices.loc[:asof] if asof is not None else prices
    if px.empty:
        raise ValueError("no prices through asof")
    return pd.Timestamp(px.index.max())


def _month_end_dates_through(prices: pd.DataFrame, asof: pd.Timestamp | None) -> pd.DatetimeIndex:
    px = prices.loc[:asof] if asof is not None else prices
    return month_end_trading_dates(px)


def _format_weights(
    df: pd.DataFrame,
    *,
    strategy_id: str,
    date: pd.Timestamp,
) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.Timestamp(date)
    out["asof"] = pd.Timestamp(date)
    out["strategy_id"] = strategy_id
    if "role" not in out.columns:
        out["role"] = ""
    if "thesis_tag" not in out.columns:
        out["thesis_tag"] = ""
    out["research_disclaimer"] = RESEARCH_DISCLAIMER
    cols = ["date", "asof", "strategy_id", "ticker", "weight", "role", "thesis_tag", "research_disclaimer"]
    extra = [c for c in out.columns if c not in cols]
    return out[cols + extra]


def _validate_weights(
    weights: pd.DataFrame,
    *,
    universe_df: pd.DataFrame,
    universe_config: dict,
) -> None:
    sleeves = weights.get("asset_type", pd.Series("ticker", index=weights.index)).eq("category_sleeve")
    if sleeves.any():
        from .regime_dual import REGIME_ELIGIBILITY
        allowed = set().union(*REGIME_ELIGIBILITY.values(), {"Crypto / Digital Assets"},
                              set(universe_df["Category"]))
        if not set(weights.loc[sleeves, "ticker"]).issubset(allowed):
            raise ValueError("unknown category sleeve in suggested weights")
    ticker_weights = weights.loc[~sleeves]
    tickers = sorted(set(ticker_weights.loc[ticker_weights["weight"].abs() > 1e-12, "ticker"].astype(str).str.upper()))
    assert_rotate_tickers_eligible(tickers, universe_df, universe_config)
    assert_eligible(tickers, universe_df, universe_config)
    sums = weights.groupby(["strategy_id", "date"])["weight"].sum()
    bad = sums[(sums - 1.0).abs() > 1e-8]
    if not bad.empty:
        raise ValueError(f"strategy weights must sum to 1: {bad.to_dict()}")


def _static_weights(params: dict[str, Any]) -> pd.DataFrame:
    weights = {str(k).upper(): float(v) for k, v in params.get("weights", {}).items()}
    if not weights:
        weights = {"VOO": 0.70, "QQQM": 0.20, "IJR": 0.10}
    return pd.DataFrame(
        {
            "ticker": list(weights),
            "weight": list(weights.values()),
            "role": ["core"] * len(weights),
            "thesis_tag": ["static_option_a"] * len(weights),
        }
    )


def _static_returns(prices: pd.DataFrame, params: dict[str, Any], asof: pd.Timestamp | None) -> pd.DataFrame:
    w = _static_weights(params).set_index("ticker")["weight"].astype(float)
    px = prices.loc[:asof] if asof is not None else prices
    rets = monthly_returns(px[list(w.index)]).dropna(how="all")
    r = rets.mul(w, axis=1).sum(axis=1, min_count=len(w))
    return pd.DataFrame({"date": r.index, "strategy_id": "static_option_a", "return": r.values, "turnover": 0.0}).dropna()


def _option_a_returns(prices: pd.DataFrame, asof: pd.Timestamp | None) -> pd.Series:
    r = _static_returns(prices, {"weights": {"VOO": 0.70, "QQQM": 0.20, "IJR": 0.10}}, asof)
    return r.set_index("date")["return"]


def _scores_asof(
    prices: pd.DataFrame,
    categories: pd.Series,
    *,
    asof: pd.Timestamp,
    benchmark: str,
    weights_cfg: dict,
) -> pd.DataFrame:
    px = prices.loc[:asof]
    raw = compute_raw_features(px, benchmark=benchmark)
    raw = raw.loc[[t for t in raw.index if t in categories.index]]
    return composite_scores(raw, categories.reindex(raw.index).fillna("Unknown"), weights_cfg)


def _rotate_returns(
    prices: pd.DataFrame,
    spec: StrategySpec,
    *,
    universe_df: pd.DataFrame,
    universe_config: dict,
    constraints: dict,
    asof: pd.Timestamp | None,
) -> pd.DataFrame:
    params = spec.default_params
    me_dates = _month_end_dates_through(prices, asof)
    me_ret = prices.loc[me_dates].pct_change()
    rows = []
    prev_w: pd.Series | None = None
    min_i = 13
    for i, d in enumerate(me_dates):
        if i < min_i or i + 1 >= len(me_dates):
            continue
        try:
            wf = build_rotated_portfolio(
                prices,
                constraints=constraints,
                asof=d,
                use_vol_gate=bool(params.get("use_vol_gate", True)),
                hysteresis_months=int(params.get("hysteresis_months", 0)),
                universe_df=universe_df,
                universe_config=universe_config,
                rotate_eligible=[str(t).upper() for t in params.get("rotate_eligible", ["XSD"])],
            )
        except Exception:
            continue
        w = wf.set_index("ticker")["weight"].astype(float)
        nxt = me_dates[i + 1]
        cols = [t for t in w.index if t in me_ret.columns]
        if me_ret.loc[nxt, cols].isna().any():
            continue
        turnover = 0.5 * float(w.subtract(prev_w, fill_value=0.0).abs().sum()) if prev_w is not None else 0.5
        ret = float((w.reindex(cols).fillna(0.0) * me_ret.loc[nxt, cols]).sum())
        rows.append(
            {
                "date": nxt,
                "decision_date": d,
                "feature_end": d,
                "strategy_id": spec.id,
                "return": ret,
                "turnover": turnover,
            }
        )
        prev_w = w
    return pd.DataFrame(rows)


def _m3_returns(
    prices: pd.DataFrame,
    spec: StrategySpec,
    *,
    universe_csv: str | Path,
    categories: pd.Series,
    weights_cfg: dict,
    constraints: dict,
    tickers: list[str],
    asof: pd.Timestamp | None,
) -> pd.DataFrame:
    px = prices.loc[:asof] if asof is not None else prices
    params = spec.default_params
    weights_df, _ic, _reg = walkforward_optimization_tables(
        px,
        categories,
        tickers=tickers,
        universe_csv=universe_csv,
        benchmark=str(params.get("benchmark", "VOO")).upper(),
        weights_cfg=weights_cfg,
        constraints=constraints,
        optimizer=str(params.get("optimizer", "P2")).upper(),
        window_months=int(params.get("window_months", 36)),
        min_history_months=int(params.get("min_history_months", 36)),
        top_n=int(params.get("top_n", 6)),
    )
    if weights_df.empty:
        return pd.DataFrame(columns=["date", "decision_date", "strategy_id", "return", "turnover"])
    return pd.DataFrame(
        {
            "date": pd.to_datetime(weights_df["eval_date"]),
            "decision_date": pd.to_datetime(weights_df["date"]),
            "feature_end": pd.to_datetime(weights_df["date"]),
            "strategy_id": spec.id,
            "return": weights_df["net_return"].astype(float),
            "turnover": weights_df["turnover"].astype(float),
        }
    )


def _vol_target_result(
    prices: pd.DataFrame,
    spec: StrategySpec,
    *,
    universe_csv: str | Path,
    universe_config: dict,
    asof: pd.Timestamp | None,
) -> StrategyResult:
    params = spec.default_params
    trial = VolTargetTrial(
        trial_id=spec.id,
        core=str(params.get("core", "option_a")),
        lookback=int(params.get("lookback", 63)),
        f_min=float(params.get("f_min", 0.25)),
        f_max=float(params.get("f_max", 1.0)),
        sigma_star=params.get("sigma_star", "expanding_annvol"),
        cash_ticker=str(params.get("cash_ticker", "BIL")).upper(),
        cost_bps_one_way=float(params.get("cost_bps_one_way", 5.0)),
    )
    px = prices.loc[:asof] if asof is not None else prices
    monthly_w, returns, _registry = run_vol_target_trial(px, trial, universe_csv=universe_csv, universe_config=universe_config)
    if monthly_w.empty:
        raise ValueError(f"{spec.id} produced no vol-target weights")
    last = monthly_w.sort_values("date").iloc[-1]
    w_cols = [c for c in monthly_w.columns if c.startswith("w_")]
    rows = []
    for c in w_cols:
        ticker = c[2:]
        rows.append(
            {
                "ticker": ticker,
                "weight": float(last[c]),
                "role": "cash" if ticker == trial.cash_ticker.upper() else "core",
                "thesis_tag": "vol_target_cash" if ticker == trial.cash_ticker.upper() else "vol_target_option_a",
            }
        )
    weights = _format_weights(pd.DataFrame(rows), strategy_id=spec.id, date=pd.Timestamp(last["date"]))
    diag = last.to_frame().T
    diag["strategy_id"] = spec.id
    diag["research_disclaimer"] = RESEARCH_DISCLAIMER
    ret = returns.rename(columns={"r_vt": "return", "decision_date": "decision_date"})
    ret = ret.assign(strategy_id=spec.id, feature_end=lambda x: x["decision_date"])[
        ["date", "decision_date", "feature_end", "strategy_id", "return", "turnover"]
    ]
    return StrategyResult(weights=weights, diagnostics=diag, returns=ret)



def vol_cond_factor_corr(
    prices: pd.DataFrame,
    spec: StrategySpec,
    *,
    universe_csv: str | Path,
    universe_config: dict,
    asof: pd.Timestamp | None,
) -> StrategyResult:
    """Registry adapter for Book-2 conditional factor-correlation gate."""
    from .vol_cond_factor_corr import VolCondFactorCorrTrial, run_vol_cond_factor_corr_trial

    params = dict(spec.default_params)
    monthly_csv = params.pop("monthly_csv", None)
    coverage_csv = params.pop("coverage_csv", None)
    monthly = None
    if monthly_csv and Path(monthly_csv).exists():
        monthly = pd.read_csv(monthly_csv, index_col=0, parse_dates=True).sort_index()
        monthly.columns = [str(c).upper() for c in monthly.columns]
    coverage = pd.read_csv(coverage_csv) if coverage_csv and Path(coverage_csv).exists() else None
    trial = VolCondFactorCorrTrial(
        trial_id=spec.id,
        core=str(params.get("core", "option_a")),
        lookback=int(params.get("lookback", 63)),
        corr_lookback_months=int(params.get("corr_lookback_months", 12)),
        f_min=float(params.get("f_min", 0.25)),
        f_max=float(params.get("f_max", 1.0)),
        g_min=float(params.get("g_min", 0.5)),
        z_rule=str(params.get("z_rule", "mkt_vol")),
        apply_to=str(params.get("apply_to", "option_a_vt")),
        sigma_star=params.get("sigma_star", "expanding_annvol"),
        cash_ticker=str(params.get("cash_ticker", "BIL")).upper(),
        cost_bps_one_way=float(params.get("cost_bps_one_way", 5.0)),
        include_thin=bool(params.get("include_thin", False)),
    )
    px = prices.loc[:asof] if asof is not None else prices
    monthly_w, returns, _registry = run_vol_cond_factor_corr_trial(
        px,
        trial,
        universe_csv=universe_csv,
        monthly=monthly,
        coverage=coverage,
        universe_config=universe_config,
    )
    if monthly_w.empty:
        raise ValueError(f"{spec.id} produced no vol-cond-factor-corr weights")
    last = monthly_w.sort_values("date").iloc[-1]
    w_cols = [c for c in monthly_w.columns if c.startswith("w_")]
    rows = []
    cash = trial.cash_ticker.upper()
    for c in w_cols:
        ticker = c[2:]
        rows.append(
            {
                "ticker": ticker,
                "weight": float(last[c]),
                "role": "cash" if ticker == cash else "core",
                "thesis_tag": "vol_cfc_cash" if ticker == cash else "vol_cfc_option_a",
            }
        )
    weights = _format_weights(pd.DataFrame(rows), strategy_id=spec.id, date=pd.Timestamp(last["date"]))
    diag = last.to_frame().T
    diag["strategy_id"] = spec.id
    diag["research_disclaimer"] = RESEARCH_DISCLAIMER
    ret = returns.rename(columns={"r_method": "return"})
    ret = ret.assign(strategy_id=spec.id, feature_end=lambda x: x["decision_date"])[
        ["date", "decision_date", "feature_end", "strategy_id", "return", "turnover"]
    ]
    return StrategyResult(weights=weights, diagnostics=diag, returns=ret)


def forecast_tangency_med(
    prices: pd.DataFrame,
    spec: StrategySpec,
    *,
    universe_csv: str | Path,
    universe_config: dict,
    asof: pd.Timestamp | None,
) -> StrategyResult:
    """Registry adapter for Forecast Tangency + MED (Archive/Methods stub; Quant gate pending)."""
    from .forecast_tangency_med import (
        ForecastTangencyMedTrial,
        run_forecast_tangency_med_trial,
        RESEARCH_DISCLAIMER as FT_DISCLAIMER,
    )

    params = dict(spec.default_params)
    monthly_csv = params.pop("monthly_csv", None)
    coverage_csv = params.pop("coverage_csv", None)

    monthly = None
    if monthly_csv and Path(monthly_csv).exists():
        monthly = pd.read_csv(monthly_csv, index_col=0, parse_dates=True).sort_index()
        monthly.columns = [str(c).upper() for c in monthly.columns]
    if monthly is None:
        raise ValueError(
            f"{spec.id}: monthly_csv not found at {monthly_csv!r}; "
            "run walkforward-forecast-tangency-med CLI directly with --monthly"
        )

    coverage = pd.read_csv(coverage_csv) if coverage_csv and Path(coverage_csv).exists() else None

    trial = ForecastTangencyMedTrial(
        trial_id=spec.id,
        ef_lookback_months=int(params.get("ef_lookback_months", 21)),
        forecast_lookback_months=int(params.get("forecast_lookback_months", 60)),
        mu_estimator=str(params.get("mu_estimator", "sample")),
        cov_estimator=str(params.get("cov_estimator", "ledoit_wolf")),
        long_only=bool(params.get("long_only", True)),
        leverage_cap=float(params.get("leverage_cap", 1.0)),
        cost_bps_one_way=float(params.get("cost_bps_one_way", 5.0)),
        cash_ticker=str(params.get("cash_ticker", "BIL")).upper(),
        min_names=int(params.get("min_names", 100)),
        apply_to=str(params.get("apply_to", "name_level")),
        include_thin=bool(params.get("include_thin", False)),
        min_history_months=int(params.get("min_history_months", 24)),
    )

    if asof is not None:
        monthly = monthly.loc[:asof]

    monthly_w, returns, _registry = run_forecast_tangency_med_trial(
        monthly,
        trial,
        universe_csv=universe_csv,
        coverage=coverage,
        universe_config=universe_config,
    )

    if monthly_w.empty:
        raise ValueError(f"{spec.id} produced no FT-MED weights")

    last = monthly_w.sort_values("date").iloc[-1]
    w_cols = [c for c in monthly_w.columns if c.startswith("w_")]
    rows = []
    cash = trial.cash_ticker.upper()
    for c in w_cols:
        ticker = c[2:]
        rows.append(
            {
                "ticker": ticker,
                "weight": float(last[c]),
                "role": "cash" if ticker == cash else "core",
                "thesis_tag": "ft_med_cash" if ticker == cash else "ft_med",
            }
        )
    weights = _format_weights(pd.DataFrame(rows), strategy_id=spec.id, date=pd.Timestamp(last["date"]))
    diag = last.to_frame().T
    diag["strategy_id"] = spec.id
    diag["research_disclaimer"] = FT_DISCLAIMER
    ret = returns.rename(columns={"r_method": "return"})
    ret = ret.assign(strategy_id=spec.id, feature_end=lambda x: x["decision_date"])[
        ["date", "decision_date", "feature_end", "strategy_id", "return", "turnover"]
    ]
    return StrategyResult(weights=weights, diagnostics=diag, returns=ret)


def spectral_risk_parity(prices, spec, *, universe_csv, asof=None) -> StrategyResult:
    """Run full panel or derive monthly returns from the supplied daily prices."""
    from .spectral_risk_parity import SpectralTrial, read_returns, run_spectral_trial
    params = dict(spec.default_params)
    path = params.pop("returns_csv", None)
    coverage_path = params.pop("coverage_csv", None)
    panel = read_returns(path) if path else monthly_returns(prices)
    cutoff = pd.Timestamp(asof) if asof is not None else None
    if cutoff is not None:
        panel = panel.loc[:cutoff]
        if cutoff < cutoff + pd.offsets.BMonthEnd(0):
            panel = panel.loc[panel.index.to_period("M") < cutoff.to_period("M")]
    result = run_spectral_trial(panel, pd.read_csv(universe_csv),
                                pd.read_csv(coverage_path) if coverage_path else None,
                                SpectralTrial(**params))
    weights = result["weights"].query("strategy_id == 'spectral_risk_parity'")
    latest = weights[weights.decision_date == weights.decision_date.max()]
    formatted = _format_weights(latest[["ticker", "weight"]], strategy_id=spec.id,
                                date=latest.decision_date.iloc[0])
    diagnostics = result["eigen_diagnostics"].merge(
        result["summary"].query("strategy_id == 'spectral_risk_parity'"), how="cross")
    diagnostics["strategy_id"] = spec.id
    returns = result["oos_returns"].query("strategy_id == 'spectral_risk_parity'").copy()
    returns["strategy_id"] = spec.id
    return StrategyResult(formatted, diagnostics, returns)


def regime_aware_dual_regime(spec: StrategySpec, *, asof: pd.Timestamp | None = None) -> StrategyResult:
    """Registry adapter; category identifiers are explicit sleeves, not tickers."""
    from .regime_dual import load_and_run

    tables = load_and_run(spec.default_params, asof)
    trial_id = f"k2_{spec.default_params.get('feature_set', 'vol_corr_spread')}_{spec.default_params.get('allocator', 'erc')}"
    monthly = tables["monthly_weights"]
    monthly = monthly.loc[monthly.trial_id.eq(trial_id)]
    if monthly.empty:
        raise ValueError(f"unregistered regime trial: {trial_id}")
    last = monthly.loc[monthly.decision_date.eq(monthly.decision_date.max())].copy()
    last = last.rename(columns={"asset": "ticker", "date": "eval_date"})
    if "asset_type" not in last.columns:
        last["asset_type"] = "category_sleeve"
    weights = _format_weights(last, strategy_id=spec.id, date=last.decision_date.iloc[0])
    diagnostics = tables["diagnostics"].loc[
        lambda x: x.feature_set.eq(spec.default_params.get("feature_set", "vol_corr_spread"))
    ].copy()
    metrics = tables["summary"].set_index("trial_id").loc[trial_id]
    for key, value in metrics.items():
        if key != "feature_set":
            diagnostics[key] = value
    diagnostics["strategy_id"] = spec.id
    diagnostics["regime"] = last.regime.iloc[0]
    diagnostics["decision_date"] = last.decision_date.iloc[0]
    returns = tables["oos_returns"].loc[lambda x: x.trial_id.eq(trial_id)].copy()
    returns["strategy_id"] = spec.id
    return StrategyResult(weights, diagnostics, returns)


def _strategy_current_result(
    spec: StrategySpec,
    *,
    prices: pd.DataFrame,
    universe_csv: str | Path,
    universe_df: pd.DataFrame,
    universe_config: dict,
    categories: pd.Series,
    weights_cfg: dict,
    constraints: dict,
    tickers: list[str],
    asof: pd.Timestamp | None,
) -> StrategyResult:
    if spec.entrypoint == "usa_etf_features.strategy_registry:spectral_risk_parity":
        return spectral_risk_parity(prices, spec, universe_csv=universe_csv, asof=asof)
    if spec.entrypoint == FT_MED_ENTRYPOINT:
        return forecast_tangency_med(prices, spec, universe_csv=universe_csv, universe_config=universe_config, asof=asof)
    if spec.entrypoint == REGIME_DUAL_ENTRYPOINT:
        return regime_aware_dual_regime(spec, asof=asof)
    decision_date = _asof_date(prices, asof)
    if spec.entrypoint == STATIC_ENTRYPOINT:
        weights = _format_weights(_static_weights(spec.default_params), strategy_id=spec.id, date=decision_date)
        diag = pd.DataFrame([{"strategy_id": spec.id, "date": decision_date, "cash_price_source": "", "research_disclaimer": RESEARCH_DISCLAIMER}])
        return StrategyResult(weights, diag, _static_returns(prices, spec.default_params, asof))
    if spec.entrypoint == VOL_TARGET_ENTRYPOINT:
        return _vol_target_result(prices, spec, universe_csv=universe_csv, universe_config=universe_config, asof=asof)
    if spec.entrypoint == VOL_CFC_ENTRYPOINT:
        return vol_cond_factor_corr(prices, spec, universe_csv=universe_csv, universe_config=universe_config, asof=asof)
    if spec.entrypoint == ROTATE_ENTRYPOINT:
        params = spec.default_params
        rotate_eligible = [str(t).upper() for t in params.get("rotate_eligible", ["XSD"])]
        wf = build_rotated_portfolio(
            prices,
            constraints=constraints,
            asof=decision_date,
            use_vol_gate=bool(params.get("use_vol_gate", True)),
            hysteresis_months=int(params.get("hysteresis_months", 0)),
            universe_df=universe_df,
            universe_config=universe_config,
            rotate_eligible=rotate_eligible,
        )
        sig = compute_rotation_signals(
            prices,
            rotate_eligible,
            benchmark=str(params.get("benchmark", "VOO")).upper(),
            use_vol_gate=bool(params.get("use_vol_gate", True)),
            hysteresis_months=int(params.get("hysteresis_months", 0)),
            asof=decision_date,
        )
        latest_sig = sig.sort_values("date").groupby("ticker").tail(1)
        latest_sig["strategy_id"] = spec.id
        latest_sig["cash_price_source"] = ""
        latest_sig["thin_history_tickers"] = ",".join(sorted(set(rotate_eligible) & thin_history_set(universe_config)))
        latest_sig["research_disclaimer"] = RESEARCH_DISCLAIMER
        return StrategyResult(
            _format_weights(wf, strategy_id=spec.id, date=decision_date),
            latest_sig,
            _rotate_returns(prices, spec, universe_df=universe_df, universe_config=universe_config, constraints=constraints, asof=asof),
        )
    if spec.entrypoint == M3_P2_ENTRYPOINT:
        params = spec.default_params
        scored = _scores_asof(
            prices,
            categories,
            asof=decision_date,
            benchmark=str(params.get("benchmark", "VOO")).upper(),
            weights_cfg=weights_cfg,
        )
        wf = build_optimized_portfolio(
            scored,
            prices,
            optimizer=str(params.get("optimizer", "P2")).upper(),
            constraints=constraints,
            asof=decision_date,
            universe_csv=universe_csv,
            universe_config=universe_config,
            window_months=int(params.get("window_months", 36)),
            benchmark=str(params.get("benchmark", "VOO")).upper(),
            top_n=int(params.get("top_n", 6)),
        )
        diag = pd.DataFrame(
            [
                {
                    "strategy_id": spec.id,
                    "date": decision_date,
                    "optimizer": str(params.get("optimizer", "P2")).upper(),
                    "n_holdings_gt0": int((wf["weight"] > 1e-12).sum()),
                    "pct_thematic_on": float(wf.loc[wf["role"].eq("thematic"), "rotate_on"].mean()) if (wf["role"].eq("thematic")).any() else np.nan,
                    "cash_price_source": "",
                    "research_disclaimer": RESEARCH_DISCLAIMER,
                }
            ]
        )
        return StrategyResult(
            _format_weights(wf, strategy_id=spec.id, date=decision_date),
            diag,
            _m3_returns(
                prices,
                spec,
                universe_csv=universe_csv,
                categories=categories,
                weights_cfg=weights_cfg,
                constraints=constraints,
                tickers=tickers,
                asof=asof,
            ),
        )
    raise ValueError(f"unknown strategy entrypoint for {spec.id}: {spec.entrypoint}")


def comparison_frame(returns: pd.DataFrame, option_a: pd.Series) -> pd.DataFrame:
    # Monthly sleeve dates are calendar ends; price strategies use trading ends.
    # Align by month so holidays/weekends do not silently remove observations.
    option_a = option_a.copy()
    option_a.index = pd.to_datetime(option_a.index).to_period("M").to_timestamp("M")
    date_sets = [
        set(pd.to_datetime(sub["date"]).dt.to_period("M").dt.to_timestamp("M"))
        for _sid, sub in returns.dropna(subset=["return"]).groupby("strategy_id")
        if not sub.empty
    ]
    common_dates = set.intersection(*date_sets) if date_sets else set()
    rows = []
    for sid, sub in returns.groupby("strategy_id"):
        tmp = sub.copy()
        tmp["date"] = pd.to_datetime(tmp["date"]).dt.to_period("M").dt.to_timestamp("M")
        r = tmp.set_index("date")["return"].dropna()
        if common_dates:
            r = r.reindex(sorted(common_dates)).dropna()
        bench = option_a.reindex(r.index).dropna()
        active = r.reindex(bench.index) - bench
        rows.append(
            {
                "strategy_id": sid,
                "AnnReturn": annualized_return(r),
                "AnnVol": annualized_vol(r),
                "MaxDD": max_drawdown(r),
                "Sharpe_rf0": sharpe_rf0(r),
                "NW_t_vs_option_a": newey_west_tstat(active),
                "turnover_per_year": float(sub["turnover"].dropna().mean() * 12) if "turnover" in sub else np.nan,
                "n_months": int(r.shape[0]),
                "start_date": r.index.min() if not r.empty else pd.NaT,
                "end_date": r.index.max() if not r.empty else pd.NaT,
                "research_disclaimer": RESEARCH_DISCLAIMER,
            }
        )
    return pd.DataFrame(rows).sort_values("strategy_id").reset_index(drop=True)


def run_strategy_registry(
    *,
    prices: pd.DataFrame,
    universe_csv: str | Path,
    registry_path: str | Path,
    out_dir: str | Path,
    asof: pd.Timestamp | None = None,
    walkforward: bool = False,
    universe_config_path: str | Path | None = None,
    constraints_path: str | Path | None = None,
    weights_path: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    specs = load_strategy_registry(registry_path)
    active = enabled_strategies(specs)
    if not active:
        raise ValueError("no enabled strategies in registry")
    uni_cfg = load_universe_config(universe_config_path)
    uni_df = load_universe_csv(universe_csv)
    approved = eligible_tickers(uni_df, uni_cfg)
    cats = category_map(uni_df, uni_cfg)
    categories = pd.Series({t: cats.get(t, "Unknown") for t in approved})
    constraints = load_portfolio_constraints(constraints_path)
    weights_cfg = load_feature_weights(weights_path)
    tickers = [t for t in prices.columns if t in approved]

    results = [
        _strategy_current_result(
            s,
            prices=prices,
            universe_csv=universe_csv,
            universe_df=uni_df,
            universe_config=uni_cfg,
            categories=categories,
            weights_cfg=weights_cfg,
            constraints=constraints,
            tickers=tickers,
            asof=asof,
        )
        for s in active
    ]
    weights = pd.concat([r.weights for r in results], ignore_index=True)
    diagnostics = pd.concat([r.diagnostics for r in results], ignore_index=True, sort=False)
    returns = pd.concat([r.returns for r in results], ignore_index=True, sort=False)
    if walkforward:
        # Suggested weights remains the latest decision book in v1; comparison is walk-forward.
        diagnostics["walkforward"] = True
    _validate_weights(weights, universe_df=uni_df, universe_config=uni_cfg)
    comparison = comparison_frame(returns, _option_a_returns(prices, asof))
    if "DSR" in diagnostics:
        metrics = diagnostics.dropna(subset=["trial_count"]).drop_duplicates("strategy_id")
        comparison = comparison.merge(metrics[["strategy_id", "trial_count"]], on="strategy_id", how="left")
        comparison["DSR"] = [
            deflated_sharpe_approx(row.Sharpe_rf0 / np.sqrt(12), row.n_months, int(row.trial_count))
            if pd.notna(row.trial_count) else np.nan
            for row in comparison.itertuples()
        ]
    registry_used = registry_used_frame(specs)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_frame(weights, out / "suggested_weights.csv")
    _write_frame(diagnostics, out / "strategy_diagnostics.csv")
    _write_frame(comparison, out / "strategy_comparison.csv")
    _write_frame(returns, out / "strategy_returns.csv")
    _write_frame(registry_used, out / "strategy_registry_used.csv")
    with pd.ExcelWriter(out / "strategy_comparison.xlsx") as writer:
        comparison.to_excel(writer, sheet_name="comparison", index=False)
        weights.to_excel(writer, sheet_name="suggested_weights", index=False)
        diagnostics.to_excel(writer, sheet_name="diagnostics", index=False)
        registry_used.to_excel(writer, sheet_name="registry_used", index=False)
    return {
        "suggested_weights": weights,
        "strategy_diagnostics": diagnostics,
        "strategy_comparison": comparison,
        "strategy_registry_used": registry_used,
        "strategy_returns": returns,
    }


def _write_frame(df: pd.DataFrame, path: Path) -> None:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = pd.to_datetime(out[col]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)
