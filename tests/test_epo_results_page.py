"""EPO gate results page: built from the committed gate output, linked per the site pattern."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
GATE = ROOT / 'data' / 'processed' / 'epo_allocator' / 'gate_result.json'
PAGE = DOCS / 'methods' / 'allocation_alpha_epo_results.html'

pytestmark = pytest.mark.skipif(not GATE.exists(), reason='EPO gate not run')


def _text(path):
    html = path.read_text(encoding='utf-8')
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))


def _builder():
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_epo_results
    return build_epo_results


def test_results_page_figures_come_from_gate_output():
    gate = json.loads(GATE.read_text(encoding='utf-8'))
    text = _text(PAGE)
    be = gate['fields']['book_eligible']
    b = _builder()
    assert f"{gate['label']} · pending Quant review" in text
    assert f"Book-eligible: {'yes' if be['eligible'] else 'no'}" in text
    assert b.verdict_text(b.gather()) in text
    for key in ('sharpe_exbil_method', 'sharpe_exbil_anchor', 'book1_window_sharpe_method', 'book1_window_sharpe_book1'):
        assert b.num(be[key]) in text
    for key in ('maxdd_method', 'maxdd_book1', 'method_equity_share'):
        assert b.pct(be[key]) in text
    bc = gate['fields']['book1_comparison']
    assert f"Anchor comparison: {bc['full_oos_months']} months" in text
    assert f"{bc['overlap_months']} overlapping months" in text
    for row in gate['fields']['asset_class_mix']:
        for c in ('equity', 'bond', 'commodity'):
            assert b.pct(row[c]) in text
    for c in gate['report']['criteria']:
        assert f' {c.upper()} ' in text
    assert 'Power caveat' in text and 'Book eligibility' in text


def test_results_page_prose_has_no_pr_numbers_or_hashes():
    text = _text(PAGE)
    assert not re.search(r'#\d+\b', text)
    assert not re.search(r'\bPR\b', text)
    assert not re.search(r'\b[0-9a-f]{7,64}\b', text)
    assert 'sha256' not in text.lower()


def test_results_page_linked_from_methods_and_archive_scoreboard():
    for rel in ('methods/index.html', 'methods/justina_round1_scoreboard.html'):
        html = (DOCS / rel).read_text(encoding='utf-8')
        assert 'href="allocation_alpha_epo_results.html"' in html, rel
        assert 'id="card-epo-gate"' in html, rel
