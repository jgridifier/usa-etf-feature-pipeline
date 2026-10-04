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
import json
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function_sha() -> dict:
    from usa_etf_features import strategy_registry as sr, walkforward as wf
    return {name: hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()
            for name, fn in (('strategy_registry._m3_returns', sr._m3_returns),
                             ('walkforward.walkforward_optimization_tables', wf.walkforward_optimization_tables))}


def main() -> None:
    new = pd.read_csv(RUN / 'strategy_returns.csv', float_precision='round_trip')
    new = new[new.strategy_id == SID].set_index(new['date'].str[:7])
    live = pd.read_csv(LIVE / 'strategy_returns.csv', dtype=str, keep_default_na=False)
    rows = live.strategy_id == SID
    old = live[rows].set_index(live.loc[rows, 'date'].str[:7])
    others = old.index[old.index != MONTH]
    diff = (old.loc[others, 'return'].astype(float) - new.loc[others, 'return']).abs()
    if len(diff) != len(others) or diff.isna().any() or diff.max() > TOL:
        raise SystemExit(f're-run does not reproduce the committed months (max |diff| {diff.max()})')
    value = float(new.loc[MONTH, 'return'])
    i = live.index[rows & live['date'].str.startswith(MONTH)]
    assert len(i) == 1
    was = live.at[i[0], 'return']
    if was and abs(float(was) - value) > 1e-15:
        raise SystemExit(f'2026-09 cell already holds {was}, not blank or the re-run value')
    live.at[i[0], 'return'] = repr(value)
    live.to_csv(LIVE / 'strategy_returns.csv', index=False)
    record = dict(
        strategy_id=SID, month=MONTH, restored_return=value, was='' if not was else float(was),
        turnover_rerun=float(new.loc[MONTH, 'turnover']), turnover_kept=float(old.loc[MONTH, 'turnover']),
        other_months_checked=int(len(others)), max_abs_return_diff_other_months=float(diff.max()),
        tolerance=TOL, code_commit='85002a84ff4c9bd1ac34146ee8b1593c7d878ff5',
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
    print(f'{SID} {MONTH}: {value!r} (other {len(others)} months max |diff| {diff.max():.2e})')


if __name__ == '__main__':
    main()
