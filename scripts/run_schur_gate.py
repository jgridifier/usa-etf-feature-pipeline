#!/usr/bin/env python3
"""Run the locked Schur complementary allocator gate (trial 12) once, only from a clean, pinned commit."""
import argparse
from pathlib import Path

import pandas as pd

from usa_etf_features.schur_allocator import (
    ROOT, BOOTSTRAP_REPS, OUT_DIR, verify_preregistration, refuse_if_already_run, run_schur_gate,
    write_schur_artifacts,
)
from usa_etf_features.monthly_panel import load_monthly_panel


def main(argv=None, *, root=ROOT):
    # Deliberately first: no data loading (or argument-dependent bypass) before the guard.
    preregistration = verify_preregistration(root=root)
    argparse.ArgumentParser(description=__doc__).parse_args(argv)   # no options: fixed output, fixed reps
    root = Path(root)
    # One run: refuse before any data load if the canonical artifacts already exist.
    refuse_if_already_run(root)
    monthly = load_monthly_panel(root / 'data/raw/usa_universe_panel_monthly_returns.csv',
                                 coverage=root / 'data/raw/usa_universe_panel_history_coverage.csv')
    weekly = pd.read_csv(root / 'data/raw/usa_universe_panel_weekly_returns.csv', index_col=0, parse_dates=True)
    universe = pd.read_csv(root / 'data/raw/usa_universe_categorized.csv')
    result = run_schur_gate(weekly, monthly, universe, bootstrap_reps=BOOTSTRAP_REPS, root=root)
    result['preregistration'] = preregistration
    return write_schur_artifacts(result, root / OUT_DIR)


if __name__ == '__main__':
    main()
