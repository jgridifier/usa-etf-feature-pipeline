"""Write the m3_p2_core_rotate data-restatement record (growth_alpha price fix, 2026-10-04).

Quant ruled on #59: keep the full-history restatement of m3_p2_core_rotate on the corrected prices. This is a data
restatement, not a new trial: code and registry params are frozen, nothing new is registered, the trial count is
unchanged. Every figure below is computed from the two return series (live/strategy_returns.csv before the fix, at
main e0ff4e3, and after) and the two comparison / site_sharpe files; build_pages.py renders the site note from the
`disclosure` block. Idempotent.

    PYTHONPATH=src python scripts/record_m3_p2_restatement.py
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed/prices_fix_2026-10/m3_p2_restatement.json'
FIX = ROOT / 'data/processed/prices_fix_2026-10/growth_alpha_fix_record.json'
RERUN = ROOT / 'data/processed/live/m3_p2_rerun_2026-09/rerun_record.json'
BEFORE = 'e0ff4e3ea9f8931f4538171e497dbae53fe0a294'      # main before the price fix
SID = 'm3_p2_core_rotate'
LAST = '2026-09'
RETURN_MOVE_TOL = 1e-6            # a month counts when its return moved by more than this
RETURN_FILES = ['data/processed/live/strategy_returns.csv',
                'data/processed/live/m3_p2_rerun_2026-09/strategy_returns.csv']


def _git(path: str) -> bytes:
    return subprocess.run(['git', 'show', f'{BEFORE}:{path}'], cwd=ROOT, check=True, capture_output=True).stdout


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _series(raw: bytes) -> pd.Series:
    df = pd.read_csv(io.BytesIO(raw), float_precision='round_trip')
    df = df[df.strategy_id == SID]
    return pd.Series(df['return'].values, index=df['date'].str[:7])


def _figures(cmp_raw: bytes, site_raw: bytes, series: pd.Series) -> dict:
    c = pd.read_csv(io.BytesIO(cmp_raw), float_precision='round_trip')
    r = c[c.strategy_id == SID].iloc[0]
    s = json.loads(site_raw)['comparison'][SID]
    return dict(return_2026_09=float(series[LAST]), AnnReturn=float(r.AnnReturn), AnnVol=float(r.AnnVol),
                MaxDD=float(r.MaxDD), Sharpe_rf0=float(r.Sharpe_rf0), Sharpe_exBIL=s['exbil'],
                NW_t_vs_option_a=float(r.NW_t_vs_option_a), turnover_per_year=float(r.turnover_per_year),
                n_months=int(r.n_months), window=f"{str(r.start_date)[:7]}..{str(r.end_date)[:7]}")


def main() -> None:
    fix = json.loads(FIX.read_text())
    rerun = json.loads(RERUN.read_text())
    old = _series(_git(RETURN_FILES[0]))
    new = _series((ROOT / RETURN_FILES[0]).read_bytes())
    assert list(old.index) == list(new.index)
    earlier = old.index[old.index != LAST]
    gap = (new - old).loc[earlier]
    moved = gap[gap.abs() > RETURN_MOVE_TOL]
    worst = gap.abs().idxmax()
    # Price differences between the two files outside the removed 2026-09-16 splice.
    o = pd.read_csv(io.BytesIO(_git('docs/data/growth_alpha_adj_close.csv')), index_col=0, float_precision='round_trip')
    n = pd.read_csv(ROOT / 'docs/data/growth_alpha_adj_close.csv', index_col=0, float_precision='round_trip')
    d = (o.pct_change(fill_method=None) - n.pct_change(fill_method=None)).abs()
    d = d[d.index < '2026-09-16'].stack()
    disclosure = dict(
        earlier_months=int(len(earlier)), months_returns_moved=int(len(moved)), return_move_tolerance=RETURN_MOVE_TOL,
        largest_gap_month=str(worst), largest_gap_pp=round(float(gap[worst]) * 100, 2),
        largest_gap_return_was=float(old[worst]), largest_gap_return_now=float(new[worst]),
        max_daily_return_diff_before_splice=float(d.max()), price_diff_bound=1e-4,
        months_returns_moved_list=list(moved.index),
        months_picks_differ=None,
        picks_measured=False,
        picks_note=('Not measured: the m3_p2 re-runs store monthly returns and turnover only; the only holdings written '
                    '(suggested_weights.csv) are the final 2026-09-30 snapshot, not a monthly history, under either price '
                    'file. The site note therefore says nothing about picks.'),
    )
    assert disclosure['max_daily_return_diff_before_splice'] < disclosure['price_diff_bound']
    record = dict(
        type='data restatement',
        not_a_new_trial=True,
        trial_count_change=0,
        trial_count_note=('No trial registered or re-specified: m3_p2_core_rotate keeps its registry entry '
                          '(registry_m3_p2_only.yaml, params hash 24f95afecd3b) and is re-run on corrected input data only.'),
        code_frozen=True, params_frozen=True,
        code_sha256=rerun['code_sha256'], function_source_sha256=rerun['function_source_sha256'],
        registry_sha256=rerun['inputs_sha256']['data/processed/live/m3_p2_rerun_2026-09/registry_m3_p2_only.yaml'],
        ruling='Quant, 2026-10-04 (#59): keep the full-history restatement of m3_p2_core_rotate.',
        reason='growth_alpha_adj_close.csv rebuilt from the full adjusted-close history (partial-day 2026-09-16 splice removed).',
        price_file=dict(path='/workspace/investments/growth_alpha_adj_close.csv (published copy docs/data/growth_alpha_adj_close.csv)',
                        old_sha256=fix['old_sha256'], new_sha256=fix['new_sha256']),
        return_files={p: dict(old_sha256=_sha(_git(p)), new_sha256=_sha((ROOT / p).read_bytes())) for p in RETURN_FILES},
        before=_figures(_git('docs/data/strategy_comparison.csv'), _git('data/processed/cash_null_audit/site_sharpe.json'), old),
        after=_figures((ROOT / 'docs/data/strategy_comparison.csv').read_bytes(),
                       (ROOT / 'data/processed/cash_null_audit/site_sharpe.json').read_bytes(), new),
        disclosure=disclosure,
        before_ref=BEFORE,
    )
    OUT.write_text(json.dumps(record, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps(disclosure | {'months_returns_moved_list': len(disclosure['months_returns_moved_list'])}, indent=1))


if __name__ == '__main__':
    main()
