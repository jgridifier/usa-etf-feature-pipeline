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
ARCHIVE = ROOT / 'apps' / 'pages' / 'src' / 'data' / 'archive_verdicts.json'
# archive_verdicts.json is append-only. Pinned 2026-10-01 when the EPO card was appended: sha256 of the
# file's bytes up to the end of the last pre-existing card (main before the append), so every
# pre-existing entry, its order and the file header stay byte-for-byte unchanged.
ARCHIVE_PREFIX_SHA256 = '63f0434c569668dfad17d84b6e7fc0bd4c544b2545e2adb91c75a402c7b07ad4'
ARCHIVE_PREFIX_LEN = 13400
PRE_EXISTING_IDS = ['spectral_rp', 'regime_dual', 'vcfc', 'ft_med', 'rr_erc', 'nls_gmv_v3', 'uncond_book2_vt']

pytestmark = pytest.mark.skipif(not GATE.exists(), reason='EPO gate not run')


def _text(path):
    html = path.read_text(encoding='utf-8')
    import html as _html
    return _html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)))


def _builder():
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_epo_results
    return build_epo_results


def test_results_page_figures_come_from_gate_output():
    gate = json.loads(GATE.read_text(encoding='utf-8'))
    text = _text(PAGE)
    be = gate['fields']['book_eligible']
    b = _builder()
    verdict = json.loads((GATE.parent / 'verdict.json').read_text(encoding='utf-8'))
    assert verdict['verdict'] == gate['label'] and verdict['final_trial_count'] == gate['fields']['trial_count']
    assert verdict['book_eligible'] is be['eligible'] is False
    line = verdict['verdict_line']
    assert line == 'Quant: FAIL / ARCHIVE, not book-eligible, no follow-up run'
    # Published record: verdict line sits beside the label, above the title; nothing pending.
    assert text.index(verdict['verdict_label']) < text.index(line) < text.index('EPO gate results: anchored EPO') < text.index('Verdict.')
    assert 'pending' not in text.lower()
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


def test_archived_fail_card_on_methods_and_archive_scoreboard():
    import html as _html
    gate = json.loads(GATE.read_text(encoding='utf-8'))
    b = _builder()
    d = b.gather()
    card = b.archive_card()
    full = d['full']
    m, a = full[b.METHOD], full[b.ANCHOR]
    # Card content comes from the run output + verdict record.
    assert card['badge'] == gate['label'] == 'FAIL'
    assert f"trial_count={gate['fields']['trial_count']}" in card['detail'] and gate['fields']['trial_count'] == 11
    assert f"Sharpe ex-BIL {b.num(m['Sharpe_exBIL'])} vs {b.num(a['Sharpe_exBIL'])}" in card['verdict']
    assert 'book-eligible: no' in card['verdict']
    assert card['verdict'].startswith(d['verdict']['verdict_line'])
    assert card['nw_t_links'] == [{'label': 'Results page', 'href': 'methods/allocation_alpha_epo_results.html'}]
    # The frozen archive file carries exactly this generated card (appended 2026-10-01).
    assert json.loads(ARCHIVE.read_text(encoding='utf-8'))['cards'][-1] == card
    rows = {r['role']: r for r in card['rows']}
    assert rows['method']['sharpe'] == f"{b.num(m['Sharpe_exBIL'])} (legacy {b.num(m['Sharpe_rf0_legacy'])})" == '0.27 (legacy 0.85)'
    assert rows['reference']['sharpe'].startswith('0.61 ')
    for rel in ('methods/index.html', 'methods/justina_round1_scoreboard.html'):
        html = (DOCS / rel).read_text(encoding='utf-8')
        start = html.index('id="card-epo_anchored_trend"')
        block = _html.unescape(html[start:html.index('</article>', start)])
        assert '<span class="badge badge-fail">FAIL</span>' in block, rel
        assert 'trial_count=11' in block and 'Sharpe ex-BIL 0.27 vs 0.61' in block and 'book-eligible: no' in block, rel
        assert 'href="allocation_alpha_epo_results.html"' in block, rel
        assert 'Pending review' not in html and 'card-epo-gate' not in html, rel
        # Appended to the archive record: listed after every pre-existing card.
        assert html.index('id="card-nls_gmv_v3"') < html.index('id="card-uncond_book2_vt"') < start, rel
    methods = (DOCS / 'methods' / 'index.html').read_text(encoding='utf-8')
    assert '6 FAIL / ARCHIVE methods + 1 VOID' in methods
    assert 'EPO gate results: FAIL / ARCHIVE' in methods
    board = (DOCS / 'methods' / 'justina_round1_scoreboard.html').read_text(encoding='utf-8')
    assert 'The six failed methods are' in board
    # CIO quote: only the count changes (derived from the FAIL cards).
    assert ('<p><em>None of the six archived methods cleared its binding null, and NLS GMV v3 is VOID.</em> '
            '<strong>No book cut.</strong></p>') in board
    assert 'None of the five archived methods' not in board


# Lead sentence: Quant's correction (CIO signed off), replacing the CIO's first draft.
CIO_LEAD = ("FAIL. EPO trailed the 1/σ anchor it is built on (0.27 vs 0.61). Any weight on correlations pulled it to about "
            "84% bonds, and the trend signal didn't make up for it (plain trend: 0.43).")
CIO_C1_END = ('It did beat its primary null, weekly Ledoit-Wolf minimum variance (0.04 Sharpe ex-BIL, about 90% bonds), '
              'by a statistically significant margin, but that is a low bar.')
# CAGRs over the Book 1 comparison window (71 overlapping months), matching the MaxDD row (re-pinned 2026-10-01).
CIO_DRAWDOWN = ("The shallower drawdown comes from holding mostly bonds (3.5% CAGR vs Book 1's 17.3%), "
                'not from better equity risk control.')
CIO_LESSONS = ('Starting from a 1/σ anchor with about 50% equity, the mean-variance step moved weight into low-vol bonds, '
               'the same pull that undid the GMV runs. Plain equal weight (0.63) did better than every allocator tested here. '
               'It is an in-sample reference only, not a candidate.')


def test_cio_copy_edits_present_and_in_order():
    import html as _html
    text = _html.unescape(_text(PAGE))
    b = _builder()
    d = b.gather()
    # Rendered from the run output; the literals above only pin the CIO wording for this committed run.
    verdict = b.verdict_text(d)
    assert verdict.startswith(CIO_LEAD) and verdict.endswith(CIO_C1_END)
    assert b.drawdown_note(d) == CIO_DRAWDOWN
    assert b.lessons_text(d) == CIO_LESSONS
    pos = [text.index(s) for s in ('Verdict.', CIO_LEAD, CIO_C1_END, 'Book eligibility (all of:', '…or on MaxDD',
                                   CIO_DRAWDOWN, 'What we learned', CIO_LESSONS, 'Power caveat')]
    assert pos == sorted(pos)
    assert text.index(CIO_LEAD) - text.index('Verdict.') == len('Verdict. ')
    assert 'trend tilt subtracted value' not in text


def test_archive_file_pre_existing_entries_byte_identical():
    import hashlib
    data = ARCHIVE.read_bytes()
    marker = b',\n    {\n      "id": "epo_anchored_trend"'
    assert marker in data, 'EPO card must be appended after the pre-existing cards'
    prefix = data[:data.index(marker)]
    assert len(prefix) == ARCHIVE_PREFIX_LEN
    assert hashlib.sha256(prefix).hexdigest() == ARCHIVE_PREFIX_SHA256
    assert data.endswith(b'\n  ]\n}\n')
    assert [c['id'] for c in json.loads(data)['cards']] == PRE_EXISTING_IDS + ['epo_anchored_trend']


def test_archive_tab_has_epo_card():
    """Fails if the EPO card is missing from the file the in-app Archive tab reads."""
    cards = {c['id']: c for c in json.loads(ARCHIVE.read_text(encoding='utf-8'))['cards']}
    card = cards.get('epo_anchored_trend')
    assert card is not None, 'EPO card missing from archive_verdicts.json'
    assert card['badge'] == 'FAIL' and 'FAIL / ARCHIVE' in card['verdict'] and 'book-eligible: no' in card['verdict']
    assert 'trial_count=11' in card['detail'] and 'Sharpe ex-BIL 0.27 vs 0.61' in card['verdict']
    assert {'label': 'Results page', 'href': 'methods/allocation_alpha_epo_results.html'} in card['nw_t_links']
    tsx = (ROOT / 'apps' / 'pages' / 'src' / 'pages' / 'Archive.tsx').read_text(encoding='utf-8')
    assert 'archiveData.cards.map' in tsx and 'None of the {failWord} archived methods' in tsx
