"""Quant's beat-the-benchmark shortlist (Oct 2026) under docs/methods/beat_benchmark/.

Source bytes: data/pinned_pages/methods/beat_benchmark/, committed byte-for-byte from Quant's folder
/workspace/investments/methods/beat_benchmark_2026-10/ (work/ is not published). The build (scripts/pinned_pages.py)
publishes each page with the shared lab header added inside <!-- lab:start -->…<!-- lab:end --> blocks only, so the
source hash and the published hash are pinned separately. Revision 2026-10-04 (final hashes from CoS, 22:48 ET)
replaces the first publication (index 4fe1d365…, idea1 148bee5b…, idea2 24420180…, idea3 f0091e77…).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import pinned_pages as pp  # noqa: E402

DIR = ROOT / 'docs/methods/beat_benchmark'
SRC = ROOT / 'data/pinned_pages/methods/beat_benchmark'
QUANT = Path('/workspace/investments/methods/beat_benchmark_2026-10')
SOURCE = {   # Quant's bytes (final revision of 2026-10-04, hashes from CoS 22:48 ET)
    'index.html': 'c51c8cedbde9ed1a5646e54de19798d8fb4a933d812ed52931a083f1e52127cb',
    'idea1_downside_vol_backbone.html': '3aee82fde8578f09495d93451996a97c3d7dc387704993524a14146375973d19',
    'idea2_fixed_blend_book2_core.html': 'cdece2fbd5e9c50542a21cca99d334608ef8433dbdd7417304f309d2c0a0cccf',
    'idea3_har_vol_forecast.html': 'f81988643880258ffddb873bc9b35285d0f088278608209f60d629088f5ea296',
}
PUBLISHED = {   # source + lab-header blocks (header, results-hub and Glossary links, nav.js)
    'index.html': '1574be2ab5a8e6888d158ca855af649081ec55e1eee75bfcbacdf7d052c52e42',
    'idea1_downside_vol_backbone.html': 'd848c18e163bee5eeb681bd6488c88585bcb9973a89babd137c00a6ac3be8c50',
    'idea2_fixed_blend_book2_core.html': 'd5a159c5605777269e207bdadd247e396abc0d680b4baea9f2fe1d9ed4e4e3b2',
    'idea3_har_vol_forecast.html': 'df1a63537c56c4633fb8666434cc001499621b0980b35f7c80c508e028641744',
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_source_bytes_are_pinned_in_test_and_build():
    assert sorted(p.name for p in SRC.iterdir()) == sorted(SOURCE)          # nothing else (no work/)
    for name, want in SOURCE.items():
        assert sha((SRC / name).read_bytes()) == want, name
        assert pp.SOURCES[f'methods/beat_benchmark/{name}'] == want, name


def test_published_bytes_are_pinned_and_strip_back_to_the_source():
    assert sorted(p.name for p in DIR.iterdir()) == sorted(PUBLISHED)
    for name, want in PUBLISHED.items():
        raw = (DIR / name).read_bytes()
        assert sha(raw) == want, name
        assert pp.strip_lab(raw.decode('utf-8')).encode('utf-8') == (SRC / name).read_bytes(), name


@pytest.mark.skipif(not QUANT.exists(), reason="Quant's source folder is only on the research box")
def test_committed_source_equals_quants_file_when_it_is_the_pinned_revision():
    # Quant keeps editing the folder; a file at a different hash is an unpinned draft, not a publication error.
    for name, want in SOURCE.items():
        if sha((QUANT / name).read_bytes()) == want:
            assert (QUANT / name).read_bytes() == (SRC / name).read_bytes(), name


def test_rebuild_reproduces_the_published_pages(tmp_path):
    import build_pages
    out = pp.publish(build_pages.nav_html, tmp_path)
    for name, want in PUBLISHED.items():
        assert out[f'methods/beat_benchmark/{name}'] == want, name


def test_results_hub_links_the_shortlist_with_its_revision_date():
    hub = (ROOT / 'docs/methods/results/index.html').read_text(encoding='utf-8')
    i = hub.index('href="../beat_benchmark/index.html"')
    assert 'revised 2026-10-04' in hub[i:i + 300]
