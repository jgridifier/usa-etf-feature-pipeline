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
