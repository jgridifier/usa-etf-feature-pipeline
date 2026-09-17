"""CLI: score-universe, build-portfolio, walkforward-ic, walkforward-vol-target."""

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

    return p


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
