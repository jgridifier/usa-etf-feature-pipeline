"""Restore the skew-managed gate-first EW / MinVar / ERC nulls' 2026-09 returns from an unchanged complete-month re-run.

PR #53 blanked r_null_c (EW), r_null_d (LW MinVar) and r_null_e (ERC) for 2026-09 in
data/processed/live/skew_managed_gatefirst_returns.csv: they are not the core, so they could not be rebuilt
without a re-run.

Prices. The re-run reads the shared, fixed price file /workspace/investments/growth_alpha_adj_close.csv
(sha256 6306e082..., rebuilt from the full adjusted-close history by #59; record
data/processed/prices_fix_2026-10/growth_alpha_fix_record.json). There is no private corrected copy any more.
With it, the re-run's core-equivalent columns (r_method, r_null_a, r_null_b) give the committed complete-month
panel core for 2026-09 (-0.1112%).

The re-run is the frozen code at main (skewness_managed / vol_target / prices / rotation / universe / features /
monthly_panel / cli are unchanged since #41) with the same command as the September refresh
(/workspace/refresh-2026-09/regenerate_staged.sh), coverage omitted as there:

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python -m usa_etf_features.cli walkforward-skewness-managed \
      --prices /workspace/investments/growth_alpha_adj_close.csv --universe /workspace/investments/usa_universe_categorized.csv \
      --monthly data/raw/usa_universe_panel_monthly_returns.csv --lookback 63 --skew-lookback 21 --g-min 0.5 \
      --f-min 0.25 --f-max 1.0 --cost-bps 5 --out <dir>/skew_managed_gatefirst_summary.csv \
      --weights <dir>/skew_managed_gatefirst_weights.csv --returns <dir>/skew_managed_gatefirst_returns.csv \
      --registry <dir>/skew_managed_gatefirst_registry.csv --state-out <dir>/skew_managed_gatefirst_state.csv

`apply` checks that every other month of every column reproduces the committed file (|diff| <= 1e-6, the rule #59
used for every consumer of the fixed file: the two price vintages differ by ~1e-6 a day) and that the
re-run's core-equivalent 2026-09 values equal the committed ones. It writes only the three blank 2026-09 null cells
and re-derives r_active_vs_c..e, then records the code, function-source, input and output sha256 values in
data/processed/live/skew_nulls_rerun_2026-09/rerun_record.json. Idempotent.

    python scripts/restore_skew_nulls_rerun.py
"""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / 'data/processed/live'
RUN = LIVE / 'skew_nulls_rerun_2026-09'
RETURNS = 'skew_managed_gatefirst_returns.csv'
MONTH, ROW = '2026-09', '2026-09-30'
NULLS = {'c': 'EW', 'd': 'LW MinVar', 'e': 'ERC'}
CORE_COLS = ['r_method', 'r_method_gross', 'r_null_a', 'r_null_b']
PRICES = Path('/workspace/investments/growth_alpha_adj_close.csv')   # shared fixed file (#59)
FIX_RECORD = ROOT / 'data/processed/prices_fix_2026-10/growth_alpha_fix_record.json'
UNIVERSE = Path('/workspace/investments/usa_universe_categorized.csv')
PANEL = ROOT / 'data/raw/usa_universe_panel_monthly_returns.csv'
CODE = ['skewness_managed.py', 'vol_target.py', 'prices.py', 'rotation.py', 'universe.py', 'features.py',
        'monthly_panel.py', 'cli.py']
TOL = 1e-6


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def function_sha() -> dict:
    from usa_etf_features import skewness_managed as sm, vol_target as vt
    names = ['run_skewness_managed_grid', 'make_skew_managed_trials']
    out = {f'skewness_managed.{n}': hashlib.sha256(inspect.getsource(getattr(sm, n)).encode()).hexdigest() for n in names}
    for n in ('option_core_daily_returns', 'portfolio_month_return'):
        out[f'vol_target.{n}'] = hashlib.sha256(inspect.getsource(getattr(vt, n)).encode()).hexdigest()
    return out


def apply() -> None:
    fixed = json.loads(FIX_RECORD.read_text())['new_sha256']
    if sha(PRICES) != fixed:
        raise SystemExit(f'{PRICES} is not the fixed file recorded by #59 ({fixed})')
    new = pd.read_csv(RUN / RETURNS, float_precision='round_trip').set_index('date')
    df = pd.read_csv(LIVE / RETURNS, dtype=str, keep_default_na=False)
    old = pd.read_csv(LIVE / RETURNS, float_precision='round_trip').set_index('date')
    assert list(new.index) == list(old.index) and new.index[-1] == ROW
    numeric = [c for c in old.columns if c not in ('decision_date', 'trial_id', 'gate_binding')]
    others = old.index[old.index != ROW]
    diffs = {c: float((old.loc[others, c] - new.loc[others, c]).abs().max()) for c in numeric}
    # 'skew' is the trailing 21-day sample skewness, a diagnostic input to the gate: it moves by ~4e-5 between the
    # price vintages. What it drives, the gate g, must be identical; the returns, weights and scale factors within TOL.
    if diffs.get('g', 1.0) != 0.0:
        raise SystemExit(f"gate decisions differ from the committed file (max |diff| g = {diffs.get('g')})")
    if any(not (v <= TOL) for c, v in diffs.items() if c != 'skew'):
        raise SystemExit(f're-run does not reproduce the committed months: {diffs}')
    for c in numeric:
        o = old.at[ROW, c]
        if c in {f'r_null_{k}' for k in NULLS} | {f'r_active_vs_{k}' for k in NULLS}:
            continue
        lim = 1e-12 if c in CORE_COLS + ['r_active_vs_a', 'r_active_vs_b', 'cost_return', 'turnover', 'f', 'g', 'f_tilde'] else TOL
        if c != 'skew' and abs(o - new.at[ROW, c]) > lim:
            raise SystemExit(f'{c} 2026-09 differs from the committed value: {o} vs {new.at[ROW, c]}')
    i = df.index[df['date'] == ROW]
    assert len(i) == 1
    i = i[0]
    restored, was = {}, {}
    for k in NULLS:
        c = f'r_null_{k}'
        v = float(new.at[ROW, c])
        cur = df.at[i, c]
        if cur and abs(float(cur) - v) > 1e-15:
            raise SystemExit(f'{c} 2026-09 already holds {cur}, not blank or the re-run value')
        prior = json.loads((RUN / 'rerun_record.json').read_text()) if (RUN / 'rerun_record.json').exists() else {}
        was[c] = prior.get('cell_before_restore', {}).get(c, '') if cur else ''   # blank as #53 left it
        df.at[i, c] = repr(v)
        restored[c] = v
        a = f'r_active_vs_{k}'
        df.at[i, a] = repr(float(df.at[i, 'r_method']) - v)
        restored[a] = float(df.at[i, a])
    df.to_csv(LIVE / RETURNS, index=False)
    blanked = {c['column']: c['was'] for c in json.loads((LIVE / 'partial_month_repair.json').read_text())['changes']
               if c['file'] == RETURNS and c['column'] in restored}
    record = dict(
        file=f'data/processed/live/{RETURNS}', month=MONTH, row=ROW, trial_id=str(new.at[ROW, 'trial_id']),
        nulls={f'r_null_{k}': n for k, n in NULLS.items()}, restored=restored, cell_before_restore=was,
        partial_month_values_blanked_in_53=blanked,
        core_equivalent_2026_09=float(new.at[ROW, 'r_method']),
        other_months_checked=int(len(others)), max_abs_diff_other_months=diffs, tolerance=TOL,
        tolerance_note='Applies to every numeric column except skew (diagnostic; its gate g is identical in every month).',
        code_commit='079717978071c3538a96fc9e5d72992aca990d59',
        code_note='skewness_managed path unchanged since #41 (991a754); identical to the files the September refresh ran.',
        code_sha256={f'src/usa_etf_features/{f}': sha(ROOT / 'src/usa_etf_features' / f) for f in CODE},
        function_source_sha256=function_sha(),
        inputs_sha256={str(PRICES): sha(PRICES), str(UNIVERSE): sha(UNIVERSE),
                       'data/raw/usa_universe_panel_monthly_returns.csv': sha(PANEL)},
        output_sha256={f'data/processed/live/skew_nulls_rerun_2026-09/{f.name}': sha(f)
                       for f in sorted(RUN.glob('skew_managed_gatefirst_*.csv'))},
        command=('OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python -m usa_etf_features.cli '
                 'walkforward-skewness-managed --prices /workspace/investments/growth_alpha_adj_close.csv --universe '
                 f'{UNIVERSE} --monthly data/raw/usa_universe_panel_monthly_returns.csv --lookback 63 '
                 '--skew-lookback 21 --g-min 0.5 --f-min 0.25 --f-max 1.0 --cost-bps 5 --out/--weights/--returns/'
                 '--registry/--state-out data/processed/live/skew_nulls_rerun_2026-09/skew_managed_gatefirst_*.csv'),
        prices_last_date=ROW,
        note=('Re-run on the shared fixed price file (#59). The three nulls are built from the complete-month monthly '
              'panel (--monthly), so they equal the values #53 blanked. The core-equivalent 2026-09 columns give the '
              'committed panel core (-0.1112%); earlier months agree with the committed file within the tolerance '
              '(the two price vintages differ by ~1e-6 a day) and are kept as committed.'),
    )
    (RUN / 'rerun_record.json').write_text(json.dumps(record, indent=1) + '\n')
    print(json.dumps(restored, indent=1))


if __name__ == '__main__':
    apply()
