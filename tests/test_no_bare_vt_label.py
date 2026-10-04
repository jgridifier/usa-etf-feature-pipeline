"""No bare "VT" label on any built page.

The vol-target backbone is called "vol-target backbone" in prose and "Backbone" in
tables, cards, legends and tooltips; internal ids / columns / JSON keys keep "vt".
VT is also a real ETF (Vanguard Total World), so the explicit, small allowlist is:
  (a) ticker contexts: tables on the Universe / issuer page, ticker <select>/<option>
      lists, and the `ticker` field of docs/data/universe.json;
  (b) the definition lines of Quant's and the CIO's Book 2 notes, which say the
      backbone is not the Vanguard Total World ETF (ticker VT).
SPA routes are rendered in headless Chrome; static pages are checked as built.
"""
from __future__ import annotations

import functools
import html as htmllib
import http.server
import json
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
BARE_VT = re.compile(r'(?<![A-Za-z0-9_])VT(?![A-Za-z0-9_])')
SPA_ROUTES = ('/', '/books', '/runs', '/universe', '/explorer', '/archive')
TICKER_TABLE_ROUTES = {'/universe'}                       # (a) universe + issuer tables
TICKER_LIST = re.compile(r'<(select|datalist)\b.*?</\1>', re.S | re.I)   # (a) ticker lists
ALLOWED_SENTENCES = {                                      # (b) note definition lines
    'notes/book2_lw2008_drawdowns.html': [
        'It is not the Vanguard Total World ETF (ticker VT), and earlier drafts that called it "VT" meant the backbone.',
    ],
    'notes/book2_reframe.html': [
        'is not the Vanguard Total World ETF (ticker VT).',
    ],
}


def visible_text(dom: str, strip_tables: bool = False) -> str:
    body = re.sub(r'<script.*?</script>|<style.*?</style>|<!--.*?-->', ' ', dom, flags=re.S)
    body = TICKER_LIST.sub(' ', body)
    if strip_tables:
        body = re.sub(r'<table\b.*?</table>', ' ', body, flags=re.S)
    body = re.sub(r'<[^>]+>', '', body)
    return re.sub(r'\s+', ' ', htmllib.unescape(body))


def bare_vt(text: str, allowed: list[str] = ()) -> list[str]:
    for sentence in allowed:
        assert sentence in text, f'allowlisted sentence no longer present: {sentence!r}'
        text = text.replace(sentence, ' ')
    return [text[max(0, m.start() - 60):m.end() + 40] for m in BARE_VT.finditer(text)]


def _static_pages():
    return sorted(p for p in DOCS.rglob('*.html') if p != DOCS / 'index.html')


@pytest.mark.parametrize('page', _static_pages(), ids=lambda p: p.relative_to(DOCS).as_posix())
def test_static_pages_have_no_bare_vt(page):
    rel = page.relative_to(DOCS).as_posix()
    text = visible_text(page.read_text(encoding='utf-8'))
    assert not bare_vt(text, ALLOWED_SENTENCES.get(rel, [])), (rel, bare_vt(text, ALLOWED_SENTENCES.get(rel, [])))


def _chrome():
    for name in (os.environ.get('CHROME'), 'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
        if name and shutil.which(name):
            return shutil.which(name)
    return None


@pytest.fixture(scope='module')
def spa():
    chrome = _chrome()
    if chrome is None:
        if os.environ.get('CI'):
            pytest.fail('headless Chrome is required in CI for the rendered label check')
        pytest.skip('no Chrome available locally')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        return {r: subprocess.run(
            [chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--virtual-time-budget=15000',
             '--dump-dom', f'http://127.0.0.1:{server.server_address[1]}/index.html#{r}'],
            capture_output=True, text=True, timeout=120, check=True).stdout for r in SPA_ROUTES}
    finally:
        server.shutdown()


@pytest.mark.parametrize('route', SPA_ROUTES)
def test_rendered_spa_routes_have_no_bare_vt(spa, route):
    assert len(spa[route]) > 2000, f'{route} did not render'
    hits = bare_vt(visible_text(spa[route], strip_tables=route in TICKER_TABLE_ROUTES))
    assert not hits, (route, hits)


def test_universe_still_shows_vt_ticker(spa):
    """Guard against over-renaming: VT the ETF must stay 'VT' in the universe table."""
    assert re.search(r'<td[^>]*>\s*VT\s*</td>', spa['/universe']) or '>VT<' in spa['/universe']


def test_site_data_display_strings_have_no_bare_vt():
    bad = []

    def walk(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f'{path}.{k}')
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f'{path}[{i}]')
        elif isinstance(obj, str) and BARE_VT.search(obj) and not path.endswith('.ticker'):
            bad.append(f'{path}: {obj[:80]}')

    for p in sorted((DOCS / 'data').glob('*.json')):
        walk(json.loads(p.read_text(encoding='utf-8')), p.name)
    assert not bad, bad


def test_checker_examples():
    assert bare_vt('Book 2 tracked VT.') and bare_vt('VT backbone −20.1%')
    assert not bare_vt('vt.exbil VTI VTV VTEB r_vt Backbone vol-target backbone')


def test_chart_legends_and_titles_label_the_backbone():
    """ECharts text is drawn on canvas, so check the chart sources: the vol_target_option_a
    series (the unconditional backbone) is labelled "Backbone", never "Book 2" or a bare vt/VT."""
    charts = ROOT / 'apps' / 'pages' / 'src' / 'components' / 'charts'
    eq = (charts / 'EquityDrawdownChart.tsx').read_text(encoding='utf-8')
    assert eq.count("name: 'Backbone'") == 2          # equity + drawdown series
    assert 'MaxDD Backbone' in eq
    for path in sorted(charts.glob('*.tsx')):
        src = path.read_text(encoding='utf-8')
        labels = re.findall(r"""(?:name|text):\s*[`'"]([^`'"]*)[`'"]""", src)
        for label in labels:
            assert 'Book 2' not in label and 'Book-2' not in label, (path.name, label)
            assert not re.search(r'(?<![A-Za-z0-9_.?])(vt|VT)(?![A-Za-z0-9_])', label), (path.name, label)


def test_no_vol_target_book2_mislabel_in_app_sources():
    """The vol-target series/page is the backbone; "Vol-target (Book 2)" is the retired mislabel."""
    src = ROOT / 'apps' / 'pages' / 'src'
    hits = [p.relative_to(ROOT).as_posix() for p in src.rglob('*.ts*')
            if 'Vol-target (Book 2)' in p.read_text(encoding='utf-8')]
    legacy = ROOT / 'docs' / 'assets' / 'app.js'   # legacy static chart script, still served
    if 'Vol-target (Book 2)' in legacy.read_text(encoding='utf-8'):
        hits.append('docs/assets/app.js')
    assert hits == []


# Stat-card labels are written in lower case ("(vt)") and upper-cased by CSS (`.stat-label` is `uppercase`), so
# the rendered-text check above cannot see them as "VT". These checks are case-insensitive.
BARE_VT_ANY_CASE = re.compile(r'(?<![A-Za-z0-9_.$])[Vv][Tt](?![A-Za-z0-9_])')


def _spa_bundles():
    html = (DOCS / 'index.html').read_text(encoding='utf-8')
    names = re.findall(r'assets/(v2-index-[A-Za-z0-9_-]+\.js)', html)
    assert names, 'SPA bundle not referenced from docs/index.html'
    return [DOCS / 'assets' / n for n in names]


def test_spa_bundle_display_strings_have_no_bare_vt_any_case():
    """JSX text in the built SPA bundle (children / label strings) never says vt / VT / (VT)."""
    bad = []
    for path in _spa_bundles():
        src = path.read_text(encoding='utf-8')
        for m in re.finditer(r'children:\s*"((?:[^"\\]|\\.)*)"', src):
            s = m.group(1)
            if BARE_VT_ANY_CASE.search(s):
                bad.append(f'{path.name}: {s[:100]}')
        for m in re.finditer(r'"[^"\n]{0,200}\((?:vt|VT)\)[^"\n]{0,200}"', src):   # inside string literals only
            bad.append(f'{path.name}: …{src[max(0, m.start() - 60):m.end() + 10]}…')
    assert not bad, bad


def test_spa_sources_jsx_text_has_no_bare_vt_any_case():
    src = ROOT / 'apps' / 'pages' / 'src'
    bad = []
    for p in sorted(src.rglob('*.tsx')):
        for m in re.finditer(r'>([^<>{}]+)<', p.read_text(encoding='utf-8')):
            if BARE_VT_ANY_CASE.search(m.group(1)):
                bad.append(f'{p.relative_to(ROOT)}: {m.group(1).strip()[:80]}')
    assert not bad, bad


@pytest.mark.parametrize('route', ['/', '/runs'])
def test_rendered_home_and_runs_stat_labels_say_backbone(spa, route):
    """Built Home and Runs output: no bare vt in any case (stat labels are upper-cased by CSS), and the
    backbone stat cards are labelled "(Backbone)"."""
    text = visible_text(spa[route])
    hits = [text[max(0, m.start() - 60):m.end() + 30] for m in BARE_VT_ANY_CASE.finditer(text)]
    assert not hits, (route, hits)
    labels = re.findall(r'class="stat-label"[^>]*>([^<]*)<', spa[route])
    backbone = [lab for lab in labels if '(Backbone)' in lab]
    expected = {'/': {'Sharpe ex-BIL (Backbone)', 'Max drawdown (Backbone)', 'Ann. vol (Backbone)'},
                '/runs': {'Max DD (Backbone)', 'Ann. return (Backbone)', 'Ann. vol (Backbone)', 'Sharpe ex-BIL (Backbone)'}}[route]
    assert expected <= set(backbone), (route, labels)


@pytest.fixture(scope='module')
def spa_inner_text():
    """Rendered text after CSS (text-transform etc.): headless Chrome's innerText of the built Home and Runs pages."""
    chrome, node = _chrome(), shutil.which('node')
    if chrome is None or node is None:
        if os.environ.get('CI'):
            pytest.fail('headless Chrome and node are required in CI for the rendered innerText check')
        pytest.skip('no Chrome/node available locally')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_address[1]}/index.html'
    urls = {'/': f'{base}?route=home#/', '/runs': f'{base}?route=runs#/runs'}
    try:
        cfg = {'urls': list(urls.values()), 'settle_ms': 2500,
               'expression': ("(async () => { document.querySelectorAll('details').forEach(d => { d.open = true; });"
                              " await new Promise(r => setTimeout(r, 500));"
                              " return {text: document.body.innerText,"
                              " labels: [...document.querySelectorAll('.stat-label')].map(e => e.innerText)}; })()")}
        out = subprocess.run([node, '--experimental-websocket', str(ROOT / 'tests' / 'tools' / 'cdp375.mjs'), chrome, json.dumps(cfg)],
                             capture_output=True, text=True, timeout=300, check=True).stdout
    finally:
        server.shutdown()
    raw = json.loads(out.strip().splitlines()[-1])
    return {r: raw[u] for r, u in urls.items()}


@pytest.mark.parametrize('route', ['/', '/runs'])
def test_home_and_runs_inner_text_after_css_has_no_bare_vt(spa_inner_text, route):
    """`.stat-label` is upper-cased by CSS, so "(vt)" in the DOM renders as "(VT)": check what the reader sees."""
    got = spa_inner_text[route]
    assert len(got['text']) > 1000, f'{route} did not render'
    hits = [got['text'][max(0, m.start() - 60):m.end() + 30] for m in BARE_VT_ANY_CASE.finditer(got['text'])]
    assert not hits, (route, hits)
    shown = {lab for lab in got['labels'] if '(BACKBONE)' in lab}
    expected = {'/': {'SHARPE EX-BIL (BACKBONE)', 'MAX DRAWDOWN (BACKBONE)', 'ANN. VOL (BACKBONE)'},
                '/runs': {'MAX DD (BACKBONE)', 'ANN. RETURN (BACKBONE)', 'ANN. VOL (BACKBONE)', 'SHARPE EX-BIL (BACKBONE)'}}[route]
    assert expected <= shown, (route, got['labels'])
