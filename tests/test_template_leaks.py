"""No published or pinned page shows an unrendered template placeholder (CoS, 2026-10-04).

A '{' followed by a Python identifier and '(' '[' or '.', or a bare {name} with no math context, in visible text
fails. <pre>, <code>, math blocks (.math, katex/MathJax, \\( \\), \\[ \\], $$ $$) are exempt (scripts/template_leaks.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import pinned_pages as pp  # noqa: E402
from template_leaks import leaks  # noqa: E402

PAGES = sorted(p for p in (ROOT / 'docs').rglob('*.html') if '/assets/' not in str(p))
SOURCES = [pp.source_path(r) for r in pp.SOURCES]


@pytest.mark.parametrize('path', PAGES + SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_unrendered_template_placeholders(path):
    assert leaks(path.read_text(encoding='utf-8')) == [], path


def test_real_formulas_pass():
    page = '<p>R = f_t·R − 5bp·|f_t − f_{t−1}|, g_t ∈ {0.5, 1}; x^{2}; \\frac{a}{b}</p>'
    assert leaks(page) == []
    src = pp.source_path('methods/beat_benchmark/idea1_downside_vol_backbone.html').read_text(encoding='utf-8')
    assert 'f_{t−1}' in src and '{0.5, 1}' in src and leaks(src) == []


@pytest.mark.parametrize('bad', ['<td>{row.cagr:.1%}</td>', '<p>Sharpe {fmt(x)} vs core</p>', '<li>{d[\'n\']} months</li>',
                                 '<p>Window: {start} to {end}</p>'])
def test_placeholders_fail(bad):
    assert leaks('<html><body>' + bad + '</body></html>')


@pytest.mark.parametrize('ok', ['<pre>{row.cagr}</pre>', '<code>{name}</code>', '<span class="math">{x.y}</span>',
                                '<p>\\(f_{t}\\) and $${w.x}$$</p>', '<script>const a = {b: 1}; x = {c.d}</script>',
                                '<div class="katex">{a(b)}</div>'])
def test_code_and_math_are_exempt(ok):
    assert leaks('<html><body>' + ok + '</body></html>') == []


def test_a_leaky_index_fails_and_the_published_index_passes():
    # The old index (a96c9bbc…) is no longer on the box; this is the published index with one cell left unrendered.
    good = (ROOT / 'docs/methods/beat_benchmark/index.html').read_text(encoding='utf-8')
    assert leaks(good) == []
    bad = good.replace('</h1>', '</h1><p>Top pick: {best.name} ({best.sharpe_gap:+.2f})</p>', 1)
    assert bad != good and leaks(bad)
