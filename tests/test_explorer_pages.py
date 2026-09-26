"""Static integration and numerical regression checks for the browser explorer."""
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_explorer_links_and_chrome():
    page = ROOT / 'docs/explorer/index.html'
    html = page.read_text()
    assert 'Research only; not investment advice' in html
    assert 'echarts@5.5.1/dist/echarts.min.js' in html
    assert '<noscript>' in html
    assert len(re.findall(r'id="chart-', html)) == 13
    for href in re.findall(r'(?:href|src)="([^"]+)"', html):
        if not href.startswith(('https:', '#')):
            # SPA routes live behind a fragment (e.g. ../index.html#/books); check the file part.
            assert (page.parent / href.split('#', 1)[0]).is_file(), href
    js = (page.parent / 'explorer.js').read_text()
    assert set(re.findall(r"'([.][.]/data/[^']+)'", js)) == {
        '../data/growth_alpha_adj_close.csv',
        '../data/growth_panel_history_coverage.csv',
    }
    for path in (ROOT / 'docs').rglob('*.html'):
        text = path.read_text()
        if 'class="site-nav"' in text:
            assert '>Explorer</a>' in text, path
    assert 'ts_explorer_metric_menu.html' in (ROOT / 'docs/methods/index.html').read_text()


def test_explorer_numerics():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for browser JavaScript numerical tests')
    subprocess.run([node, str(ROOT / 'tests/explorer_numerics.cjs')], cwd=ROOT, check=True)
