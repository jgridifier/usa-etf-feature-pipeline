"""Prose figures on the built site must equal the live-book outputs.

Books / Home / Runs prose renders every return and Sharpe figure through
<LiveFig> (apps/pages/src/lib/liveFigures.tsx), which reads docs/data/live_figures.json.
That JSON is written by scripts/build_pages.py from data/processed/live/ and the
live fields of site_sharpe.json. This test (1) recomputes the JSON from the live
outputs, (2) renders the committed built site in headless Chrome and checks every
[data-live-figure] span against the live value formatted with the same rounding,
and (3) checks the hard-coded drawdown / vol strings against the live values.
"""
from __future__ import annotations

import functools
import html as htmllib
import http.server
import json
import math
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
LIVE = ROOT / 'data' / 'processed' / 'live'
SITE = ROOT / 'data' / 'processed' / 'cash_null_audit' / 'site_sharpe.json'
SOURCES = {
    'book1': ('vol_target_oos_returns.csv', 'r_option_a', 'book1_static_core'),
    'book2': ('skew_managed_gatefirst_returns.csv', 'r_method', 'book2_vt_x_gatefirst'),
    'vt': ('vol_target_oos_returns.csv', 'r_vt', 'uncond_vt_audit_null'),
}
OLD_FIGURES = ('13.6', '0.97', '14.7', '0.84', '0.75', '1.28', '1.059', '0.92')
ARCHIVE_ALLOWED = ('0.75 (1.05)',)   # frozen VCFC archive row on Home


def expected_books() -> dict:
    site = json.loads(SITE.read_text(encoding='utf-8'))['books']
    out = {}
    for key, (name, col, site_key) in SOURCES.items():
        r = pd.read_csv(LIVE / name)[col].astype(float).to_numpy()
        wealth = np.cumprod(1 + r)
        peak = np.maximum.accumulate(np.r_[1.0, wealth])[1:]
        out[key] = {
            'ann_return': wealth[-1] ** (12 / len(r)) - 1,
            'ann_vol': r.std(ddof=1) * math.sqrt(12),
            'max_dd': (wealth / peak - 1).min(),
            'sharpe_exbil': site[site_key]['exbil'],
            'sharpe_rf0': site[site_key]['rf0_legacy'],
        }
    return out


def fmt(key: str, b: dict) -> str:
    """Python mirror of formatLive() in apps/pages/src/lib/liveFigures.tsx."""
    book, _, kind = key.partition('.')
    if key == 'gap.points':
        n = math.floor((b['vt']['ann_return'] - b['book2']['ann_return']) * 100 + 0.5)
        return f"{n} point{'' if n == 1 else 's'}"
    if kind == 'return':
        return f"{b[book]['ann_return'] * 100:.1f}%"
    if kind == 'return.whole':
        return f"{math.floor(b[book]['ann_return'] * 100 + 0.5)}%"
    if kind == 'exbil':
        return f"{b[book]['sharpe_exbil']:.2f}"
    if kind == 'rf0':
        return f"{b[book]['sharpe_rf0']:.{3 if book == 'vt' else 2}f}"
    raise KeyError(key)


def neg_pct(x: float) -> str:
    return f"−{abs(x) * 100:.1f}%"


def test_live_figures_json_matches_live_outputs():
    payload = json.loads((DOCS / 'data' / 'live_figures.json').read_text(encoding='utf-8'))
    exp = expected_books()
    assert payload['n_months'] == len(pd.read_csv(LIVE / 'vol_target_oos_returns.csv'))
    assert payload['asof'] == '2026-09-30'
    for key, vals in exp.items():
        for field, value in vals.items():
            assert payload['books'][key][field] == pytest.approx(value, abs=1e-12), (key, field)


def _chrome() -> str | None:
    for name in (os.environ.get('CHROME'), 'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
        if name and shutil.which(name):
            return shutil.which(name)
    return None


@pytest.fixture(scope='module')
def rendered():
    chrome = _chrome()
    if chrome is None:
        if os.environ.get('CI'):
            pytest.fail('headless Chrome is required in CI for the rendered-figure check')
        pytest.skip('no Chrome available locally')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    pages = {}
    try:
        for route in ('/', '/books', '/runs'):
            dom = subprocess.run(
                [chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--virtual-time-budget=15000',
                 '--dump-dom', f'http://127.0.0.1:{port}/index.html#{route}'],
                capture_output=True, text=True, timeout=120, check=True,
            ).stdout
            pages[route] = dom
    finally:
        server.shutdown()
    return pages


SPAN = re.compile(r'<span data-live-figure="([^"]+)">([^<]*)</span>')
MIN_KEYS = {
    '/': {'book1.exbil', 'book1.rf0', 'book2.return', 'vt.return', 'book2.exbil', 'vt.exbil',
          'book2.rf0', 'vt.rf0', 'gap.points', 'vt.return.whole', 'book1.return'},
    '/books': {'book1.return', 'book1.exbil', 'book1.rf0', 'book2.return', 'vt.return', 'book2.exbil',
               'vt.exbil', 'book2.rf0', 'vt.rf0', 'gap.points'},
    '/runs': {'vt.return.whole', 'book2.exbil'},
}


def _text(dom: str, prose_only: bool = False) -> str:
    body = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', dom, flags=re.S)
    if prose_only:  # data tables render live CSV/JSON values directly; check prose only
        body = re.sub(r'<table.*?</table>', ' ', body, flags=re.S)
    return re.sub(r'\s+', ' ', htmllib.unescape(re.sub(r'<[^>]+>', '', body)))


@pytest.mark.parametrize('route', ['/', '/books', '/runs'])
def test_rendered_prose_figures_equal_live_outputs(rendered, route):
    exp = expected_books()
    spans = SPAN.findall(rendered[route])
    assert spans, f'no live figures rendered on {route}'
    seen = set()
    for key, text in spans:
        assert text == fmt(key, exp), (route, key, text, fmt(key, exp))
        seen.add(key)
    assert MIN_KEYS[route] <= seen, (route, MIN_KEYS[route] - seen)


@pytest.mark.parametrize('route', ['/', '/books'])
def test_rendered_drawdown_vol_and_order_match_live(rendered, route):
    b = expected_books()
    text = _text(rendered[route])
    stat = (f"Max drawdown {neg_pct(b['book2']['max_dd'])} (vol-target backbone {neg_pct(b['vt']['max_dd'])}, "
            f"Book 1 {neg_pct(b['book1']['max_dd'])}) · volatility ~{b['book2']['ann_vol'] * 100:.1f}% "
            f"(~{b['vt']['ann_vol'] * 100:.1f}%, ~{b['book1']['ann_vol'] * 100:.1f}%) · "
            f"return ~{fmt('book2.return', b)} (~{fmt('vt.return', b)}, ~{fmt('book1.return', b)}) · "
            f"Sharpe above BIL {fmt('book2.exbil', b)} ({fmt('vt.exbil', b)}, {fmt('book1.exbil', b)})")
    assert stat in text, route
    assert f"about {fmt('gap.points', b)} a year" in text
    assert 'Its protection has been seen in one bear market' in text
    if route == '/books':  # comparison-table stance is built from the same live Sharpe
        assert f"gate-first overlay ({fmt('book2.exbil', b)} excess of BIL)" in text


@pytest.mark.parametrize('route', ['/', '/books', '/runs'])
def test_no_old_figures_in_rendered_live_copy(rendered, route):
    text = _text(rendered[route], prose_only=True)
    for allowed in ARCHIVE_ALLOWED:
        text = text.replace(allowed, '')
    for old in OLD_FIGURES:
        assert not re.search(r'(?<![\d.])' + re.escape(old) + r'(?!\d)', text), (route, old)
    assert '…' not in ''.join(t for _, t in SPAN.findall(rendered[route]))
