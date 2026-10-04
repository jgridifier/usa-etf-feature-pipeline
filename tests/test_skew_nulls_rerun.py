"""Skew-managed gate-first EW / MinVar / ERC nulls, 2026-09: restored from an unchanged complete-month re-run
(follow-up to #53, same approach as #56). See scripts/restore_skew_nulls_rerun.py."""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / 'data/processed/live'
RUN = LIVE / 'skew_nulls_rerun_2026-09'
ROW = '2026-09-30'
EXPECTED = {'r_null_c': -0.009814917499939884, 'r_null_d': -0.0032092819326397432, 'r_null_e': -0.006988083893757187}


def record():
    return json.loads((RUN / 'rerun_record.json').read_text())


def frames():
    live = pd.read_csv(LIVE / 'skew_managed_gatefirst_returns.csv', float_precision='round_trip').set_index('date')
    rerun = pd.read_csv(RUN / 'skew_managed_gatefirst_returns.csv', float_precision='round_trip').set_index('date')
    return live, rerun


def test_restored_cells_equal_the_saved_rerun_output():
    rec = record()
    live, rerun = frames()
    for c, v in EXPECTED.items():
        assert live.at[ROW, c] == rerun.at[ROW, c] == rec['restored'][c] == v, c
        k = c[-1]
        assert live.at[ROW, f'r_active_vs_{k}'] == pytest.approx(live.at[ROW, 'r_method'] - v, abs=1e-15)
        assert rec['restored'][f'r_active_vs_{k}'] == live.at[ROW, f'r_active_vs_{k}']
    assert rec['cell_before_restore'] == {c: '' for c in EXPECTED}
    assert rec['prices_last_date'] == ROW


def test_every_other_cell_reproduces_the_committed_file():
    live, rerun = frames()
    assert list(live.index) == list(rerun.index) and len(live) == 68
    numeric = [c for c in live.columns if c not in ('decision_date', 'trial_id', 'gate_binding')]
    assert (live[numeric] - rerun[numeric]).abs().max().max() <= 1e-7
    assert (live['gate_binding'] == rerun['gate_binding']).all()
    rec = record()
    assert rec['other_months_checked'] == 67 and max(rec['max_abs_diff_other_months'].values()) <= rec['tolerance'] == 1e-7
    # September core-equivalent columns equal the committed complete-month panel core (not the partial +0.2412%).
    for c in ('r_method', 'r_null_a', 'r_null_b'):
        assert rerun.at[ROW, c] == pytest.approx(live.at[ROW, c], abs=1e-15)
        assert rerun.at[ROW, c] == rec['core_equivalent_2026_09']
    assert abs(rec['core_equivalent_2026_09'] - 0.002411878710272353) > 1e-3


def test_outputs_and_corrected_price_rows_match_recorded_hashes():
    rec = record()
    for rel, h in rec['output_sha256'].items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == h, rel
    rows = 'data/processed/live/skew_nulls_rerun_2026-09/prices_corrected_rows_2026-09-16_to_30.csv'
    assert hashlib.sha256((ROOT / rows).read_bytes()).hexdigest() == rec['inputs_sha256'][rows]
    p = pd.read_csv(ROOT / rows, index_col=0)
    assert p.index[0] == '2026-09-16' and p.index[-1] == ROW and len(p) == 11
    panel = 'data/raw/usa_universe_panel_monthly_returns.csv'
    assert hashlib.sha256((ROOT / panel).read_bytes()).hexdigest() == rec['inputs_sha256'][panel]


def test_rerun_used_the_frozen_skewness_managed_code():
    from usa_etf_features import skewness_managed as sm, vol_target as vt
    rec = record()
    for name, h in rec['function_source_sha256'].items():
        mod, fn = name.split('.')
        obj = getattr({'skewness_managed': sm, 'vol_target': vt}[mod], fn)
        assert hashlib.sha256(inspect.getsource(obj).encode()).hexdigest() == h, name
    for rel, h in rec['code_sha256'].items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == h, rel


def test_repair_script_keeps_the_restored_cells():
    import importlib.util
    spec = importlib.util.spec_from_file_location('repair', ROOT / 'scripts/repair_live_partial_month.py')
    repair = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(repair)
    for c, v in EXPECTED.items():
        assert repair._rerun_restored_cell('skew_managed_gatefirst_returns.csv', c, repr(v))
        assert not repair._rerun_restored_cell('skew_managed_gatefirst_returns.csv', c, repr(v + 1e-6))
    assert not repair._rerun_restored_cell('vol_target_oos_returns.csv', 'r_null_c', repr(EXPECTED['r_null_c']))


def test_live_book2_nulls_cover_68_months():
    live, _ = frames()
    for c in list(EXPECTED) + [f'r_active_vs_{k}' for k in 'cde']:
        assert live[c].notna().all() and len(live[c]) == 68, c
