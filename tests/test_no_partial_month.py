"""No published data file carries the partial-September 2026 row (Sep-core fix, PR #53).

The live books' 2026-09 row was a partial-month return (+0.2412% for the core, prices through about
2026-09-16). scripts/repair_live_partial_month.py rebuilt it from the complete-month panel (-0.1112%).
Fingerprints of the partial row: the core value itself and the 68-month figures derived from it
(Book 1 CAGR 0.150315542…, vol-target backbone CAGR 0.150730702…, Book 2 CAGR 0.139244078…)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTIAL = ('0.0024118787', '0.15031554243', '0.15073070287', '0.13924407813', '1.0872785462', '0.9483116763')
FILES = [p for d in ('docs/data', 'data/processed/live', 'data/processed/cash_null_audit')
         for p in (ROOT / d).rglob('*') if p.suffix in ('.csv', '.json')
         and p.name not in ('partial_month_repair.json',)]


def test_no_published_file_carries_the_partial_2026_09_row():
    hits = []
    for p in FILES:
        text = p.read_text(encoding='utf-8', errors='replace')
        hits += [(str(p.relative_to(ROOT)), f) for f in PARTIAL if f in text]
    assert not hits, hits


def test_published_core_return_files_have_the_complete_month_2026_09():
    for rel, col in [('docs/data/vol_target_oos_returns.csv', 'r_option_a'),
                     ('data/processed/live/vol_target_oos_returns.csv', 'r_option_a'),
                     ('data/processed/live/skew_managed_gatefirst_returns.csv', 'r_null_b')]:
        rows = [r for r in csv.DictReader((ROOT / rel).open()) if r['date'].startswith('2026-09')]
        assert len(rows) == 1 and abs(float(rows[0][col]) - (-0.0011122712)) < 1e-9, rel
    log = json.loads((ROOT / 'data/processed/live/partial_month_repair.json').read_text())
    assert log['month'] == '2026-09' and abs(log['complete_month_panel_core'] - (-0.0011122712)) < 1e-9
