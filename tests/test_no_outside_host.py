"""The built site loads nothing from an outside host (PM re-test of a221d3c, item 1).

Fonts are vendored under docs/assets/fonts (docs/assets/fonts.css) and ECharts under docs/assets/vendor,
so no built page or stylesheet may point a <link>, <script>, <img>, <iframe>, <source>, <video>, <audio>
or <object> at an outside host, and no CSS may @import or url() one. Ordinary <a href> links out are fine:
they load nothing.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
OUTSIDE = r'(?:https?:)?//'
RESOURCE_TAG = re.compile(
    r'<(link|script|img|iframe|source|video|audio|object|embed|use|image)\b[^>]*?\b(?:src|href|srcset|data|poster|xlink:href)\s*=\s*["\']?\s*'
    + OUTSIDE, re.I)
CSS_REF = re.compile(r'@import\s+(?:url\(\s*)?["\']?\s*' + OUTSIDE + r'|url\(\s*["\']?\s*' + OUTSIDE, re.I)
FONT_HOSTS = re.compile(r'fonts\.(?:googleapis|gstatic)\.com', re.I)


def _files(suffixes):
    return sorted(p for p in DOCS.rglob('*') if p.is_file() and p.suffix in suffixes)


def test_pages_and_css_are_found():
    assert len(_files({'.html'})) >= 30
    assert (DOCS / 'assets' / 'style.css').exists() and (DOCS / 'assets' / 'fonts.css').exists()


def test_no_built_page_loads_from_an_outside_host():
    bad = []
    for p in _files({'.html'}):
        s = p.read_text(encoding='utf-8')
        for m in RESOURCE_TAG.finditer(s):
            bad.append(f'{p.relative_to(ROOT)}: {m.group(0)[:120]}')
        for block in re.findall(r'<style\b[^>]*>(.*?)</style>|style\s*=\s*"([^"]*)"', s, flags=re.S | re.I):
            for css in block:
                if css and CSS_REF.search(css):
                    bad.append(f'{p.relative_to(ROOT)}: inline CSS {CSS_REF.search(css).group(0)}')
    assert not bad, '\n'.join(bad)


def test_no_stylesheet_imports_or_urls_an_outside_host():
    bad = [f'{p.relative_to(ROOT)}: {m.group(0)}' for p in _files({'.css'})
           for m in CSS_REF.finditer(p.read_text(encoding='utf-8'))]
    assert not bad, '\n'.join(bad)


def test_no_google_fonts_reference_anywhere_in_the_site():
    bad = [str(p.relative_to(ROOT)) for p in _files({'.html', '.css', '.js'})
           if FONT_HOSTS.search(p.read_text(encoding='utf-8', errors='replace'))]
    assert not bad, bad


def test_fonts_are_vendored_and_every_face_is_local():
    css = (DOCS / 'assets' / 'fonts.css').read_text(encoding='utf-8')
    urls = re.findall(r'url\(\s*["\']?([^"\')]+)', css)
    assert urls and len(re.findall(r'@font-face', css)) == len(urls)
    for u in urls:
        assert not re.match(OUTSIDE, u), u
        f = (DOCS / 'assets' / u).resolve()
        assert f.suffix == '.woff2' and f.exists() and f.stat().st_size > 1000, u
    for fam in ('Inter', 'JetBrains Mono', 'Newsreader', 'Playfair Display'):
        assert f"font-family: '{fam}'" in css or f'font-family: "{fam}"' in css or f'font-family:{fam}' in css, fam


def test_echarts_is_local():
    pages = [p for p in _files({'.html'}) if 'echarts' in p.read_text(encoding='utf-8').lower()]
    assert pages
    for p in pages:
        for src in re.findall(r'<script\b[^>]*\bsrc\s*=\s*["\']([^"\']*echarts[^"\']*)', p.read_text(encoding='utf-8'), re.I):
            assert not re.match(OUTSIDE, src), (p, src)
            assert (p.parent / src.split('?')[0]).resolve().exists(), (p, src)
