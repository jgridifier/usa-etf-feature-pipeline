"""Subject verdict sentences: present on every subject page and, for Book 2, consistent with the data files."""
from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_hub_pages as hub  # noqa: E402


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


def test_every_subject_page_has_a_verdict_text():
    for id in hub.PILOTS:
        text = (load(f'data/processed/hub/subjects/{id}.json')['verdict'] or {}).get('text')
        assert isinstance(text, str) and text.strip(), id


def test_book2_page_renders_the_verdict_sentence_under_the_badge():
    raw = (ROOT / 'docs/methods/results/book2.html').read_text(encoding='utf-8')
    block = re.search(r'<div class="verdict"><p><span class="badge">([^<]+)</span></p><p[^>]*>([^<]*)</p></div>', raw)
    assert block, 'verdict block missing under the h1'
    assert block[1] == 'LIVE BOOK'
    sentence = unescape(block[2]).strip()
    assert sentence and sentence == load('data/processed/hub/subjects/book2.json')['verdict']['text']
    assert raw.index('<h1') < raw.index('<div class="verdict">')


def test_book2_verdict_figures_match_the_data():
    text = load('data/processed/hub/subjects/book2.json')['verdict']['text']
    books = load('docs/data/live_figures.json')['books']
    b2, core = books['book2'], books['book1']
    pct = lambda x: f'{x * 100:.1f}%'.replace('-', '−')
    assert f"Max drawdown {pct(b2['max_dd'])} vs {pct(core['max_dd'])} for the core" in text
    assert f"Sharpe ex-BIL {b2['sharpe_exbil']:.2f} vs {core['sharpe_exbil']:.2f}" in text
    assert f"CAGR {pct(b2['ann_return'])} vs {pct(core['ann_return'])}" in text
    backbone = next(n for n in load('data/processed/hub/subjects/book2.json')['vs_nulls'] if n['key'] == 'backbone')
    assert backbone['sharpe_test']['significant_5pct_two_sided'] is False and 'not significant' in text
