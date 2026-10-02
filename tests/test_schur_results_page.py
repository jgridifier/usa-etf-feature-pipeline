"""Schur allocator results page: built from the committed gate output; CIO copy (2026-10-02).

CIO copy: (1) the page opens with the gate verdict, PENDING QUANT RECOMPUTE until Quant rules;
(2) every Book comparison carries the power caveat, month count and detectable gap from data
(book_power.json, recomputed here from the committed returns); (3) on FAIL the Book table is
headed 'Reported only, not book-eligible'; nothing on VOID.
"""
import copy
import html as _html
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
SCHUR = ROOT / 'data' / 'processed' / 'schur_allocator'
GATE = SCHUR / 'gate_result.json'
PAGE = DOCS / 'methods' / 'allocation_alpha_schur_results.html'
ARCHIVE = ROOT / 'apps' / 'pages' / 'src' / 'data' / 'archive_verdicts.json'

pytestmark = pytest.mark.skipif(not GATE.exists(), reason='Schur gate not run')


def _text(path):
    raw = path.read_text(encoding='utf-8')
    raw = raw[raw.index('<main') if '<main' in raw else 0:]
    return _html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', raw)))


def _builder():
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_schur_results
    return build_schur_results


def test_page_opens_with_gate_verdict_pending_quant():
    b = _builder()
    gate = json.loads(GATE.read_text(encoding='utf-8'))
    text = _text(PAGE)
    badge = f"{gate['label']} · PENDING QUANT RECOMPUTE"
    first = text.index(badge)
    assert first < text.index('Schur allocator gate results') < text.index(f'Gate verdict: {badge}.')
    assert text.index(f'Gate verdict: {badge}.') < text.index('Pre-registered gate criteria')
    raw = PAGE.read_text(encoding='utf-8')
    band = raw[raw.index('<section class="band">'):]
    assert band.index('PENDING QUANT RECOMPUTE') < band.index('<table')
    assert b.verdict_text(b.gather()) in text


def test_page_figures_come_from_gate_output():
    b = _builder()
    gate = json.loads(GATE.read_text(encoding='utf-8'))
    d = b.gather()
    text = _text(PAGE)
    full, t = d['full'], b.primary_test(d)
    for sid in b.ORDER:
        for col in ('Sharpe_exBIL', 'Sharpe_rf0_legacy'):
            assert b.num(full[sid][col]) in text
        assert b.pct(full[sid]['MaxDD']) in text and b.pct(full[sid]['CAGR']) in text
    assert b.num(full[b.METHOD]['DSR_exBIL'], 3) in text
    assert f"p = {b.pval(t['p_one_sided_hac'])} (HAC), {b.pval(t['p_one_sided_boot'])} (bootstrap)" in text
    be = gate['fields']['book_eligible']
    for s in be['stats'].values():
        assert b.num(s['Sharpe_exBIL']) in text and b.pct(s['MaxDD']) in text and b.pct(s['CAGR']) in text
    assert f"{be['n_months']} common months" in text
    for c in gate['report']['criteria']:
        assert f' {c.upper()} ' in text
    assert f"{gate['fields']['trial_count']} trials counted" in text and gate['fields']['trial_count'] == 12
    assert gate['fields']['weekly_cutoff_note'] in text
    for label in gate['fields']['display_labels'].values():
        assert label in text
    assert 'HRP (Schur γ=0)' in text


def test_book_power_json_matches_committed_returns():
    sys.path.insert(0, str(ROOT / 'scripts'))
    import schur_book_power
    committed = json.loads((SCHUR / 'book_power.json').read_text(encoding='utf-8'))
    fresh = json.loads(json.dumps(schur_book_power.compute()))
    assert fresh['n_months'] == committed['n_months']
    assert fresh['window'] == committed['window']
    for k, c in committed['comparisons'].items():
        assert fresh['comparisons'][k]['detectable_gap_annual'] == pytest.approx(c['detectable_gap_annual'], abs=1e-9)
        assert fresh['comparisons'][k]['n_months'] == c['n_months']
    gate = json.loads(GATE.read_text(encoding='utf-8'))
    assert committed['n_months'] == gate['fields']['book_eligible']['n_months']
    assert committed['window'] == gate['fields']['book_eligible']['window']


def test_every_book_comparison_has_power_caveat_from_data():
    b = _builder()
    power = json.loads((SCHUR / 'book_power.json').read_text(encoding='utf-8'))
    text = _text(PAGE)
    n = power['n_months']
    lo, hi = b.num(power['detectable_gap_min'], 1), b.num(power['detectable_gap_max'], 1)
    assert f"{n} months ({power['window'].replace('..', ' to ')}) can only detect an annualized Sharpe gap of roughly {lo}–{hi}" in text
    for c in power['comparisons'].values():
        assert f"{c['n_months']} months can only detect a Sharpe gap of roughly {b.num(c['detectable_gap_annual'], 1)} vs {c['label']}" in text
    # Each Book row (Backbone, Book 1, Book 2) and each Book condition carries its caveat.
    raw = PAGE.read_text(encoding='utf-8')
    for row in re.findall(r'<tr>(.*?)</tr>', raw):
        cells = [_html.unescape(re.sub(r'<[^>]+>', '', c)) for c in re.findall(r'<td>(.*?)</td>', row)]
        if cells and cells[0] in ('Backbone', 'Book 1', 'Book 2', 'Sharpe ex-BIL above the Backbone', 'MaxDD no worse than Book 1'):
            assert 'can only detect a Sharpe gap of roughly' in cells[-1], cells
    # Month count and gap are not typed into the builder.
    src = (ROOT / 'scripts' / 'build_schur_results.py').read_text(encoding='utf-8')
    for lit in (str(n), lo, hi):
        assert not re.search(rf'(?<![\d.]){re.escape(lit)}(?!\d)', src), lit


def test_fail_book_table_heading_and_void_shows_nothing():
    b = _builder()
    d = b.gather()
    text = _text(PAGE)
    assert d['gate']['label'] == 'FAIL'
    assert 'Reported only, not book-eligible' in text
    html = b.book_section(d)
    assert '<h2 id="books">Reported only, not book-eligible</h2>' in html
    void = copy.deepcopy(d)
    void['gate']['label'] = 'VOID'
    assert b.book_section(void) == ''
    passing = copy.deepcopy(d)
    passing['gate']['label'] = 'PASS'
    assert '<h2 id="books">Book eligibility</h2>' in b.book_section(passing)
    assert 'Reported only' not in b.book_section(passing)


def test_no_bare_vt_and_site_theme():
    text = _text(PAGE)
    assert not re.search(r'\bVT\b', text)
    assert 'vol-target backbone' in text and 'Backbone' in text
    raw = PAGE.read_text(encoding='utf-8')
    assert 'gold' not in raw.lower()  # site theme: navy/black/white; brand tokens: tests/test_no_brand_tokens.py
    assert 'class="table-scroll"' in raw


def test_archive_card_is_generated_and_linked():
    b = _builder()
    card = b.archive_card()
    cards = {c['id']: c for c in json.loads(ARCHIVE.read_text(encoding='utf-8'))['cards']}
    assert cards['schur_allocator'] == card
    assert list(cards)[-1] == 'schur_allocator'
    assert card['badge'] == 'FAIL' and 'PENDING QUANT RECOMPUTE' in card['verdict'] and 'book-eligible: no' in card['verdict']
    assert 'trial_count=12' in card['detail']
    for rel in ('methods/index.html', 'methods/justina_round1_scoreboard.html'):
        html = (DOCS / rel).read_text(encoding='utf-8')
        start = html.index('id="card-schur_allocator"')
        block = html[start:html.index('</article>', start)]
        assert 'href="allocation_alpha_schur_results.html"' in block, rel
    methods = _text(DOCS / 'methods' / 'index.html')
    assert 'Schur allocator gate results: FAIL · PENDING QUANT RECOMPUTE' in methods


def test_composition_chart_has_schur_group():
    data = json.loads((DOCS / 'data' / 'composition_over_time.json').read_text(encoding='utf-8'))
    charts = {c['id']: c for c in data['charts']}
    for sid in ('schur_g050', 'hrp_g000', 'lw_minvar_156w', 'equal_weight'):
        assert charts[f'schur_{sid}']['source'] == 'data/processed/schur_allocator/weights.csv'
    assert charts['schur_hrp_g000']['name'] == 'HRP (Schur γ=0)'
    page = (DOCS / 'methods' / 'composition_over_time.html').read_text(encoding='utf-8')
    assert '<h2 id="schur">' in page
