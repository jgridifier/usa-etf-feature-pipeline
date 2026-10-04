"""Write the results hub data (PR A): data/processed/hub/. Saved artifacts only; nothing is re-run.

    .venv/bin/python scripts/build_hub_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

from usa_etf_features import hub_data

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed/hub'


def dump(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def main():
    res = hub_data.build(ROOT)
    dump(res['manifest'], OUT / 'manifest.json')
    dump(res['leaderboard'], OUT / 'leaderboard.json')
    for sid, s in res['subjects'].items():
        dump(s, OUT / 'subjects' / f'{sid}.json')
    res['static_core'].to_csv(OUT / 'static_core_monthly.csv', float_format='%.10f')
    res['regimes'].to_csv(OUT / 'market_regimes.csv', float_format='%.10f')
    print('wrote', OUT)


if __name__ == '__main__':
    main()
