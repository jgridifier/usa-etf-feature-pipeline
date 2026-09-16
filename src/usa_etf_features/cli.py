"""CLI: score-universe, build-portfolio, walkforward-ic."""

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
from .universe import (
    UniverseGateError,
    assert_eligible,
    category_map,
    eligible_tickers,
    load_universe_config,
    load_universe_csv,
    thin_history_set,
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="usa_etf_features",
        description="USA pre-approved ETF feature pipeline (research; not investment advice)",
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
