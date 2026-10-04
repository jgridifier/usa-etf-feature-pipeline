"""Restore the skew-managed gate-first EW / MinVar / ERC nulls' 2026-09 returns from an unchanged complete-month re-run.

PR #53 blanked r_null_c (EW), r_null_d (LW MinVar) and r_null_e (ERC) for 2026-09 in
data/processed/live/skew_managed_gatefirst_returns.csv: they are not the core, so they could not be rebuilt
without a re-run.

Why the price file is corrected first. The live refresh's price file
(/workspace/investments/growth_alpha_adj_close.csv) carries a bad 2026-09-16 row: it is the partial-day snapshot
taken that day, and the later rows were spliced onto it. Its 2026-09-16 daily returns differ from the full price
history (/workspace/investments/usa_universe_adj_close.csv) by 0.1 to 1.1 points; every other day agrees to about 1e-6.
Re-running on that file reproduces the blanked partial values exactly. So `prices` writes a complete-month copy:
every line through 2026-09-15 is byte-for-byte the original, and 2026-09-16..2026-09-30 are the 2026-09-15 level
chained with the full-history daily returns. With it, the re-run's core-equivalent columns (r_method, r_null_a,
r_null_b) give exactly the committed complete-month panel core for 2026-09 (-0.1112%).

The re-run is the frozen code at main (skewness_managed / vol_target / prices / rotation / universe / features /
monthly_panel / cli are unchanged since #41) with the same command as the September refresh
(/workspace/refresh-2026-09/regenerate_staged.sh), coverage omitted as there:

    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python -m usa_etf_features.cli walkforward-skewness-managed \
      --prices <complete-month prices> --universe /workspace/investments/usa_universe_categorized.csv \
      --monthly data/raw/usa_universe_panel_monthly_returns.csv --lookback 63 --skew-lookback 21 --g-min 0.5 \
      --f-min 0.25 --f-max 1.0 --cost-bps 5 --out <dir>/skew_managed_gatefirst_summary.csv \
      --weights <dir>/skew_managed_gatefirst_weights.csv --returns <dir>/skew_managed_gatefirst_returns.csv \
      --registry <dir>/skew_managed_gatefirst_registry.csv --state-out <dir>/skew_managed_gatefirst_state.csv

`apply` checks that every other month of every column reproduces the committed file (|diff| <= 1e-7) and that the
re-run's core-equivalent 2026-09 values equal the committed ones. It writes only the three blank 2026-09 null cells
and re-derives r_active_vs_c..e, then records the code, function-source, input and output sha256 values in
data/processed/live/skew_nulls_rerun_2026-09/rerun_record.json. Idempotent.

    python scripts/restore_skew_nulls_rerun.py prices /tmp/growth_alpha_adj_close_complete_months.csv
    python scripts/restore_skew_nulls_rerun.py apply /tmp/growth_alpha_adj_close_complete_months.csv
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / 'data/processed/live'
RUN = LIVE / 'skew_nulls_rerun_2026-09'
RETURNS = 'skew_managed_gatefirst_returns.csv'
MONTH, ROW = '2026-09', '2026-09-30'
NULLS = {'c': 'EW', 'd': 'LW MinVar', 'e': 'ERC'}
CORE_COLS = ['r_method', 'r_method_gross', 'r_null_a', 'r_null_b']
FIRST_BAD = '2026-09-16'
SPLICED = Path('/workspace/investments/growth_alpha_adj_close.csv')
FULL = Path('/workspace/investments/usa_universe_adj_close.csv')
UNIVERSE = Path('/workspace/investments/usa_universe_categorized.csv')
PANEL = ROOT / 'data/raw/usa_universe_panel_monthly_returns.csv'
CODE = ['skewness_managed.py', 'vol_target.py', 'prices.py', 'rotation.py', 'universe.py', 'features.py',
        'monthly_panel.py', 'cli.py']
TOL = 1e-7


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_prices(out: Path) -> dict:
    lines = SPLICED.read_text().splitlines(keepends=True)
    keep = [ln for ln in lines if ln.split(',', 1)[0] < FIRST_BAD or ln.startswith('Date')]
    g = pd.read_csv(SPLICED, index_col=0)
    u = pd.read_csv(FULL, index_col=0)[g.columns]
    days = [d for d in g.index if d >= FIRST_BAD]
    assert days and days[-1] == ROW and list(u.loc[u.index >= FIRST_BAD].index) == days
    prev = max(d for d in g.index if d < FIRST_BAD)
    base = g.loc[prev]
    growth = u.loc[days] / u.loc[prev]                      # full-history daily path from the last good close
    fixed = growth.mul(base, axis=1)
    rows = []
    for d in days:
        vals = ['' if pd.isna(v) else repr(float(v)) for v in fixed.loc[d]]
        rows.append(','.join([d] + vals) + '\n')
    out.write_text(''.join(keep) + ''.join(rows))
    fixed.to_csv(RUN / 'prices_corrected_rows_2026-09-16_to_30.csv')
    return dict(rows_replaced=len(days), first=days[0], last=days[-1], anchor=prev)


def function_sha() -> dict:
    from usa_etf_features import skewness_managed as sm, vol_target as vt
    names = ['run_skewness_managed_grid', 'make_skew_managed_trials']
    out = {f'skewness_managed.{n}': hashlib.sha256(inspect.getsource(getattr(sm, n)).encode()).hexdigest() for n in names}
    for n in ('option_core_daily_returns', 'portfolio_month_return'):
        out[f'vol_target.{n}'] = hashlib.sha256(inspect.getsource(getattr(vt, n)).encode()).hexdigest()
    return out


def apply(prices: Path) -> None:
    new = pd.read_csv(RUN / RETURNS, float_precision='round_trip').set_index('date')
    df = pd.read_csv(LIVE / RETURNS, dtype=str, keep_default_na=False)
    old = pd.read_csv(LIVE / RETURNS, float_precision='round_trip').set_index('date')
    assert list(new.index) == list(old.index) and new.index[-1] == ROW
    numeric = [c for c in old.columns if c not in ('decision_date', 'trial_id', 'gate_binding')]
    others = old.index[old.index != ROW]
    diffs = {c: float((old.loc[others, c] - new.loc[others, c]).abs().max()) for c in numeric}
    if any(not (v <= TOL) for v in diffs.values()):
        raise SystemExit(f're-run does not reproduce the committed months: {diffs}')
    for c in numeric:
        o = old.at[ROW, c]
        if c in {f'r_null_{k}' for k in NULLS} | {f'r_active_vs_{k}' for k in NULLS}:
            continue
        if abs(o - new.at[ROW, c]) > 1e-12:
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
        code_commit='079717978071c3538a96fc9e5d72992aca990d59',
        code_note='skewness_managed path unchanged since #41 (991a754); identical to the files the September refresh ran.',
        code_sha256={f'src/usa_etf_features/{f}': sha(ROOT / 'src/usa_etf_features' / f) for f in CODE},
        function_source_sha256=function_sha(),
        inputs_sha256={'prices (complete-month copy, built by `prices`)': sha(prices), str(SPLICED): sha(SPLICED),
                       str(FULL): sha(FULL), str(UNIVERSE): sha(UNIVERSE),
                       'data/raw/usa_universe_panel_monthly_returns.csv': sha(PANEL),
                       'data/processed/live/skew_nulls_rerun_2026-09/prices_corrected_rows_2026-09-16_to_30.csv':
                           sha(RUN / 'prices_corrected_rows_2026-09-16_to_30.csv')},
        output_sha256={f'data/processed/live/skew_nulls_rerun_2026-09/{f.name}': sha(f)
                       for f in sorted(RUN.glob('skew_managed_gatefirst_*.csv'))},
        command=('OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=src python -m usa_etf_features.cli '
                 'walkforward-skewness-managed --prices <complete-month prices> --universe '
                 f'{UNIVERSE} --monthly data/raw/usa_universe_panel_monthly_returns.csv --lookback 63 '
                 '--skew-lookback 21 --g-min 0.5 --f-min 0.25 --f-max 1.0 --cost-bps 5 --out/--weights/--returns/'
                 '--registry/--state-out data/processed/live/skew_nulls_rerun_2026-09/skew_managed_gatefirst_*.csv'),
        prices_last_date=ROW,
        note=('The three nulls are built from the complete-month monthly panel (--monthly), so a first re-run on the '
              'uncorrected spliced price file gave the same three 2026-09 values to the last bit, and they equal the '
              'values #53 blanked. That run reproduced the partial-month core (+0.2412%) in the core-equivalent '
              'columns; the complete-month prices give the committed panel core (-0.1112%) there, so every committed '
              'cell is reproduced.'),
    )
    (RUN / 'rerun_record.json').write_text(json.dumps(record, indent=1) + '\n')
    print(json.dumps(restored, indent=1))


if __name__ == '__main__':
    cmd, path = sys.argv[1], Path(sys.argv[2])
    if cmd == 'prices':
        print(build_prices(path), sha(path))
    elif cmd == 'apply':
        apply(path)
    else:
        raise SystemExit(__doc__)
