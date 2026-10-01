#!/usr/bin/env python3
"""EPO gate results page (stdlib only).

Every figure on the page is read from the committed gate output in data/processed/epo_allocator/
(gate_result.json written by the enforced gate-results writer, plus its CSV tables). Nothing is
hard-coded here except the pre-registered rule text. If the gate has not been run, no page is built.
"""
from __future__ import annotations

import csv
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPO_DIR = ROOT / 'data' / 'processed' / 'epo_allocator'
PAGE = 'methods/allocation_alpha_epo_results.html'
TEACHING = 'allocation_alpha_epo.html'

METHOD, PRIMARY, ANCHOR, TREND, EW, ERC, BOOK1 = (
    'epo_a_w075', 'lw_minvar_156w', 'anchor_ivol', 'trend_ivol', 'equal_weight', 'erc_lw', 'book1_static_option_a')
SENSITIVITIES = ('epo_a_w050', 'epo_a_w090')
NAMES = {
    METHOD: 'Anchored EPO, w = 0.75 (method)',
    'epo_a_w050': 'Anchored EPO, w = 0.50 (sensitivity)',
    'epo_a_w090': 'Anchored EPO, w = 0.90 (sensitivity)',
    PRIMARY: 'Weekly Ledoit-Wolf MinVar (primary null)',
    ANCHOR: '1/σ anchor (EPO at w = 1)',
    TREND: 'Trend names at inverse vol',
    EW: 'Equal weight',
    ERC: 'Equal risk contribution (LW)',
    BOOK1: 'Book 1, rebuilt net of costs (reference)',
}
SHORT = {PRIMARY: 'LW MinVar (null)', ANCHOR: '1/σ anchor', BOOK1: 'Book 1 (net)'}
ORDER = [METHOD, *SENSITIVITIES, PRIMARY, ANCHOR, TREND, EW, ERC, BOOK1]
Z95, Z80 = 1.6449, 0.8416   # one-sided 5% test, 80% power (normal approximation)


def load_verdict() -> dict:
    """Quant's verdict record beside the committed run (written after review; the run artifacts are unchanged)."""
    path = EPO_DIR / 'verdict.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def available() -> bool:
    return (EPO_DIR / 'gate_result.json').exists()


def load_gate() -> dict:
    return json.loads((EPO_DIR / 'gate_result.json').read_text(encoding='utf-8'))


def _rows(name: str) -> list[dict]:
    with (EPO_DIR / name).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _f(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if v != v else v


def pct(x, d=1) -> str:
    v = _f(x)
    return '—' if v is None else f'{100 * v:.{d}f}%'.replace('-', '−')


def num(x, d=2) -> str:
    v = _f(x)
    return '—' if v is None else f'{v:.{d}f}'.replace('-', '−')


def pval(x) -> str:
    v = _f(x)
    return '—' if v is None else f'{v:.3f}'


def month(s: str) -> str:
    return s[:7] if s else '—'


def yes(ok: bool) -> str:
    return 'Yes' if ok else 'No'


def name(sid: str) -> str:
    return NAMES.get(sid, sid)


def table(headers, rows, caption) -> str:
    return (
        f'<div class="table-scroll" tabindex="0" role="region" aria-label="{escape(caption)}">'
        f'<table><caption>{escape(caption)}</caption><thead><tr>'
        + ''.join(f'<th scope="col">{escape(str(h))}</th>' for h in headers)
        + '</tr></thead><tbody>'
        + ''.join('<tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in row) + '</tr>' for row in rows)
        + '</tbody></table></div>'
    )


def gather() -> dict:
    gate = load_gate()
    summary = _rows('summary.csv')
    full = {r['strategy_id']: r for r in summary if r['period_role'] == 'full window'}
    sub = {r['strategy_id']: r for r in summary if r['period_role'] != 'full window'}
    sub_role = next((r['period_role'] for r in summary if r['period_role'] != 'full window'), '')
    tests = _rows('tests.csv')
    test = {(r['period_role'], r['strategy_id'], r['primary_null']): r for r in tests}
    mix = {r['strategy_id']: r for r in _rows('asset_class_mix.csv')}
    book1 = {r['strategy_id']: r for r in _rows('book1_window_summary.csv')}
    stress = _rows('cost_stress.csv')
    return dict(gate=gate, verdict=load_verdict(), full=full, sub=sub, sub_role=sub_role, test=test, mix=mix, book1=book1, stress=stress)


def label(d: dict | None = None) -> str:
    return (d or {}).get('gate', {}).get('label') if d else load_gate()['label']


def criteria_rows(d: dict) -> list[list[str]]:
    g, full, test = d['gate'], d['full'], d['test']
    crit = g['report']['criteria']
    comp = g['composition']
    m, p = full[METHOD], full[PRIMARY]
    t = test.get(('full window', METHOD, PRIMARY), {})
    n_trials = g['fields']['trial_count']
    rows = [
        ['C1', 'Sharpe ex-BIL above the primary null, with the one-sided Ledoit-Wolf (2008) p ≤ 0.05 on both the HAC test and the block bootstrap',
         f"{num(m['Sharpe_exBIL'])} vs {num(p['Sharpe_exBIL'])}; p = {pval(t.get('p_one_sided_hac'))} (HAC), {pval(t.get('p_one_sided_boot'))} (bootstrap)",
         'Pass' if crit['c1'] else 'Fail'],
        ['C2', 'Sharpe ex-BIL at least the 1/σ anchor’s',
         f"{num(m['Sharpe_exBIL'])} vs {num(full[ANCHOR]['Sharpe_exBIL'])}", 'Pass' if crit['c2'] else 'Fail'],
        ['C3', 'Sharpe ex-BIL at least equal weight’s and trend-at-inverse-vol’s',
         f"{num(m['Sharpe_exBIL'])} vs {num(full[EW]['Sharpe_exBIL'])} (equal weight) and {num(full[TREND]['Sharpe_exBIL'])} (trend)",
         'Pass' if crit['c3'] else 'Fail'],
        ['C4', f'Deflated Sharpe ratio ≥ 0.95 at {n_trials} trials',
         f"DSR {num(m['DSR_exBIL'], 3)}", 'Pass' if crit['c4'] else 'Fail'],
        ['C5', 'Both sensitivities (w = 0.50 and w = 0.90) have a higher Sharpe ex-BIL than the primary null',
         '; '.join(f"{name(s).split(' (')[0].replace('Anchored EPO, ', '')}: {num(full[s]['Sharpe_exBIL'])}" for s in SENSITIVITIES)
         + f" vs {num(p['Sharpe_exBIL'])}", 'Pass' if crit['c5'] else 'Fail'],
        ['C6', f"Tripwires: cash-like, short-duration and near-cash share ≤ {pct(comp['max_share'], 0)} for the method and the null; method effective N ≥ 5",
         f"share {pct(comp['method_share'], 2)} (method), {pct(comp['null_share'], 2)} (null); effective N {num(g['report']['effN_method'])}",
         'Pass' if crit['c6'] else 'Fail (VOID)'],
    ]
    return rows


def _sharpe(full, sid):
    return _f(full[sid]['Sharpe_exBIL']) if sid in full else None


def verdict_text(d: dict) -> str:
    g, full, mix = d['gate'], d['full'], d['mix']
    lab = g['label']
    crit = g['report']['criteria']
    be = g['fields']['book_eligible']
    ms, sa = _sharpe(full, METHOD), _sharpe(full, ANCHOR)
    parts = [f'{lab}.']
    trailed_anchor = ms is not None and sa is not None and ms < sa
    if trailed_anchor:
        parts.append(f"EPO trailed the 1/σ anchor it is built on ({num(ms)} vs {num(sa)}). Any weight on correlations pulled it "
                     f"to about {pct(mix[METHOD]['bond'], 0)} bonds, and the trend signal didn't make up for it "
                     f"(plain trend: {num(_sharpe(full, TREND))}).")
    elif lab == 'PASS':
        parts.append('Anchored EPO passed every pre-registered gate criterion.')
    elif lab == 'VOID':
        parts.append('The run is VOID: a pre-registered tripwire fired, so the comparison does not count.')
    elif lab == 'INCOMPLETE':
        parts.append('The run is INCOMPLETE: the composition check could not be computed.')
    else:
        parts.append('Anchored EPO did not pass its pre-registered gate.')
    others = [(EW, 'equal weight')]
    if not trailed_anchor:
        others = [(ANCHOR, 'the 1/σ anchor'), (EW, 'equal weight'), (TREND, 'the trend-at-inverse-vol portfolio')]
    trailed = [f"{desc} ({num(_sharpe(full, sid))})" for sid, desc in others
               if ms is not None and _sharpe(full, sid) is not None and _sharpe(full, sid) > ms]
    if trailed:
        joined = trailed[0] if len(trailed) == 1 else ', '.join(trailed[:-1]) + ' and ' + trailed[-1]
        parts.append(f"On Sharpe ex-BIL it also trailed {joined}.")
    if not crit['c4']:
        parts.append(f"Its deflated Sharpe ratio ({num(full[METHOD]['DSR_exBIL'], 3)}) is below the 0.95 bar once all "
                     f"{g['fields']['trial_count']} trials are counted.")
    if not crit['c5']:
        parts.append('At least one sensitivity did not beat the primary null.')
    parts.append(f"Its average equity share was {pct(be['method_equity_share'])}.")
    parts.append('Not book-eligible.' if not be['eligible'] else 'Book-eligible on the pre-registered conditions; mapping it to a book is the CIO’s call.')
    parts.append('No book changes.' if d.get('verdict') else 'This is the mechanical reading, pending Quant and CIO review. No book changes.')
    null_desc = (f"weekly Ledoit-Wolf minimum variance ({num(_sharpe(full, PRIMARY))} Sharpe ex-BIL, "
                 f"about {pct(mix[PRIMARY]['bond'], 0)} bonds)")
    if crit['c1']:
        parts.append(f"It did beat its primary null, {null_desc}, by a statistically significant margin, but that is a low bar.")
    else:
        parts.append(f"It did not beat its primary null, {null_desc}, by a statistically significant margin.")
    return ' '.join(parts)


def drawdown_note(d: dict) -> str:
    """CIO note under the eligibility table: why the MaxDD leg passes."""
    be = d['gate']['fields']['book_eligible']
    book1 = d['book1']   # the Book 1 comparison window (overlapping months), same window as the MaxDD row
    if not be['beats_on_maxdd'] or METHOD not in book1 or BOOK1 not in book1:
        return ''
    return (f"The shallower drawdown comes from holding mostly bonds ({pct(book1[METHOD]['CAGR'])} CAGR vs Book 1's "
            f"{pct(book1[BOOK1]['CAGR'])}), not from better equity risk control.")


def lessons_text(d: dict) -> str:
    full, mix = d['full'], d['mix']
    return (f"Starting from a 1/σ anchor with about {pct(mix[ANCHOR]['equity'], 0)} equity, the mean-variance step moved weight "
            f"into low-vol bonds, the same pull that undid the GMV runs. Plain equal weight ({num(full[EW]['Sharpe_exBIL'])}) "
            "did better than every allocator tested here. It is an in-sample reference only, not a candidate.")


def power_rows(d: dict) -> list[list[str]]:
    rows = []
    bc = d['gate']['fields']['book1_comparison']
    for base, window in ((PRIMARY, bc['full_oos_months']), (ANCHOR, bc['full_oos_months']), (BOOK1, bc['overlap_months'])):
        t = d['test'].get(('full window', METHOD, base))
        if not t:
            continue
        se = _f(t['se_nat'])
        se_ann = None if se is None else se * 12 ** 0.5
        mde = None if se_ann is None else (Z95 + Z80) * se_ann
        rows.append([f'{SHORT[base]}, {window} mo', num(se_ann), num(mde)])
    return rows


REPO_BLOB = 'https://github.com/jgridifier/usa-etf-feature-pipeline/blob/main/data/processed/epo_allocator/'


def archive_card() -> dict | None:
    """Archived-gate card (same schema as archive_verdicts.json cards), built from the run output and the
    Quant verdict record. None until Quant has given a verdict."""
    if not available():
        return None
    d = gather()
    v = d['verdict']
    if not v:
        return None
    g, full, test = d['gate'], d['full'], d['test']
    bc = g['fields']['book1_comparison']
    trials = g['fields']['trial_count']
    if v.get('final_trial_count') != trials or v.get('verdict') != g['label']:
        raise ValueError('EPO verdict record disagrees with the gate output')
    be = g['fields']['book_eligible']
    ms, sa = _sharpe(full, METHOD), _sharpe(full, ANCHOR)

    def row(sid, role, label_):
        r = full[sid]
        return dict(role=role, label=label_, sharpe=f"{num(r['Sharpe_exBIL'])} (legacy {num(r['Sharpe_rf0_legacy'])})",
                    maxdd=pct(r['MaxDD']))
    tp, ta = test.get(('full window', METHOD, PRIMARY), {}), test.get(('full window', METHOD, ANCHOR), {})
    return dict(
        id='epo_anchored_trend',
        name='Bet 1 anchored EPO (12-1 trend signal)',
        detail=(f"Pedersen, Babu & Levine 2021 anchored EPO · w = 0.75 primary, 0.50 / 0.90 sensitivities · "
                f"{bc['full_oos_months']}m OOS ({month(bc['full_start'])} → {month(bc['full_end'])}) · 5 bps · "
                f"trial_count={trials} (final)"),
        badge=v['verdict'],
        verdict=(f"{v['verdict_line']}. Sharpe ex-BIL {num(ms)} vs {num(sa)} for the 1/σ anchor it is built on; "
                 f"book-eligible: {'yes' if be['eligible'] else 'no'}."),
        null='Weekly LW MinVar on the same names (primary); the 1/σ anchor is the book-eligibility bar',
        rows=[row(METHOD, 'method', 'Anchored EPO, w = 0.75 (method)'), row(ANCHOR, 'reference', '1/σ anchor (EPO at w = 1)'),
              row(PRIMARY, 'null', 'Weekly LW MinVar (primary null)')],
        nw_t=(f"n/a · LW2008 HAC z {num(tp.get('z_hac'))} vs LW MinVar (p {pval(tp.get('p_one_sided_hac'))}), "
              f"{num(ta.get('z_hac'))} vs the 1/σ anchor"),
        dsr=f"{num(full[METHOD]['DSR_exBIL'], 3)} on Sharpe ex-BIL, not legacy (trial_count={trials})",
        gate=dict(label='gate_result.json', href=REPO_BLOB + 'gate_result.json'),
        method_page='methods/allocation_alpha_epo.html',
        artifact=dict(label='epo_allocator/summary.csv', href=REPO_BLOB + 'summary.csv'),
        archived=v['verdict_date'],
        archived_via=f"{v['verdict_by']} verdict; the results page is the published record",
        nw_t_links=[dict(label='Results page', href=PAGE)],
    )


def build_epo_results(page_shell, write_page) -> str | None:
    if not available():
        return None
    d = gather()
    g, full, sub, mix, book1 = d['gate'], d['full'], d['sub'], d['mix'], d['book1']
    lab = g['label']
    be = g['fields']['book_eligible']
    bc = g['fields']['book1_comparison']
    comp = g['composition']
    pub = g['fields'].get('book1_published_reference', {})
    badge = 'badge' if lab == 'PASS' else 'badge badge-fail'
    window = f"{month(bc['full_start'])} to {month(bc['full_end'])}"
    overlap = f"{month(bc['overlap_start'])} to {month(bc['overlap_end'])}"
    present = [s for s in ORDER if s in full]

    metrics = table(
        ['Strategy', 'Months', 'Sharpe ex-BIL', 'Sharpe (legacy rf = 0)', 'CAGR', 'Vol', 'MaxDD', 'Turnover / yr',
         'Effective N', 'DSR'],
        [[name(s), full[s]['n_months'], num(full[s]['Sharpe_exBIL']), num(full[s]['Sharpe_rf0_legacy']),
          pct(full[s]['CAGR']), pct(full[s]['AnnVol']), pct(full[s]['MaxDD']), num(full[s]['turnover_per_year']),
          num(full[s]['eff_N_mean'], 1), num(full[s]['DSR_exBIL'], 3)] for s in present],
        f'Full out-of-sample window, {window}, net of 5 bp')
    tests_tbl = table(
        ['Method vs', 'p one-sided (HAC)', 'p one-sided (bootstrap)', 'z (HAC)'],
        [[name(base), pval(t['p_one_sided_hac']), pval(t['p_one_sided_boot']), num(t['z_hac'])]
         for base in (PRIMARY, ANCHOR, TREND, EW, BOOK1)
         if (t := d['test'].get(('full window', METHOD, base)))],
        'Ledoit-Wolf (2008) Sharpe-difference tests, method (w = 0.75), full window')

    m, a = full[METHOD], full[ANCHOR]
    anchor_tbl = table(
        ['', 'Sharpe ex-BIL', 'CAGR', 'Vol', 'MaxDD'],
        [[name(s), num(full[s]['Sharpe_exBIL']), pct(full[s]['CAGR']), pct(full[s]['AnnVol']), pct(full[s]['MaxDD'])]
         for s in (METHOD, ANCHOR)],
        f"Anchor comparison: {bc['full_oos_months']} months, {window}")
    bm, bb = book1.get(METHOD, {}), book1.get(BOOK1, {})
    book1_tbl = table(
        ['', 'Sharpe ex-BIL', 'CAGR', 'Vol', 'MaxDD'],
        [[name(s), num(r.get('Sharpe_exBIL')), pct(r.get('CAGR')), pct(r.get('AnnVol')), pct(r.get('MaxDD'))]
         for s, r in ((METHOD, bm), (BOOK1, bb))],
        f"Book 1 comparison, net vs net: {bc['overlap_months']} overlapping months, {overlap}")
    pub_line = (
        f"<p class=\"muted\">Reference only, not used for eligibility: the published gross Book 1 series over its "
        f"{pub['n_months']} months in this window ({month(pub['start'])} to {month(pub['end'])}) had Sharpe ex-BIL "
        f"{num(pub['Sharpe_exBIL'])}, CAGR {pct(pub['CAGR'])} and MaxDD {pct(pub['MaxDD'])}.</p>"
        if pub.get('available') else '')

    mix_tbl = table(
        ['Strategy', 'Equity', 'Bond', 'Commodity'],
        [[name(s), pct(mix[s]['equity']), pct(mix[s]['bond']), pct(mix[s]['commodity'])] for s in ORDER if s in mix],
        'Average out-of-sample weight by asset class')
    comp_tbl = table(
        ['Check', 'Method', 'Null', 'Result'],
        [[f"Cash-like + short-duration + near-cash (tripwire, limit ≤ {pct(comp['max_share'], 0)})",
          pct(comp['method_share'], 2), pct(comp['null_share'], 2), comp['status'].title()],
         ['Equity share (method needs ≥ 50%)', pct(mix[METHOD]['equity']), pct(mix[PRIMARY]['equity']),
          'Meets' if be['growth_mandate_fit'] else 'Below']],
        'Composition')

    elig_tbl = table(
        ['Condition', 'Value', 'Met?'],
        [['Gate label is PASS', lab, yes(lab == 'PASS')],
         ['Sharpe ex-BIL above the 1/σ anchor (full window)', f"{num(be['sharpe_exbil_method'])} vs {num(be['sharpe_exbil_anchor'])}",
          yes(be['beats_anchor'])],
         ['Beats Book 1 on Sharpe ex-BIL (overlap, net)', f"{num(be['book1_window_sharpe_method'])} vs {num(be['book1_window_sharpe_book1'])}",
          yes(be['beats_on_sharpe'])],
         ['…or on MaxDD (shallower; overlap, net)', f"{pct(be['maxdd_method'])} vs {pct(be['maxdd_book1'])}", yes(be['beats_on_maxdd'])],
         ['Average equity share ≥ 50%', pct(be['method_equity_share']), yes(be['growth_mandate_fit'])],
         ['Book-eligible', '', yes(be['eligible'])]],
        'Book eligibility (all of: PASS, beats the anchor, beats Book 1 on Sharpe ex-BIL or MaxDD, equity ≥ 50%)')

    sub_present = [s for s in ORDER if s in sub]
    sub_tbl = table(
        ['Strategy', 'Months', 'Sharpe ex-BIL', 'MaxDD'],
        [[name(s), sub[s]['n_months'], num(sub[s]['Sharpe_exBIL']), pct(sub[s]['MaxDD'])] for s in sub_present],
        f"Sub-period from {month(sub[sub_present[0]]['start'])} (reported, not a trial)") if sub_present else ''
    stress_by = {}
    for r in d['stress']:
        stress_by.setdefault(r['strategy_id'], {})[r['cost_bps']] = r['Sharpe_exBIL']
    bps = sorted({r['cost_bps'] for r in d['stress']}, key=float)
    stress_tbl = table(
        ['Strategy', 'Sharpe ex-BIL at 5 bp'] + [f'at {b} bp' for b in bps],
        [[name(s), num(full[s]['Sharpe_exBIL'])] + [num(stress_by.get(s, {}).get(b)) for b in bps] for s in present],
        'Cost stress (diagnostic)') if bps else ''

    power = power_rows(d)
    power_tbl = table(
        ['Method vs', 'SE of gap', 'Detectable gap'],
        power, 'Annualized Sharpe gap: standard error and smallest gap detected with 80% power (derived from the test standard errors)')

    content = (
        '<section class="band"><div class="band-inner">'
        + (f'<p class="verdict-line"><span class="{badge}">{escape(d["verdict"]["verdict_label"])}</span> '
           f'<strong>{escape(d["verdict"]["verdict_line"])}</strong></p>' if d['verdict'] else
           f'<p><span class="{badge}">{escape(lab)} · pending Quant review</span> '
           f'<span class="badge">Book-eligible: {escape(yes(be["eligible"]).lower())}</span></p>')
        + '<h1>EPO gate results: anchored EPO with a 12-1 trend signal</h1>'
        f'<p class="muted">Single pre-registered run · {bc["full_oos_months"]} out-of-sample months ({escape(window)}) · '
        f'net of 5 bp · {g["fields"]["trial_count"]} trials counted · complete months through {escape(month(g["monthly_panel"]["source_asof"]))}</p>'
        f'<div class="callout"><strong>Verdict.</strong> {escape(verdict_text(d))}</div>'
        f'<p><a href="{TEACHING}">How the method works (teaching page)</a> · '
        '<a href="justina_round1_scoreboard.html">Archive scoreboard</a> · <a href="index.html">Methods</a></p>'
        '<h2>Pre-registered gate criteria</h2>'
        + table(['', 'Rule', 'Result', 'Outcome'], criteria_rows(d), 'Gate criteria, method (w = 0.75), full window')
        + '<h2>Every pre-registered metric</h2>' + metrics
        + '<p class="muted">Sharpe ex-BIL is in excess of BIL (TB3MS before BIL’s first full month). The legacy rf = 0 Sharpe is '
          'shown for continuity only. Turnover is measured against drifted weights and drives the 5 bp cost. Book 1 exists only '
          'on the overlapping months, so its row covers that shorter window.</p>'
        + tests_tbl
        + '<h2>Comparison with the 1/σ anchor</h2>'
        '<p>Anchored EPO starts from inverse-volatility weights and tilts toward the trend signal. At w = 1 it is the anchor itself, '
        'so this comparison asks whether the tilt added anything.</p>' + anchor_tbl
        + '<h2>Comparison with Book 1</h2>'
        '<p>Book 1 is rebuilt from the panel, net of the same cost model, and compared only on the months where all of its funds trade. '
        'The method is restricted to exactly those months.</p>' + book1_tbl + pub_line
        + '<h2>Composition</h2>' + comp_tbl + mix_tbl
        + '<h2>Book eligibility</h2>' + elig_tbl
        + (f'<p class="drawdown-note"><strong>Note on the MaxDD row:</strong> {escape(note)}</p>' if (note := drawdown_note(d)) else '')
        + '<p class="muted">Book eligibility is separate from the gate label. Mapping any PASS to a book is the CIO’s decision; there is no third book.</p>'
        + f'<h2 id="lessons">What we learned</h2><p>{escape(lessons_text(d))}</p>'
        + '<h2>Power caveat</h2>'
        f'<p>With {bc["full_oos_months"]} months of data ({bc["overlap_months"]} against Book 1), a Sharpe-difference test can only detect large gaps. The table shows, for each comparison, '
        'the smallest Sharpe gap the test would detect four times in five at the one-sided 5% level. A failed significance test with a positive '
        'point estimate means “not shown”, not “shown not to work”. A point-estimate shortfall against the anchor is a different matter.</p>'
        + power_tbl
        + '<h2>Diagnostics (do not change the label)</h2>' + sub_tbl + stress_tbl
        + '<p class="muted">Source: the committed gate output (gate_result.json and its tables in data/processed/epo_allocator/), '
          'written once by the enforced gate-results writer. No reruns, retuning or re-selection.</p>'
        '</div></section>'
    )
    write_page(PAGE, page_shell('EPO gate results', content, prefix='../', active='methods/index.html', include_charts=False))
    return lab
