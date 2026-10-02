#!/usr/bin/env python3
"""Run the locked Schur complementary allocator gate (trial 12) only from a clean, pinned commit."""
import argparse
from pathlib import Path

import pandas as pd

from usa_etf_features.schur_allocator import (
    ROOT, BOOTSTRAP_REPS, verify_preregistration, run_schur_gate, write_schur_artifacts,
)
from usa_etf_features.monthly_panel import load_monthly_panel


def main(argv=None, *, root=ROOT):
    # Deliberately first: no data loading (or argument-dependent bypass) before the guard.
    preregistration = verify_preregistration(root=root)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', default='data/processed/schur_allocator')
    args = parser.parse_args(argv)
    root = Path(root)
    monthly = load_monthly_panel(root / 'data/raw/usa_universe_panel_monthly_returns.csv',
                                 coverage=root / 'data/raw/usa_universe_panel_history_coverage.csv')
    weekly = pd.read_csv(root / 'data/raw/usa_universe_panel_weekly_returns.csv', index_col=0, parse_dates=True)
    universe = pd.read_csv(root / 'data/raw/usa_universe_categorized.csv')
    result = run_schur_gate(weekly, monthly, universe, bootstrap_reps=BOOTSTRAP_REPS, root=root)
    result['preregistration'] = preregistration
    return write_schur_artifacts(result, root / args.out_dir)


if __name__ == '__main__':
    main()
