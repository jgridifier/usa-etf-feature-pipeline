"""CLI: score-universe, build-portfolio, walkforward-ic, walkforward-vol-target, walkforward-vol-cond-factor-corr, walkforward-skewness-managed."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from .features import compute_raw_features
from .portfolio import build_portfolio, build_optimized_portfolio, optimizer_strategy_registry
from .prices import load_adj_close_csv
from .rotation import load_portfolio_constraints
from .scores import composite_scores, load_feature_weights
from .strategy_registry import run_strategy_registry
from .universe import (
    UniverseGateError,
    assert_eligible,
    category_map,
    eligible_tickers,
    load_universe_config,
    load_universe_csv,
    thin_history_set,
)
from .vol_target import (
    load_vol_target_config,
    make_trials,
    run_vol_target_grid,
)
from .vol_cond_factor_corr import (
    load_vol_cond_factor_corr_config,
    make_vol_cfc_trials,
    run_vol_cond_factor_corr_grid,
)
from .skewness_managed import (
    load_skewness_managed_config,
    make_skew_managed_trials,
    run_skewness_managed_grid,
)
from .forecast_tangency_med import (
    load_forecast_tangency_med_config,
    make_ft_med_trials,
    run_forecast_tangency_med_grid,
)
from .regime_resilient_erc import (
    load_regime_resilient_erc_config,
    make_rr_erc_trials,
    run_regime_resilient_erc_grid,
)
from .walkforward import (
    rotation_on_off_next_month_table,
    walkforward_ic_table,
    walkforward_optimization_tables,
    write_ic_csv,
    write_strategy_registry,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cmd_score_universe(args: argparse.Namespace) -> int:
    uni_path = Path(args.universe)
    prices_path = Path(args.prices)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cfg_path = Path(args.universe_config) if args.universe_config else _repo_root() / "config" / "universe.yaml"
    weights_path = Path(args.weights) if args.weights else _repo_root() / "config" / "feature_weights.yaml"

    uni_cfg = load_universe_config(cfg_path if cfg_path.exists() else None)
    weights_cfg = load_feature_weights(weights_path if weights_path.exists() else None)

    universe_df = load_universe_csv(uni_path)
    eligible = eligible_tickers(universe_df, uni_cfg)
    cats = category_map(universe_df, uni_cfg)
    thin = thin_history_set(uni_cfg)

    prices = load_adj_close_csv(prices_path)
    if args.tickers:
        req = [t.strip().upper() for t in args.tickers.split(",")]
        assert_eligible(req, universe_df, uni_cfg)
        tickers = req
    else:
        tickers = [t for t in prices.columns if t in eligible]

    missing = [t for t in tickers if t not in prices.columns]
    if missing:
        print(f"warning: no price columns for {missing}", file=sys.stderr)
        tickers = [t for t in tickers if t in prices.columns]

    if not tickers:
        print("error: no eligible tickers with prices", file=sys.stderr)
        return 1

    assert_eligible(tickers, universe_df, uni_cfg)

    px = prices[tickers]
    fw = weights_cfg.get("quality", {})
    raw = compute_raw_features(
        px,
        volumes=None,
        expense_ratios=None,
        benchmark=fw.get("benchmark", "VOO"),
        fallback_benchmark=fw.get("fallback_benchmark", "VTI"),
    )
    cat_series = pd.Series({t: cats.get(t, "Unknown") for t in raw.index})
    scored = composite_scores(raw, cat_series, weights_cfg)
    scored["thin_history"] = scored.index.map(lambda t: str(t).upper() in thin)
    scored["rank"] = range(1, len(scored) + 1)
    scored = scored.reset_index().rename(columns={"ticker": "ticker"})

    scored.to_csv(out_path, index=False)
    print(f"wrote {len(scored)} rows → {out_path}")
    return 0


def cmd_build_portfolio(args: argparse.Namespace) -> int:
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cons_path = (
        Path(args.constraints)
        if getattr(args, "constraints", None)
        else _repo_root() / "config" / "portfolio_constraints.yaml"
    )
    constraints = load_portfolio_constraints(cons_path if cons_path.exists() else None)

    if args.optimize and args.walkforward_optimize:
        print("error: choose one of --optimize or --walkforward-optimize", file=sys.stderr)
        return 1

    # Rotate and optimizer defaults are OFF unless CLI flags are set.
    rotate = bool(args.rotate_thematic)
    optimize = bool(args.optimize)
    walkforward_optimize = bool(args.walkforward_optimize)
    use_vol_gate = bool(args.rotate_vol_gate)
    hyst = args.hysteresis_months
    if hyst is None:
        hyst = int(constraints.get("hysteresis_months", 2)) if rotate else 0

    scores = None
    if args.scores:
        scores = pd.read_csv(args.scores)
        if "ticker" in scores.columns:
            scores["ticker"] = scores["ticker"].astype(str).str.upper()

    prices = None
    if args.prices:
        prices = load_adj_close_csv(args.prices)

    asof = pd.Timestamp(args.asof) if args.asof else None

    if walkforward_optimize:
        if prices is None:
            print("error: --walkforward-optimize requires --prices", file=sys.stderr)
            return 1
        if not args.universe:
            print("error: --walkforward-optimize requires --universe", file=sys.stderr)
            return 1
        cfg_path = Path(args.universe_config) if args.universe_config else _repo_root() / "config" / "universe.yaml"
        weights_path = Path(args.weights) if args.weights else _repo_root() / "config" / "feature_weights.yaml"
        uni_cfg = load_universe_config(cfg_path if cfg_path.exists() else None)
        weights_cfg = load_feature_weights(weights_path if weights_path.exists() else None)
        universe_df = load_universe_csv(args.universe)
        eligible = eligible_tickers(universe_df, uni_cfg)
        cats = category_map(universe_df, uni_cfg)
        if args.tickers:
            tickers = [t.strip().upper() for t in args.tickers.split(",")]
            assert_eligible(tickers, universe_df, uni_cfg)
        else:
            tickers = [t for t in prices.columns if t in eligible]
        tickers = [t for t in tickers if t in prices.columns]
        weights_df, ic_df, registry = walkforward_optimization_tables(
            prices,
            pd.Series({t: cats.get(t, "Unknown") for t in tickers}),
            tickers=tickers,
            universe_csv=args.universe,
            benchmark=args.benchmark,
            weights_cfg=weights_cfg,
            constraints=constraints,
            optimizer=args.optimizer,
            window_months=args.window_months,
            min_history_months=args.min_history_months,
            top_n=args.top_n,
        )
        weights_df.to_csv(out_path, index=False)
        print(f"wrote {len(weights_df)} walk-forward weight rows → {out_path}")
        ic_path = Path(args.ic_out) if args.ic_out else out_path.with_name(out_path.stem + "_ic.csv")
        write_ic_csv(ic_df, ic_path)
        print(f"wrote {len(ic_df)} IC rows → {ic_path}")
        reg_path = Path(args.registry_out) if args.registry_out else out_path.with_name(out_path.stem + "_strategy_registry.csv")
        write_strategy_registry(reg_path, registry)
        print(f"wrote strategy registry → {reg_path}")
        return 0

    uni_csv = args.universe
    try:
        if optimize:
            if scores is None or prices is None:
                raise ValueError("--optimize requires --scores and --prices")
            weights = build_optimized_portfolio(
                scores,
                prices,
                optimizer=args.optimizer,
                constraints=constraints,
                asof=asof,
                universe_csv=uni_csv,
                window_months=args.window_months,
                benchmark=args.benchmark,
                top_n=args.top_n,
            )
        else:
            weights = build_portfolio(
                scores=scores,
                prices=prices,
                rotate_thematic=rotate,
                use_vol_gate=use_vol_gate,
                hysteresis_months=int(hyst) if rotate else 0,
                constraints=constraints,
                asof=asof,
                universe_csv=uni_csv,
            )
    except UniverseGateError:
        raise
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    weights.to_csv(out_path, index=False)
    print(
        f"wrote {len(weights)} rows → {out_path} "
        f"(rotate_thematic={rotate}, optimize={optimize}, optimizer={args.optimizer})"
    )

    if optimize:
        reg_path = Path(args.registry_out) if args.registry_out else out_path.with_name(out_path.stem + "_strategy_registry.csv")
        write_strategy_registry(reg_path, optimizer_strategy_registry())
        print(f"wrote strategy registry → {reg_path}")

    if args.xlsx:
        xlsx_path = Path(args.xlsx)
        xlsx_path.parent.mkdir(parents=True, exist_ok=True)
        weights.to_excel(xlsx_path, index=False)
        print(f"wrote xlsx → {xlsx_path}")
    return 0


def cmd_walkforward_ic(args: argparse.Namespace) -> int:
    uni_path = Path(args.universe)
    prices_path = Path(args.prices)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cfg_path = Path(args.universe_config) if args.universe_config else _repo_root() / "config" / "universe.yaml"
    weights_path = Path(args.weights) if args.weights else _repo_root() / "config" / "feature_weights.yaml"
    uni_cfg = load_universe_config(cfg_path if cfg_path.exists() else None)
    weights_cfg = load_feature_weights(weights_path if weights_path.exists() else None)

    universe_df = load_universe_csv(uni_path)
    eligible = eligible_tickers(universe_df, uni_cfg)
    cats = category_map(universe_df, uni_cfg)
    prices = load_adj_close_csv(prices_path)

    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",")]
        assert_eligible(tickers, universe_df, uni_cfg)
    else:
        tickers = [t for t in prices.columns if t in eligible]

    tickers = [t for t in tickers if t in prices.columns]
    if len(tickers) < 3:
        print("error: need ≥3 tickers with prices for IC", file=sys.stderr)
        return 1

    cat_series = pd.Series({t: cats.get(t, "Unknown") for t in tickers})
    ic = walkforward_ic_table(
        prices,
        cat_series,
        tickers=tickers,
        benchmark=args.benchmark,
        weights_cfg=weights_cfg,
    )
    write_ic_csv(ic, out_path)
    mean_ic = ic["IC"].mean() if not ic.empty else float("nan")
    print(f"wrote {len(ic)} IC rows → {out_path} (mean IC={mean_ic:.4f})")

    if args.rotate_table:
        rot = rotation_on_off_next_month_table(
            prices,
            ticker=args.rotate_ticker.upper(),
            benchmark=args.benchmark,
            use_vol_gate=True,
            hysteresis_months=0,
        )
        rot_path = Path(args.rotate_table)
        rot_path.parent.mkdir(parents=True, exist_ok=True)
        rot.to_csv(rot_path, index=False)
        print(f"wrote rotate ON/OFF table → {rot_path}")
    return 0


def _parse_csv_list(value: str | None, *, cast=str) -> list:
    if value is None:
        return []
    return [cast(x.strip()) for x in str(value).split(",") if x.strip()]


def _write_csv(df: pd.DataFrame, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = df.copy()
    for col in tmp.columns:
        if pd.api.types.is_datetime64_any_dtype(tmp[col]):
            tmp[col] = pd.to_datetime(tmp[col]).dt.strftime("%Y-%m-%d")
    tmp.to_csv(out, index=False)
    return out


def cmd_walkforward_regime_dual(args: argparse.Namespace) -> int:
    from .regime_dual import load_and_run

    params = {key: value for key, value in vars(args).items() if value is not None}
    tables = load_and_run(params, pd.Timestamp(args.asof) if args.asof else None)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        _write_csv(frame, out / f"regime_dual_{name}.csv")
    print(f"wrote regime research tables → {out}")
    return 0


def cmd_walkforward_vol_target(args: argparse.Namespace) -> int:
    prices_path = Path(args.prices)
    universe_path = Path(args.universe)
    out_path = Path(args.out)
    weights_path = Path(args.weights)
    registry_path = Path(args.registry)
    returns_path = Path(args.returns) if args.returns else out_path.with_name("vol_target_oos_returns.csv")
    regime_path = Path(args.regime) if args.regime else out_path.with_name("vol_target_regime_table.csv")

    cfg_path = Path(args.config) if args.config else _repo_root() / "config" / "vol_target.yaml"
    vt_cfg = load_vol_target_config(cfg_path if cfg_path.exists() else None).get("vol_target", {})
    uni_cfg_path = Path(args.universe_config) if args.universe_config else _repo_root() / "config" / "universe.yaml"
    uni_cfg = load_universe_config(uni_cfg_path if uni_cfg_path.exists() else None)

    prices = load_adj_close_csv(prices_path)
    if args.grid:
        cores = _parse_csv_list(args.cores or ",".join(vt_cfg.get("apply_to", ["option_a"])), cast=str)
        lookbacks = _parse_csv_list(args.lookbacks or ",".join(map(str, vt_cfg.get("lookbacks", [21, 63, 252]))), cast=int)
        sigma_stars = _parse_csv_list(args.sigma_stars or "expanding,0.12,0.15", cast=str)
    else:
        cores = [args.core]
        lookbacks = [int(args.lookback)]
        sigma_stars = [args.sigma_star]

    sigma_stars = ["expanding_annvol" if str(s).lower() in {"expanding", "expanding_annvol"} else s for s in sigma_stars]
    trials = make_trials(
        cores=[c.lower() for c in cores],
        lookbacks=lookbacks,
        sigma_stars=sigma_stars,
        f_min=float(args.f_min if args.f_min is not None else vt_cfg.get("f_min", 0.25)),
        f_max=float(args.f_max if args.f_max is not None else vt_cfg.get("f_max", 1.0)),
        cash_ticker=str(args.cash or vt_cfg.get("cash_ticker", "BIL")).upper(),
        cost_bps_one_way=float(args.cost_bps if args.cost_bps is not None else vt_cfg.get("cost_bps_one_way", 5)),
    )
    summary, weights, returns, registry, regimes = run_vol_target_grid(
        prices,
        trials,
        universe_csv=universe_path,
        universe_config=uni_cfg,
        bootstrap_samples=int(args.bootstrap_samples if args.bootstrap_samples is not None else vt_cfg.get("bootstrap_samples", 1000)),
        bootstrap_block_months=int(vt_cfg.get("bootstrap_block_months", 3)),
    )
    if summary.empty:
        print("error: no vol-target OOS rows produced; check common price history", file=sys.stderr)
        return 1

    _write_csv(summary, out_path)
    _write_csv(weights, weights_path)
    _write_csv(returns, returns_path)
    _write_csv(registry, registry_path)
    _write_csv(regimes, regime_path)
    print(f"wrote vol-target summary → {out_path}")
    print(f"wrote monthly weights → {weights_path}")
    print(f"wrote OOS returns → {returns_path}")
    print(f"wrote trial registry → {registry_path}")
    print(f"wrote regime table → {regime_path}")
    return 0



def cmd_walkforward_vol_cond_factor_corr(args: argparse.Namespace) -> int:
    prices_path = Path(args.prices)
    universe_path = Path(args.universe)
    out_path = Path(args.out)
    weights_path = Path(args.weights)
    registry_path = Path(args.registry)
    returns_path = Path(args.returns) if args.returns else out_path.with_name("vol_cfc_oos_returns.csv")
    state_path = Path(args.state) if args.state else out_path.with_name("vol_cfc_state_table.csv")

    cfg_path = Path(args.config) if args.config else _repo_root() / "config" / "vol_cond_factor_corr.yaml"
    vc_cfg = load_vol_cond_factor_corr_config(cfg_path if cfg_path.exists() else None).get("vol_cond_factor_corr", {})
    uni_cfg_path = Path(args.universe_config) if args.universe_config else _repo_root() / "config" / "universe.yaml"
    uni_cfg = load_universe_config(uni_cfg_path if uni_cfg_path.exists() else None)

    prices = load_adj_close_csv(prices_path)
    monthly = None
    if args.monthly:
        monthly = pd.read_csv(args.monthly, index_col=0, parse_dates=True).sort_index()
        monthly.columns = [str(c).upper() for c in monthly.columns]
    coverage = None
    if args.coverage:
        coverage = pd.read_csv(args.coverage)

    if args.grid:
        lookbacks = _parse_csv_list(args.lookbacks or ",".join(map(str, vc_cfg.get("lookbacks", [21, 63, 126]))), cast=int)
        g_mins = _parse_csv_list(args.g_mins or ",".join(map(str, vc_cfg.get("g_min", [0.25, 0.5]))), cast=float)
        apply_tos = _parse_csv_list(args.apply_to or ",".join(vc_cfg.get("apply_to", ["option_a_vt"])), cast=str)
        z_rules = _parse_csv_list(args.z_rules or str(vc_cfg.get("z_rule", "mkt_vol")), cast=str)
        corr_lbs = _parse_csv_list(
            args.corr_lookbacks or ",".join(map(str, vc_cfg.get("corr_lookback_months", [6, 12]))),
            cast=int,
        )
    else:
        lookbacks = [int(args.lookback)]
        g_mins = [float(args.g_min)]
        apply_tos = [args.apply_to]
        z_rules = [args.z_rule]
        corr_lbs = [int(args.corr_lookback)] if args.corr_lookback is not None else None

    trials = make_vol_cfc_trials(
        lookbacks=lookbacks,
        g_mins=g_mins,
        z_rules=z_rules,
        apply_tos=apply_tos,
        f_min=float(args.f_min if args.f_min is not None else vc_cfg.get("f_min", 0.25)),
        f_max=float(args.f_max if args.f_max is not None else vc_cfg.get("f_max", 1.0)),
        sigma_star=args.sigma_star or vc_cfg.get("sigma_star", "expanding_annvol"),
        cash_ticker=str(args.cash or vc_cfg.get("cash_ticker", "BIL")).upper(),
        cost_bps_one_way=float(args.cost_bps if args.cost_bps is not None else vc_cfg.get("cost_bps_one_way", 5)),
        corr_lookback_months=corr_lbs,
        include_thin=bool(args.include_thin),
        min_names=int(args.min_names if args.min_names is not None else vc_cfg.get("min_names", 100)),
        core=str(args.core),
    )
    summary, weights, returns, registry, states = run_vol_cond_factor_corr_grid(
        prices,
        trials,
        universe_csv=universe_path,
        monthly=monthly,
        coverage=coverage,
        universe_config=uni_cfg,
        bootstrap_samples=int(
            args.bootstrap_samples
            if args.bootstrap_samples is not None
            else vc_cfg.get("bootstrap_samples", 500)
        ),
        bootstrap_block_months=int(vc_cfg.get("bootstrap_block_months", 3)),
    )
    if summary.empty:
        print("error: no vol-cond-factor-corr OOS rows produced; check common price history", file=sys.stderr)
        return 1

    _write_csv(summary, out_path)
    _write_csv(weights, weights_path)
    _write_csv(returns, returns_path)
    _write_csv(registry, registry_path)
    _write_csv(states, state_path)
    print(f"wrote vol-cond-factor-corr summary → {out_path}")
    print(f"wrote monthly weights → {weights_path}")
    print(f"wrote OOS returns → {returns_path}")
    print(f"wrote trial registry → {registry_path}")
    print(f"wrote state table → {state_path}")
    return 0


def cmd_run_strategies(args: argparse.Namespace) -> int:
    prices = load_adj_close_csv(args.prices)
    asof = pd.Timestamp(args.asof) if args.asof else None
    try:
        run_strategy_registry(
            prices=prices,
            universe_csv=args.universe,
            registry_path=args.registry,
            out_dir=args.out_dir,
            asof=asof,
            walkforward=bool(args.walkforward),
            universe_config_path=args.universe_config,
            constraints_path=args.constraints,
            weights_path=args.weights,
        )
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    out = Path(args.out_dir)
    print(f"wrote suggested weights → {out / 'suggested_weights.csv'}")
    print(f"wrote diagnostics → {out / 'strategy_diagnostics.csv'}")
    print(f"wrote comparison → {out / 'strategy_comparison.csv'}")
    print(f"wrote registry snapshot → {out / 'strategy_registry_used.csv'}")
    print(f"wrote xlsx → {out / 'strategy_comparison.xlsx'}")
    return 0


def cmd_walkforward_forecast_tangency_med(args: argparse.Namespace) -> int:
    """Walk-forward forecast-tangency + MED portfolio (Alexander & Scherer 2023)."""
    import pandas as pd

    universe_path = Path(args.universe)
    monthly_path = Path(args.monthly)
    out_path = Path(args.out)
    weights_path = Path(args.weights)
    registry_path = Path(args.registry)
    returns_path = (
        Path(args.returns) if args.returns else out_path.with_name("ft_med_oos_returns.csv")
    )
    coef_path = (
        Path(args.coef_out) if getattr(args, "coef_out", None)
        else out_path.with_name("ft_med_coef_forecast.csv")
    )

    cfg_path = (
        Path(args.config)
        if getattr(args, "config", None)
        else _repo_root() / "config" / "forecast_tangency_med.yaml"
    )
    ft_cfg = load_forecast_tangency_med_config(
        cfg_path if cfg_path.exists() else None
    ).get("forecast_tangency_med", {})

    uni_cfg_path = (
        Path(args.universe_config)
        if getattr(args, "universe_config", None)
        else _repo_root() / "config" / "universe.yaml"
    )
    uni_cfg = load_universe_config(uni_cfg_path if uni_cfg_path.exists() else None)

    monthly = pd.read_csv(monthly_path, index_col=0, parse_dates=True).sort_index()
    monthly.columns = [str(c).upper() for c in monthly.columns]

    nulls_requested = set(
        _parse_csv_list(getattr(args, "nulls", None) or "ew,lw_minvar,erc", cast=str)
    )

    ef_lookbacks = _parse_csv_list(
        getattr(args, "ef_lookbacks", None)
        or ",".join(map(str, ft_cfg.get("ef_lookbacks", [21]))),
        cast=int,
    )
    forecast_lookbacks = _parse_csv_list(
        getattr(args, "forecast_lookbacks", None)
        or ",".join(map(str, ft_cfg.get("forecast_lookbacks", [60]))),
        cast=int,
    )
    mu_estimators = _parse_csv_list(
        getattr(args, "mu_estimators", None)
        or ",".join(ft_cfg.get("mu_estimator", ["sample"])),
        cast=str,
    )
    apply_tos = _parse_csv_list(
        getattr(args, "apply_to", None)
        or ",".join(ft_cfg.get("apply_to", ["name_level"])),
        cast=str,
    )

    trials = make_ft_med_trials(
        ef_lookbacks=ef_lookbacks,
        forecast_lookbacks=forecast_lookbacks,
        mu_estimators=mu_estimators,
        apply_tos=apply_tos,
        cost_bps_one_way=float(
            getattr(args, "cost_bps", None)
            or ft_cfg.get("cost_bps_one_way", 5)
        ),
        cash_ticker=str(
            getattr(args, "cash", None) or ft_cfg.get("cash_ticker", "BIL")
        ).upper(),
        min_names=int(
            getattr(args, "min_names", None) or ft_cfg.get("min_names", 100)
        ),
        include_thin=bool(getattr(args, "include_thin", False)),
        min_history_months=int(
            getattr(args, "min_history_months", None) or ft_cfg.get("min_history_months", 24)
        ),
    )

    if not trials:
        print("error: no trials configured", file=sys.stderr)
        return 1

    coverage = None
    if getattr(args, "coverage", None) and Path(args.coverage).exists():
        coverage = pd.read_csv(args.coverage)

    summary, monthly_weights, oos_returns, registry = run_forecast_tangency_med_grid(
        monthly,
        trials,
        universe_csv=universe_path,
        coverage=coverage,
        universe_config=uni_cfg,
        bootstrap_samples=int(
            getattr(args, "bootstrap_samples", None)
            or ft_cfg.get("bootstrap_samples", 500)
        ),
    )

    if summary.empty:
        print(
            "error: no FT-MED OOS rows produced; check common price history and min_names",
            file=sys.stderr,
        )
        return 1

    _write_csv(summary, out_path)
    _write_csv(monthly_weights, weights_path)
    _write_csv(oos_returns, returns_path)
    _write_csv(registry, registry_path)

    # Extract coef / forecast columns for separate output
    coef_cols = [
        "date", "decision_date", "trial_id",
        "coef_r_mvp", "coef_sigma_mvp", "coef_u",
        "fc_r_mvp", "fc_sigma_mvp", "fc_u",
        "rhat_tp", "sigmahat_tp", "r_star", "distance",
    ]
    if not oos_returns.empty:
        avail = [c for c in coef_cols if c in oos_returns.columns]
        _write_csv(oos_returns[avail], coef_path)

    print(f"wrote FT-MED summary       → {out_path}")
    print(f"wrote monthly weights       → {weights_path}")
    print(f"wrote OOS returns           → {returns_path}")
    print(f"wrote trial registry        → {registry_path}")
    print(f"wrote coef/forecast table   → {coef_path}")
    print(
        f"nulls computed: EW (null_a), LW MinVar (null_b), ERC (null_c), LW MVO (null_d)"
    )
    print(f"nulls requested: {sorted(nulls_requested)}")
    return 0


def cmd_walkforward_regime_resilient_erc(args: argparse.Namespace) -> int:
    """Walk-forward regime-resilient ERC (LOIM regime-parity + stress/corr overlays).

    Construction overlays only — NOT dual-regime asset selection (archived #2).
    Primary null: unconditional ERC. Additional nulls: EW, LW MinVar.
    Registry enabled:false until Quant gate PASS.

    Research tooling only; not investment advice.
    Lead citation: Ielpo, Muhammetgulyyeva & Royer (2026), JPM 52(9):189-213.
    doi:10.3905/jpm.2026.030
    """
    import pandas as pd

    universe_path = Path(args.universe)
    monthly_path = Path(args.monthly)
    out_path = Path(args.out)
    weights_path = Path(args.weights)
    registry_path = Path(args.registry)
    returns_path = Path(args.returns) if args.returns else out_path.with_name("rr_erc_oos_returns.csv")
    diag_path = Path(args.diag_out) if getattr(args, "diag_out", None) else out_path.with_name("rr_erc_construction_diag.csv")

    cfg_path = (
        Path(args.config) if getattr(args, "config", None)
        else _repo_root() / "config" / "regime_resilient_erc.yaml"
    )
    rr_cfg = load_regime_resilient_erc_config(
        cfg_path if cfg_path.exists() else None
    ).get("regime_resilient_erc", {})

    uni_cfg_path = (
        Path(args.universe_config) if getattr(args, "universe_config", None)
        else _repo_root() / "config" / "universe.yaml"
    )
    uni_cfg = load_universe_config(uni_cfg_path if uni_cfg_path.exists() else None)

    monthly = pd.read_csv(monthly_path, index_col=0, parse_dates=True).sort_index()
    monthly.columns = [str(c).upper() for c in monthly.columns]

    constructions = _parse_csv_list(
        getattr(args, "constructions", None)
        or ",".join(rr_cfg.get("construction", ["stress_corr_overlay"])),
        cast=str,
    )
    stress_windows = _parse_csv_list(
        getattr(args, "stress_windows", None)
        or ",".join(map(str, rr_cfg.get("stress_window_months", [12]))),
        cast=int,
    )
    mix_lambdas = _parse_csv_list(
        getattr(args, "mix_lambdas", None)
        or ",".join(map(str, rr_cfg.get("mix_lambda", [0.25]))),
        cast=float,
    )
    corr_gates_raw = _parse_csv_list(
        getattr(args, "corr_breakdown_gates", None) or "false",
        cast=str,
    )
    corr_gates = [v.lower() not in ("false", "0", "no") for v in corr_gates_raw]

    regime_pool_rules = _parse_csv_list(
        getattr(args, "regime_pool_rules", None)
        or ",".join(rr_cfg.get("regime_pool_rule", ["rolling_vol_split"])),
        cast=str,
    )
    pi_rules = _parse_csv_list(
        getattr(args, "pi_rules", None)
        or ",".join(rr_cfg.get("pi_rule", ["historical_freq"])),
        cast=str,
    )
    cov_estimators = _parse_csv_list(
        getattr(args, "cov_estimators", None)
        or ",".join(rr_cfg.get("cov_estimator", ["ledoit_wolf"])),
        cast=str,
    )
    min_obs_per_pools = _parse_csv_list(
        getattr(args, "min_obs_per_pools", None)
        or ",".join(map(str, rr_cfg.get("min_obs_per_pool", [24]))),
        cast=int,
    )
    apply_tos = _parse_csv_list(
        getattr(args, "apply_to", None)
        or ",".join(rr_cfg.get("apply_to", ["name_level"])),
        cast=str,
    )

    cost_bps = float(
        getattr(args, "cost_bps", None) or rr_cfg.get("cost_bps_one_way", 5)
    )
    cash_ticker = str(
        getattr(args, "cash", None) or rr_cfg.get("cash_ticker", "BIL")
    ).upper()
    min_names = int(
        getattr(args, "min_names", None) or rr_cfg.get("min_names", 100)
    )
    include_thin = bool(getattr(args, "include_thin", False))
    min_history_months = int(
        getattr(args, "min_history_months", None) or rr_cfg.get("min_history_months", 36)
    )

    trials = make_rr_erc_trials(
        constructions=constructions,
        stress_window_months=stress_windows,
        mix_lambdas=mix_lambdas,
        corr_breakdown_gates=corr_gates,
        regime_pool_rules=regime_pool_rules,
        pi_rules=pi_rules,
        cov_estimators=cov_estimators,
        min_obs_per_pools=min_obs_per_pools,
        apply_tos=apply_tos,
        cost_bps_one_way=cost_bps,
        cash_ticker=cash_ticker,
        min_names=min_names,
        include_thin=include_thin,
        min_history_months=min_history_months,
    )

    if not trials:
        print("error: no trials configured", file=sys.stderr)
        return 1

    coverage = None
    if getattr(args, "coverage", None) and Path(args.coverage).exists():
        coverage = pd.read_csv(args.coverage)

    summary, monthly_weights, oos_returns, construction_diag, registry = run_regime_resilient_erc_grid(
        monthly,
        trials,
        universe_csv=universe_path,
        coverage=coverage,
        universe_config=uni_cfg,
        bootstrap_samples=int(
            getattr(args, "bootstrap_samples", None)
            or rr_cfg.get("bootstrap_samples", 500)
        ),
    )

    if summary.empty:
        print(
            "error: no regime-resilient ERC OOS rows produced; check common price history and min_names",
            file=sys.stderr,
        )
        return 1

    _write_csv(summary, out_path)
    _write_csv(monthly_weights, weights_path)
    _write_csv(oos_returns, returns_path)
    _write_csv(registry, registry_path)
    _write_csv(construction_diag, diag_path)

    print(f"wrote RR-ERC summary              → {out_path}")
    print(f"wrote monthly weights              → {weights_path}")
    print(f"wrote OOS returns                  → {returns_path}")
    print(f"wrote trial registry               → {registry_path}")
    print(f"wrote construction diagnostics     → {diag_path}")
    print(f"trials run: {len(trials)}")
    print(
        "nulls computed: unconditional ERC (null_a, PRIMARY), "
        "EW (null_b), LW MinVar (null_c)"
    )
    print("construction: stress/corr overlays and/or LOIM regime-parity blend")
    print("NOT dual-regime asset selection (archived #2 — forbidden pattern).")
    return 0


def cmd_walkforward_skewness_managed(args: argparse.Namespace) -> int:
    """Walk-forward skewness-managed Book-2 overlay (Gong–Lynch–Ogden).

    Book-2 f_t = clip(σ*/σ̂_t, f_min, f_max); skew/left-tail gate g_t ∈ [g_min,1];
    f̃_t = f_t · g_t; residual → BIL.

    Primary null: unconditional Book-2 VT (Option A). Additional nulls: EW, LW MinVar, ERC.
    Registry enabled:false until Quant gate PASS.

    Research tooling only; not investment advice.
    Lead citation: Gong, Lynch & Ogden, Skewness Managed Portfolios (Jan 2025 / Jul 2026).
    """
    import pandas as pd

    universe_path = Path(args.universe)
    out_path = Path(args.out)
    weights_path = Path(args.weights)
    registry_path = Path(args.registry)
    returns_path = (
        Path(args.returns) if getattr(args, "returns", None)
        else out_path.with_name("skew_managed_oos_returns.csv")
    )
    state_path = (
        Path(args.state_out) if getattr(args, "state_out", None)
        else out_path.with_name("skew_managed_state_table.csv")
    )

    cfg_path = (
        Path(args.config) if getattr(args, "config", None)
        else _repo_root() / "config" / "skewness_managed.yaml"
    )
    sm_cfg = load_skewness_managed_config(
        cfg_path if cfg_path.exists() else None
    ).get("skewness_managed", {})

    uni_cfg_path = (
        Path(args.universe_config) if getattr(args, "universe_config", None)
        else _repo_root() / "config" / "universe.yaml"
    )
    uni_cfg = load_universe_config(uni_cfg_path if uni_cfg_path.exists() else None)

    prices = load_adj_close_csv(Path(args.prices))

    monthly = None
    if getattr(args, "monthly", None):
        monthly = pd.read_csv(args.monthly, index_col=0, parse_dates=True).sort_index()
        monthly.columns = [str(c).upper() for c in monthly.columns]

    coverage = None
    if getattr(args, "coverage", None) and Path(args.coverage).exists():
        coverage = pd.read_csv(args.coverage)

    if getattr(args, "grid", False):
        lookbacks = _parse_csv_list(
            getattr(args, "lookbacks", None) or ",".join(map(str, sm_cfg.get("lookbacks", [21, 63, 126]))),
            cast=int,
        )
        g_mins = _parse_csv_list(
            getattr(args, "g_mins", None) or ",".join(map(str, sm_cfg.get("g_min", [0.25, 0.5]))),
            cast=float,
        )
        skew_estimators = _parse_csv_list(
            getattr(args, "skew_estimators", None)
            or ",".join(sm_cfg.get("skew_estimator", ["realized_amaya", "expected_bmv_lite"])),
            cast=str,
        )
        left_tail_rules = _parse_csv_list(
            getattr(args, "left_tail_rules", None)
            or ",".join(sm_cfg.get("left_tail_rule", ["cvar_5", "adverse_rs", "pct_lt_neg_k_sigma"])),
            cast=str,
        )
        apply_tos = _parse_csv_list(
            getattr(args, "apply_to", None)
            or ",".join(sm_cfg.get("apply_to", ["option_a_vt"])),
            cast=str,
        )
        skew_lbs = _parse_csv_list(
            getattr(args, "skew_lookbacks", None)
            or ",".join(map(str, sm_cfg.get("skew_lookback_months", [63]))),
            cast=int,
        )
    else:
        lookbacks = [int(getattr(args, "lookback", 63))]
        g_mins = [float(getattr(args, "g_min", sm_cfg.get("g_min", [0.5])[0] if isinstance(sm_cfg.get("g_min"), list) else sm_cfg.get("g_min", 0.5)))]
        skew_estimators = [str(getattr(args, "skew_estimator", "realized_amaya"))]
        left_tail_rules = [str(getattr(args, "left_tail_rule", "cvar_5"))]
        apply_tos = [str(getattr(args, "apply_to", "option_a_vt"))]
        skew_lbs = [int(getattr(args, "skew_lookback", 63))]

    trials = make_skew_managed_trials(
        lookbacks=lookbacks,
        g_mins=g_mins,
        skew_estimators=skew_estimators,
        left_tail_rules=left_tail_rules,
        apply_tos=apply_tos,
        f_min=float(getattr(args, "f_min", None) or sm_cfg.get("f_min", 0.25)),
        f_max=float(getattr(args, "f_max", None) or sm_cfg.get("f_max", 1.0)),
        sigma_star=str(getattr(args, "sigma_star", None) or sm_cfg.get("sigma_star", "expanding_annvol")),
        cash_ticker=str(getattr(args, "cash", None) or sm_cfg.get("cash_ticker", "BIL")).upper(),
        cost_bps_one_way=float(getattr(args, "cost_bps", None) or sm_cfg.get("cost_bps_one_way", 5)),
        skew_lookback_months=skew_lbs,
        include_thin=bool(getattr(args, "include_thin", False)),
        min_names=int(getattr(args, "min_names", None) or sm_cfg.get("min_names", 100)),
        core=str(getattr(args, "core", "option_a")),
        cov_lookback_months=int(getattr(args, "cov_lookback_months", None) or sm_cfg.get("cov_lookback_months", 36)),
        max_null_names_cov=int(getattr(args, "cov_max_names", None) or sm_cfg.get("max_null_names_cov", 50)),
    )

    if not trials:
        print("error: no trials configured", file=sys.stderr)
        return 1

    summary, weights, returns, registry, states = run_skewness_managed_grid(
        prices,
        trials,
        universe_csv=universe_path,
        monthly=monthly,
        coverage=coverage,
        universe_config=uni_cfg,
        bootstrap_samples=int(
            getattr(args, "bootstrap_samples", None) or sm_cfg.get("bootstrap_samples", 500)
        ),
        bootstrap_block_months=int(sm_cfg.get("bootstrap_block_months", 3)),
    )

    if summary.empty:
        print(
            "error: no skewness-managed OOS rows produced; check price history and min_names",
            file=sys.stderr,
        )
        return 1

    _write_csv(summary, out_path)
    _write_csv(weights, weights_path)
    _write_csv(returns, returns_path)
    _write_csv(registry, registry_path)
    _write_csv(states, state_path)

    print(f"wrote skewness-managed summary    → {out_path}")
    print(f"wrote monthly weights             → {weights_path}")
    print(f"wrote OOS returns                 → {returns_path}")
    print(f"wrote trial registry              → {registry_path}")
    print(f"wrote gate state table            → {state_path}")
    print(f"trials run: {len(trials)}")
    print(
        "nulls: Book-2 VT (null_a, PRIMARY), "
        "Option A (null_b), EW (null_c), LW MinVar (null_d), ERC (null_e)"
    )
    print("registry enabled:false — no live book change until Quant gate PASS.")
    print("NOT a third book; Book-2 overlay only until PASS.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="usa_etf_features",
        description="USA research-universe ETF feature pipeline (research; not investment advice)",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("score-universe", help="Score eligible universe tickers")
    s.add_argument("--universe", required=True, help="Path to usa_universe_categorized.csv")
    s.add_argument("--prices", required=True, help="Wide adj-close CSV (Date + tickers)")
    s.add_argument("--out", required=True, help="Output scores CSV path")
    s.add_argument("--tickers", default=None, help="Optional comma-separated ticker filter")
    s.add_argument("--universe-config", default=None)
    s.add_argument("--weights", default=None)
    s.set_defaults(func=cmd_score_universe)

    b = sub.add_parser("build-portfolio", help="Build constrained growth portfolio")
    b.add_argument("--scores", default=None, help="Scores CSV (required unless --rotate-thematic)")
    b.add_argument("--prices", default=None, help="Adj-close CSV (required for --rotate-thematic)")
    b.add_argument("--universe", default=None, help="Universe CSV for gate under rotate")
    b.add_argument("--tickers", default=None, help="Optional comma-separated ticker filter for --walkforward-optimize")
    b.add_argument("--mode", default="growth")
    b.add_argument("--out", required=True)
    b.add_argument("--xlsx", default=None, help="Optional Excel output path")
    b.add_argument(
        "--rotate-thematic",
        action="store_true",
        default=False,
        help="Enable thematic rotation sleeve (default OFF). ScoreSimple when combined with --rotate-vol-gate.",
    )
    b.add_argument(
        "--rotate-vol-gate",
        action="store_true",
        default=False,
        help="ScoreSimple vol gate: vol_63 ≤ expanding Q90 through t-1 only",
    )
    b.add_argument(
        "--rotate-signal",
        default="mom12_1_rel_voo",
        help="Signal name (documented: mom12_1_rel_voo / ScoreSimple with vol gate)",
    )
    b.add_argument(
        "--hysteresis-months",
        type=int,
        default=None,
        help="Override config hysteresis_months (default 2 when rotating)",
    )
    b.add_argument("--asof", default=None, help="Decision date YYYY-MM-DD (default: last price date)")
    b.add_argument("--constraints", default=None)
    b.add_argument("--universe-config", default=None)
    b.add_argument("--weights", default=None, help="Feature weights YAML for --walkforward-optimize")
    b.add_argument("--benchmark", default="VOO")
    b.add_argument("--optimize", action="store_true", default=False, help="Build current M3 optimized portfolio")
    b.add_argument(
        "--walkforward-optimize",
        action="store_true",
        default=False,
        help="Write walk-forward optimized weights plus IC and strategy registry",
    )
    b.add_argument("--optimizer", choices=["P1", "P2", "P3"], default="P2")
    b.add_argument("--window-months", type=int, default=36)
    b.add_argument("--min-history-months", type=int, default=36)
    b.add_argument("--top-n", type=int, default=6)
    b.add_argument("--ic-out", default=None, help="Output IC CSV path for --walkforward-optimize")
    b.add_argument("--registry-out", default=None, help="Output strategy registry CSV path")
    b.set_defaults(func=cmd_build_portfolio)

    w = sub.add_parser("walkforward-ic", help="Walk-forward IC CSV (no same-month leakage)")
    w.add_argument("--universe", required=True)
    w.add_argument("--prices", required=True)
    w.add_argument("--out", required=True, help="ic_walkforward_*.csv")
    w.add_argument("--tickers", default=None)
    w.add_argument("--benchmark", default="VOO")
    w.add_argument("--rotate-table", default=None, help="Optional ON/OFF next-month excess CSV")
    w.add_argument("--rotate-ticker", default="XSD")
    w.add_argument("--universe-config", default=None)
    w.add_argument("--weights", default=None)
    w.set_defaults(func=cmd_walkforward_ic)

    vt = sub.add_parser("walkforward-vol-target", help="Walk-forward vol-target Option A vs static core")
    vt.add_argument("--prices", required=True, help="Wide adj-close CSV (Date + tickers)")
    vt.add_argument("--universe", required=True, help="Path to usa_universe_categorized.csv")
    vt.add_argument("--core", default="option_a", choices=["option_a", "g1"])
    vt.add_argument("--lookback", type=int, default=63)
    vt.add_argument("--f-min", type=float, default=None)
    vt.add_argument("--f-max", type=float, default=1.0)
    vt.add_argument("--sigma-star", default="expanding_annvol")
    vt.add_argument("--cash", default="BIL")
    vt.add_argument("--cost-bps", type=float, default=5.0)
    vt.add_argument("--out", required=True, help="vol_target_oos_summary.csv")
    vt.add_argument("--weights", required=True, help="vol_target_monthly_weights.csv")
    vt.add_argument("--registry", required=True, help="vol_target_trial_registry.csv")
    vt.add_argument("--returns", default=None, help="Optional vol_target_oos_returns.csv path")
    vt.add_argument("--regime", default=None, help="Optional vol_target_regime_table.csv path")
    vt.add_argument("--config", default=None, help="Vol-target YAML config")
    vt.add_argument("--universe-config", default=None)
    vt.add_argument("--grid", action="store_true", default=False, help="Run robustness grid")
    vt.add_argument("--cores", default=None, help="Comma-separated cores for --grid, e.g. option_a,g1")
    vt.add_argument("--lookbacks", default=None, help="Comma-separated lookbacks for --grid")
    vt.add_argument("--sigma-stars", default=None, help="Comma-separated sigma targets for --grid")
    vt.add_argument("--bootstrap-samples", type=int, default=None)
    vt.set_defaults(func=cmd_walkforward_vol_target)

    rd = sub.add_parser("walkforward-regime-dual", help="Category-sleeve dual-regime research grid")
    rd.add_argument("--panel-returns-path")
    rd.add_argument("--categorized-path")
    rd.add_argument("--coverage-path")
    rd.add_argument("--out-dir", required=True)
    rd.add_argument("--name-level", action="store_true", default=False)
    rd.add_argument("--min-names", type=int, default=100)
    rd.add_argument("--asof")
    rd.add_argument("--fit-mode", choices=["expanding", "rolling"], default="expanding")
    rd.add_argument("--min-history-months", type=int, default=36)
    rd.add_argument("--min-name-months", type=int, default=12)
    rd.add_argument("--rolling-window", type=int, default=60)
    rd.add_argument("--vol-window", type=int, default=6)
    rd.add_argument("--corr-window", type=int, default=12)
    rd.set_defaults(func=cmd_walkforward_regime_dual)

    rs = sub.add_parser("run-strategies", help="Run enabled strategies from config registry")
    rs.add_argument("--asof", default=None, help="Decision date YYYY-MM-DD")
    rs.add_argument("--walkforward", action="store_true", default=False, help="Run walk-forward comparison mode")
    rs.add_argument("--prices", required=True, help="Wide adj-close CSV (Date + tickers)")
    rs.add_argument("--universe", required=True, help="Path to usa_universe_categorized.csv")
    rs.add_argument("--registry", default=str(_repo_root() / "config" / "strategies.yaml"))
    rs.add_argument("--out-dir", required=True)
    rs.add_argument("--universe-config", default=None)
    rs.add_argument("--constraints", default=None)
    rs.add_argument("--weights", default=None, help="Feature weights YAML")
    rs.set_defaults(func=cmd_run_strategies)


    vc = sub.add_parser(
        "walkforward-vol-cond-factor-corr",
        help="Walk-forward Book-2 vol-target with conditional factor-correlation gate",
    )
    vc.add_argument("--prices", required=True, help="Wide adj-close CSV (Date + tickers)")
    vc.add_argument("--universe", required=True, help="Path to usa_universe_categorized.csv")
    vc.add_argument("--monthly", default=None, help="Optional monthly returns panel for sleeve corr")
    vc.add_argument("--coverage", default=None, help="Optional history coverage CSV (thin_lt5y)")
    vc.add_argument("--core", default="option_a", choices=["option_a", "g1"])
    vc.add_argument("--lookback", type=int, default=63)
    vc.add_argument("--corr-lookback", type=int, default=None, help="Monthly corr window (default from lookback)")
    vc.add_argument("--f-min", type=float, default=None)
    vc.add_argument("--f-max", type=float, default=1.0)
    vc.add_argument("--g-min", type=float, default=0.5)
    vc.add_argument("--z-rule", default="mkt_vol", choices=["mkt_vol", "inv_mkt_vol"])
    vc.add_argument("--apply-to", default="option_a_vt", choices=["option_a_vt", "category_sleeves"])
    vc.add_argument("--sigma-star", default="expanding_annvol")
    vc.add_argument("--cash", default="BIL")
    vc.add_argument("--cost-bps", type=float, default=5.0)
    vc.add_argument("--min-names", type=int, default=None)
    vc.add_argument("--include-thin", action="store_true", default=False)
    vc.add_argument("--null", default="book2_vol_target", help="Primary null label (informational)")
    vc.add_argument("--out", required=True, help="vol_cfc_oos_summary.csv")
    vc.add_argument("--weights", required=True, help="vol_cfc_monthly_weights.csv")
    vc.add_argument("--registry", required=True, help="vol_cfc_trial_registry.csv")
    vc.add_argument("--returns", default=None, help="Optional vol_cfc_oos_returns.csv path")
    vc.add_argument("--state", default=None, help="Optional vol_cfc_state_table.csv path")
    vc.add_argument("--config", default=None, help="vol_cond_factor_corr YAML config")
    vc.add_argument("--universe-config", default=None)
    vc.add_argument("--grid", action="store_true", default=False, help="Run robustness grid")
    vc.add_argument("--lookbacks", default=None, help="Comma-separated daily lookbacks for --grid")
    vc.add_argument("--corr-lookbacks", default=None, help="Comma-separated monthly corr lookbacks for --grid")
    vc.add_argument("--g-mins", default=None, help="Comma-separated g_min values for --grid")
    vc.add_argument("--z-rules", default=None, help="Comma-separated z rules for --grid")
    vc.add_argument("--bootstrap-samples", type=int, default=None)
    vc.set_defaults(func=cmd_walkforward_vol_cond_factor_corr)

    ftm = sub.add_parser(
        "walkforward-forecast-tangency-med",
        help="Walk-forward forecast-tangency + MED portfolio (Alexander & Scherer 2023)",
    )
    ftm.add_argument("--universe", required=True, help="Path to usa_universe_categorized.csv")
    ftm.add_argument("--monthly", required=True, help="Monthly returns panel CSV (Date × tickers)")
    ftm.add_argument("--coverage", default=None, help="Optional history coverage CSV (thin_lt5y flags)")
    ftm.add_argument("--nulls", default="ew,lw_minvar,erc", help="Comma-separated nulls (informational; all four always computed)")
    ftm.add_argument("--cost-bps", type=float, default=5.0, dest="cost_bps")
    ftm.add_argument("--cash", default="BIL")
    ftm.add_argument("--min-names", type=int, default=100, dest="min_names")
    ftm.add_argument("--min-history-months", type=int, default=24, dest="min_history_months")
    ftm.add_argument("--include-thin", action="store_true", default=False, dest="include_thin")
    ftm.add_argument("--ef-lookbacks", default=None, dest="ef_lookbacks", help="Comma-separated EF lookbacks in months, e.g. 21,63")
    ftm.add_argument("--forecast-lookbacks", default=None, dest="forecast_lookbacks", help="Comma-separated VARX lookbacks in months, e.g. 60")
    ftm.add_argument("--mu-estimators", default=None, dest="mu_estimators", help="Comma-separated mu estimators: sample,james_stein")
    ftm.add_argument("--apply-to", default=None, dest="apply_to", help="Comma-separated apply_to: name_level,category_sleeves")
    ftm.add_argument("--out", required=True, help="ft_med_oos_summary.csv")
    ftm.add_argument("--weights", required=True, help="ft_med_monthly_weights.csv")
    ftm.add_argument("--registry", required=True, help="ft_med_trial_registry.csv")
    ftm.add_argument("--returns", default=None, help="Optional ft_med_oos_returns.csv path")
    ftm.add_argument("--coef-out", default=None, dest="coef_out", help="Optional ft_med_coef_forecast.csv path")
    ftm.add_argument("--config", default=None, help="forecast_tangency_med YAML config path")
    ftm.add_argument("--universe-config", default=None, dest="universe_config")
    ftm.add_argument("--bootstrap-samples", type=int, default=500, dest="bootstrap_samples")
    ftm.set_defaults(func=cmd_walkforward_forecast_tangency_med)

    rr = sub.add_parser(
        "walkforward-regime-resilient-erc",
        help=(
            "Walk-forward regime-resilient ERC (LOIM regime-parity + stress/corr overlays). "
            "Construction only — NOT dual-regime selection. "
            "Primary null: unconditional ERC. Registry enabled:false until Quant gate PASS. "
            "Research only; not investment advice."
        ),
    )
    rr.add_argument("--universe", required=True, help="Path to usa_universe_categorized.csv")
    rr.add_argument("--monthly", required=True, help="Monthly returns panel CSV (Date × tickers)")
    rr.add_argument("--coverage", default=None, help="Optional history coverage CSV (thin_lt5y flags)")
    rr.add_argument("--out", required=True, help="rr_erc_oos_summary.csv")
    rr.add_argument("--weights", required=True, help="rr_erc_monthly_weights.csv")
    rr.add_argument("--registry", required=True, help="rr_erc_trial_registry.csv")
    rr.add_argument("--returns", default=None, help="Optional rr_erc_oos_returns.csv path")
    rr.add_argument("--diag-out", default=None, dest="diag_out", help="Optional rr_erc_construction_diag.csv path")
    rr.add_argument(
        "--constructions", default=None,
        help="Comma-separated construction paths: stress_corr_overlay,loim_regime_parity",
    )
    rr.add_argument("--stress-windows", default=None, dest="stress_windows",
                    help="Comma-separated stress_window_months values, e.g. 12,24")
    rr.add_argument("--mix-lambdas", default=None, dest="mix_lambdas",
                    help="Comma-separated mix_lambda values (Path A), e.g. 0.25,0.5")
    rr.add_argument("--corr-breakdown-gates", default=None, dest="corr_breakdown_gates",
                    help="Comma-separated corr_breakdown_gate values: false,true")
    rr.add_argument("--regime-pool-rules", default=None, dest="regime_pool_rules",
                    help="Comma-separated regime pool rules: rolling_vol_split,nber_lag")
    rr.add_argument("--pi-rules", default=None, dest="pi_rules",
                    help="Comma-separated pi_rule values: historical_freq,markov_steady")
    rr.add_argument("--cov-estimators", default=None, dest="cov_estimators",
                    help="Comma-separated cov estimators: ledoit_wolf,sample")
    rr.add_argument("--min-obs-per-pools", default=None, dest="min_obs_per_pools",
                    help="Comma-separated min_obs_per_pool values, e.g. 24,36")
    rr.add_argument("--apply-to", default=None, dest="apply_to",
                    help="Comma-separated apply_to: name_level,category_sleeves")
    rr.add_argument("--cost-bps", type=float, default=5.0, dest="cost_bps")
    rr.add_argument("--cash", default="BIL")
    rr.add_argument("--min-names", type=int, default=100, dest="min_names")
    rr.add_argument("--min-history-months", type=int, default=36, dest="min_history_months")
    rr.add_argument("--include-thin", action="store_true", default=False, dest="include_thin")
    rr.add_argument("--config", default=None, help="regime_resilient_erc YAML config path")
    rr.add_argument("--universe-config", default=None, dest="universe_config")
    rr.add_argument("--bootstrap-samples", type=int, default=500, dest="bootstrap_samples")
    rr.set_defaults(func=cmd_walkforward_regime_resilient_erc)

    sp = sub.add_parser("walkforward-spectral-rp", help="Experimental panel spectral RP and nulls")
    sp.add_argument("--returns", required=True)
    sp.add_argument("--universe", required=True)
    sp.add_argument("--coverage", required=True)
    sp.add_argument("--out-dir", required=True)
    sp.add_argument("--lookback", type=int, default=60)
    sp.add_argument("--gamma", type=float, default=1.0)
    sp.add_argument("--mode", choices=["name", "sleeve"], default="name")
    sp.add_argument("--include-thin", choices=["true", "false"], default="false")
    sp.add_argument("--adv-min", type=float, default=0.0)
    sp.add_argument("--asof", default=None)
    sp.set_defaults(func=cmd_walkforward_spectral_rp)

    sm = sub.add_parser(
        "walkforward-skewness-managed",
        help=(
            "Walk-forward skewness-managed Book-2 overlay (Gong–Lynch–Ogden). "
            "Gates/rescales Book-2 vol-target using skewness/left-tail diagnostics. "
            "Primary null: unconditional Book-2 VT. Registry enabled:false until Quant gate PASS. "
            "Research only; not investment advice."
        ),
    )
    sm.add_argument("--prices", required=True, help="Wide adj-close CSV (Date + tickers)")
    sm.add_argument("--universe", required=True, help="Path to usa_universe_categorized.csv")
    sm.add_argument("--monthly", default=None, help="Optional monthly returns panel CSV (Date × tickers)")
    sm.add_argument("--coverage", default=None, help="Optional history coverage CSV (thin_lt5y flags)")
    sm.add_argument("--out", required=True, help="skew_managed_oos_summary.csv")
    sm.add_argument("--weights", required=True, help="skew_managed_monthly_weights.csv")
    sm.add_argument("--registry", required=True, help="skew_managed_trial_registry.csv")
    sm.add_argument("--returns", default=None, help="Optional skew_managed_oos_returns.csv path", dest="returns")
    sm.add_argument("--state-out", default=None, dest="state_out", help="Optional skew_managed_state_table.csv path")
    sm.add_argument("--null", default="book2_vol_target", help="Primary null label (informational)")
    sm.add_argument("--core", default="option_a", choices=["option_a", "g1"])
    sm.add_argument("--lookback", type=int, default=63)
    sm.add_argument("--f-min", type=float, default=None, dest="f_min")
    sm.add_argument("--f-max", type=float, default=1.0, dest="f_max")
    sm.add_argument("--g-min", type=float, default=0.5, dest="g_min")
    sm.add_argument("--sigma-star", default="expanding_annvol", dest="sigma_star")
    sm.add_argument("--skew-estimator", default="realized_amaya", dest="skew_estimator",
                    choices=["realized_amaya", "expected_bmv_lite"])
    sm.add_argument("--left-tail-rule", default="cvar_5", dest="left_tail_rule",
                    choices=["cvar_5", "adverse_rs", "pct_lt_neg_k_sigma"])
    sm.add_argument("--skew-lookback", type=int, default=63, dest="skew_lookback",
                    help="Monthly lookback for CVaR / tail score")
    sm.add_argument("--apply-to", default="option_a_vt", dest="apply_to",
                    choices=["option_a_vt", "category_sleeves"])
    sm.add_argument("--cash", default="BIL")
    sm.add_argument("--cost-bps", type=float, default=5.0, dest="cost_bps")
    sm.add_argument("--min-names", type=int, default=100, dest="min_names")
    sm.add_argument("--cov-lookback-months", type=int, default=36, dest="cov_lookback_months")
    sm.add_argument("--cov-max-names", type=int, default=50, dest="cov_max_names",
                    help="Max names for LW MinVar/ERC null computation (default 50)")
    sm.add_argument("--include-thin", action="store_true", default=False, dest="include_thin")
    sm.add_argument("--config", default=None, help="skewness_managed YAML config path")
    sm.add_argument("--universe-config", default=None, dest="universe_config")
    sm.add_argument("--bootstrap-samples", type=int, default=500, dest="bootstrap_samples")
    sm.add_argument("--grid", action="store_true", default=False, help="Run robustness grid")
    sm.add_argument("--lookbacks", default=None, help="Comma-separated vol lookbacks for --grid")
    sm.add_argument("--g-mins", default=None, dest="g_mins", help="Comma-separated g_min values for --grid")
    sm.add_argument("--skew-estimators", default=None, dest="skew_estimators",
                    help="Comma-separated skew estimators for --grid: realized_amaya,expected_bmv_lite")
    sm.add_argument("--left-tail-rules", default=None, dest="left_tail_rules",
                    help="Comma-separated left-tail rules for --grid: cvar_5,adverse_rs,pct_lt_neg_k_sigma")
    sm.add_argument("--skew-lookbacks", default=None, dest="skew_lookbacks",
                    help="Comma-separated monthly skew lookbacks for --grid, e.g. 21,63")
    sm.set_defaults(func=cmd_walkforward_skewness_managed)

    return p


def cmd_walkforward_spectral_rp(args) -> int:
    from .spectral_risk_parity import SpectralTrial, read_returns, run_spectral_trial, write_artifacts
    trial = SpectralTrial(lookback=args.lookback, gamma=args.gamma, mode=args.mode,
                          include_thin=args.include_thin == "true", adv_min=args.adv_min)
    panel = read_returns(args.returns)
    if args.asof:
        panel = panel.loc[:args.asof]
    result = run_spectral_trial(panel, pd.read_csv(args.universe), pd.read_csv(args.coverage), trial)
    write_artifacts(result, args.out_dir)
    print(result["summary"].to_string(index=False))
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code = args.func(args)
    except UniverseGateError as e:
        print(f"universe gate: {e}", file=sys.stderr)
        raise SystemExit(1) from e
    raise SystemExit(code)


if __name__ == "__main__":
    main()
