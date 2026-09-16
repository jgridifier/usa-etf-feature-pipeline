"""CLI: score-universe (M1); build-portfolio stub."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from .features import compute_raw_features
from .prices import load_adj_close_csv
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
    # Restrict to eligible ∩ available; hard-fail if CLI tickers filter includes off-list
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

    # Gate every scored ticker
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


def cmd_build_portfolio(_args: argparse.Namespace) -> int:
    print(
        "build-portfolio is not implemented in Milestone 1 "
        "(see config/portfolio_constraints.yaml stub).",
        file=sys.stderr,
    )
    return 2


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

    b = sub.add_parser("build-portfolio", help="Build constrained portfolio (M2+)")
    b.add_argument("--scores", required=True)
    b.add_argument("--mode", default="growth")
    b.add_argument("--out", required=True)
    b.set_defaults(func=cmd_build_portfolio)

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
