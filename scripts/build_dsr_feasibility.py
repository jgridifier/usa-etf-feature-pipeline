#!/usr/bin/env python3
"""Trial-13 DSR feasibility methods page (stdlib only).

Every figure on the page is read from data/processed/dsr_feasibility_trial13/feasibility.json, written by
scripts/dsr_feasibility_trial13.py from the committed trial registry. Not an archived trial: it adds no
archive card and changes no archive or scoreboard count. If the JSON is missing, no page is built.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'processed' / 'dsr_feasibility_trial13' / 'feasibility.json'
PAGE = 'methods/dsr_feasibility_trial13.html'
TITLE = 'Trial-13 DSR feasibility check'
REPO_BLOB = 'https://github.com/jgridifier/usa-etf-feature-pipeline/blob/main/'
# Quant's wording (2026-10-03).
LOWER_BOUND_TEXT = ('The hurdle is a lower bound. If trial {next_trial} scores well, it raises the cross-trial variance, '
                    'and that raises SR0.')


def available() -> bool:
    return DATA.exists()


def load() -> dict:
    return json.loads(DATA.read_text(encoding='utf-8'))


def n2(x: float) -> str:
    return f'{x:.2f}'


def n3(x: float) -> str:
    return f'{x:.3f}'


def dsr_label(t: float) -> str:
    return f'{t:.2f}'.rstrip('0').rstrip('.') if t != 0.5 else '0.5'


def table(head: list[str], rows: list[list[str]], caption: str) -> str:
    return (f'<div class="table-scroll" tabindex="0" role="region" aria-label="{escape(caption)}">'
            '<table><caption>' + escape(caption) + '</caption><thead><tr>'
            + ''.join(f'<th scope="col">{escape(h)}</th>' for h in head) + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows)
            + '</tbody></table></div>')


def build_dsr_feasibility(page_shell, write_page) -> bool:
    if not available():
        return False
    d = load()
    inp, c4, ref, chk = d['inputs'], d['c4'], d['reference'], d['check']
    n, t = inp['N'], inp['T']
    lo, hi = c4['hurdle_fat_tail_range']
    ew = ref['capped_equal_weight_sharpe_exbil']
    head = (
        '<p class="verdict-line"><span class="badge badge-fail">C4 out of reach at trial ' + str(n) + '</span> '
        '<span class="badge">Decision pending with Jared</span></p>'
        f'<h1>{escape(TITLE)}</h1>'
        f'<div class="callout"><strong>Result: trial {n} can’t pass C4.</strong> C4 needs DSR ≥ {dsr_label(c4["dsr"])}. '
        f'With {n} trials over {t} months, that takes a Sharpe ex-BIL of about {n2(c4["hurdle_normal"])}, versus {n3(ew)} '
        f'for capped equal weight over the same months, about {ref["hurdle_to_ew_ratio"]:.1f} times as much. With fat tails '
        f'the hurdle rises to {n2(lo)} to {n2(hi)}. '
        + escape(LOWER_BOUND_TEXT.format(next_trial=n)) + '</div>'
        f'<p class="muted">Registry-only arithmetic · no gate run, no new trial, no signal on the panel looked at · '
        f'not an archived trial · research on an experimental ETF panel, not investment advice. Nothing here changes '
        f'Book 1, Book 2 or the vol-target backbone.</p>'
    )
    cases = d['cases']
    targets = [h['dsr'] for h in cases[0]['hurdles']]
    rows = []
    for i, tg in enumerate(targets):
        label = f'DSR ≥ {dsr_label(tg)}' + (' (C4)' if tg == c4['dsr'] else '')
        cells = [n2(c['hurdles'][i]['sharpe_exbil_annual']) for c in cases]
        if tg == c4['dsr']:
            label, cells = f'<strong>{escape(label)}</strong>', [f'<strong>{c}</strong>' for c in cells]
        else:
            label = escape(label)
        rows.append([label, *cells])
    hurdles = table(['Target', *[escape(c['label']) for c in cases]], rows,
                    f'Sharpe ex-BIL (annualized) needed at N = {n}, T = {t} months')
    sr0_line = (f'<p>The expected best Sharpe among {n} strategies with no skill, SR0, is {n2(d["sr0_annual"])} annualized. '
                f'A trial at exactly SR0 has DSR 0.5, which is why the 0.5 row equals SR0 in every case: skew and '
                f'kurtosis only widen the uncertainty around it.</p>')
    inputs = table(['Input', 'Value'], [
        ['Months, T', str(t)],
        ['Trials counted if trial ' + str(n) + ' runs, N', str(n)],
        ['Registry trials (with a Sharpe ex-BIL)', f'{inp["registry_trials"]} ({inp["registry_trials_with_sharpe"]})'],
        ['Cross-trial variance of the monthly Sharpe', f'{inp["sr_var_cross_trial_monthly"]:.6f}'],
        ['Kurtosis convention', escape(inp['kurtosis_convention'])],
    ], f'Inputs (variance from {d["sources"]["registry"]})')
    check = (f'<p>Check: the same function at N = {chk["N"]} gives the Schur trial (Sharpe ex-BIL {n3(chk["schur_sharpe_exbil"])}) '
             f'a DSR of {n3(chk["schur_dsr_reproduced"])}, against the recorded {n3(chk["schur_dsr_recorded"])}, '
             f'which used realized skew and kurtosis.</p>')
    opts = ''.join(f'<li>{escape(o)}</li>' for o in d['decision']['options'])
    options = ('<h2>Options for Jared</h2>'
               '<p>Changing or keeping C4 is Jared’s call. The options, in no order:</p>'
               f'<ul>{opts}</ul>'
               f'<p><strong>Decision: {escape(d["decision"]["status"])} with {escape(d["decision"]["owner"])}.</strong></p>')
    content = (
        '<section class="band"><div class="band-inner">' + head
        + '<h2>Hurdles</h2>' + hurdles + sr0_line
        + '<h2>Inputs</h2>' + inputs
        + f'<p>Method: {escape(d["method"])}.</p>' + check
        + options
        + '<p class="muted">Source: <a href="' + REPO_BLOB + 'data/processed/dsr_feasibility_trial13/feasibility.json">'
          'feasibility.json</a>, written by scripts/dsr_feasibility_trial13.py from '
        + escape(d['sources']['registry']) + ' and ' + escape(d['sources']['summary']) + '. '
          '<a href="allocation_alpha_schur_results.html">Schur gate results</a> · <a href="index.html">Methods</a></p>'
        '</div></section>'
    )
    write_page(PAGE, page_shell(TITLE, content, prefix='../', active='methods/index.html', include_charts=False))
    return True
