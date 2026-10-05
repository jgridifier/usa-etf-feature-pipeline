"""Byte-pinned pages get the shared lab header at build time (scripts/pinned_pages.py, PM/CoS 2026-10-04).

Model: the Schur teaching note. The source hash is pinned and verified; the published page is the source plus
<!-- lab:start -->…<!-- lab:end --> blocks (header-only CSS, site header, link back to the results hub, nav.js), and its
hash is pinned separately (tests/test_beat_benchmark_pages.py, and STAGE2_PUBLISHED below).
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
sys.path.insert(0, str(ROOT / 'scripts'))
import pinned_pages as pp  # noqa: E402

STAGE2_PUBLISHED = '55dd0508234678a29f05bf0e0cc3103dc538aaba5624c38dedc6d54a133c48b1'


def test_every_pinned_page_is_its_source_plus_lab_blocks():
    assert set(pp.SOURCES) == {'methods/stage2_demiguel.html', 'methods/beat_benchmark/index.html',
                               'methods/beat_benchmark/idea1_downside_vol_backbone.html',
                               'methods/beat_benchmark/idea2_fixed_blend_book2_core.html',
                               'methods/beat_benchmark/idea3_har_vol_forecast.html'}
    for rel, want in pp.SOURCES.items():
        src = pp.source_path(rel).read_bytes()
        assert hashlib.sha256(src).hexdigest() == want, rel
        pub = (DOCS / rel).read_text(encoding='utf-8')
        assert pp.strip_lab(pub).encode('utf-8') == src, rel
        blocks = pp.LAB.findall(pub)
        assert len(blocks) == 3, rel
        assert 'assets/lab-header.css' in blocks[0] and 'assets/style.css' not in pub, rel   # page CSS untouched
        assert 'class="site-header"' in blocks[1] and 'class="lab-backlink"' in blocks[1], rel
        hub = re.search(r'class="lab-backlink"><a href="([^"]+)"', blocks[1])[1]
        assert (DOCS / rel).parent.joinpath(hub).resolve() == (DOCS / 'methods/results/index.html').resolve(), rel
        assert 'assets/nav.js' in blocks[2], rel
        for ref in re.findall(r'(?:href|src)="([^"#]+)"', ''.join(blocks)):
            assert (DOCS / rel).parent.joinpath(ref).resolve().exists(), (rel, ref)


def test_stage2_teaching_note_published_hash_is_pinned():
    assert hashlib.sha256((DOCS / 'methods/stage2_demiguel.html').read_bytes()).hexdigest() == STAGE2_PUBLISHED


def test_build_refuses_a_source_that_does_not_match_its_pin(tmp_path, monkeypatch):
    rel = 'methods/beat_benchmark/index.html'
    bad = tmp_path / 'src' / rel
    bad.parent.mkdir(parents=True)
    bad.write_bytes(pp.source_path(rel).read_bytes() + b' ')
    monkeypatch.setattr(pp, 'SRC_DIR', tmp_path / 'src')
    monkeypatch.setattr(pp, 'SOURCES', {rel: pp.SOURCES[rel]})
    with pytest.raises(SystemExit):
        pp.publish(lambda p, a: '<header class="site-header"></header>', tmp_path / 'docs')
    assert not (tmp_path / 'docs' / rel).exists()


def test_swap_is_one_step_and_refuses_a_wrong_hash(tmp_path, monkeypatch):
    names = ['index.html', 'idea1_downside_vol_backbone.html', 'idea2_fixed_blend_book2_core.html',
             'idea3_har_vol_forecast.html']
    folder = tmp_path / 'quant'
    folder.mkdir()
    for n in names:
        (folder / n).write_bytes(pp.source_path('methods/beat_benchmark/' + n).read_bytes())
    pins = {n: pp.SOURCES['methods/beat_benchmark/' + n] for n in names}
    with pytest.raises(SystemExit):
        pp.swap('beat_benchmark', folder, {**pins, 'index.html': '0' * 64})


def test_header_css_is_scoped_to_the_injected_header():
    css = (DOCS / 'assets/lab-header.css').read_text(encoding='utf-8')
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    for sel in re.findall(r'([^{}@]+)\{', css):
        for part in sel.split(','):
            part = part.strip()
            if part.startswith(('(', 'media')) or not part:
                continue
            if part in (':target', '[id]'):      # anchor offset under the sticky header (PM, 2026-10-04)
                continue
            assert re.match(r'(\.nav-open\s+)?\.(site-header|lab-backlink)\b', part), part
    assert 'http' not in css
    rule = re.search(r':target,\s*\[id\]\s*\{([^}]*)\}', css)
    assert rule and rule.group(1).strip() == 'scroll-margin-top: 60px;', rule


def test_beat_benchmark_header_glossary_link_resolves_to_the_index_glossary():
    from html.parser import HTMLParser
    index = DOCS / 'methods/beat_benchmark/index.html'
    ids = re.findall(r'\bid="([^"]+)"', pp.strip_lab(index.read_text(encoding='utf-8')))
    assert 'glossary' in ids                       # Quant's own element, not an injected one
    for rel in pp.SOURCES:
        if not rel.startswith('methods/beat_benchmark/'):
            continue
        block = pp.LAB.findall((DOCS / rel).read_text(encoding='utf-8'))[1]
        href = re.search(r'<a href="([^"]+)">Glossary</a>', block)[1]
        path, frag = href.split('#')
        assert (DOCS / rel).parent.joinpath(path).resolve() == index.resolve(), (rel, href)
        assert frag == 'glossary', (rel, href)


@pytest.mark.parametrize('width', [375, 768, 1280])
def test_glossary_anchor_lands_below_the_sticky_header(width):
    """PM, 2026-10-04: the header's Glossary link must not hide the heading under the sticky header."""
    import functools, http.server, json, os, shutil, subprocess, threading
    chrome = next((shutil.which(n) for n in (os.environ.get('CHROME'), 'google-chrome', 'google-chrome-stable',
                                             'chromium', 'chromium-browser') if n and shutil.which(n)), None)
    node = shutil.which('node')
    if chrome is None or node is None:
        if os.environ.get('CI'):
            pytest.fail('headless Chrome and node are required in CI')
        pytest.skip('no Chrome/node available locally')
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DOCS))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_address[1]}/methods/beat_benchmark/index.html#glossary'
    probe = ("(() => { const h = document.getElementById('glossary'), s = document.querySelector('.site-header');"
             " return {top: h.getBoundingClientRect().top, bottom: s.getBoundingClientRect().bottom,"
             " scrollY: window.scrollY, tag: h.tagName, margin: getComputedStyle(h).scrollMarginTop}; })()")
    try:
        cfg = {'urls': [url], 'expression': probe, 'settle_ms': 1500, 'width': width, 'height': 812 if width < 1000 else 900,
               'mobile': width < 1000}
        out = subprocess.run([node, '--experimental-websocket', str(ROOT / 'tests/tools/cdp375.mjs'), chrome, json.dumps(cfg)],
                             capture_output=True, text=True, timeout=300, check=True).stdout
    finally:
        server.shutdown()
    r = json.loads(out.strip().splitlines()[-1])[url]
    assert r['tag'] == 'H2' and r['margin'] == '60px', r
    assert r['scrollY'] > 0, r                       # the fragment navigation actually scrolled
    assert r['top'] >= r['bottom'], (width, r)
