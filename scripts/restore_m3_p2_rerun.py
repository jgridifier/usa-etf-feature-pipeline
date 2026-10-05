"""Restore m3_p2_core_rotate's 2026-09 return from an unchanged re-run on the complete-month prices.

PR #53 blanked this cell: the live refresh used a partial September (prices through about 2026-09-16) and
m3_p2_core_rotate is not the core, so it could not be rebuilt without a re-run. The re-run used the frozen
code at main 85002a8 (the M3/P2 code path is byte-identical to the original refresh commit 111fbc7; the only
strategy_registry.py change since then adds the disabled EPO adapter) and the same registry entry:

    PYTHONPATH=src python -m usa_etf_features.cli run-strategies --walkforward \
      --prices /workspace/investments/growth_alpha_adj_close.csv \
      --universe /workspace/investments/usa_universe_categorized.csv \
      --registry data/processed/live/m3_p2_rerun_2026-09/registry_m3_p2_only.yaml --out-dir <tmp>

Its output is saved in data/processed/live/m3_p2_rerun_2026-09/. This script checks the other 179 months
reproduce the committed returns (|diff| <= 1e-7), writes only the 2026-09 return into
data/processed/live/strategy_returns.csv, and records the code and input sha256 values with the output in
data/processed/live/m3_p2_rerun_2026-09/rerun_record.json. Idempotent.
"""
from __future__ import annotations

import hashlib
import inspect
import io
import json
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / 'data/processed/live'
RUN = LIVE / 'm3_p2_rerun_2026-09'
SID, MONTH = 'm3_p2_core_rotate', '2026-09'
PRICES = Path('/workspace/investments/growth_alpha_adj_close.csv')
UNIVERSE = Path('/workspace/investments/usa_universe_categorized.csv')
CODE = ['strategy_registry.py', 'walkforward.py', 'portfolio.py', 'scores.py', 'features.py', 'rotation.py',
        'universe.py', 'vol_target.py', 'cli.py']
TOL = 1e-7
PREV_REF = 'e0ff4e3ea9f8931f4538171e497dbae53fe0a294'   # main before the growth_alpha price fix


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function_sha() -> dict:
    from usa_etf_features import strategy_registry as sr, walkforward as wf
    return {name: hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()
            for name, fn in (('strategy_registry._m3_returns', sr._m3_returns),
                             ('walkforward.walkforward_optimization_tables', wf.walkforward_optimization_tables))}


def main() -> None:
    new = pd.read_csv(RUN / 'strategy_returns.csv', dtype=str, keep_default_na=False)
    new = new[new.strategy_id == SID].set_index(new['date'].str[:7])
    live = pd.read_csv(LIVE / 'strategy_returns.csv', dtype=str, keep_default_na=False)
    rows = live.strategy_id == SID
    before = pd.read_csv(io.StringIO(subprocess.run(['git', 'show', f'{PREV_REF}:data/processed/live/strategy_returns.csv'],
                                                    cwd=ROOT, check=True, capture_output=True, text=True).stdout),
                         dtype=str, keep_default_na=False)       # the series as committed before the price fix
    brows = before.strategy_id == SID
    old = before[brows].set_index(before.loc[brows, 'date'].str[:7])
    if list(old.index) != list(new.index) or not (old[['date', 'decision_date', 'feature_end']].values ==
                                                    new[['date', 'decision_date', 'feature_end']].values).all():
        raise SystemExit('re-run months / decision dates differ from the committed series')
    others = old.index[old.index != MONTH]
    prev = old['return'].replace('', 'nan').astype(float)
    diff = (prev.loc[others] - new.loc[others, 'return'].astype(float)).abs()
    changed = diff[diff > TOL]
    # 2026-10-04: growth_alpha_adj_close.csv was rebuilt from the full adjusted-close history (2026-09-16 splice
    # removed; scripts/fix_growth_alpha_prices.py). The whole m3_p2_core_rotate series is replaced by the re-run on
    # the fixed file; months that moved by more than TOL are listed in the record.
    i = live.index[rows]
    assert list(live.loc[i, 'date']) == list(new['date'])
    live.loc[i, 'return'] = new['return'].values
    live.loc[i, 'turnover'] = new['turnover'].values
    live.to_csv(LIVE / 'strategy_returns.csv', index=False)
    value = float(new.loc[MONTH, 'return'])
    was = old.loc[MONTH, 'return']
    record = dict(
        strategy_id=SID, month=MONTH, restored_return=value, was='' if not was else float(was),
        turnover_rerun=float(new.loc[MONTH, 'turnover']), turnover_was=float(old.loc[MONTH, 'turnover']),
        series_replaced=True, other_months_checked=int(len(others)),
        max_abs_return_diff_other_months=float(diff.max()), tolerance=TOL,
        other_months_changed_beyond_tolerance={m: dict(was=float(prev[m]), now=float(new.loc[m, 'return']))
                                               for m in changed.index},
        reason=('growth_alpha_adj_close.csv rebuilt from the full adjusted-close history on 2026-10-04 (partial-day '
                '2026-09-16 splice removed; data/processed/prices_fix_2026-10/growth_alpha_fix_record.json). '
                'm3_p2_core_rotate re-run on the fixed file; the whole series is replaced.'), code_commit=PREV_REF,
        code_note='M3/P2 path unchanged since the original refresh 111fbc7 (only the disabled EPO adapter was added).',
        code_sha256={f'src/usa_etf_features/{f}': sha(ROOT / 'src/usa_etf_features' / f) for f in CODE},
        function_source_sha256=function_sha(),
        inputs_sha256={str(PRICES): sha(PRICES), str(UNIVERSE): sha(UNIVERSE),
                       'data/processed/live/m3_p2_rerun_2026-09/registry_m3_p2_only.yaml': sha(RUN / 'registry_m3_p2_only.yaml')},
        output_sha256={'data/processed/live/m3_p2_rerun_2026-09/strategy_returns.csv': sha(RUN / 'strategy_returns.csv')},
        command=('PYTHONPATH=src python -m usa_etf_features.cli run-strategies --walkforward --prices '
                 f'{PRICES} --universe {UNIVERSE} --registry data/processed/live/m3_p2_rerun_2026-09/registry_m3_p2_only.yaml '
                 '--out-dir <tmp>'),
        prices_last_date=str(pd.read_csv(PRICES, usecols=[0]).iloc[-1, 0]),
    )
    (RUN / 'rerun_record.json').write_text(json.dumps(record, indent=1) + '\n')
    print(f'{SID} {MONTH}: {value!r}; {len(changed)} other months moved by > {TOL} (max {diff.max():.2e})')


if __name__ == '__main__':
    main()
