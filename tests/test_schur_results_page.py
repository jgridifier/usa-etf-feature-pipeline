"""Schur allocator results page: built from the committed gate output; CIO copy (2026-10-02).

CIO copy: (1) the page opens with the gate verdict (Quant's verdict record: FAIL / ARCHIVE, recompute confirmed);
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


def test_page_opens_with_confirmed_gate_verdict():
    b = _builder()
    gate = json.loads(GATE.read_text(encoding='utf-8'))
    text = _text(PAGE)
    verdict = json.loads((SCHUR / 'verdict.json').read_text(encoding='utf-8'))
    assert verdict['verdict'] == gate['label'] == 'FAIL' and verdict['final_trial_count'] == gate['fields']['trial_count'] == 12
    assert verdict['book_eligible'] is False and verdict['follow_up_run'] is False
    badge = verdict['verdict_label']
    assert badge == 'FAIL / ARCHIVE (Quant recompute confirmed)'
    assert 'PENDING' not in text
    first = text.index(badge)
    assert first < text.index('Schur allocator gate results') < text.index(f'Gate verdict: {badge}.')
    assert text.index(f'Gate verdict: {badge}.') < text.index('Pre-registered gate criteria')
    raw = PAGE.read_text(encoding='utf-8')
    band = raw[raw.index('<section class="band">'):]
    assert band.index(badge) < band.index('<table')
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
        if cells and cells[0] in ('Backbone', 'Book 1', 'Book 2', 'Sharpe ex-BIL above the Backbone'):
            assert 'can only detect a Sharpe gap of roughly' in cells[-1], cells
        if cells and cells[0] == 'MaxDD no worse than Book 1':
            assert cells[-1] == 'single path, no test', cells
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
    assert card['badge'] == 'FAIL' and card['verdict'].startswith('FAIL / ARCHIVE (Quant recompute confirmed). ') and 'book-eligible: no' in card['verdict']
    assert 'trial_count=12' in card['detail']
    for rel in ('methods/index.html', 'methods/justina_round1_scoreboard.html'):
        html = (DOCS / rel).read_text(encoding='utf-8')
        start = html.index('id="card-schur_allocator"')
        block = html[start:html.index('</article>', start)]
        assert 'href="allocation_alpha_schur_results.html"' in block, rel
    methods = _text(DOCS / 'methods' / 'index.html')
    assert 'Schur allocator gate results: FAIL / ARCHIVE (Quant recompute confirmed)' in methods
    assert card['rows'] == []   # site_sharpe.json stays as pinned on main
    assert card['method_page'] == 'methods/allocation_alpha_schur.html'
    for rel in ('methods/index.html', 'methods/justina_round1_scoreboard.html', 'methods/composition_over_time.html'):
        assert 'PENDING' not in (DOCS / rel).read_text(encoding='utf-8'), rel


def test_composition_chart_has_schur_group():
    data = json.loads((DOCS / 'data' / 'composition_over_time.json').read_text(encoding='utf-8'))
    charts = {c['id']: c for c in data['charts']}
    for sid in ('schur_g050', 'hrp_g000', 'lw_minvar_156w', 'equal_weight'):
        assert charts[f'schur_{sid}']['source'] == 'data/processed/schur_allocator/weights.csv'
    assert charts['schur_hrp_g000']['name'] == 'HRP (Schur γ=0)'
    page = (DOCS / 'methods' / 'composition_over_time.html').read_text(encoding='utf-8')
    assert '<h2 id="schur">' in page


# ---------------------------------------------------------------- CIO copy edits (2026-10-02, round 2)
def _callout(text):
    start = text.index('Gate verdict:')
    return text[start:text.index('Single pre-registered run', start)]


def test_cio_edit_1_edged_hrp_diff_from_data():
    b = _builder()
    d = b.gather()
    diff = b.num(b.sharpe(d, b.METHOD) - b.sharpe(d, b.HRP))
    assert diff == '0.01'
    callout = _callout(_text(PAGE))
    assert f'It edged HRP (Schur γ=0) by {diff}, which is within noise.' in callout
    assert 'matched or beat HRP' not in callout


def test_cio_edit_2_quant_gamma_sentence_from_split_log():
    """Quant's sentence replaces the CIO draft; every number recomputed here from split_log.csv."""
    import csv
    b = _builder()
    with (SCHUR / 'split_log.csv').open(newline='', encoding='utf-8') as f:
        rows = [r for r in csv.DictReader(f) if r['strategy_id'] == 'schur_g050']
    halved = [r for r in rows if float(r['gamma']) < float(r['gamma_initial'])]
    assert (len(halved), len(rows)) == (783, 2251)
    w = sum(float(r['n']) * float(r['gamma']) / float(r['gamma_max']) for r in rows) / sum(float(r['n']) for r in rows)
    assert round(w, 2) == 0.43
    assert sum(int(r['depth']) >= 3 for r in halved) / len(halved) > 0.5      # "deep in the tree"
    assert sum(float(r['n']) <= 16 for r in halved) / len(halved) > 0.5       # "small clusters"
    assert not any(int(r['depth']) == 0 for r in halved)
    gs = b.gamma_stats(b.gather())
    assert (gs['n_halved'], gs['n_splits']) == (783, 2251) and gs['weighted'] == pytest.approx(w)
    quant = ('About a third of splits, mostly small clusters deep in the tree, ran with γ halved. Weighted by cluster size, '
             'the average γ was 0.43 instead of 0.5, so the method sat slightly closer to HRP than its label.')
    assert b.smaller_gamma_text(b.gather()) == quant
    raw = PAGE.read_text(encoding='utf-8')
    li = [_html.unescape(x) for x in re.findall(r'<li>(.*?)</li>', raw)]
    i = next(k for k, x in enumerate(li) if x.startswith('γ fallback share of Schur splits'))
    assert li[i + 1] == quant + ' Halved: 783 of 2,251 splits (34.8%).'
    src = (ROOT / 'scripts' / 'build_schur_results.py').read_text(encoding='utf-8')
    for lit in ('783', '2,251', '0.43', '34.8'):
        assert lit not in src, lit


def test_teaching_page_published_byte_for_byte_and_cross_linked():
    import hashlib
    page = DOCS / 'methods' / 'allocation_alpha_schur.html'
    raw = page.read_bytes()
    source = Path('/workspace/investments/methods/allocation_alpha_schur.html')
    if source.exists():   # Quant's source on the shared box; CI checks the pinned hash only
        assert hashlib.sha256(source.read_bytes()).hexdigest() == hashlib.sha256(raw).hexdigest()
    assert hashlib.sha256(raw).hexdigest() == '53f740e918dae4220549008773a44fda594fd0980688c7d47849f455a852ed3a'
    text = raw.decode('utf-8')
    assert 'href="allocation_alpha_schur_results.html"' in text
    assert 'href="allocation_alpha_schur.html"' in PAGE.read_text(encoding='utf-8')
    methods = (DOCS / 'methods' / 'index.html').read_text(encoding='utf-8')
    assert methods.index('href="allocation_alpha_schur.html"') < methods.index('href="allocation_alpha_schur_results.html"')
    low = text.lower()
    assert 'gold' not in low and '<img' not in low and '<svg' not in low
    assert not re.search(r'\bVT\b', re.sub(r'<[^>]+>', ' ', text))


def test_cio_edit_4_no_power_caveat_under_full_window_table():
    text = _text(PAGE)
    start = text.index('Sharpe ex-BIL is in excess of BIL')
    note = text[start:text.index('Ledoit-Wolf (2008) Sharpe-difference test', start)]
    assert 'Power caveat' not in note and 'can only detect' not in note
    assert text.index('Power caveat:') > text.index('Reported only, not book-eligible')


def test_cio_edit_5_lessons_line_closes_callout_with_data_figures():
    b = _builder()
    gate = json.loads(GATE.read_text(encoding='utf-8'))
    st = gate['fields']['book_eligible']['stats']
    schur, backbone = b.num(st['schur_g050']['Sharpe_exBIL']), b.num(st['backbone']['Sharpe_exBIL'])
    assert (schur, backbone) == ('0.57', '0.86')
    lesson = b.LESSONS_TEXT.format(schur=schur, backbone=backbone)
    callout = _callout(_text(PAGE))
    assert lesson in callout and callout.index(lesson) > callout.index('No book changes.')
    # The Book comparison in the lesson carries its caveat (power for Sharpe, single path for MaxDD).
    tail = callout[callout.index(lesson) + len(lesson):]
    assert 'can only detect a Sharpe gap of roughly' in tail and 'single path, no test' in tail
