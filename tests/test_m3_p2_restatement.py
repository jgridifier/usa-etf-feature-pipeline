"""m3_p2_core_rotate data restatement on the corrected growth_alpha prices (Quant ruling on #59, 2026-10-04).

The record says it is a data restatement (not a new trial; trial count unchanged; code and params frozen) and
carries the price-file and return-file hashes, the before / after figures and the fragility figures. The site note
(Runs page, next to the strategy_comparison.csv download: the only place m3_p2 appears) is generated from it.
"""
from __future__ import annotations

import csv
import functools
import hashlib
import html as htmllib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
REC = ROOT / 'data/processed/prices_fix_2026-10/m3_p2_restatement.json'
RERUN = ROOT / 'data/processed/live/m3_p2_rerun_2026-09/rerun_record.json'
NOTES = DOCS / 'data/strategy_comparison_notes.json'
sys.path.insert(0, str(ROOT / 'scripts'))


def rec() -> dict:
    return json.loads(REC.read_text(encoding='utf-8'))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_record_is_a_data_restatement_with_frozen_code_and_params():
    r = rec()
    assert r['type'] == 'data restatement' and r['not_a_new_trial'] is True and r['trial_count_change'] == 0
    assert r['code_frozen'] is True and r['params_frozen'] is True
    assert r['price_file'] == {
        'path': r['price_file']['path'],
        'old_sha256': '6af174a5a0f9096e68e22a9a25695ba770c9877e1c761abe121432835b7c6d5c',
        'new_sha256': '6306e0825ededbc9f013d26854384290e1bdf1927b3192b392dc261632057314'}
    assert _sha(DOCS / 'data/growth_alpha_adj_close.csv') == r['price_file']['new_sha256']
    for path, h in r['return_files'].items():
        assert _sha(ROOT / path) == h['new_sha256'] != h['old_sha256'], path
    rr = json.loads(RERUN.read_text())
    assert r['code_sha256'] == rr['code_sha256'] and r['function_source_sha256'] == rr['function_source_sha256']


def test_after_figures_equal_the_published_comparison():
    r = rec()['after']
    row = next(x for x in csv.DictReader((DOCS / 'data/strategy_comparison.csv').open()) if x['strategy_id'] == 'm3_p2_core_rotate')
    for k in ('AnnReturn', 'AnnVol', 'MaxDD', 'Sharpe_rf0', 'NW_t_vs_option_a', 'turnover_per_year'):
        assert float(row[k]) == r[k], k
    site = json.loads((ROOT / 'data/processed/cash_null_audit/site_sharpe.json').read_text())['comparison']['m3_p2_core_rotate']
    assert site['exbil'] == r['Sharpe_exBIL'] and r['n_months'] == 68 and r['window'] == '2021-02..2026-09'
    live = [x for x in csv.DictReader((ROOT / 'data/processed/live/strategy_returns.csv').open())
            if x['strategy_id'] == 'm3_p2_core_rotate' and x['date'].startswith('2026-09')]
    assert float(live[0]['return']) == r['return_2026_09'] and round(r['return_2026_09'] * 100, 4) == -0.6847
    assert rec()['before']['return_2026_09'] == pytest.approx(-0.0023403295106801, abs=1e-15)


def test_fragility_figures_recompute_from_the_two_return_series():
    """56 / 179 and the 2020-03 gap, recomputed from the was / now values saved with the re-run record."""
    d = rec()['disclosure']
    moved = json.loads(RERUN.read_text())['other_months_changed_beyond_tolerance']   # every month that moved > 1e-7
    gaps = {m: v['now'] - v['was'] for m, v in moved.items() if m != '2026-09'}
    changed = sorted(m for m, g in gaps.items() if abs(g) > d['pick_tolerance'])
    worst = max(gaps, key=lambda m: abs(gaps[m]))
    assert (d['months_changed'], d['earlier_months']) == (len(changed), 179) == (56, 179)
    assert d['months'] == changed
    assert d['largest_gap_month'] == worst == '2020-03' and d['largest_gap_pp'] == round(gaps[worst] * 100, 2) == -1.02
    assert d['max_daily_return_diff_before_splice'] < d['price_diff_bound'] == 1e-4


def test_note_text_is_generated_from_the_record():
    import build_pages
    want = ('56 of 179 earlier months changed picks between the two price files; largest monthly gap 2020-03, '
            '\u22121.02 pp; picks flip on price differences under 1e-4, so this stays a lab run.')
    assert build_pages.m3_p2_fragility_note(rec()) == want
    notes = json.loads(NOTES.read_text(encoding='utf-8'))
    assert notes['file'] == 'strategy_comparison.csv'
    assert [(n['strategy_id'], n['text']) for n in notes['notes']] == [('m3_p2_core_rotate', want)]
    fake = json.loads(json.dumps(rec()))
    fake['disclosure'].update(months_changed=3, earlier_months=10, largest_gap_month='2001-01', largest_gap_pp=-0.5)
    assert build_pages.m3_p2_fragility_note(fake).startswith('3 of 10 earlier months') and '2001-01, \u22120.50 pp' in build_pages.m3_p2_fragility_note(fake)


def test_spa_bundle_renders_the_notes_on_runs():
    spa = re.search(r'assets/v2-index-[\w-]+\.js', (DOCS / 'index.html').read_text())[0]
    js = (DOCS / spa).read_text(encoding='utf-8')
    assert 'strategy_comparison_notes.json' in js and 'strategy-comparison-notes' in js
    src = (ROOT / 'apps/pages/src/pages/Runs.tsx').read_text()
    assert '<StrategyComparisonNotes />' in src


def _chrome() -> str | None:
    for name in (os.environ.get('CHROME'), 'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
        if name and shutil.which(name):
            return shutil.which(name)
    return None


def test_note_renders_on_the_runs_page():
    chrome = _chrome()
    if chrome is None:
        if os.environ.get('CI'):
            pytest.fail('headless Chrome is required in CI for the rendered-note check')
        pytest.skip('no Chrome available locally')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        dom = subprocess.run(
            [chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--virtual-time-budget=15000',
             '--window-size=375,812', '--dump-dom', f'http://127.0.0.1:{server.server_address[1]}/index.html#/runs'],
            capture_output=True, text=True, timeout=120, check=True).stdout
    finally:
        server.shutdown()
    m = re.search(r'<div[^>]*data-testid="strategy-comparison-notes".*?</div>', dom, flags=re.S)
    assert m, 'notes block not rendered on #/runs'
    text = re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]+>', '', m[0])))
    assert json.loads(NOTES.read_text(encoding='utf-8'))['notes'][0]['text'] in text
    assert 'M3 P2 (held off)' in text and 'not a new trial' in text
