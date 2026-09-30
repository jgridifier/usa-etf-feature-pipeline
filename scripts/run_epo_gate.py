#!/usr/bin/env python3
"""Run the locked EPO gate only after the data refresh and a clean commit."""
import argparse
from pathlib import Path

import pandas as pd

from usa_etf_features.epo_allocator import (
    ROOT, BOOTSTRAP_REPS, verify_preregistration, run_epo_gate, write_epo_artifacts,
)
from usa_etf_features.monthly_panel import load_monthly_panel


def main(argv=None, *, root=ROOT):
    # Deliberately first: no data loading (or argument-dependent bypass) before the guard.
    preregistration = verify_preregistration(root=root)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', default='data/processed/epo_allocator')
    parser.add_argument('--bootstrap-reps', type=int, default=BOOTSTRAP_REPS)
    args = parser.parse_args(argv)
    if args.bootstrap_reps < BOOTSTRAP_REPS:
        parser.error('real-data gate requires at least 5000 bootstrap reps')
    root = Path(root)
    monthly = load_monthly_panel(root / 'data/raw/usa_universe_panel_monthly_returns.csv',
                                coverage=root / 'data/raw/usa_universe_panel_history_coverage.csv')
    weekly = pd.read_csv(root / 'data/raw/usa_universe_panel_weekly_returns.csv', index_col=0, parse_dates=True)
    universe = pd.read_csv(root / 'data/raw/usa_universe_categorized.csv')
    result = run_epo_gate(weekly, monthly, universe, bootstrap_reps=args.bootstrap_reps)
    result['preregistration'] = preregistration
    return write_epo_artifacts(result, root / args.out_dir)


if __name__ == '__main__':
    main()
