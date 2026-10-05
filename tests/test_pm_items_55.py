"""PM items on #55 (2026-10-04): lab notes, banners, captions, tap targets, phone layout.

Every check reads the built docs/ pages; nothing here edits a pinned source."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
A6_NOTE = ('Lab note: −0.71 pp (−0.705 at 5 bp, −0.712 at 10 bp) from A_dev_results.json supersedes −0.73, '
           'a transcription error (Quant).')
BANNER = 'Superseded: Book 2 Sharpe ex-BIL is 0.99 after the September full-month fix.'


def read(rel):
    return (DOCS / rel).read_text(encoding='utf-8')


def test_a6_lab_note_renders_after_the_073_line_without_editing_pins():
    import sys
    sys.path.insert(0, str(ROOT / 'scripts'))
    import build_stage2_pages as s2
    assert hashlib.sha256(s2.ADDENDUM3_SRC.read_bytes()).hexdigest() == s2.ADDENDUM3_SHA256
    assert hashlib.sha256(s2.RECHECK_SRC.read_bytes()).hexdigest() == s2.RECHECK_SHA256
    for rel, marker in (('methods/stage2_addendum3.html', "A6's gap is −0.73 pp against the live core."),
                        ('methods/stage2_livecore_recheck.html', 'its gap is −0.73 pp')):
        raw = read(rel)
        note = raw.index(A6_NOTE.replace("'", '&#x27;'))
        line = raw.index(marker)
        assert line < note and raw.count(A6_NOTE) == 1
        # The note is the very next list item after the one carrying −0.73.
        assert raw.find('<li', line) == raw.rfind('<li', 0, note)
        assert 'class="lab-link a6-note"' in raw


def test_a6_forward_tracked_entry_shows_071_pp():
    raw = read('methods/results/index.html')
    section = re.search(r'<section id="forward-tracked">.*?</section>', raw, re.S)[0]
    row = re.search(r'<tr><td>A6:.*?</tr>', section, re.S)[0]
    assert '−0.71 pp' in row and '−0.73' not in row
    assert 'supersedes the −0.73' in section


def test_demiguel_book_rule_caption_names_the_standin_weights():
    raw = read('methods/results/index.html')
    cap = re.search(r'<p class="muted book-rule-caption">([^<]*)</p>', raw)[1]
    assert 'stand-in core only (70% IVV / 20% QQQ / 10% IJR)' in cap


def test_one_correction_per_figure_and_book2_reframe_lab_note_shows_hub_sharpe():
    """PM + CIO, 2026-10-04: the 2026-10-04 lab note is the only correction on book2_reframe (the earlier
    'Superseded: Book 2 Sharpe ex-BIL is 0.99' callout was removed there; book2_lw2008_drawdowns keeps it).
    (1) The lab note shows Book 2's Sharpe from book2.json. (2) No published page carries two correction callouts or
    banners for the same figure."""
    import html as _h
    b2 = json.loads((ROOT / 'data/processed/hub/subjects/book2.json').read_text(encoding='utf-8'))
    sharpe = f"{b2['books_window']['sharpe_exbil']:.2f}"
    assert sharpe == '0.99'
    raw = read('notes/book2_reframe.html')
    lab = [_h.unescape(t) for t in re.findall(r'<p class="callout note-banner" role="note">(.*?)</p>', raw, re.S)]
    assert len(lab) == 1 and lab[0].startswith('Lab note, 2026-10-04:'), lab
    assert f"Book 2's Sharpe above BIL is {sharpe}" in lab[0], lab[0]
    assert BANNER not in raw
    if '<h1' in raw:
        assert raw.index('Lab note, 2026-10-04:') < raw.index('<h1')
    assert BANNER in read('notes/book2_lw2008_drawdowns.html')
    for slug in ('book2_reframe', 'book2_lw2008_drawdowns'):
        assert BANNER not in read(f'notes/{slug}.md') and 'Lab note' not in read(f'notes/{slug}.md')
    figures = {   # figure label -> pattern in a correction's text
        'Book 2 Sharpe': r"Book 2(?:'s)? Sharpe",
        'Backbone CAGR': r'\b[Bb]ackbone\b[^.;]{0,40}\bCAGR\b',
        'Book 2 vs backbone return gap': r'points a year',
        'Book 2 / backbone drawdown': r'drawdowns? (?:are|is) still',
    }
    corr = re.compile(r'<(p|div|aside|section)\b[^>]*class="[^"]*\b(?:note-banner|lab-note|correction|banner)\b[^"]*"[^>]*>(.*?)</\1>', re.S)
    seen = {}
    for page in sorted(DOCS.rglob('*.html')):
        if '/assets/' in str(page):
            continue
        texts = [_h.unescape(re.sub(r'<[^>]+>', ' ', m.group(2))) for m in corr.finditer(page.read_text(encoding='utf-8'))]
        for label, rx in figures.items():
            n = sum(bool(re.search(rx, t)) for t in texts)
            assert n <= 1, (page.relative_to(DOCS).as_posix(), label, n, texts)
            if n:
                seen.setdefault(page.relative_to(DOCS).as_posix(), []).append(label)
    assert 'Backbone CAGR' in seen['notes/stage2_wrap.html'], seen
    assert {'Book 2 Sharpe', 'Backbone CAGR', 'Book 2 vs backbone return gap', 'Book 2 / backbone drawdown'} <= set(seen['notes/book2_reframe.html']), seen
    # the check bites: a second Book 2 Sharpe callout on book2_reframe fails it
    doubled = raw.replace('</h1>', '</h1><p class="callout note-banner" role="note">' + BANNER + '</p>', 1) if '</h1>' in raw else raw + '<p class="callout note-banner">' + BANNER + '</p>'
    texts = [_h.unescape(re.sub(r'<[^>]+>', ' ', m.group(2))) for m in corr.finditer(doubled)]
    assert sum(bool(re.search(figures['Book 2 Sharpe'], t)) for t in texts) == 2


def test_comparison_labelled_to_2026_08_until_m3_p2_rerun():
    viz = json.loads(read('data/viz_comparison.json'))
    ends = {r['end_date'][:7] for r in viz['rows']}
    end = max(ends)
    assert f'to {end}' in viz['window']
    if end < '2026-09':
        assert 'to 2026-08' in viz['window'] and 'm3_p2_core_rotate' in viz['window']
    assert 'payload.window' in read('assets/app.js')
    spa = re.search(r'assets/v2-index-[\w-]+\.js', read('index.html'))[0]
    assert 'data.window' in (ROOT / 'apps/pages/src/components/ComparisonTable.tsx').read_text(encoding='utf-8')
    assert '.window' in read(spa)


def test_header_menu_button_is_a_44px_tap_target():
    css = read('assets/style.css')
    rule = re.search(r'\.nav-toggle \{[^}]*\}', css)[0]
    assert 'min-width: 44px' in rule and 'min-height: 44px' in rule


def test_explorer_stats_table_and_charts_fit_375():
    raw = read('explorer/index.html')
    assert '.explorer-grid, .explorer-grid .chart-card, .chart-wrap { min-width: 0; max-width: 100%; }' in raw
    assert '#stats th' in raw and 'white-space: normal' in raw
    assert 'ResizeObserver' in read('explorer/explorer.js')


def test_leaderboard_phone_layout_and_duplicate():
    raw = read('methods/results/index.html')
    assert 'id="lb-cols"' in raw and 'position:sticky;left:0' in raw
    assert '<td>= 2</td>' in raw  # #6 overlay is the same series as Book 2: ranked once
    for page in ('schur', 'ft_med', 'book2'):
        sub = read(f'methods/results/{page}.html')
        assert sub.count('← Results hub') == 2
        assert re.search(r'<th scope="col">Metric</th><th scope="col">Difference vs core</th>', sub)


def test_scatter_tooltip_names_point_with_text_content():
    js = read('assets/hub-charts.js')
    block = js[js.index('if (hints.pointTooltip)'):]
    block = block[:block.index('chart = globalThis.echarts.init')]
    assert 'textContent = point.name' in block and 'innerHTML' not in block


def test_book2_own_nulls_table_labels_the_67_month_window():
    """PM/CIO: Book 2's EW / MinVar / ERC null rows (NW t 1.99 etc.) cover 67 months to 2026-08; the caption under
    the own-null table says so, and the numbers it labels come from the hub JSON."""
    import html as _h
    import json as _j
    import re as _re
    root = Path(__file__).resolve().parents[1]
    s = (root / 'docs' / 'methods' / 'results' / 'book2.html').read_text(encoding='utf-8')
    i = s.index('aria-label="Own null comparisons')
    j = s.index('</table>', i)
    tbl = _h.unescape(_re.sub(r'<[^>]+>', ' ', s[i:j]))
    cap = _re.match(r'\s*</div>\s*<p class="caption null-windows">(.*?)</p>', s[j + len('</table>'):], _re.S)
    assert cap, 'no window caption directly under the own-null table'
    text = _h.unescape(cap.group(1))
    assert 'Equal weight, LW MinVar, ERC: 2021-02 to 2026-08, 67 months (to 2026-08' in text, text
    assert 'Backbone: 2021-02 to 2026-09, 68 months' in text, text
    d = _j.loads((root / 'data' / 'processed' / 'hub' / 'subjects' / 'book2.json').read_text(encoding='utf-8'))
    for r in d['vs_nulls']:
        if r['key'] in ('ew', 'minvar', 'erc'):
            assert (r['n'], r['end']) == (67, '2026-08'), r['key']
            assert f"{r['return_test']['nw_t']:.2f}" in tbl, r['key']
    assert '1.99' in tbl
