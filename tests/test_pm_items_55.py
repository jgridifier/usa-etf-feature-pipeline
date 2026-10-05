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


def test_superseded_banner_on_both_book2_notes_md_untouched():
    for slug in ('book2_reframe', 'book2_lw2008_drawdowns'):
        raw = read(f'notes/{slug}.html')
        assert raw.count(BANNER) == 1
        assert raw.index(BANNER) < raw.index('<h1') if '<h1' in raw else True
        assert BANNER not in read(f'notes/{slug}.md')


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
