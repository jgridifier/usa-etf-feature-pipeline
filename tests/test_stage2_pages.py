"""Stage-2 pages: the appendix is a pinned verbatim copy, rendered phone-readable; the teaching note ships only at
its final pinned hash (Quant is revising it)."""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_stage2_pages as st  # noqa: E402

PAGE = ROOT / 'docs' / st.PAGE
TEACH = ROOT / 'docs/methods' / st.TEACHING


def test_appendix_copy_matches_pin_and_provenance():
    assert hashlib.sha256(st.APPENDIX_SRC.read_bytes()).hexdigest() == st.APPENDIX_SHA256
    assert st.APPENDIX_SHA256 in (ROOT / 'data/processed/stage2/PROVENANCE.md').read_text()
    assert not [p for p in (ROOT / 'data/processed/stage2').iterdir() if p.name.upper().startswith('QUANT_')]
    assert not [p for p in (ROOT / 'docs/methods').iterdir() if p.name.upper().startswith('QUANT_')]


def test_rendered_page_is_current_and_carries_kwz_correction_and_placebo():
    html = PAGE.read_text()
    pages = {}
    import build_pages
    st.build_page(build_pages.page_shell, lambda rel, h: pages.__setitem__(rel, h), ROOT / 'docs')
    assert pages[st.PAGE] == html, 'docs page is stale: run scripts/build_stage2_pages.py'
    assert 'does not fall back to EW. It falls back to GMV' in html
    assert re.search(r'Placebo: shuffled characteristics', html) and '<strong>0.08</strong>' in html
    assert html.count('assets/nav.js') == 1 and 'class="nav-toggle"' in html
    assert html.count('<table>') == html.count('class="table-scroll"')   # tables scroll inside a box at 375px
    assert '**' not in html and '| ---' not in html and '|---' not in html  # no raw markdown left


def test_every_appendix_number_reaches_the_page():
    text = re.sub(r'<[^>]+>', '', PAGE.read_text())
    import html as h
    text = h.unescape(text)
    md = st.APPENDIX_SRC.read_text()
    for num in set(re.findall(r'(?<![\w.])[−-]?\d+\.\d+', md)):
        assert num in text, num


def test_teaching_note_ships_only_at_its_final_pinned_hash():
    if st.TEACHING_SHA256 is None:
        assert not TEACH.exists(), 'teaching note must not ship before its final sha256 is pinned'
        assert 'being revised' in PAGE.read_text()
    else:
        assert hashlib.sha256(TEACH.read_bytes()).hexdigest() == st.TEACHING_SHA256
        assert f'href="{st.TEACHING}"' in PAGE.read_text()
        assert st.TEACHING_SHA256 in (ROOT / 'data/processed/stage2/PROVENANCE.md').read_text()


def test_publish_refuses_wrong_or_unpinned_hash(tmp_path, monkeypatch):
    import pytest
    src = tmp_path / 'x.html'
    src.write_text('draft')
    (tmp_path / 'methods').mkdir()
    monkeypatch.setattr(st, 'TEACHING_SHA256', None)
    with pytest.raises(SystemExit):
        st.publish_teaching(src, tmp_path)
    monkeypatch.setattr(st, 'TEACHING_SHA256', '0' * 64)
    with pytest.raises(SystemExit):
        st.publish_teaching(src, tmp_path)
    assert not (tmp_path / 'methods' / st.TEACHING).exists()


def test_final_teaching_note_is_pinned_and_the_kwz_version_never_ships():
    assert st.TEACHING == 'stage2_demiguel.html'
    assert st.TEACHING_SHA256 == '08b251a2425b1802ddf5c8e7de63ab8b97469744d5fbff8490c3c8cb56fb0893'   # replaces 8091157e…
    assert hashlib.sha256(TEACH.read_bytes()).hexdigest() == st.TEACHING_SHA256
    assert not (ROOT / 'docs/methods/stage2_demiguel_kwz.html').exists()
    raw = TEACH.read_text()
    assert '<script' not in raw.lower() and 'cdn' not in raw.lower()


def test_demiguel_book_rule_json_is_sourced_and_consistent():
    import json
    d = json.loads((ROOT / 'data/processed/stage2/demiguel_book_rule.json').read_text())
    assert d['source']['body_sha256'] == 'f004527e2c41183ef679b7ca5b9de18bc9884ef1c64816201df9963c96496e0c'
    assert d['source']['body_sha256'] in (ROOT / 'data/processed/stage2/PROVENANCE.md').read_text()
    assert d['status'] == 'forward-tracked research line' and d['book_eligible'] is False
    a, b = d['book_rule']
    assert a['value'] > a['limit'] and a['outcome'] == 'FAIL' and a['unit'].startswith('one-way')
    assert abs((b['cagr'] - b['core_cagr']) - b['diff']) < 1e-9 and b['diff'] < 0 and b['outcome'] == 'FAIL'
    assert b['cost_bp_one_way'] == 10 and 'two-way' in d['cost_convention'] and '10 bp one-way' in d['cost_convention']


def test_addendum3_and_livecore_recheck_are_verbatim_renamed_and_linked():
    a3 = ROOT / 'data/processed/stage2/stage2_holdout_addendum3.md'
    rc = ROOT / 'data/processed/stage2/stage2_livecore_recheck.md'
    assert hashlib.sha256(a3.read_bytes()).hexdigest() == st.ADDENDUM3_SHA256 == \
        '47234cbc5f1af5beb9a859ccb56da52dfb28cb1164a507b6025a60f3994756df'
    assert hashlib.sha256(rc.read_bytes()).hexdigest() == st.RECHECK_SHA256 == \
        '930692cdd2f03e5a5024226a0abb3f17d02d26d86d20f6c841d1adc7740c12ff'
    prov = (ROOT / 'data/processed/stage2/PROVENANCE.md').read_text()
    assert st.ADDENDUM3_SHA256 in prov and st.RECHECK_SHA256 in prov
    assert not [f for f in (ROOT / 'data/processed/stage2').iterdir() if f.name.upper().startswith('QUANT_')]
    a3h = (ROOT / 'docs/methods/stage2_addendum3.html').read_text()
    assert '<li id="s1-1"><strong>DeMiguel (frozen κ = 5 spec' in a3h
    assert 'href="stage2_livecore_recheck.html"' in a3h and 'Nothing needs recomputing' in (ROOT / 'docs/methods/stage2_livecore_recheck.html').read_text()
    rob = (ROOT / 'docs/methods/stage2_robustness.html').read_text()
    i = rob.index('<li>N_holdout = 1, DeMiguel only.')
    j = rob.index('</li>', i)
    # §7 text is untouched; the Addendum 3 link is a separate lab note right after it
    assert rob[j:j + 200].startswith('</li><li class="lab-link"') and 'stage2_addendum3.html#s1-1' in rob[j:j + 300]


def test_family2_json_leads_with_live_core_and_one_way_turnover():
    import json
    d = json.loads((ROOT / 'data/processed/stage2/family2_dev.json').read_text())
    a6, b3 = d['candidates']
    assert (a6['id'], b3['id']) == ('A6', 'B3') and d['status'].startswith('forward-only')
    assert round(a6['turnover_one_way'] * 100) == 12 and round(a6['turnover_l1'] * 100) == 24
    assert round(b3['turnover_one_way'] * 100) == 75 and round(b3['turnover_l1'] * 100) == 149
    assert round(b3['vs_live_core']['cagr_diff_10bp'] * 100, 1) == -1.4
    assert round(b3['vs_standin_core']['cagr_diff_10bp'] * 100, 1) == -2.7
    assert a6['vs_live_core']['sharpe_gap_ci'][0] == -0.1228 and a6['vs_live_core']['sharpe_gap_ci'][2] == 0.0575
    assert a6['caution'] == 'degenerate: holds the Oct 2020 weights' and b3['caution'] == '0.95 correlated with Book 2'
    assert '½·Σ|Δw|' in d['turnover_convention']
    assert round(a6['vs_live_core']['cagr_diff'] * 100, 2) == -0.71 and 'transcription error' in a6['vs_live_core']['cagr_diff_footnote']
    dm = json.loads((ROOT / 'data/processed/stage2/demiguel_book_rule.json').read_text())
    assert dm['core_label'] == dm['book_rule'][1]['core_label'] == 'stand-in core only'
