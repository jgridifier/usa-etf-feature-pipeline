#!/usr/bin/env python3
"""Schur allocator gate results page (stdlib only).

Every figure on the page is read from the committed gate output in data/processed/schur_allocator/
(gate_result.json and its CSV tables) or from book_power.json (presentation-only power note derived
from the committed returns by scripts/schur_book_power.py). Nothing is hard-coded except the
pre-registered rule text. If the gate has not been run, no page is built.

CIO copy (2026-10-02): the page opens with the gate verdict, which reads PENDING QUANT RECOMPUTE
until Quant rules; every Book comparison carries the power caveat (month count and detectable gap
from data); on FAIL the Book table is headed 'Reported only, not book-eligible'; nothing on VOID.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHUR_DIR = ROOT / 'data' / 'processed' / 'schur_allocator'
PAGE = 'methods/allocation_alpha_schur_results.html'
PENDING = 'PENDING QUANT RECOMPUTE'
REPORTED_ONLY = 'Reported only, not book-eligible'
REPO_BLOB = 'https://github.com/jgridifier/usa-etf-feature-pipeline/blob/main/data/processed/schur_allocator/'
GATE_PR = 'https://github.com/jgridifier/usa-etf-feature-pipeline/pull/48'

METHOD, PRIMARY, HRP, EW, BOOK1 = 'schur_g050', 'lw_minvar_156w', 'hrp_g000', 'equal_weight', 'book1_static_option_a'
ORDER = [METHOD, HRP, PRIMARY, EW, BOOK1]
ROLE = {METHOD: 'method', PRIMARY: 'primary null', HRP: 'null', EW: 'null', BOOK1: 'reference'}
# Book comparison series (gate_result.json fields.book_eligible.stats keys) and their table labels.
BOOK_ROWS = (('schur_g050', None), ('backbone', 'Backbone'), (BOOK1, 'Book 1'), ('book2', 'Book 2'))


def available() -> bool:
    return (SCHUR_DIR / 'gate_result.json').exists()


def load_gate() -> dict:
    return json.loads((SCHUR_DIR / 'gate_result.json').read_text(encoding='utf-8'))


def load_power() -> dict:
    path = SCHUR_DIR / 'book_power.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def label() -> str:
    return load_gate()['label']


def badge_line(lab: str) -> str:
    return f'{lab} · {PENDING}'


def _rows(name: str) -> list[dict]:
    with (SCHUR_DIR / name).open(newline='', encoding='utf-8') as f:
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


def yes(ok) -> str:
    return 'Yes' if ok else 'No'


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
    tests = {(r['strategy_id'], r['primary_null']): r for r in _rows('tests.csv')}
    return dict(gate=gate, full=full, tests=tests, power=load_power(),
                labels=gate['fields'].get('display_labels', {}),
                caps=_rows('cap_report.csv'), shares=_rows('low_vol_share.csv'),
                names=_rows('name_counts.csv'), qp=_rows('minvar_qp_log.csv'))


def name(d: dict, sid: str) -> str:
    return d['labels'].get(sid, sid)


def name_role(d: dict, sid: str) -> str:
    return f'{name(d, sid)} ({ROLE[sid]})' if sid in ROLE and ROLE[sid] != 'null' else name(d, sid)


def sharpe(d: dict, sid: str) -> float | None:
    return _f(d['full'][sid]['Sharpe_exBIL']) if sid in d['full'] else None


def primary_test(d: dict) -> dict:
    return d['tests'].get((METHOD, PRIMARY), {})


def criteria_rows(d: dict) -> list[list[str]]:
    g, full = d['gate'], d['full']
    crit = g['report']['criteria']
    m = full[METHOD]
    t = primary_test(d)
    out = lambda c: 'Pass' if crit[c] else 'Fail'  # noqa: E731
    return [
        ['C1', f'Sharpe ex-BIL above the primary null ({name(d, PRIMARY)}), with the one-sided Ledoit-Wolf (2008) '
               'p ≤ 0.05 on both the HAC test and the block bootstrap',
         f"{num(m['Sharpe_exBIL'])} vs {num(full[PRIMARY]['Sharpe_exBIL'])}; p = {pval(t.get('p_one_sided_hac'))} (HAC), "
         f"{pval(t.get('p_one_sided_boot'))} (bootstrap)", out('c1')],
        ['C2', f"Sharpe ex-BIL at least {name(d, HRP)}’s",
         f"{num(m['Sharpe_exBIL'])} vs {num(full[HRP]['Sharpe_exBIL'])}", out('c2')],
        ['C3', f"Sharpe ex-BIL at least {name(d, EW)}’s",
         f"{num(m['Sharpe_exBIL'])} vs {num(full[EW]['Sharpe_exBIL'])}", out('c3')],
        ['C4', f"Deflated Sharpe ratio ≥ 0.95 at {g['fields']['trial_count']} trials",
         f"DSR {num(m['DSR_exBIL'], 3)}", out('c4')],
    ]


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ', '.join(items[:-1]) + ' and ' + items[-1]


def verdict_text(d: dict) -> str:
    """Opening verdict paragraph: gate label, criteria and nulls only (no Book figures)."""
    g, full = d['gate'], d['full']
    lab = g['label']
    if lab == 'VOID':
        reasons = g['fields']['tripwires'].get('reasons') or []
        return (f"VOID, {PENDING}. A pre-registered tripwire fired ({'; '.join(reasons) or 'see the tripwires'}), "
                'so no criterion or Sharpe test counts and no Book comparison is computed. No book changes.')
    crit = g['report']['criteria']
    failing = g['report'].get('failing_criteria', [])
    t = primary_test(d)
    ms = sharpe(d, METHOD)
    parts = ["This is the mechanical reading; the label is not final until Quant’s recompute rules."]
    if failing:
        parts.append(f"The Schur allocator failed {len(failing)} of {len(crit)} pre-registered criteria "
                     f"({_join([c.upper() for c in failing])}).")
    else:
        parts.append('The Schur allocator met every pre-registered criterion.')
    above = 'above' if ms > sharpe(d, PRIMARY) else 'below'
    parts.append(f"Its Sharpe ex-BIL of {num(ms)} was {above} the primary null, {name(d, PRIMARY)} ({num(sharpe(d, PRIMARY))}), "
                 + ('by a statistically significant margin' if crit['c1'] else 'but not by a statistically significant margin')
                 + f" (one-sided p = {pval(t.get('p_one_sided_hac'))} HAC, {pval(t.get('p_one_sided_boot'))} bootstrap).")
    beat = [f"{name(d, s)} ({num(sharpe(d, s))})" for s in (HRP, EW) if ms >= sharpe(d, s)]
    trail = [f"{name(d, s)} ({num(sharpe(d, s))})" for s in (HRP, EW) if ms < sharpe(d, s)]
    if beat:
        parts.append(f"It matched or beat {_join(beat)}.")
    if trail:
        parts.append(f"It trailed {_join(trail)}.")
    if not crit['c4']:
        parts.append(f"Its deflated Sharpe ratio ({num(full[METHOD]['DSR_exBIL'], 3)}) is below the 0.95 bar once all "
                     f"{g['fields']['trial_count']} trials are counted.")
    trip = g['fields']['tripwires']
    parts.append(f"Tripwires: {trip['status'].lower()} (effective N mean {num(trip['effective_n']['mean'], 1)}, "
                 f"cash-like share {pct(g['composition']['method_share'], 0)}).")
    be = g['fields']['book_eligible']
    parts.append('Not book-eligible.' if not be.get('eligible') else
                 'Book-eligible on the pre-registered conditions; mapping it to a book is the CIO’s call.')
    parts.append('No book changes.')
    return ' '.join(parts)


def power_caveat(d: dict, key: str | None = None) -> str:
    """Power caveat for a Book comparison, figures from book_power.json (presentation only)."""
    p = d['power']
    if not p:
        return ''
    if key is None:
        lo, hi = p['detectable_gap_min'], p['detectable_gap_max']
        gap = num(lo, 1) if num(lo, 1) == num(hi, 1) else f'{num(lo, 1)}–{num(hi, 1)}'
        return (f"Power caveat: {p['n_months']} months ({p['window'].replace('..', ' to ')}) can only detect an annualized "
                f"Sharpe gap of roughly {gap} against the Books (one-sided {pct(p['alpha_one_sided'], 0)} test, "
                f"{pct(p['power'], 0)} power). A smaller gap in either direction is not evidence either way.")
    c = p['comparisons'][key]
    return (f"{c['n_months']} months can only detect a Sharpe gap of roughly {num(c['detectable_gap_annual'], 1)} "
            f"vs {c['label']}")


def book_section(d: dict) -> str:
    g = d['gate']
    lab = g['label']
    be = g['fields']['book_eligible']
    if lab == 'VOID' or 'stats' not in be:
        return ''
    st = be['stats']
    heading = REPORTED_ONLY if lab == 'FAIL' else 'Book eligibility'
    window = be['window'].replace('..', ' to ')
    rows = []
    for key, short in BOOK_ROWS:
        s = st[key]
        caveat = '' if key == METHOD else power_caveat(d, key)
        rows.append([short or name(d, key), num(s['Sharpe_exBIL']), pct(s['CAGR']), pct(s['MaxDD']), caveat or '—'])
    tbl = table(['', 'Sharpe ex-BIL', 'CAGR', 'MaxDD', 'Power caveat (80% power, one-sided 5%)'], rows,
                f"{heading}: {be['n_months']} common months, {window}, net vs net")
    m, bb, b1 = st[METHOD], st['backbone'], st[BOOK1]
    cond = table(
        ['Condition', 'Value', 'Met?', 'Power caveat'],
        [['Gate label is PASS', lab, yes(lab == 'PASS'), '—'],
         ['Sharpe ex-BIL above the Backbone', f"{num(m['Sharpe_exBIL'])} vs {num(bb['Sharpe_exBIL'])}",
          yes(be['beats_backbone_sharpe']), power_caveat(d, 'backbone') or '—'],
         ['MaxDD no worse than Book 1', f"{pct(m['MaxDD'])} vs {pct(b1['MaxDD'])}",
          yes(be['maxdd_no_worse_than_book1']), power_caveat(d, BOOK1) or '—'],
         ['Book-eligible', '', yes(be['eligible']), '—']],
        f"{heading}: conditions (Book 2 is reference only)")
    caveat = power_caveat(d)
    lead = (f"From {month(m['start'])}, {name(d, METHOD)} had a Sharpe ex-BIL of {num(m['Sharpe_exBIL'])} vs "
            f"{num(bb['Sharpe_exBIL'])} for the vol-target backbone, and a MaxDD of {pct(m['MaxDD'])} vs {pct(b1['MaxDD'])} for Book 1.")
    intro = ('The gate label is FAIL, so this comparison is computed and shown for the record only: '
             'book_eligible = no whatever the figures say.' if lab == 'FAIL' else
             'Book eligibility needs a PASS, a Sharpe ex-BIL above the vol-target backbone and a MaxDD no worse than Book 1.')
    return (f'<h2 id="books">{escape(heading)}</h2>'
            f'<p>{escape(intro)} {escape(lead)}</p>'
            + (f'<p class="callout"><strong>{escape(caveat)}</strong></p>' if caveat else '')
            + tbl + cond
            + '<p class="muted">Common window: months where the method, the vol-target backbone, Book 1 and Book 2 all have a '
              'net return, from 2021-02. Book 1 is the net rebuild; the backbone and Book 2 are the published live series. '
              'Detectable gaps come from the Ledoit-Wolf (2008) HAC standard error of each Sharpe difference '
              '(data/processed/schur_allocator/book_power.json, presentation only; it does not change the label).</p>')


def diagnostics(d: dict) -> str:
    g = d['gate']
    f = g['fields']
    trip = f['tripwires']
    comp = g['composition']
    lv = trip['low_vol']
    trip_tbl = table(
        ['Tripwire', 'Value', 'Limit', 'Result'],
        [['Effective N, method (mean / min)', f"{num(trip['effective_n']['mean'], 1)} / {num(trip['effective_n']['min'], 1)}",
          f"mean ≥ {num(trip['effective_n']['threshold'], 0)}", 'Pass' if trip['effective_n']['ok'] else 'Fail'],
         ['Months with effective N below the limit', pct(trip['effective_n']['share_below']), 'reported', '—'],
         [f"Cash-like + short-duration + near-cash, {name(d, METHOD)} / {name(d, PRIMARY)}",
          f"{pct(comp['method_share'], 2)} / {pct(comp['null_share'], 2)}", f"≤ {pct(comp['max_share'], 0)}", comp['status'].title()],
         ['Low-vol target share, max over months (method)', pct(lv['max_target_by_strategy'][METHOD]),
          f"≤ {pct(lv['limit'], 0)}", 'Pass' if lv['ok'] else 'Fail']],
        f"Tripwires (checked first): {trip['status'].title()}")
    by = defaultdict(lambda: dict(lv=0, nm=0, mech=''))
    for r in d['caps']:
        b = by[r['strategy_id']]
        b['lv'] += r['low_vol_cap_binding'] == 'True'
        b['nm'] += bool(r['name_cap_binding']) and r['name_cap_binding'] not in ('False', 'nan')
        b['mech'] = r['cap_mechanism']
    sh = defaultdict(lambda: [0.0, 0.0, 0])
    for r in d['shares']:
        s = sh[r['strategy_id']]
        s[0] += float(r['low_vol_share_target'])
        s[1] += float(r['dividend_income_share_target'])
        s[2] += 1
    drift = lv['max_drifted_month_end_by_strategy_diagnostic']
    sids = [s for s in (METHOD, HRP, PRIMARY, EW) if s in by]
    caps_tbl = table(
        ['Strategy', 'Cap mechanism', 'Low-vol cap binding (months)', 'Single-name cap binding (months)',
         'Avg low-vol share', 'Max low-vol share (drifted month-end, diagnostic)', 'Avg dividend / income share (reported only)'],
        [[name(d, s), by[s]['mech'], by[s]['lv'], by[s]['nm'], pct(sh[s][0] / sh[s][2], 2), pct(drift.get(s), 1),
          pct(sh[s][1] / sh[s][2], 2)] for s in sids],
        'Caps and shares (target weights unless marked drifted)')
    n_elig = [int(r['n_eligible']) for r in d['names']]
    skipped = sum(r['skipped'] == 'True' for r in d['names'])
    gaps = [float(r['kkt_gap']) for r in d['qp']]
    certified = sum(r['polished'] == 'True' and r['status'] == '0' for r in d['qp'])
    return (
        '<h2>Tripwires and diagnostics (do not change the label)</h2>' + trip_tbl + caps_tbl
        + '<ul>'
        f"<li>Eligible names per rebalance: {min(n_elig)} / {sum(n_elig) / len(n_elig):.2f} / {max(n_elig)} (min / mean / max); "
        f"skipped months: {skipped or 'none'}.</li>"
        f"<li>γ fallback share of Schur splits: {pct(f['fallback_share'], 2)}; HRP fallback share: {pct(f['hrp_fallback_share'], 2)}.</li>"
        f"<li>{escape(name(d, PRIMARY))}: {certified} of {len(gaps)} solves certified by the LP gap check; "
        f"max KKT gap {max(gaps):.1e}.</li>"
        '</ul>'
        f"<p class=\"muted\">{escape(f['weekly_cutoff_note'])}</p>"
    )


def archive_card() -> dict | None:
    """Archive card (archive_verdicts.json schema), built from the run output. Mechanical label, pending Quant."""
    if not available():
        return None
    d = gather()
    g, full = d['gate'], d['full']
    lab = g['label']
    t = primary_test(d)
    trials = g['fields']['trial_count']
    first, last = full[METHOD]['start'], full[METHOD]['end']

    def row(sid, role):
        r = full[sid]
        return dict(role=role, label=archive_label(d, sid),
                    sharpe=f"{num(r['Sharpe_exBIL'])} (legacy {num(r['Sharpe_rf0_legacy'])})", maxdd=pct(r['MaxDD']))
    return dict(
        id='schur_allocator',
        name='Bet 1 Schur complementary allocator',
        detail=(f"Schur complementary allocation, γ = 0.5·γ_max · capped nulls (LW MinVar QP primary, HRP = Schur at γ = 0, "
                f"equal weight) · {full[METHOD]['n_months']}m OOS ({month(first)} → {month(last)}) · 5 bps · trial_count={trials}"),
        badge=lab,
        verdict=(f"{lab} (mechanical), {PENDING}. Sharpe ex-BIL {num(sharpe(d, METHOD))} vs {num(sharpe(d, PRIMARY))} "
                 f"for the capped LW MinVar null (one-sided p {pval(t.get('p_one_sided_hac'))} HAC), "
                 f"{num(sharpe(d, EW))} for equal weight; book-eligible: {'yes' if g['fields']['book_eligible'].get('eligible') else 'no'}."),
        null=f"{name(d, PRIMARY)} on the same names (primary); {name(d, HRP)} and {name(d, EW)} also binding",
        rows=[row(METHOD, 'method'), row(PRIMARY, 'null'), row(HRP, 'null'), row(EW, 'null')],
        nw_t=(f"n/a · LW2008 HAC z {num(t.get('z_hac'))} vs {name(d, PRIMARY)} "
              f"(p {pval(t.get('p_one_sided_hac'))}; bootstrap p {pval(t.get('p_one_sided_boot'))})"),
        dsr=f"{num(full[METHOD]['DSR_exBIL'], 3)} on Sharpe ex-BIL, not legacy (trial_count={trials})",
        gate=dict(label='PR #48', href=GATE_PR),
        method_page=PAGE,
        artifact=dict(label='schur_allocator/summary.csv', href=REPO_BLOB + 'summary.csv'),
        archived=run_date_et(),
        archived_via='Single pre-registered gate run (trial 12); mechanical label, Quant recompute pending',
        nw_t_links=[dict(label='Results page', href=PAGE)],
    )


def run_date_et() -> str:
    """Date (ET) the single gate run was reserved, from RUN_RESERVED.json."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    ts = json.loads((SCHUR_DIR / 'RUN_RESERVED.json').read_text(encoding='utf-8'))['reserved_at']
    return datetime.fromisoformat(ts).astimezone(ZoneInfo('America/New_York')).date().isoformat()


def archive_label(d: dict, sid: str) -> str:
    return {METHOD: f'{name(d, METHOD)} (method)', PRIMARY: f'{name(d, PRIMARY)} (primary null)'}.get(sid, name(d, sid))


def build_schur_results(page_shell, write_page) -> str | None:
    if not available():
        return None
    d = gather()
    g, full = d['gate'], d['full']
    lab = g['label']
    badge = 'badge' if lab == 'PASS' else 'badge badge-fail'
    m = full.get(METHOD, {})
    window = f"{month(m.get('start', ''))} to {month(m.get('end', ''))}"
    present = [s for s in ORDER if s in full]
    head = (
        f'<p class="verdict-line"><span class="{badge}">{escape(badge_line(lab))}</span> '
        f'<span class="badge">Book-eligible: {escape(yes(g["fields"]["book_eligible"].get("eligible")).lower())}</span></p>'
        '<h1>Schur allocator gate results</h1>'
        f'<div class="callout"><strong>Gate verdict: {escape(badge_line(lab))}.</strong> {escape(verdict_text(d))}</div>'
        f'<p class="muted">Single pre-registered run · {escape(str(m.get("n_months", "—")))} out-of-sample months ({escape(window)}) · '
        f'net of 5 bp · {g["fields"]["trial_count"]} trials counted · complete months through {escape(month(g["monthly_panel"]["source_asof"]))}</p>'
        '<p><a href="composition_over_time.html#schur">Composition over time</a> · '
        '<a href="justina_round1_scoreboard.html">Archive scoreboard</a> · <a href="index.html">Methods</a></p>'
    )
    if lab == 'VOID':
        body = diagnostics(d)
    else:
        metrics = table(
            ['Strategy', 'Months', 'Sharpe ex-BIL', 'Sharpe (legacy rf = 0)', 'CAGR', 'Vol', 'MaxDD', 'Turnover / yr',
             'Effective N', 'DSR'],
            [[name_role(d, s), full[s]['n_months'], num(full[s]['Sharpe_exBIL']), num(full[s]['Sharpe_rf0_legacy']),
              pct(full[s]['CAGR']), pct(full[s]['AnnVol']), pct(full[s]['MaxDD']), num(full[s]['turnover_per_year']),
              num(full[s]['eff_N_mean'], 1), num(full[s]['DSR_exBIL'], 3)] for s in present],
            f'Full out-of-sample window, {window}, net of 5 bp')
        t = primary_test(d)
        tests_tbl = table(['Method vs', 'p one-sided (HAC)', 'p one-sided (bootstrap)', 'z (HAC)', 'z (bootstrap)'],
                          [[name(d, PRIMARY), pval(t.get('p_one_sided_hac')), pval(t.get('p_one_sided_boot')),
                            num(t.get('z_hac')), num(t.get('z_boot'))]],
                          'Ledoit-Wolf (2008) Sharpe-difference test, method vs primary null, full window')
        body = (
            '<h2>Pre-registered gate criteria</h2>'
            + table(['', 'Rule', 'Result', 'Outcome'], criteria_rows(d), 'Gate criteria, method, full window')
            + '<h2>Every pre-registered metric</h2>' + metrics
            + '<p class="muted">Sharpe ex-BIL is in excess of BIL (TB3MS before BIL’s first full month). The legacy rf = 0 Sharpe is '
              'shown for continuity only. Book 1 exists only on months where all its funds trade, so its row covers a shorter '
              'window and is not a criterion. '
              + escape(power_caveat(d)) + '</p>'
            + tests_tbl
            + book_section(d)
            + diagnostics(d)
        )
    content = (
        '<section class="band"><div class="band-inner">' + head + body
        + '<p class="muted">Source: the committed gate output (gate_result.json and its tables in data/processed/schur_allocator/), '
          'written once by the gate script. No reruns, retuning or re-selection.</p>'
        '</div></section>'
    )
    write_page(PAGE, page_shell('Schur allocator gate results', content, prefix='../', active='methods/index.html',
                                include_charts=False))
    return lab
