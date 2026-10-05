"""growth_alpha_adj_close.csv: one canonical, splice-free price file (fixed 2026-10-04).

The September refresh had spliced a partial-day 2026-09-16 snapshot into the file and chained the later rows onto
it. scripts/fix_growth_alpha_prices.py rebuilt the 29 columns from the full adjusted-close history; build_pages.py
copies that one file byte-for-byte to docs/data/. The full history (/workspace/investments/usa_universe_adj_close.csv)
is not in the repo, so CI checks the published copy against the committed panels built from that same file
(data/raw/usa_universe_panel_monthly_returns.csv, data/raw/usa_universe_panel_weekly_returns.csv) to 1e-6, plus
structure: no duplicate, out-of-order, weekend or partial-day rows. A future splice fails here. The daily check
against the full file runs wherever that file exists (the research box).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs/data/growth_alpha_adj_close.csv'
SAMPLE = ROOT / 'data/raw/growth_alpha_adj_close_sample.csv'
RECORD = ROOT / 'data/processed/prices_fix_2026-10/growth_alpha_fix_record.json'
MONTHLY = ROOT / 'data/raw/usa_universe_panel_monthly_returns.csv'
WEEKLY = ROOT / 'data/raw/usa_universe_panel_weekly_returns.csv'
FULL = Path('/workspace/investments/usa_universe_adj_close.csv')
CANONICAL = Path('/workspace/investments/growth_alpha_adj_close.csv')
SNAPSHOT_END = '2026-09-30'      # last complete day in the source snapshot
TOL = 1e-6


def _prices(path: Path = DOCS) -> pd.DataFrame:
    return pd.read_csv(path, index_col=0, float_precision='round_trip')


def structure_problems(px: pd.DataFrame) -> list[str]:
    """Duplicate, out-of-order, weekend and post-snapshot (partial-day) rows."""
    idx = pd.to_datetime(px.index, format='%Y-%m-%d')
    out = []
    if idx.duplicated().any():
        out.append(f'duplicate dates: {list(px.index[idx.duplicated()])[:5]}')
    if not idx.is_monotonic_increasing:
        out.append('dates out of order')
    if (idx.dayofweek >= 5).any():
        out.append(f'weekend rows: {list(px.index[idx.dayofweek >= 5])[:5]}')
    if str(px.index[-1]) > SNAPSHOT_END:
        out.append(f'rows after the {SNAPSHOT_END} snapshot (partial day): {list(px.index[px.index > SNAPSHOT_END])}')
    return out


def _period_returns(px: pd.DataFrame, freq: str) -> pd.DataFrame:
    px = px.copy()
    px.index = pd.to_datetime(px.index)
    last = px.groupby(px.index.to_period(freq)).tail(1)
    r = last.pct_change(fill_method=None)
    r.index = r.index.to_period(freq)
    return r.iloc[1:]


def panel_mismatches(px: pd.DataFrame, panel: Path, freq: str) -> pd.Series:
    """|period return from px - committed panel| over every overlapping period and ticker, above TOL."""
    p = pd.read_csv(panel, index_col=0, parse_dates=True, float_precision='round_trip')
    p.index = p.index.to_period(freq)
    r = _period_returns(px, freq)
    common = r.index.intersection(p.index)
    assert set(px.columns) <= set(p.columns)
    d = (r.loc[common, px.columns] - p.loc[common, px.columns]).abs().stack()
    both = r.loc[common, px.columns].notna() & p.loc[common, px.columns].notna()
    assert int(both.values.sum()) > 1000
    return d[d > TOL]


def daily_mismatches(px: pd.DataFrame, full: pd.DataFrame) -> pd.Series:
    full = full.loc[full.index.intersection(px.index), px.columns]
    assert len(full) == len(px)
    d = (px.pct_change(fill_method=None) - full.loc[px.index].pct_change(fill_method=None)).abs().stack()
    return d[d > TOL]


def test_published_copy_structure():
    px = _prices()
    assert px.shape == (5470, 29)
    assert structure_problems(px) == []
    assert str(px.index[0]) == '2005-01-03' and str(px.index[-1]) == SNAPSHOT_END


def test_monthly_returns_match_the_committed_panel():
    bad = panel_mismatches(_prices(), MONTHLY, 'M')
    assert bad.empty, bad.sort_values().tail(10)


def test_weekly_returns_match_the_committed_panel():
    bad = panel_mismatches(_prices(), WEEKLY, 'W-FRI')
    assert bad.empty, bad.sort_values().tail(10)


def test_one_canonical_file_recorded():
    rec = json.loads(RECORD.read_text())
    assert hashlib.sha256(DOCS.read_bytes()).hexdigest() == rec['new_sha256'] == rec['docs_copy_new_sha256']
    assert rec['old_sha256'] == rec['docs_copy_old_sha256'] == '6af174a5a0f9096e68e22a9a25695ba770c9877e1c761abe121432835b7c6d5c'
    assert rec['new_rows'] == rec['old_rows'] == 5470 and rec['columns'] == 29
    assert rec['worst_daily_return_diff_after']['diff'] <= TOL
    assert rec['worst_daily_return_diff_before'] == {'diff': pytest.approx(0.0110911, abs=1e-6), 'ticker': 'GVIP',
                                                    'date': '2026-09-16'}
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == rec['sample_new_sha256']


def test_sample_is_a_verbatim_slice_of_the_canonical_file():
    full = {ln.split(',', 1)[0]: ln for ln in DOCS.read_text().splitlines()}
    lines = SAMPLE.read_text().splitlines()
    assert lines[0] == DOCS.read_text().splitlines()[0]
    assert all(full[ln.split(',', 1)[0]] == ln for ln in lines[1:])
    assert structure_problems(_prices(SAMPLE)) == []


def test_build_pages_copies_the_canonical_file_unchanged():
    src = (ROOT / 'scripts/build_pages.py').read_text()
    assert "GROWTH_PRICES = Path('/workspace/investments/growth_alpha_adj_close.csv')" in src
    assert 'shutil.copyfile(GROWTH_PRICES, DATA / ' in src


@pytest.mark.skipif(not CANONICAL.exists(), reason='research-box file')
def test_canonical_file_equals_the_published_copy():
    assert CANONICAL.read_bytes() == DOCS.read_bytes()


@pytest.mark.skipif(not FULL.exists(), reason='full adjusted-close history is only on the research box')
def test_every_daily_return_matches_the_full_history():
    px = _prices()
    full = pd.read_csv(FULL, index_col=0, usecols=['Date'] + list(px.columns), float_precision='round_trip')
    bad = daily_mismatches(px, full)
    assert bad.empty, bad.sort_values().tail(10)


# The checks must catch the splice they were written for, and the generic row faults.

SPLICED = Path('/workspace/investments/growth_alpha_adj_close.csv.bak')


@pytest.mark.skipif(not SPLICED.exists(), reason='old spliced file is only on the research box')
def test_checks_fail_on_the_old_spliced_file():
    old = _prices(SPLICED)
    assert not panel_mismatches(old, MONTHLY, 'M').empty
    bad = panel_mismatches(old, WEEKLY, 'W-FRI')
    weeks = {str(p.end_time.date()) for p in bad.index.get_level_values(0)}
    assert '2026-09-18' in weeks and bad.loc[bad.index.get_level_values(0).astype(str).str.endswith('2026-09-18')].max() > 1e-3
    if FULL.exists():
        full = pd.read_csv(FULL, index_col=0, usecols=['Date'] + list(old.columns), float_precision='round_trip')
        assert '2026-09-16' in set(daily_mismatches(old, full).index.get_level_values(0))


def test_checks_fail_on_a_synthetic_splice_and_bad_rows():
    px = _prices()
    spliced = px.copy()
    i = spliced.index.get_loc('2026-09-16')
    spliced.iloc[i:] = spliced.iloc[i:] * 1.003          # a level shift chained from one day on
    assert not panel_mismatches(spliced, WEEKLY, 'W-FRI').empty
    assert any('duplicate' in p for p in structure_problems(pd.concat([px, px.iloc[[-1]]])))
    assert any('order' in p for p in structure_problems(px.iloc[::-1]))
    late = px.iloc[[-1]].copy()
    late.index = ['2026-10-01']
    assert any('partial day' in p for p in structure_problems(pd.concat([px, late])))
    wk = px.iloc[[-1]].copy()
    wk.index = ['2026-09-27']
    assert any('weekend' in p for p in structure_problems(pd.concat([px.iloc[:-1], wk])))
