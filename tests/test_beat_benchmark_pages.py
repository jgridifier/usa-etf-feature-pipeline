"""Quant's beat-the-benchmark shortlist (Oct 2026), published byte-for-byte under docs/methods/beat_benchmark/.

Source: /workspace/investments/methods/beat_benchmark_2026-10/ (work/ is not published). The pages are committed in
docs/ (the build neither regenerates nor restyles this directory: restyle_methods_shell only globs docs/methods/*.html
and self_host_fonts leaves pages without outside font links untouched), and their bytes are pinned here.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / 'docs/methods/beat_benchmark'
SRC = Path('/workspace/investments/methods/beat_benchmark_2026-10')
PINNED = {
    'index.html': '4fe1d365023e881fe74b298053e26d60dd58b17e03670eb2e4cec8f8feb2edc2',
    'idea1_downside_vol_backbone.html': '148bee5be00d8f8532140e2d5134fcd24f8fd2e8da4772bd7b22b6d372587fac',
    'idea2_fixed_blend_book2_core.html': '244201804f1b828e7530ff5953cf731c2ac9a9d46d3feecfb71c274db1e3e731',
    'idea3_har_vol_forecast.html': 'f0091e7735aea9311f51947d5bfa8e3ad1c134d025bc250db5ce9d832e5c8c75',
}


def test_published_bytes_are_pinned():
    assert sorted(p.name for p in DIR.iterdir()) == sorted(PINNED)      # nothing else (no work/)
    for name, sha in PINNED.items():
        assert hashlib.sha256((DIR / name).read_bytes()).hexdigest() == sha, name


@pytest.mark.skipif(not SRC.exists(), reason="Quant's source folder is only on the research box")
def test_published_bytes_equal_quants_source():
    for name in PINNED:
        assert (DIR / name).read_bytes() == (SRC / name).read_bytes(), name


def test_build_does_not_touch_the_pages():
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    src = (ROOT / 'scripts/build_pages.py').read_text()
    assert "(DOCS / 'methods').glob('*.html')" in src        # restyle pass is top-level only
    for name in PINNED:
        s = (DIR / name).read_text(encoding='utf-8')
        assert 'fonts.googleapis.com' not in s and 'assets/style.css' not in s   # self_host_fonts no-op


def test_results_hub_links_the_shortlist():
    hub = (ROOT / 'docs/methods/results/index.html').read_text(encoding='utf-8')
    assert 'href="../beat_benchmark/index.html"' in hub
