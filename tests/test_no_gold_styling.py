"""No gold / amber / yellow styling: the theme is navy, black and white.

Scans site styling sources and built assets for colours with a hue of roughly
30-60 degrees (gold, amber, yellow, warm cream/beige) and for named gold/amber
colour keywords or Tailwind classes. Wording such as "Treasuries or gold" is
text, not styling, and is not matched. The vendored ECharts bundle
(docs/assets/v2-echarts-*.js) carries the library's built-in colour tables and
is excluded; site charts set explicit colours in components/EChart.tsx.
"""
from __future__ import annotations

import colorsys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLOBS = [
    'apps/pages/tailwind.config.ts', 'apps/pages/index.html',
    'apps/pages/src/**/*.css', 'apps/pages/src/**/*.ts', 'apps/pages/src/**/*.tsx',
    'apps/pages/public/*.svg',
    'docs/**/*.html', 'docs/**/*.css', 'docs/**/*.svg', 'docs/**/*.js',
    'scripts/build_pages.py', 'scripts/build_notes.py',
]
EXCLUDE = re.compile(r'docs/assets/v2-echarts-[^/]+\.js$')
HEX = re.compile(r'(?<![\w&])#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z])')
RGB = re.compile(r'rgba?\(\s*(\d{1,3})[\s,]+(\d{1,3})[\s,]+(\d{1,3})')
NAMED = re.compile(
    r'(?:[:\s"\'](?:color|background|border|fill|stroke)[\w-]*\s*:\s*(?:gold|goldenrod|darkgoldenrod|amber|yellow|khaki|wheat|beige)\b)'
    r'|\b(?:bg|text|border|ring|fill|stroke|from|via|to|outline|decoration|accent)-(?:amber|yellow|orange)-\d{2,3}\b',
    re.I)


def is_goldish(r: int, g: int, b: int) -> bool:
    h, _, _ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    chroma = (max(r, g, b) - min(r, g, b)) / 255
    return 30 <= h * 360 <= 60 and chroma >= 0.03


def violations() -> list[str]:
    bad = []
    files = sorted({p for g in GLOBS for p in ROOT.glob(g) if p.is_file()})
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if EXCLUDE.search(rel):
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for m in HEX.finditer(text):
            h = m.group(1)
            h = ''.join(c * 2 for c in h) if len(h) == 3 else h
            if is_goldish(*(int(h[i:i + 2], 16) for i in (0, 2, 4))):
                bad.append(f'{rel}: #{m.group(1)}')
        for m in RGB.finditer(text):
            rgb = tuple(int(x) for x in m.groups())
            if max(rgb) <= 255 and is_goldish(*rgb):
                bad.append(f'{rel}: {m.group(0)}')
        for m in NAMED.finditer(text):
            bad.append(f'{rel}: {m.group(0).strip()}')
    return bad


def test_no_gold_or_amber_styling():
    bad = violations()
    assert not bad, 'gold/amber styling found:\n' + '\n'.join(sorted(set(bad)))


def test_detector_examples():
    for c in ('#c9a227', '#d4af37', '#f0d78c', '#fff8e6', '#c98100', '#f5f0e8'):
        assert is_goldish(*(int(c[i:i + 2], 16) for i in (1, 3, 5))), c
    for c in ('#1c2d6b', '#ffffff', '#111318', '#c3c7cf', '#8b1a1a', '#1a5e33', '#1a1410'):
        assert not is_goldish(*(int(c[i:i + 2], 16) for i in (1, 3, 5))), c
    assert NAMED.search('class="bg-amber-100"') and NAMED.search('style="color: gold"')
    assert not NAMED.search('rotates into Treasuries or gold') and not NAMED.search('Markowitz Meets Goldilocks')
