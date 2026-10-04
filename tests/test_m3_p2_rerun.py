"""m3_p2_core_rotate: re-run unchanged on the fixed growth_alpha_adj_close.csv (2026-09-16 splice removed, 2026-10-04).

First restored for 2026-09 after #53; the 2026-10-04 price fix replaced the whole series with the re-run on the
rebuilt price file (data/processed/prices_fix_2026-10/growth_alpha_fix_record.json)."""
from __future__ import annotations

import csv
import hashlib
import inspect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'data/processed/live/m3_p2_rerun_2026-09'


def record():
    return json.loads((RUN / 'rerun_record.json').read_text())


def test_restored_cell_equals_the_saved_rerun_output():
    rec = record()
    live = [r for r in csv.DictReader((ROOT / 'data/processed/live/strategy_returns.csv').open())
            if r['strategy_id'] == 'm3_p2_core_rotate' and r['date'].startswith('2026-09')]
    rerun = [r for r in csv.DictReader((RUN / 'strategy_returns.csv').open())
             if r['strategy_id'] == 'm3_p2_core_rotate' and r['date'].startswith('2026-09')]
    assert len(live) == len(rerun) == 1
    assert float(live[0]['return']) == rec['restored_return'] == float(rerun[0]['return'])
    assert rec['other_months_checked'] == 179 and rec['series_replaced'] is True
    # Quant's expectation for 2026-09 on the fixed prices: -0.6847%.
    assert round(rec['restored_return'] * 100, 4) == -0.6847
    assert hashlib.sha256((RUN / 'strategy_returns.csv').read_bytes()).hexdigest() == \
        rec['output_sha256']['data/processed/live/m3_p2_rerun_2026-09/strategy_returns.csv']
    assert rec['prices_last_date'] == '2026-09-30'
    fix = json.loads((ROOT / 'data/processed/prices_fix_2026-10/growth_alpha_fix_record.json').read_text())
    assert rec['inputs_sha256']['/workspace/investments/growth_alpha_adj_close.csv'] == fix['new_sha256']


def test_whole_live_series_equals_the_saved_rerun_output():
    live = {r['date']: r for r in csv.DictReader((ROOT / 'data/processed/live/strategy_returns.csv').open())
            if r['strategy_id'] == 'm3_p2_core_rotate'}
    rerun = {r['date']: r for r in csv.DictReader((RUN / 'strategy_returns.csv').open())
             if r['strategy_id'] == 'm3_p2_core_rotate'}
    assert len(live) == len(rerun) == 180 and list(live) == list(rerun)
    for d, r in rerun.items():
        assert float(live[d]['return']) == float(r['return']) and float(live[d]['turnover']) == float(r['turnover']), d
        assert (live[d]['decision_date'], live[d]['feature_end']) == (r['decision_date'], r['feature_end']), d


def test_rerun_used_the_frozen_m3_code():
    """The M3 return path is byte-identical to the code recorded with the re-run."""
    from usa_etf_features import strategy_registry as sr, walkforward as wf
    got = {'strategy_registry._m3_returns': sr._m3_returns,
           'walkforward.walkforward_optimization_tables': wf.walkforward_optimization_tables}
    for name, fn in got.items():
        assert hashlib.sha256(inspect.getsource(fn).encode()).hexdigest() == record()['function_source_sha256'][name], name
    for rel in ('src/usa_etf_features/walkforward.py', 'src/usa_etf_features/portfolio.py', 'src/usa_etf_features/scores.py'):
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == record()['code_sha256'][rel], rel


def test_comparison_back_to_68_months_through_2026_09():
    rows = list(csv.DictReader((ROOT / 'docs/data/strategy_comparison.csv').open()))
    assert {r['n_months'] for r in rows} == {'68'} and {r['end_date'] for r in rows} == {'2026-09-30'}
    m3 = next(r for r in rows if r['strategy_id'] == 'm3_p2_core_rotate')
    assert m3['NW_t_vs_option_a']
