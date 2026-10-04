#!/usr/bin/env python3
"""Results hub HTML from the saved hub JSON; stdlib only, no strategy execution.

All display formatting lives here. Charts use hub_charts; their tables retain
saved observations, rather than exposing plotting offsets as measured data.
"""
from __future__ import annotations

from collections import Counter
from html import escape
import json
import math
import os
from pathlib import Path
import re

import build_stage2_pages as stage2
import hub_charts as charts

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/processed/hub'
DEMIGUEL = ROOT / 'data/processed/stage2/demiguel_book_rule.json'
FAMILY2 = ROOT / 'data/processed/stage2/family2_dev.json'
DOCS = ROOT / 'docs'
PILOTS = ('schur', 'ft_med', 'book2')
SECTIONS = [('vs-core', 'Result vs the static core'), ('nulls', 'Against its own nulls'),
            ('testing', 'Testing breakdown'), ('charts', 'Under the test'),
            ('regimes', 'Regimes and stress windows'), ('sources', 'Sources and method transparency')]
PALETTE = ['#1c2d6b', '#1a1410', '#858a94', '#0e1a42', '#3f434a', '#b8bcc4', '#6b7079']
HEAD = '''<style>
.hub{max-width:1200px;margin:auto;padding:1rem;min-width:0;overflow-wrap:anywhere}
.hub section{margin:2rem 0}.hub h2{margin-top:1.5rem}.hub .table-scroll{max-width:100%;overflow-x:auto}
.hub table{font-size:.85rem;width:max-content;min-width:100%}.hub td,.hub th{min-width:5rem;overflow-wrap:normal;word-break:normal}.hub td{max-width:22rem}.hub tbody td:first-child{min-width:7.5rem}#leaderboard td:first-child,#leaderboard th:first-child{min-width:2.5rem}.hub tbody td:first-child,#leaderboard td:nth-child(2){max-width:11rem}#leaderboard td:first-child{max-width:3rem}.hub summary{cursor:pointer;font-weight:600;padding:.75rem 0}
.hub-chart{border-top:1px solid #c3c7cf;margin:1rem 0}.hub-chart-box{width:100%;height:300px;min-width:0}
.hub .badge,.hub .chip{color:#1c2d6b;background:#f4f5f7;padding:.2rem .4rem}
.hub button{color:#1c2d6b;background:#ffffff;border:1px solid #c3c7cf;cursor:pointer;font:inherit}
.hub .spark{width:96px;height:24px}.hub .on-page{display:flex;flex-wrap:wrap;gap:.25rem 1rem;padding-left:0;list-style:none}
.hub .on-page a{display:inline-flex;align-items:center;min-height:44px;padding:0 .25rem}
.hub button{min-height:44px;padding:.25rem .6rem}.hub summary{min-height:44px;display:flex;align-items:center}
#leaderboard th button{font-weight:600;text-align:left}
#leaderboard th[aria-sort] button::after{content:" \\2195";color:#858a94}
#leaderboard th[aria-sort="descending"] button::after{content:" \\25BC";color:#1c2d6b}
#leaderboard th[aria-sort="ascending"] button::after{content:" \\25B2";color:#1c2d6b}
#leaderboard th[aria-sort="descending"] button,#leaderboard th[aria-sort="ascending"] button{background:#1c2d6b;color:#ffffff}
#leaderboard th[aria-sort="descending"] button::after,#leaderboard th[aria-sort="ascending"] button::after{color:#ffffff}
#leaderboard th:nth-child(2),#leaderboard td:nth-child(2){position:sticky;left:0;background:#ffffff;z-index:1;box-shadow:1px 0 0 #c3c7cf}
#leaderboard tr.benchmark td{border-top:2px solid #1a1410;border-bottom:2px solid #1a1410;font-weight:600}
.hub .back{margin:.25rem 0 0}.hub .back a{display:inline-flex;align-items:center;min-height:44px}
.hub .verdict{border-left:3px solid #1c2d6b;padding:.25rem 0 .25rem .75rem;margin:.5rem 0 1rem}
.hub .footnote{font-size:.85rem;color:#3f434a}
#lb-cols{display:none}
@media(max-width:699px){.hub-chart-box{height:260px}.hub{padding:.75rem}
#lb-cols{display:inline-block;margin:.5rem 0}
#leaderboard:not(.all-cols) th:nth-child(n+7),#leaderboard:not(.all-cols) td:nth-child(n+7){display:none}}
</style>
<script src="../../assets/vendor/echarts-6.1.0.custom.min.js" defer></script>
<script src="../../assets/hub-theme.js" defer></script>
<script src="../../assets/hub-charts.js" defer></script>'''


def load(name):
    return json.loads((DATA / f'{name}.json').read_text(encoding='utf-8'))


def num(value):
    return '—' if value is None else f'{value:.2f}'.replace('-', '−')


def pct(value):
    return '—' if value is None else f'{value * 100:.1f}%'.replace('-', '−')


def pp(value):
    """A return difference in percentage points, two decimals (A6: −0.71 pp)."""
    return '—' if value is None else f'{value * 100:.2f} pp'.replace('-', '−')


def integer(value):
    return '—' if value is None else str(int(value)).replace('-', '−')


def text(value):
    if value is None:
        return '—'
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, (float, int)):
        return num(value)
    if isinstance(value, dict):
        return '; '.join(f'{k}: {text(v)}' for k, v in value.items())
    if isinstance(value, list):
        return '; '.join(text(v) for v in value) or 'none'
    # Saved identifiers stay intact; standalone display labels use the table name.
    return re.sub(r'(?<![\w.])(?:VT|vt)(?![\w])', 'Backbone', str(value))


def e(value):
    return escape(text(value))


def p(value, cls=''):
    return f'<p class="{cls}">{e(value)}</p>'


def table(headers, rows, caption):
    from build_pages import table_html
    return table_html(headers, rows, caption)


def missing(source):
    source = re.sub(r'^Source:\s*', '', str(source)).strip().rstrip('.')
    return f'<p class="muted not-saved">Not saved for this run (checked {e(source)}).</p>'


def source(d, kind='series'):
    return d['sources'].get(kind) or f"data/processed/hub/subjects/{d['id']}.json ({kind})"


def caption_text(*parts):
    """Join caption fragments, skipping missing ones (no stray '—.')."""
    out = []
    for part in parts:
        t = '' if part is None else str(part).strip()
        if t and t != '—':
            out.append(t if t.endswith(('.', ')', ':')) else t + '.')
    return ' '.join(out)


def legend_layout(option):
    """Wrapping legend below the plot, no paging; the grid and box grow with the number of rows."""
    entries = [x for x in (option.get('legend', {}).get('data') or [s.get('name') for s in option.get('series', [])
               if s.get('name') and not s.get('silent') and (s.get('tooltip') or {}).get('show', True)]) if x]
    if not entries or option.get('_hub', {}).get('no_legend'):
        option['legend'] = {'show': False}
        return 0
    rows = 0
    width = 0
    for name in entries:          # ~6.5px per character at 12px plus the swatch, in a ~320px phone row
        w = 34 + 6.5 * len(name)
        if rows == 0 or width + w > 320:
            rows, width = rows + 1, w
        else:
            width += w
    option['legend'] = {'type': 'plain', 'bottom': 4, 'left': 'center', 'width': '92%', 'itemGap': 12,
                        'itemWidth': 18, 'itemHeight': 10, 'data': entries, 'textStyle': {'fontSize': 12}}
    extra = 22 * rows
    option.setdefault('grid', {}).update(bottom=36 + extra, left=30, right=20, containLabel=True)
    return extra


def chart_content(id, option, caption, extra=''):
    option['color'] = PALETTE
    legend_extra = legend_layout(option)
    for axis, gap in (('xAxis', 30), ('yAxis', 52)):
        if option.get(axis, {}).get('type') in ('value', 'log'):
            option[axis].update(nameLocation='middle', nameGap=gap)
    if option.get('yAxis', {}).get('type') == 'category':
        option['yAxis']['axisLabel'] = {'width': 105, 'overflow': 'truncate', **option['yAxis'].get('axisLabel', {})}
    headers, rows = charts.table_rows(option)
    fmt = pct if option['_hub'].get('percent') else num
    cells = [[fmt(v) if isinstance(v, (int, float)) else text(v) for v in row] for row in rows]
    payload = json.dumps(option, ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    height = option['_hub'].get('height') or (300 + legend_extra if legend_extra > 22 else None)
    style = f' style="height:{int(height)}px"' if height else ''
    return (p(caption, 'muted') + f'<div class="hub-chart-box" data-hub-chart="opt-{id}"{style} role="img" aria-label="{e(caption)}"></div>'
            f'<script type="application/json" id="opt-{id}">{payload}</script>' + extra
            + '<details><summary>Data table</summary>' + table(headers, cells, caption) + '</details>')


def chart(id, title, option, caption, *, first=False, extra='', src=None):
    # A missing chart names only the file that was checked, not the caption of the chart it would have been.
    return (f'<details class="hub-chart" id="chart-{id}"' + (' open' if first else '') + '>'
            f'<summary>{e(title)}</summary>' + (chart_content(id, option, caption, extra) if option else missing(src or caption)) + '</details>')


SHORT = {'schur': 'Schur', 'ft_med': 'FT-MED', 'book2': 'Book 2', 'book1': 'Book 1', 'backbone': 'Backbone',
         'skew_overlay': '#6 overlay', 'vcfc': 'VCFC', 'rr_erc': 'RR-ERC', 'spectral_rp': 'Spectral RP',
         'regime_dual': 'Regime dual', 'epo': 'EPO', 'nls_v1': 'NLS v1', 'nls_v2': 'NLS v2', 'nls_v3': 'NLS v3'}


def short(label):
    """Legend-length series names: drop parentheticals and leading '#n' tags."""
    t = text(label)
    t = re.sub(r'\s*\([^)]*\)', '', t)
    t = re.sub(r'^#\d+\s+', '', t)
    return t if len(t) <= 22 else t[:21].rstrip() + '…'


def names(d):
    return {'subject': SHORT.get(d['id'], short(d['name'])), 'core': 'Core', 'primary_null': 'Primary null',
            **{r['key']: short(r['label']) for r in d.get('vs_nulls', [])}}


def series(d, values):
    labels = names(d)
    return [{'name': text(labels.get(k, k.replace('_', ' '))), 'values': v, 'dashed': k == 'core'}
            for k, v in values.items() if isinstance(v, list)]


def line(d, dates, values, label, **kw):
    if not dates or not values or not any(v and any(x is not None for x in v) for v in values.values()):
        return None
    opt = charts.line_chart(dates, series(d, values), y_label=label, **kw)
    if kw.get('log_y'):        # fit the log axis to the data range
        vals = [x for v in values.values() if isinstance(v, list) for x in v if isinstance(x, (int, float)) and x > 0]
        if vals:
            opt['yAxis'].update(min=round(min(vals) * 0.95, 3), max=round(max(vals) * 1.05, 3), scale=True)
    return opt


def power(comparison):
    return (comparison.get('power') or {}).get('text', 'Power not saved for this run')


LIVE_CORE = 'live core (VOO / QQQM / IJR, gross)'
STANDIN_CORE = 'stand-in core (IVV / QQQ / IJR, gross)'


def comparison(d, c, label, core_label=LIVE_CORE):
    if not c:
        return missing(source(d))
    coverage = c.get('coverage')
    window = (f"{integer(coverage['k'])} of {integer(coverage['m'])} months covered by the core; " if coverage else '')
    win = f"{c['start']} to {c['end']}, {integer(c['n'])} paired months"
    out = p(f"Over {label} ({window}{win}), {d['name']} returned "
            f"{pct(c['a'].get('total_return'))} vs the {core_label}'s {pct(c['b'].get('total_return'))}.")
    rows = []
    for key, name in [('total_return', 'Total return'), ('cagr', 'CAGR'), ('sharpe_exbil', 'Sharpe ex-BIL'), ('maxdd', 'MaxDD (single path, no test)')]:
        if key == 'sharpe_exbil' and d['label'] == 'VOID':
            continue
        fmt = num if key == 'sharpe_exbil' else pct
        rows.append([name, *(fmt(c[k].get(key)) for k in ('diff', 'a', 'b'))])
    # CIO ruling on PM item 1: the difference column sits right after Metric so it never scrolls off a phone.
    out += table(['Metric', 'Difference vs core', SHORT.get(d['id'], 'Subject'), 'Core'], rows,
                 f"{label[0].upper() + label[1:]}: {win}; vs the {core_label}")
    rt, st = c.get('return_test') or {}, c.get('sharpe_test') or {}
    out += p(f"HAC return difference (Newey–West t): NW t {num(rt.get('nw_t'))}; two-sided p {num(rt.get('p_two_sided'))}.")
    if st and d['label'] != 'VOID':
        sig = 'not significant' if not st.get('significant_5pct_two_sided') else 'significant at 5%'
        out += p(f"LW2008 HAC Sharpe difference: z {num(st.get('z'))}; one-sided p {num(st.get('p_one_sided'))}; "
                 f"two-sided p {num(st.get('p_two_sided'))} ({sig}).")
    return out + p(power(c), 'power')


def dsr_html(d):
    dsr = d.get('dsr') or {}
    out = ''
    if dsr.get('grid_reference') and not dsr.get('corrected'):
        g = dsr['grid_reference']
        out += p(dsr.get('note'))
        out += table([f"Grid row (N = {integer(g['n_trials'])}): DSR ex-BIL, corrected", 'Basis', 'As recorded'],
                     [[num(g['dsr_exbil']), f"Sharpe ex-BIL {num(g['sharpe_exbil'])}, {g['window']}, {integer(g['months'])} months",
                       num(g.get('dsr_rf0_recorded')) + ' (as recorded)']], 'DSR: reference only (the gate-first spec has N = 1)')
        return out + p(g.get('error_note'))
    corrected = dsr.get('corrected')
    if corrected:
        out += table(['DSR ex-BIL (primary)', 'Basis', 'As recorded'],
                     [[num(corrected['dsr_exbil']), text(dsr.get('primary_basis')),
                       num(corrected.get('dsr_rf0_recorded')) + ' (as recorded)']], 'DSR')
        out += p(corrected.get('error_note'))
    else:
        out += p(f"DSR: {text(dsr.get('recorded'))}; {text(dsr.get('recorded_basis'))}.")
    if dsr.get('note'):
        out += p(dsr['note'])
    return out


def subject_charts(d):
    out = []
    def add(slot, title, option, kind='series', caption='', extra=''):
        out.append(chart(str(slot), title, option, caption_text(f"Source: {source(d, kind)}", caption), extra=extra,
                         src=source(d, kind)))
    curves = d.get('curves') or {}
    g = curves.get('growth_vs_core') or {}
    add(1, 'Growth of $1: subject vs static core (log)', line(d, g.get('months'), {k:g.get(k) for k in ('subject','core')}, 'Growth', log_y=True),
        caption='Only paired months are drawn; uncovered months are not in window.')
    add(2, 'Cumulative excess and rolling 12m excess', line(d, g.get('months'), {k:g.get(k) for k in ('cumulative_excess','rolling_12m_excess')}, 'Excess', percent=True, zero_line=True))
    rolling = d.get('rolling_sharpe') or {}
    r = rolling.get('diff_vs_core') or {}
    gap = r.get('detectable_gap_36m')
    band = {'name':'Detectable gap', 'lower':[-gap] * len(r['months']), 'upper':[gap] * len(r['months'])} if gap is not None else None
    opt = line(d, r.get('months'), {'Sharpe difference': r.get('values')}, 'Sharpe difference', band=band, zero_line=True)
    if opt and band:
        opt['_hub']['table'] = {'headers':['Date','Sharpe difference','Detectable gap'], 'rows':[[m,v,gap] for m,v in zip(r['months'],r['values'])]}
    add(3, f"Rolling {integer(rolling.get('window_months'))}m Sharpe difference vs core", opt, caption=r.get('band_note',''))
    primary = next((n['key'] for n in d.get('vs_nulls',[]) if n.get('primary')), None)
    dd = curves.get('drawdown') or {}
    core_dd = dict(zip(g.get('months',[]),g.get('drawdown_core',[])))
    add(4, 'Drawdowns: subject, core and primary null', line(d, d.get('months'),
        {'subject':dd.get('subject'), 'core':[core_dd.get(m) for m in d.get('months',[])], **({primary:dd[primary]} if primary in dd else {})}, 'Drawdown', percent=True))
    years = d.get('calendar_years') or []
    opt = charts.bar_chart([integer(y['year']) + (' (partial)' if y['partial'] else '') for y in years],
            series(d,{k:[y.get(k) for y in years] for k in ('subject','core')}), y_label='Return', percent=True) if years else None
    add(5, 'Calendar-year returns', opt)
    sc = d.get('scatter_vs_core') or {}
    opt = charts.scatter_chart([{'name':m,'x':x,'y':y} for m,x,y in zip(sc.get('months',[]),sc.get('core',[]),sc.get('subject',[]))], x_label='Core',y_label='Subject',percent=True,diagonal=True) if sc else None
    add(6, 'Monthly returns vs core', opt, caption=f"Beta {num(sc.get('beta'))}; correlation {num(sc.get('correlation'))}.")
    add(7, 'Growth of $1 vs own nulls', line(d,d.get('months'),curves.get('growth'), 'Growth'))
    add(8, f"Rolling {integer(rolling.get('window_months'))}m Sharpe ex-BIL", line(d,d.get('months'),{k:v for k,v in rolling.items() if isinstance(v,list)}, 'Sharpe ex-BIL'))
    t = d.get('turnover') or {}
    opt = charts.bar_chart(t['months'],[{'name':'Turnover','values':t['per_rebalance']}],y_label='Turnover',percent=True) if t.get('per_rebalance') else None
    all_rows = (f"All saved rows, including the dropped partial month: {pct(t.get('per_year_all_saved_rows'))}/yr. {t['all_rows_note']}"
                if t.get('all_rows_note') else None)
    add(9, 'Turnover per rebalance (one-way, ½·Σ|Δw|)', opt, caption=caption_text(
        f"Per year: {pct(t.get('per_year'))} one-way (½·Σ|Δw| per rebalance, mean × 12) over {text(t.get('window'))}",
        all_rows, t.get('nulls_note')))
    w = d.get('weights') or {}
    top = w.get('top5') or {}
    TOP_N = 5
    if top:
        shown = top  # saved by hub_data.weights_block: top 5 by average weight + "Other"
        opt = charts.stacked_area(w['months'], [{'name': k, 'values': v} for k, v in shown.items()], y_label='Weight')
        opt['yAxis'].update(max=1, min=0)
        for s_ in opt['series']:
            s_['areaStyle'] = {'opacity': 0.55}
            s_['lineStyle'] = {'width': 0.5}
        if 'Other' in shown:
            opt['series'][-1]['areaStyle'] = {'opacity': 0.35, 'color': '#b8bcc4'}
    else:
        opt = None
    add(10, f'Weights over time (top {TOP_N} + other)', opt, 'weights', caption_text(
        w.get('basis'), f'Top {TOP_N} holdings by average weight; "Other" is everything else (1 − sum of the top {TOP_N})' if top else None))
    opt = line(d,w.get('months'),{'Effective N':w.get('effective_n'),'Largest weight (fraction)':w.get('largest_weight')}, 'Concentration')
    add(11, 'Effective N and largest weight',opt,'weights')
    regimes = d.get('regimes') or []
    opt = charts.bar_chart([r['regime'] for r in regimes],series(d,{k:[r['series'].get(k,{}).get('cumulative_return') for r in regimes] for k in ('subject','core','primary_null')}),y_label='Cumulative return',percent=True) if regimes else None
    chips = ''.join(p(f"{r['regime']} · {names(d).get(k,k)}: {v['status']}", 'chip') for r in regimes for k,v in (r.get('own_coverage') or {}).items() if v['status'] != 'in window')
    add(12, 'Regime cumulative returns (paired months)',opt,'regimes',caption='Method, core and primary null on the same months (those all three cover); own coverage below.',extra=chips)
    stress_parts = []
    for r in d.get('stress') or []:
        path = r.get('path') or {}
        if not any(v is not None for k in ('subject','core') for v in path.get(k,[])):
            stress_parts.append(p(f"{r['name']}: not in window")); continue
        values = {}
        for k in ('subject','core'):
            growth, vals = 1., []
            for v in path.get(k,[]):
                if v is None: vals.append(None)
                else:
                    growth *= 1 + v
                    vals.append(growth - 1)
            values[k] = vals
        opt = line(d,path['months'],values,'Cumulative return',percent=True)
        # Data table exposes the saved monthly inputs, not derived plotted coordinates.
        opt['_hub']['table'] = {'headers':['Date','Subject monthly return','Core monthly return'],
            'rows':[[m,a,b] for m,a,b in zip(path['months'],path['subject'],path['core'])]}
        stress_parts.append(chart_content('stress-'+r['window'],opt,f"{r['name']}. Source: {source(d)}. Cumulative paths compounded from the saved monthly returns."))
    out.append('<details class="hub-chart" id="chart-13"><summary>Stress-window cumulative paths</summary>' + (''.join(stress_parts) or missing(source(d))) + '</details>')
    trials = d.get('trials') or {}
    rows = trials.get('rows') or []
    opt = charts.scatter_chart([{'name':v['trial_id'] + (' (chosen)' if v['trial_id']==trials.get('chosen') else ''),'x':v.get('sharpe'),'y':0} for v in rows],x_label='Trial Sharpe',y_label='Trials') if rows else None
    if opt:
        core = (d.get('vs_core',{}).get('own_window') or {}).get('b',{}).get('sharpe_exbil')
        if core is not None:
            opt['series'][0]['markLine'] = {'data':[{'xAxis':core}], 'symbol':['none','none'], 'label':{'formatter':'Core','position':'insideEndTop'}}
        opt['yAxis'].update(show=False)
        for point, row in zip(opt['series'][0]['data'], rows):
            chosen = row['trial_id'] == trials.get('chosen')
            point.update(symbol='diamond' if chosen else 'circle', symbolSize=12 if chosen else 6,
                         itemStyle={'color': '#1c2d6b' if chosen else '#858a94'})
        opt['_hub']['table'] = {'headers':['Trial','Sharpe','Chosen'], 'rows':[[r['trial_id'],r.get('sharpe'),'chosen' if r['trial_id']==trials.get('chosen') else '—'] for r in rows]}
    add(14,'Trial Sharpe dot plot',opt,'trials',f"{text(trials.get('basis'))}. Core reference Sharpe ex-BIL {num(core) if opt else '—'}; bases may differ.")
    dsr = d.get('dsr') or {}
    ref = dsr.get('corrected') or dsr.get('grid_reference')
    val = ref.get('dsr_exbil') if ref else dsr.get('primary')
    if val is None and isinstance(dsr.get('recorded'),str):
        match = re.match(r'([0-9.]+) on Sharpe',dsr['recorded'])
        if match: val = float(match[1])
    opt = charts.scatter_chart([{'name':'DSR ex-BIL','x':val,'y':0}],x_label='DSR ex-BIL',y_label='DSR') if isinstance(val,(float,int)) else None
    if opt:
        opt['yAxis']['show'] = False
        opt['xAxis'].update(min=0,max=1)
        opt['_hub']['table'] = {'headers':['Measure','Value'], 'rows':[['DSR ex-BIL',val]]}
    add(15,'DSR number line',opt,'trials','Grid reference only. ' if dsr.get('grid_reference') else '',extra=p('Observed Sharpe, expected-best Sharpe and hurdle are not saved together on a common DSR basis in the hub JSON.','muted'))
    comparisons = [(k.replace('_',' '),v) for k,v in d.get('vs_core',{}).items() if k != 'standin_sensitivity' and v] + [(r['label'],r) for r in d.get('vs_nulls',[])]
    pairs = [(name,c) for name,c in comparisons if c.get('power',{}).get('detectable_sharpe_gap') is not None]
    opt = charts.bar_chart([name for name,c in pairs],[{'name':'Observed Sharpe difference','values':[c['diff'].get('sharpe_exbil') for name,c in pairs]}, {'name':'Detectable gap','values':[c['power']['detectable_sharpe_gap'] for name,c in pairs]}],y_label='Sharpe gap',horizontal=True) if pairs else None
    if opt:
        # Long null names ("LW MinVar (capped QP)") wrap inside a fixed label width instead of being cut off at 375px.
        opt['yAxis']['axisLabel'] = {'width': 96, 'overflow': 'break', 'lineHeight': 12, 'fontSize': 10}
        opt.setdefault('grid', {}).update(left=8, right=16, containLabel=True)
    add(16,'Head-to-head power',opt,extra=''.join(p(f'{name}: {power(c)}','power') for name,c in comparisons))
    return ''.join(out)


def window_table(d, rows, title):
    """Method, core and primary null on the SAME months (CIO review of #55, item 5); own coverage shown beside."""
    result = []
    for r in rows:
        label = r.get('name',r.get('regime'))
        if 'start' in r: label += f" ({r['start']} to {r['end']})"
        own = r.get('own_coverage') or {}
        paired = r.get('paired_months', 0)
        blocks = [(f"{integer(paired)} paired months" + (f" ({r['paired_window']})" if r.get('paired_window') else ''), r['series'])]
        if r.get('series_ex_core'):
            x = r['series_ex_core']
            blocks.append((f"core not in window; method and null on {integer(x['months'])} shared months ({x['window']})", x['series']))
        for basis, block in blocks:
            for key, v in block.items():
                cov = own.get(key, v['coverage'])
                if not v['coverage']['k']:
                    cells = ['not in window'] * 3
                else:
                    cells = [pct(v.get('cumulative_return')),pct(v.get('ann_vol')),
                             num(v['sharpe_exbil']) if v.get('sharpe_exbil') is not None else 'too few months for a Sharpe']
                result.append([label,names(d).get(key,key),basis,cov['status'],*cells,
                               r['vs_core_power']['text'] if key == 'subject' and basis == blocks[0][0] else ''])
    return table(['Window','Series','Months used','Own coverage','Cumulative return','Annual volatility','Sharpe ex-BIL','Power vs core'],result,title)


def source_rows(value, prefix=''):
    if isinstance(value,dict):
        return [row for k,v in value.items() for row in source_rows(v,f'{prefix}.{k}' if prefix else k)]
    if isinstance(value,list):
        return [row for v in value for row in source_rows(v,prefix)] or [[prefix,'none']]
    return [[prefix,text(value)]]


GLOSSARY = [
    ('HAC', 'Heteroskedasticity- and autocorrelation-consistent standard errors: they stay honest when monthly returns '
            'have changing volatility and are correlated from one month to the next.'),
    ('NW t (Newey–West t)', 'The t-statistic of the average monthly return difference, using HAC standard errors '
                            '(Newey and West 1987). Roughly, |t| above 2 is evidence of a real difference.'),
    ('LW2008', 'The Ledoit and Wolf (2008) test of whether two Sharpe ratios differ, with HAC standard errors. '
               'It compares risk-adjusted returns, not raw returns.'),
    ('Detectable gap', 'The smallest Sharpe (or return) difference these months could detect at one-sided 5% with 80% power. '
                       'Smaller observed gaps are not evidence either way.'),
    ('DSR / PSR', 'The deflated Sharpe ratio discounts the best Sharpe for the number of trials tried; with one trial it '
                  'reduces to the probabilistic Sharpe ratio (PSR).'),
]


def trial_counts_html(manifest, d=None):
    tc = manifest.get('trial_counts') or {}
    if not tc:
        return ''
    own = ''
    if d is not None:
        n = len((d.get('trials') or {}).get('rows') or [])
        own = (f" This page's own registry holds {integer(n)} trial{'s' if n != 1 else ''}." if n else
               ' This subject has no saved trial registry of its own.')
    return ('<div class="footnote trial-counts">' + p(
        f"Trials: {tc['third_book_search']['label']} versus {tc['all_registries']['label']}. {tc['why_they_differ']}{own}")
        + p(f"Source: {manifest.get('trial_counts_source')} (Addendum 2 §8).", 'muted') + '</div>')


def verdict_html(d):
    v = d.get('verdict') or {}
    out = f'<div class="verdict"><p><span class="badge">{e(d["label"])}</span></p>'
    if v.get('text'):
        out += p(v['text'])
    return out + '</div>'


def admission_html(d):
    a = d.get('admission')
    if not a:
        return ''
    rows = [[c['criterion'], c['recorded'], c['result']] for c in a['criteria']]
    return ('<h3>Eligibility: the rule Book 2 was admitted under</h3>'
            + p(f"Admitted {a['gate_date']} as {a['admitted_as']}. {a['rule']}")
            + table(['Recorded gate-first criterion', 'Recorded value', 'Result'], rows, 'Book 2 admission (#6 gate, recorded)')
            + p(f"Verdict: {a['verdict']}.") + p(a['stage2_book_rule_note'])
            + p(f"Source: {a['source']}; " + '; '.join(f"{x['document']}" + (f" (sha256 {x['sha256'][:12]}…)" if x.get('sha256') else '')
                                                    for x in a['sources']), 'muted'))


def gate_value(d, g):
    value = text(g.get('value'))
    if g['gate'] == 'DSR / C4':
        dsr = d.get('dsr') or {}
        if dsr.get('corrected'):
            ref = dsr['corrected']
            value = f"{num(ref['dsr_exbil'])} ex-BIL (primary); {num(ref.get('dsr_rf0_recorded'))} as recorded"
        elif g.get('grid_reference'):
            ref = g['grid_reference']
            value = (f"{text(g.get('value'))}. Grid reference (N = {integer(ref['n_trials'])}): {num(ref['dsr_exbil'])} "
                     f"corrected ex-BIL, {num(ref.get('as_recorded'))} as recorded")
    if g['gate'].startswith('Empirical gate') and g.get('value') is None and d.get('admission'):
        value = d['admission']['verdict'] + ' (see the admission criteria above)'
    return value


def own_window_notes(d, manifest):
    notes = []
    own, bw, cw = d.get('own') or {}, d.get('books_window'), d.get('common_window_own')
    if d['label'] != 'VOID' and bw and own.get('start') != '2021-02' and own.get('sharpe_exbil') is not None:
        notes.append(f"Sharpe ex-BIL over different windows: {num(own['sharpe_exbil'])} over its own window "
                     f"({own['start']} to {own['end']}, {integer(own['n'])} months); {num(bw.get('sharpe_exbil'))} over the "
                     f"{bw['label']}, {integer(bw['n'])} months; {num((cw or {}).get('sharpe_exbil'))} over the common window. "
                     'These are window effects, not errors.')
    vs_own = (d.get('vs_core') or {}).get('own_window') or {}
    if d['label'] != 'VOID' and vs_own.get('a', {}).get('sharpe_exbil') is not None and vs_own.get('start') != own.get('start'):
        notes.append(f"Paired with the {LIVE_CORE} (from {manifest['static_core']['first_month']}), its Sharpe ex-BIL is "
                     f"{num(vs_own['a']['sharpe_exbil'])} over {vs_own['start']} to {vs_own['end']}.")
    notes.append(manifest.get('cost_basis', ''))
    return ''.join(p(n, 'footnote') for n in notes if n)


def subject_body(d, manifest):
    parts = []
    core = d.get('vs_core') or {}
    body = own_window_notes(d, manifest)
    body += comparison(d,core.get('own_window'),'its own window') + comparison(d,core.get('common_window'),'the common window')
    if d['id'] == 'book1':
        body = p('This is the static core benchmark; its difference vs itself is zero by definition. It was not gated: no pre-registered null, trial count or DSR. Other comparisons are reference only.') + body
    if d['label'] == 'VOID':
        body = p(d.get('verdict', {}).get('void_reason')) + p('Reported for transparency; the test design was void.', 'callout') + body
    sensitivity = core.get('standin_sensitivity')
    if sensitivity:
        body += ('<details><summary>Stand-in core sensitivity</summary>' + p(sensitivity['label'])
                 + comparison(d,sensitivity,'the sensitivity window', STANDIN_CORE) + '</details>')
    if d.get('vintage_note'):
        body += p(d['vintage_note']) + '<p>The #6 skew overlay gets its own page next; for now see <a href="index.html">its hub listing</a>.</p>'
    parts.append(body)
    rows = []
    for r in d.get('vs_nulls',[]):
        st = r.get('sharpe_test') or {}
        sig = '—' if not st else ('not significant' if not st.get('significant_5pct_two_sided') else 'significant at 5%')
        rows.append([text(r['label']) + (' (primary)' if r.get('primary') else ''),num(r['diff'].get('sharpe_exbil')),
                     num(st.get('z')),num(st.get('p_one_sided')),num(st.get('p_two_sided')),sig,
                     num((r.get('return_test') or {}).get('nw_t')),integer(r['n']),num(r.get('power',{}).get('detectable_sharpe_gap')),power(r)])
    parts.append(table(['Null','Sharpe ex-BIL diff','z (LW2008)','p (one-sided)','p (two-sided)','Significance (two-sided 5%)',
                        'NW t','Months','Detectable gap','Power'],rows,'Own null comparisons (Sharpe ex-BIL, own paired months)')
                 if rows else p('No pre-registered null saved.'))
    own = d['own']; trials = d.get('trials') or {}
    body = admission_html(d)
    body += p(f"Data / universe: {source(d)}; weights: {source(d,'weights')}. Saved window: {own['start']} to {own['end']}, {integer(own['n'])} months.")
    body += p(f"Trials in the saved registry: {integer(len(trials.get('rows') or []))}. Nulls it had to beat: " + '; '.join(r['label'] for r in d.get('vs_nulls',[])))
    body += p(f"Pre-registration: {d['sources'].get('prereg') or 'not pre-registered'}.")
    gate_rows = []
    for g in d.get('gates') or []:
        context = text({k:v for k,v in g.items() if k not in ('gate','value','outcome','grid_reference','note') and v is not None})
        if g['gate'] == 'Null comparison (recorded)':
            context += '; ' + '; '.join(f"{r['label']}: {power(r)}" for r in d.get('vs_nulls', []))
        gate_rows.append([g['gate'],gate_value(d, g),text(g.get('outcome')),context])
    body += table(['Gate','Value','Outcome','Basis, scope and source'],gate_rows,'Recorded gates and hub recompute')
    body += dsr_html(d)
    parts.append(body)
    parts.append(subject_charts(d))
    parts.append(window_table(d,d.get('regimes') or [],'Regimes (paired months)') + window_table(d,d.get('stress') or [],'Stress windows (paired months)'))
    entry = next(r for r in manifest['subjects'] if r['id']==d['id'])
    body = '<h3>Plain-language notes</h3><dl>' + ''.join(f'<dt>{e(k)}</dt><dd>{e(v)}</dd>' for k, v in GLOSSARY) + '</dl>'
    body += table(['Source / column','Saved value'],source_rows(d['sources'])+source_rows(entry,'manifest'),'Source manifest')
    body += p('Dropped partial month: ' + (', '.join(d.get('partial_months_dropped') or []) or 'none'))
    for label,path in d.get('pages',{}).items():
        target = DOCS / path.split('#')[0]
        href = os.path.relpath(target,DOCS/'methods/results') + ('#'+path.split('#',1)[1] if '#' in path else '')
        body += '<p>' + (f'<a href="{escape(href)}">{e(label)}: {e(path)}</a>' if target.exists() else e(f'{label}: {path}')) + '</p>'
    body += p('Derivation: src/usa_etf_features/hub_data.py; scripts/build_hub_data.py. Saved artifacts only; no strategy or gate re-run.')
    parts.append(body)
    toc = '<p>On this page</p><ul class="on-page">' + ''.join(f'<li><a href="#{id}">{title}</a></li>' for id,title in SECTIONS) + '</ul>'
    return ('<article class="hub"><p class="back"><a href="index.html">← Results hub</a></p>' + f'<h1>{e(d["name"])}</h1>'
            + verdict_html(d) + trial_counts_html(manifest, d) + toc
            + ''.join(f'<section id="{id}"><h2>{title}</h2>{body}</section>' for (id,title),body in zip(SECTIONS,parts))
            + '<p class="back"><a href="index.html">← Results hub</a></p></article>')


def spark(values):
    saved = [(i,v) for i,v in enumerate(values or []) if v is not None]
    if not saved: return '—'
    lo, hi = min(0.,*(v for i,v in saved)), max(0.,*(v for i,v in saved))
    span = hi-lo or 1
    y = lambda v: 22 - (v-lo)/span*20
    points = ' '.join(f'{2+i/max(len(values)-1,1)*92:.2f},{y(v):.2f}' for i,v in saved)
    return (f'<svg class="spark" viewBox="0 0 96 24" role="img" aria-label="Excess vs core">'
            f'<path d="M2 {y(0):.2f} H94" stroke="#c3c7cf" fill="none"/>'
            f'<polyline points="{points}" stroke="#1c2d6b" fill="none"/></svg>')


SORT_SCRIPT = """<script>
(() => {
  const table = document.getElementById('leaderboard');
  const body = table.tBodies[0];
  table.querySelectorAll('button[data-key]').forEach(button => {
    button.addEventListener('click', () => {
      const header = button.closest('th');
      const ascending = header.getAttribute('aria-sort') === 'descending';
      table.querySelectorAll('th[aria-sort]').forEach(th => th.setAttribute('aria-sort', 'none'));
      header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
      const key = button.dataset.key;
      const rows = [...body.rows].filter(row => !row.classList.contains('benchmark'));
      const zero = body.querySelector('tr.benchmark');
      rows.sort((a, b) => (Number(a.dataset[key]) - Number(b.dataset[key])) * (ascending ? 1 : -1));
      // Book 1 (the zero line) stays pinned at zero: rows above it beat the core on this column's sign.
      const above = rows.filter(row => ascending ? Number(row.dataset[key]) < 0 : Number(row.dataset[key]) > 0);
      const below = rows.filter(row => !above.includes(row));
      [...above, ...(zero ? [zero] : []), ...below].forEach(row => body.appendChild(row));
    });
  });
  const toggle = document.getElementById('lb-cols');
  if (toggle) toggle.addEventListener('click', () => {
    const all = table.classList.toggle('all-cols');
    toggle.setAttribute('aria-expanded', String(all));
    toggle.textContent = all ? 'Show fewer columns' : 'Show all columns';
  });
})();
</script>"""


def subject_link(r):
    label = 'Backbone' if r['id']=='backbone' else r['name']
    return f'<a href="{r["id"]}.html">{e(label)}</a>' if r['id'] in PILOTS else e(label) + ' <span class="muted">page coming</span>'


def same_series(rows):
    """Rows whose common-window figures are identical to an earlier row (Book 2 and the #6 overlay are one series)."""
    seen, dup = {}, {}
    for r in rows:
        key = (round(r['cagr_diff'], 12), round(r['sharpe_diff'], 12), round(r['maxdd_diff'], 12))
        if key in seen and not r.get('is_benchmark'):
            dup[r['id']] = seen[key]
        else:
            seen.setdefault(key, r)
    return dup


def nice_step(span, ticks=4):
    raw = span / ticks
    for step in (0.005, 0.01, 0.02, 0.025, 0.05, 0.1, 0.2, 0.25, 0.5):
        if step >= raw:
            return step
    return 1.0


def place_labels(data, x0, x1, y0, y1, mid, w=290.0, h=250.0, ch=5.6, lh=12.0, r=5.0):
    """Choose a label side per point so no two labels (or a label and a dot) overlap at the narrowest (375px) plot.

    Pixel geometry is estimated from the axis bounds for a ~290×250 px plot; sides are tried in order
    default (right, or left in the right half), top, bottom, the other side."""
    def px(v):
        return ((v[0] - x0) / ((x1 - x0) or 1) * w, (y1 - v[1]) / ((y1 - y0) or 1) * h)

    def box(cx, cy, side, text):
        tw = ch * len(text)
        if side == 'right':
            return (cx + r + 2, cy - lh / 2, cx + r + 2 + tw, cy + lh / 2)
        if side == 'left':
            return (cx - r - 2 - tw, cy - lh / 2, cx - r - 2, cy + lh / 2)
        if side == 'top':
            return (cx - tw / 2, cy - r - 2 - lh, cx + tw / 2, cy - r - 2)
        return (cx - tw / 2, cy + r + 2, cx + tw / 2, cy + r + 2 + lh)

    def hit(a, b):
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    items = [it for it in data]
    dots = [(lambda c: (c[0] - r, c[1] - r, c[0] + r, c[1] + r))(px(it['value'])) for it in items if isinstance(it, dict) and it.get('value')]
    placed, out = [], []
    for it in items:
        if not (isinstance(it, dict) and it.get('value')):
            out.append(it)
            continue
        cx, cy = px(it['value'])
        first = 'left' if it['value'][0] > mid else 'right'
        other = 'right' if first == 'left' else 'left'
        own = (cx - r, cy - r, cx + r, cy + r)
        choice = first
        for side in (first, 'top', 'bottom', other):
            b = box(cx, cy, side, str(it.get('name', '')))
            if b[0] < 0 or b[2] > w:
                continue
            if not any(hit(b, q) for q in placed) and not any(hit(b, d) for d in dots if d != own):
                choice = side
                break
        placed.append(box(cx, cy, choice, str(it.get('name', ''))))
        out.append(dict(it, label={'position': choice}) if choice != 'right' else it)
    return out


def scatter_option(ranked):
    pts = [{'name': SHORT.get(r['id'], short(r['name'])), 'x': r['cagr_diff'], 'y': r['maxdd_diff']} for r in ranked]
    opt = charts.scatter_chart(pts, x_label='CAGR diff vs core', y_label='MaxDD diff vs core', percent=True, quadrant_lines=True)
    xs, ys = [q['x'] for q in pts] + [0], [q['y'] for q in pts] + [0]
    # Axis bounds: padded, then rounded outward to a round step so tick labels read 0%, −5%, … not −11.68%.
    spx, spy = (max(xs) - min(xs)) or 0.04, (max(ys) - min(ys)) or 0.04
    sx, sy = nice_step(spx, 5), nice_step(spy, 5)
    x0, x1 = math.floor((min(xs) - 0.1 * spx) / sx) * sx, math.ceil((max(xs) + 0.1 * spx) / sx) * sx
    y0, y1 = math.floor((min(ys) - 0.1 * spy) / sy) * sy, math.ceil((max(ys) + 0.1 * spy) / sy) * sy
    opt['xAxis'].update(min=round(x0, 4), max=round(x1, 4), interval=sx, axisLabel={'hideOverlap': True})
    opt['yAxis'].update(min=round(y0, 4), max=round(y1, 4), interval=sy)
    opt.setdefault('grid', {}).update(right=16)
    main = opt['series'][0]
    mid = (x0 + x1) / 2
    main.update(symbolSize=9, label={'show': True, 'formatter': '{b}', 'position': 'right', 'fontSize': 10, 'color': '#3f434a'},
                itemStyle={'color': '#1c2d6b'}, z=5,
                emphasis={'scale': 1.6})
    # Zero lines sit under the dots and never take the tap (PM: Backbone dot on the dashed line had no tooltip).
    if main.get('markLine'):
        main['markLine'].update(silent=True, z=1)
    # Points in the right half label to their left so names are not clipped at the plot edge; close
    # neighbours (PM: Spectral RP / EPO, RR-ERC / Regime dual) get the first free side from place_labels.
    main['data'] = place_labels(main.get('data', []), x0, x1, y0, y1, mid)
    quads = [('Higher CAGR\nshallower DD', x1, y1), ('Lower CAGR\nshallower DD', x0, y1),
             ('Lower CAGR\ndeeper DD', x0, y0), ('Higher CAGR\ndeeper DD', x1, y0)]
    opt['series'].append({'name': 'Quadrants', 'type': 'scatter', 'silent': True, 'z': 0, 'symbolSize': 0, 'tooltip': {'show': False},
                          'data': [{'name': q[0].replace('\n', ', '), 'value': [round(q[1], 4), round(q[2], 4)],
                                    'label': {'show': True, 'formatter': q[0], 'fontSize': 9, 'lineHeight': 11, 'color': '#6b7079',
                                              'position': 'inside', 'offset': [-34 if q[1] == x1 else 34, 14 if q[2] == y1 else -14],
                                              'align': 'right' if q[1] == x1 else 'left'}} for q in quads]})
    opt['_hub']['pointTooltip'] = ['CAGR diff', 'MaxDD diff']
    opt['_hub']['decimals'] = 1
    opt['_hub']['no_legend'] = True
    opt['_hub']['height'] = 340
    return opt


def leaderboard_body(d, manifest, subjects, archive):
    title = 'Results hub: every method against the static core'
    rows = sorted(d['rows'],key=lambda r:r['cagr_diff'],reverse=True)
    dup = same_series(rows)
    by_id = {s['id']: s for s in subjects}
    bb = next((r for r in rows if r['id'] == 'backbone'), None)
    bb_own = (by_id.get('backbone') or {}).get('own') or {}
    out = ('<article class="hub"><h1>' + title + '</h1><div class="callout">'
           + p(f"{d['common_window']['start']} to {d['common_window']['end']} ({integer(d['common_window']['months'])} months), "
               f"ranked by CAGR difference vs the {LIVE_CORE}.")
           + '<details><summary>What this table compares</summary>' + p(d['common_window']['label']) + p(d['benchmark'])
           + p(manifest.get('cost_basis')) + '</details></div>')
    out += trial_counts_html(manifest)
    if bb and bb_own:
        out += p(f"Backbone's headline Sharpe ex-BIL {num(bb_own.get('sharpe_exbil'))} is over its own {integer(bb_own.get('n'))} months "
                 f"({bb_own['start']} to {bb_own['end']}); on the common window it is {num(bb.get('sharpe_exbil'))}.", 'footnote')
    counts = Counter(c['badge'] for c in archive['cards'])
    out += p('Archive: ' + ', '.join(f'{integer(counts[label])} {label}' for label in ('FAIL','VOID','AUDIT NULL')))
    headers = ['Rank','Subject','CAGR diff','Sharpe ex-BIL diff','MaxDD diff (single path, no test)','Label',
               'Total return (subject)','Total return diff','CAGR','Sharpe ex-BIL','MaxDD','Detectable Sharpe gap','Own window','Excess vs core']
    keys = {2:'cagrDiff',3:'sharpeDiff',4:'maxddDiff'}
    out += ('<button type="button" id="lb-cols" aria-controls="leaderboard" aria-expanded="false">Show all columns</button>'
            '<div class="table-scroll" tabindex="0" role="region" aria-label="Leaderboard"><table id="leaderboard">'
            f"<caption>Common window {d['common_window']['start']} to {d['common_window']['end']}; differences vs the {LIVE_CORE}</caption><thead><tr>")
    for i,h in enumerate(headers):
        out += (f'<th scope="col" aria-sort="{"descending" if i==2 else "none"}"><button type="button" data-key="{keys[i]}">{h}</button></th>' if i in keys else f'<th scope="col">{h}</th>')
    out += '</tr></thead><tbody id="ranked-body">'
    rank = 0
    for r in rows:
        if r.get('is_benchmark'):
            shown = '—'
        elif r['id'] in dup:
            shown = f"= {rank}"
        else:
            rank += 1
            shown = integer(rank)
        cls = ' class="benchmark"' if r.get('is_benchmark') else ''
        out += f'<tr{cls} data-subject="{r["id"]}" data-cagr-diff="{r["cagr_diff"]}" data-sharpe-diff="{r["sharpe_diff"]}" data-maxdd-diff="{r["maxdd_diff"]}">'
        cell = lambda key: f'<td data-sort="{r[key]}">{num(r[key]) if key in ("sharpe_diff","sharpe_exbil") else pct(r[key])}</td>'
        link = subject_link(r)
        if r['id'] in dup:
            other = dup[r['id']]
            link += f' <span class="muted">(same series as <a href="{other["id"]}.html">{e(SHORT.get(other["id"], other["name"]))}</a>; ranked once)</span>'
        out += f'<td>{e(shown)}</td><td>{link}</td>'
        out += ''.join(cell(k) for k in ('cagr_diff','sharpe_diff','maxdd_diff'))
        out += f'<td>{e("benchmark (zero line)" if r.get("is_benchmark") else r["label"])}</td>'
        out += ''.join(cell(k) for k in ('total_return','total_return_diff','cagr','sharpe_exbil','maxdd'))
        own = r['own_window']
        out += f'<td>{e(r["power"]["text"])}</td><td>{integer(own["n"])} of {integer(own["months"])} months covered; CAGR diff {pct(own.get("cagr_diff"))}</td><td>{spark(r.get("excess_spark"))}</td></tr>'
    out += '</tbody></table></div>' + SORT_SCRIPT
    out += p('Book 2 and the #6 skew overlay are the same saved series (the overlay is how Book 2 was admitted), so they are ranked once and cross-linked.', 'footnote')
    out += '<section id="void"><h2>VOID runs (not ranked; the test design was void)</h2>'
    out += '<div class="table-scroll" tabindex="0" role="region" aria-label="VOID runs"><table id="void-table"><thead><tr>' + ''.join(f'<th scope="col">{h}</th>' for h in ['Subject','Label','CAGR diff','MaxDD diff (single path, no test)','Total return diff','Months']) + '</tr></thead><tbody>'
    for r in d['void']:
        out += f'<tr data-subject="{r["id"]}"><td>{subject_link(r)}</td>' + ''.join(f'<td>{e(v)}</td>' for v in [r['label'],pct(r['cagr_diff']),pct(r['maxdd_diff']),pct(r['total_return_diff']),integer(r['n'])]) + '</tr>'
    out += '</tbody></table></div></section>'
    ranked = [r for r in rows if not r.get('is_benchmark') and r['id'] not in dup]
    forest = [{'name':SHORT.get(r['id'], short(r['name'])),'value':r['sharpe_diff'],
               'lower':r['sharpe_diff']-r['power']['detectable_sharpe_gap'],'upper':r['sharpe_diff']+r['power']['detectable_sharpe_gap']} for r in ranked]
    opt = charts.forest_plot(forest,x_label='Sharpe ex-BIL diff')
    opt['_hub']['height'] = 120 + 26 * len(forest)
    opt['_hub']['no_legend'] = True
    opt['yAxis']['axisLabel'] = {'width': 140, 'overflow': 'truncate', 'interval': 0, 'fontSize': 11}
    opt['_hub']['table'] = {'headers':['Subject','Sharpe ex-BIL diff','Detectable gap','Months','Power'],
        'rows':[[r['name'],r['sharpe_diff'],r['power']['detectable_sharpe_gap'],integer(r['power']['n']),r['power']['text']] for f,r in zip(forest,ranked)]}
    out += chart('forest','Sharpe differences and detectable gaps',opt,f"Source: data/processed/hub/leaderboard.json; saved returns in the source manifest. Common window, vs the {LIVE_CORE}. Intervals are observed difference ± detectable gap, not confidence intervals.")
    out += chart('scatter','CAGR difference vs MaxDD difference',scatter_option(ranked),f'Source: data/processed/hub/leaderboard.json. Common window, vs the {LIVE_CORE}. Right: higher CAGR; up: shallower drawdown. MaxDD: single path, no test.')
    # Month coordinates are presentation geometry only. The table and tooltips use dates.
    def month(s):
        year,m = map(int,s.split('-')); return year*12+m-1
    timeline = [{'name':SHORT.get(s['id'], short(s['name'])),'value':month(s['own']['start']),'lower':month(s['own']['start']),'upper':month(s['own']['end'])} for s in subjects]
    opt = charts.forest_plot(timeline,x_label='Saved window',zero_line=False)
    opt['xAxis'].update(min=min(r['lower'] for r in timeline), max=max(r['upper'] for r in timeline))
    opt['series'][0]['markArea'] = {'itemStyle':{'color':'#f4f5f7'},'data':[[{'xAxis':month(d['common_window']['start'])},{'xAxis':month(d['common_window']['end'])}]]}
    opt['series'][0]['markLine'] = {'data':[{'xAxis':month(manifest['static_core']['first_month'])}],'label':{'formatter':'Core starts'}}
    opt['_hub']['monthIndex'] = True
    opt['_hub']['no_legend'] = True
    opt['_hub']['height'] = 120 + 26 * len(timeline)
    opt['xAxis']['minInterval'] = 72
    opt['yAxis']['axisLabel'] = {'width': 110, 'overflow': 'truncate', 'interval': 0, 'fontSize': 10}
    opt['series'][0]['markLine']['label'] = {'show': False}  # named in the caption
    opt['_hub']['table'] = {'headers':['Subject','Start','End'],'rows':[[s['name'],s['own']['start'],s['own']['end']] for s in subjects]}
    out += chart('coverage','Own-window coverage',opt,f"Source: data/processed/hub/manifest.json and subjects/*.json; saved series named in each manifest entry. Core starts {manifest['static_core']['first_month']}; shaded: {d['common_window']['label']}.")
    out += forward_tracked_html()
    out += related_html()
    return out + '</article>'


ADDENDUM2_SLOT = None   # Addendum 2 is not published on Pages yet; link slot kept (hub plan).


def related_html():
    items = [('../stage2_robustness.html', 'Stage-two robustness appendix', DOCS / 'methods/stage2_robustness.html')]
    items.append(('../' + stage2.TEACHING, 'Stage-two teaching note: the DeMiguel tilt', DOCS / 'methods' / stage2.TEACHING))
    items.append(('../stage2_addendum3.html', 'Addendum 3: final dispositions and errata', DOCS / 'methods/stage2_addendum3.html'))
    items.append(('../stage2_livecore_recheck.html', 'Live-core recheck for family 2 (correction to Addendum 3 E4)', DOCS / 'methods/stage2_livecore_recheck.html'))
    items.append(('../../notes/stage2_wrap.html', 'CIO stage-2 wrap-up: nothing beat the static core', DOCS / 'notes/stage2_wrap.html'))
    out = '<section id="related"><h2>Related pages</h2><ul>'
    for href, label, path in items:
        out += f'<li><a href="{href}">{e(label)}</a></li>' if path.exists() else f'<li>{e(label)} <span class="muted">(link when published)</span></li>'
    out += ('<li>Addendum 2 to the stage-2 pre-registration <span class="muted">(link when published)</span></li>' if not ADDENDUM2_SLOT
            else f'<li><a href="{ADDENDUM2_SLOT}">Addendum 2</a></li>')
    out += '<li><a href="../justina_round1_scoreboard.html">Archive scoreboard</a></li><li><a href="../index.html">Methods index</a></li></ul></section>'
    return out


def forward_tracked_html():
    """Forward-tracked research lines (not ranked): DeMiguel from demiguel_book_rule.json, A6/B3 from family2_dev.json."""
    if not DEMIGUEL.exists():
        return ''
    d = json.loads(DEMIGUEL.read_text(encoding='utf-8'))
    a, b = d['book_rule']
    core_lbl = d.get('core_label', 'stand-in core only')
    rows = [[f"({a['rule']}) {a['test']}", f"{pct(a['value'])} {a['unit']} (½·Σ|Δw|)", f"limit {pct(a['limit'])}", a['outcome']],
            [f"({b['rule']}) {b['test']} [{core_lbl}]", f"CAGR {pct(b['cagr'])} vs stand-in core {pct(b['core_cagr'])} at {integer(b['cost_bp_one_way'])} bp one-way",
             f"difference {pct(b['diff'])} ({pct(b['diff_at_5bp_one_way'])} at 5 bp one-way)", b['outcome']]]
    src = d['source']
    out = ('<section id="forward-tracked"><h2>Forward-tracked research lines (not ranked)</h2>'
           + p('Tracked forward from 2026-10, the first complete month, against the live core with a month count and a power caveat '
               '(Addendum 3 §1.4). None is a Book candidate. Turnover is textbook one-way, ½·Σ|Δw| per year.')
           + f"<h3>{e(d['name'])}</h3><p><span class=\"badge\">{e(d['status'])}</span> <span class=\"chip\">{e(core_lbl)}</span></p>"
           + p(d['status_note']) + p('Book-eligible: ' + ('yes' if d['book_eligible'] else 'no. It fails the CIO Book rule:'))
           + table(['Book rule', 'Value', 'Threshold / result', 'Outcome'], rows, f'DeMiguel tilt against the CIO Book rule ({core_lbl})')
           + p('Book-rule figures: stand-in core only (70% IVV / 20% QQQ / 10% IJR). ' + (d.get('core_label_note') or ''), 'muted book-rule-caption')
           + p(d['fix_variants_note'])
           + p('Cost convention: ' + d['cost_convention'])
           + p(f"Source: {src['document']}, body sha256 {src['body_sha256_short']}; {src['window']}. "
               'Transcribed to data/processed/stage2/demiguel_book_rule.json.', 'muted'))
    if FAMILY2.exists():
        f = json.loads(FAMILY2.read_text(encoding='utf-8'))
        frows = []
        for c in f['candidates']:
            lv, sv = c['vs_live_core'], c['vs_standin_core']
            fn = ' *' if lv.get('cagr_diff_footnote') else ''
            frows.append([f"{c['id']}: {c['name']}", c['caution'],
                          f"{pp(lv['cagr_diff'])}{fn} at 5 bp; {pp(lv['cagr_diff_10bp'])} at 10 bp ({lv['window']}) "
                          f"[stand-in {pp(sv['cagr_diff_10bp'])} at 10 bp, {sv['window']}]",
                          f"{num(lv['sharpe_diff'])}; CI [{num(lv['sharpe_gap_ci'][0])}, {num(lv['sharpe_gap_ci'][2])}] "
                          f"[stand-in {num(sv['sharpe_diff'])}]",
                          f"{pct(c['turnover_one_way'])} (L1 {pct(c['turnover_l1'])})",
                          f"turnover {c['book_rule']['turnover']}; CAGR at 10 bp {c['book_rule']['cagr_10bp']}"])
        out += ('<h3>Family 2: forward-only (Addendum 3 §1.3)</h3>'
                + table(['Candidate', 'Caution', 'CAGR gap vs live core [stand-in]', 'Sharpe ex-BIL gap vs live core [stand-in]',
                         'Turnover/yr, one-way ½·Σ|Δw|', 'CIO Book rule'], frows,
                        'Family 2 frozen specs A6 and B3: live core first, stand-in core in brackets')
                + ''.join(p('* ' + c['vs_live_core']['cagr_diff_footnote'], 'footnote') for c in f['candidates'] if c['vs_live_core'].get('cagr_diff_footnote'))
                + p(f.get('live_core_note', ''), 'muted')
                + p('Sources: ' + '; '.join(f"{x['file']} ({x['sha256'][:12]}…)" for x in f['sources']) + '. Transcribed to data/processed/stage2/family2_dev.json.', 'muted'))
    return out + '</section>'


def build_hub_pages(page_shell, write_page):
    manifest, leaderboard = load('manifest'), load('leaderboard')
    subjects = [load('subjects/'+entry['id']) for entry in manifest['subjects']]
    archive = json.loads((ROOT/'apps/pages/src/data/archive_verdicts.json').read_text(encoding='utf-8'))
    pages = []
    def write(id, title, body):
        path = f'methods/results/{id}.html'
        write_page(path,page_shell(title,body,prefix='../../',active='methods/index.html',extra_head=HEAD))
        pages.append(path)
    write('index','Results hub: every method against the static core',leaderboard_body(leaderboard,manifest,subjects,archive))
    for id in PILOTS:
        d = next(s for s in subjects if s['id']==id)
        write(id,d['name'],subject_body(d,manifest))
    return pages


if __name__ == '__main__':
    import build_pages
    import build_stage2_pages
    written = build_hub_pages(build_pages.page_shell,build_pages.write_page)
    build_stage2_pages.build_page(build_pages.page_shell,build_pages.write_page,build_pages.DOCS)
    print('Built ' + ', '.join(written) + '; refreshed stage-two robustness appendix.')
