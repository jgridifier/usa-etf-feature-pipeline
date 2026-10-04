#!/usr/bin/env python3
"""Results hub HTML from the saved hub JSON; stdlib only, no strategy execution.

All display formatting lives here. Charts use hub_charts; their tables retain
saved observations, rather than exposing plotting offsets as measured data.
"""
from __future__ import annotations

from collections import Counter
from html import escape
import json
import os
from pathlib import Path
import re

import build_stage2_pages as stage2
import hub_charts as charts

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/processed/hub'
DEMIGUEL = ROOT / 'data/processed/stage2/demiguel_book_rule.json'
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
.hub .spark{width:96px;height:24px}.hub .on-page{display:flex;flex-wrap:wrap;gap:.5rem 1.5rem}
@media(max-width:699px){.hub-chart-box{height:260px}.hub{padding:.75rem}}
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
    return f'<p class="muted not-saved">Not saved for this run: {e(source)}</p>'


def source(d, kind='series'):
    return d['sources'].get(kind) or f"data/processed/hub/subjects/{d['id']}.json ({kind})"


def chart_content(id, option, caption, extra=''):
    option['color'] = PALETTE
    for axis, gap in (('xAxis', 30), ('yAxis', 52)):
        if option.get(axis, {}).get('type') in ('value', 'log'):
            option[axis].update(nameLocation='middle', nameGap=gap)
    if option.get('yAxis', {}).get('type') == 'category':
        option['yAxis']['axisLabel'] = {'width': 105, 'overflow': 'truncate', **option['yAxis'].get('axisLabel', {})}
    headers, rows = charts.table_rows(option)
    fmt = pct if option['_hub'].get('percent') else num
    cells = [[fmt(v) if isinstance(v, (int, float)) else text(v) for v in row] for row in rows]
    payload = json.dumps(option, ensure_ascii=False, allow_nan=False, separators=(',', ':')).replace('<', '\\u003c')
    height = option['_hub'].get('height')
    style = f' style="height:{int(height)}px"' if height else ''
    return (p(caption, 'muted') + f'<div class="hub-chart-box" data-hub-chart="opt-{id}"{style} role="img" aria-label="{e(caption)}"></div>'
            f'<script type="application/json" id="opt-{id}">{payload}</script>' + extra
            + '<details><summary>Data table</summary>' + table(headers, cells, caption) + '</details>')


def chart(id, title, option, caption, *, first=False, extra=''):
    return (f'<details class="hub-chart" id="chart-{id}"' + (' open' if first else '') + '>'
            f'<summary>{e(title)}</summary>' + (chart_content(id, option, caption, extra) if option else missing(caption)) + '</details>')


def names(d):
    return {'subject': d['name'], 'core': 'Static core', 'primary_null': 'Primary null',
            **{r['key']: r['label'] for r in d.get('vs_nulls', [])}}


def series(d, values):
    labels = names(d)
    return [{'name': text(labels.get(k, k.replace('_', ' '))), 'values': v} for k, v in values.items() if isinstance(v, list)]


def line(d, dates, values, label, **kw):
    if not dates or not values or not any(v and any(x is not None for x in v) for v in values.values()):
        return None
    return charts.line_chart(dates, series(d, values), y_label=label, **kw)


def power(comparison):
    return (comparison.get('power') or {}).get('text', 'Power not saved for this run')


def comparison(d, c, label):
    if not c:
        return missing(source(d))
    coverage = c.get('coverage')
    window = (f"{integer(coverage['k'])} of {integer(coverage['m'])} months covered by the core; " if coverage else '')
    out = p(f"Over {label} ({window}{c['start']} to {c['end']}, {integer(c['n'])} paired months), {d['name']} returned "
            f"{pct(c['a'].get('total_return'))} vs the core's {pct(c['b'].get('total_return'))}.")
    rows = []
    for key, name in [('total_return', 'Total return'), ('cagr', 'CAGR'), ('sharpe_exbil', 'Sharpe ex-BIL'), ('maxdd', 'MaxDD (single path, no test)')]:
        if key == 'sharpe_exbil' and d['label'] == 'VOID':
            continue
        fmt = num if key == 'sharpe_exbil' else pct
        rows.append([name, *(fmt(c[k].get(key)) for k in ('a', 'b', 'diff'))])
    out += table(['Metric', 'Subject', 'Core', 'Difference'], rows, label)
    rt, st = c.get('return_test') or {}, c.get('sharpe_test') or {}
    out += p(f"HAC return difference: NW t {num(rt.get('nw_t'))}; two-sided p {num(rt.get('p_two_sided'))}.")
    if st and d['label'] != 'VOID':
        out += p(f"LW2008 HAC Sharpe difference: z {num(st.get('z'))}; one-sided p {num(st.get('p_one_sided'))}.")
    return out + p(power(c), 'power')


def dsr_html(d):
    dsr = d.get('dsr') or {}
    corrected = dsr.get('corrected') or dsr.get('grid_reference')
    out = ''
    if dsr.get('grid_reference'):
        out += p(dsr.get('note'))
    if corrected:
        out += table(['DSR ex-BIL (primary)', 'Basis', 'As recorded'],
                     [[num(corrected['dsr_exbil']), text(dsr.get('primary_basis') or 'Grid reference, Sharpe ex-BIL'),
                       num(corrected.get('dsr_rf0_recorded')) + ' (as recorded)']], 'DSR')
        out += p(corrected.get('error_note'))
    else:
        out += p(f"DSR: {text(dsr.get('recorded'))}; {text(dsr.get('recorded_basis'))}.")
    if dsr.get('note') and not dsr.get('grid_reference'):
        out += p(dsr['note'])
    return out


def subject_charts(d):
    out = []
    def add(slot, title, option, kind='series', caption='', extra=''):
        out.append(chart(str(slot), title, option, f"Source: {source(d, kind)}. {caption}", first=slot == 1, extra=extra))
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
    add(9, 'Turnover per rebalance', opt, caption=f"Per year: {pct(t.get('per_year'))}. {text(t.get('basis'))}. {text(t.get('nulls_note'))}.")
    w = d.get('weights') or {}
    opt = charts.stacked_area(w['months'],series(d,w['top']),y_label='Weight') if w.get('top') else None
    if opt:
        opt['yAxis']['max'] = 1
        for s_ in opt['series']:
            s_['areaStyle'] = {'opacity': 0.22}
    add(10, 'Weights over time', opt, 'weights', text(w.get('basis')))
    opt = line(d,w.get('months'),{'Effective N':w.get('effective_n'),'Largest weight (fraction)':w.get('largest_weight')}, 'Concentration')
    add(11, 'Effective N and largest weight',opt,'weights')
    regimes = d.get('regimes') or []
    opt = charts.bar_chart([r['regime'] for r in regimes],series(d,{k:[r['series'].get(k,{}).get('cumulative_return') for r in regimes] for k in ('subject','core','primary_null')}),y_label='Cumulative return',percent=True) if regimes else None
    chips = ''.join(p(f"{r['regime']} · {names(d).get(k,k)}: {v['coverage']['status']}", 'chip') for r in regimes for k,v in r['series'].items() if v['coverage']['status'] != 'in window')
    add(12, 'Regime cumulative returns',opt,'regimes',extra=chips)
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
            opt['series'][0]['markLine'] = {'data':[{'xAxis':core}], 'label':{'formatter':'Core Sharpe ex-BIL'}}
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
    add(16,'Head-to-head power',opt,extra=''.join(p(f'{name}: {power(c)}','power') for name,c in comparisons))
    return ''.join(out)


def window_table(d, rows, title):
    result = []
    for r in rows:
        label = r.get('name',r.get('regime'))
        if 'start' in r: label += f" ({r['start']} to {r['end']})"
        for key, v in r['series'].items():
            coverage = v['coverage']['status']
            if not v['coverage']['k']:
                cells = [coverage] * 3
            else:
                cells = [pct(v.get('cumulative_return')),pct(v.get('ann_vol')),
                         num(v['sharpe_exbil']) if v.get('sharpe_exbil') is not None else 'too few months for a Sharpe']
            result.append([label,names(d).get(key,key),coverage,*cells,r['vs_core_power']['text']])
    return table(['Window','Series','Coverage','Cumulative return','Annual volatility','Sharpe ex-BIL','Power vs core'],result,title)


def source_rows(value, prefix=''):
    if isinstance(value,dict):
        return [row for k,v in value.items() for row in source_rows(v,f'{prefix}.{k}' if prefix else k)]
    if isinstance(value,list):
        return [row for v in value for row in source_rows(v,prefix)] or [[prefix,'none']]
    return [[prefix,text(value)]]


def subject_body(d, manifest):
    parts = []
    core = d.get('vs_core') or {}
    body = comparison(d,core.get('own_window'),'its own window') + comparison(d,core.get('common_window'),'the common window')
    if d['id'] == 'book1':
        body = p('This is the static core benchmark; its difference vs itself is zero by definition. It was not gated: no pre-registered null, trial count or DSR. Other comparisons are reference only.') + body
    if d['label'] == 'VOID':
        body = p(d.get('verdict', {}).get('void_reason')) + p('Reported for transparency; the test design was void.', 'callout') + body
    sensitivity = core.get('standin_sensitivity')
    if sensitivity:
        body += '<details><summary>Stand-in core sensitivity</summary>' + p(sensitivity['label']) + comparison(d,sensitivity,'the sensitivity window') + '</details>'
    body += f'<p><span class="badge">{e(d["label"])}</span></p>'
    if d.get('verdict',{}).get('text'): body += p(d['verdict']['text'])
    if d.get('vintage_note'):
        body += p(d['vintage_note']) + '<p>The #6 skew overlay gets its own page next; for now see <a href="index.html">its hub listing</a>.</p>'
    parts.append(body)
    rows = []
    for r in d.get('vs_nulls',[]):
        rows.append([text(r['label']) + (' (primary)' if r.get('primary') else ''),num(r['diff'].get('sharpe_exbil')),
                     num((r.get('sharpe_test') or {}).get('z')),num((r.get('sharpe_test') or {}).get('p_one_sided')),
                     num((r.get('return_test') or {}).get('nw_t')),integer(r['n']),num(r.get('power',{}).get('detectable_sharpe_gap')),power(r)])
    parts.append(table(['Null','Sharpe ex-BIL diff','z','p (one-sided)','NW t','Months','Detectable gap','Power'],rows,'Own null comparisons') if rows else p('No pre-registered null saved.'))
    own = d['own']; trials = d.get('trials') or {}
    body = p(f"Data / universe: {source(d)}; weights: {source(d,'weights')}. Saved window: {own['start']} to {own['end']}, {integer(own['n'])} months.")
    body += p(f"Trials in the saved registry: {integer(len(trials.get('rows') or []))}. Nulls it had to beat: " + '; '.join(r['label'] for r in d.get('vs_nulls',[])))
    body += p(f"Pre-registration: {d['sources'].get('prereg') or 'not pre-registered'}.")
    gate_rows = []
    for g in d.get('gates') or []:
        value = text(g.get('value'))
        if g['gate'] == 'DSR / C4':
            dsr = d.get('dsr') or {}
            ref = dsr.get('corrected') or dsr.get('grid_reference')
            if ref:
                value = f"{num(ref['dsr_exbil'])} ex-BIL (primary); {num(ref.get('dsr_rf0_recorded'))} as recorded"
                if dsr.get('grid_reference'): value = 'Grid reference only: ' + value
        context = text({k:v for k,v in g.items() if k not in ('gate','value','outcome')})
        if g['gate'] == 'Null comparison (recorded)':
            context += '; ' + '; '.join(f"{r['label']}: {power(r)}" for r in d.get('vs_nulls', []))
        gate_rows.append([g['gate'],value,text(g.get('outcome')),context])
    body += table(['Gate','Value','Outcome','Basis, scope and source'],gate_rows,'Recorded gates and hub recompute')
    body += dsr_html(d)
    parts.append(body)
    parts.append(subject_charts(d))
    parts.append(window_table(d,d.get('regimes') or [],'Regimes') + window_table(d,d.get('stress') or [],'Stress windows'))
    entry = next(r for r in manifest['subjects'] if r['id']==d['id'])
    body = table(['Source / column','Saved value'],source_rows(d['sources'])+source_rows(entry,'manifest'),'Source manifest')
    body += p('Dropped partial month: ' + (', '.join(d.get('partial_months_dropped') or []) or 'none'))
    for label,path in d.get('pages',{}).items():
        target = DOCS / path.split('#')[0]
        href = os.path.relpath(target,DOCS/'methods/results') + ('#'+path.split('#',1)[1] if '#' in path else '')
        body += '<p>' + (f'<a href="{escape(href)}">{e(label)}: {e(path)}</a>' if target.exists() else e(f'{label}: {path}')) + '</p>'
    body += p('Derivation: src/usa_etf_features/hub_data.py; scripts/build_hub_data.py. Saved artifacts only; no strategy or gate re-run.')
    parts.append(body)
    toc = '<p>On this page</p><ul class="on-page">' + ''.join(f'<li><a href="#{id}">{title}</a></li>' for id,title in SECTIONS) + '</ul>'
    return '<article class="hub">' + f'<h1>{e(d["name"])}</h1>' + toc + ''.join(f'<section id="{id}"><h2>{title}</h2>{body}</section>' for (id,title),body in zip(SECTIONS,parts)) + '<p><a href="index.html">Results hub</a></p></article>'


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


SORT_SCRIPT = '''<script>
(() => {
  const table = document.getElementById('leaderboard');
  table.querySelectorAll('button[data-key]').forEach(button => {
    button.addEventListener('click', () => {
      const header = button.closest('th');
      const ascending = header.getAttribute('aria-sort') === 'descending';
      table.querySelectorAll('th[aria-sort]').forEach(th => th.setAttribute('aria-sort', 'none'));
      header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
      const rows = [...table.tBodies[0].rows];
      rows.sort((a,b) => (Number(a.dataset[button.dataset.key]) - Number(b.dataset[button.dataset.key])) * (ascending ? 1 : -1));
      rows.forEach(row => table.tBodies[0].appendChild(row));
    });
  });
})();
</script>'''


def subject_link(r):
    label = 'Backbone' if r['id']=='backbone' else r['name']
    return f'<a href="{r["id"]}.html">{e(label)}</a>' if r['id'] in PILOTS else e(label) + ' <span class="muted">page coming</span>'


def leaderboard_body(d, manifest, subjects, archive):
    title = 'Results hub: every method against the static core'
    out = '<article class="hub"><h1>' + title + '</h1><div class="callout">' + p(d['common_window']['label']) + p(d['benchmark']) + p('Ranked by: '+d['ranked_by']) + '</div>'
    counts = Counter(c['badge'] for c in archive['cards'])
    out += p('Archive: ' + ', '.join(f'{integer(counts[label])} {label}' for label in ('FAIL','VOID','AUDIT NULL')))
    headers = ['Rank','Subject','CAGR diff','Sharpe ex-BIL diff','MaxDD diff (single path, no test)','Label',
               'Total return (subject)','Total return diff','CAGR','Sharpe ex-BIL','MaxDD','Detectable Sharpe gap','Own window','Excess vs core']
    keys = {2:'cagrDiff',3:'sharpeDiff',4:'maxddDiff'}
    out += '<div class="table-scroll" tabindex="0" role="region" aria-label="Leaderboard"><table id="leaderboard"><caption>Common-window leaderboard</caption><thead><tr>'
    for i,h in enumerate(headers):
        out += (f'<th scope="col" aria-sort="{"descending" if i==2 else "none"}"><button type="button" data-key="{keys[i]}">{h}</button></th>' if i in keys else f'<th scope="col">{h}</th>')
    out += '</tr></thead><tbody id="ranked-body">'
    rows = sorted(d['rows'],key=lambda r:r['cagr_diff'],reverse=True)
    for r in rows:
        out += f'<tr data-subject="{r["id"]}" data-cagr-diff="{r["cagr_diff"]}" data-sharpe-diff="{r["sharpe_diff"]}" data-maxdd-diff="{r["maxdd_diff"]}">'
        cell = lambda key: f'<td data-sort="{r[key]}">{num(r[key]) if key in ("sharpe_diff","sharpe_exbil") else pct(r[key])}</td>'
        out += f'<td>{e(integer(r.get("rank")))}</td><td>{subject_link(r)}</td>'
        out += ''.join(cell(k) for k in ('cagr_diff','sharpe_diff','maxdd_diff'))
        out += f'<td>{e("benchmark (zero line)" if r.get("is_benchmark") else r["label"])}</td>'
        out += ''.join(cell(k) for k in ('total_return','total_return_diff','cagr','sharpe_exbil','maxdd'))
        own = r['own_window']
        out += f'<td>{e(r["power"]["text"])}</td><td>{integer(own["n"])} of {integer(own["months"])} months covered; CAGR diff {pct(own.get("cagr_diff"))}</td><td>{spark(r.get("excess_spark"))}</td></tr>'
    out += '</tbody></table></div>' + SORT_SCRIPT
    out += '<section id="void"><h2>VOID runs (not ranked; the test design was void)</h2>'
    out += '<div class="table-scroll" tabindex="0" role="region" aria-label="VOID runs"><table id="void-table"><thead><tr>' + ''.join(f'<th scope="col">{h}</th>' for h in ['Subject','Label','CAGR diff','MaxDD diff (single path, no test)','Total return diff','Months']) + '</tr></thead><tbody>'
    for r in d['void']:
        out += f'<tr data-subject="{r["id"]}"><td>{subject_link(r)}</td>' + ''.join(f'<td>{e(v)}</td>' for v in [r['label'],pct(r['cagr_diff']),pct(r['maxdd_diff']),pct(r['total_return_diff']),integer(r['n'])]) + '</tr>'
    out += '</tbody></table></div></section>'
    ranked = [r for r in rows if not r.get('is_benchmark')]
    forest = [{'name':'Backbone' if r['id']=='backbone' else r['name'],'value':r['sharpe_diff'],
               'lower':r['sharpe_diff']-r['power']['detectable_sharpe_gap'],'upper':r['sharpe_diff']+r['power']['detectable_sharpe_gap']} for r in ranked]
    opt = charts.forest_plot(forest,x_label='Sharpe ex-BIL diff')
    opt['_hub']['height'] = 120 + 26 * len(forest)
    opt['yAxis']['axisLabel'] = {'width': 110, 'overflow': 'truncate', 'interval': 0, 'fontSize': 10}
    opt['_hub']['table'] = {'headers':['Subject','Sharpe ex-BIL diff','Detectable gap','Months','Power'],
        'rows':[[f['name'],r['sharpe_diff'],r['power']['detectable_sharpe_gap'],integer(r['power']['n']),r['power']['text']] for f,r in zip(forest,ranked)]}
    out += chart('forest','Sharpe differences and detectable gaps',opt,'Source: data/processed/hub/leaderboard.json; saved returns in the source manifest. Intervals are observed difference ± detectable gap, not confidence intervals.',first=True)
    opt = charts.scatter_chart([{'name':r['name'],'x':r['cagr_diff'],'y':r['maxdd_diff']} for r in ranked],x_label='CAGR diff',y_label='MaxDD diff',percent=True,quadrant_lines=True)
    out += chart('scatter','CAGR difference vs MaxDD difference',opt,'Source: data/processed/hub/leaderboard.json. Right: higher CAGR; up: shallower drawdown. MaxDD: single path, no test.')
    # Month coordinates are presentation geometry only. The table and tooltips use dates.
    def month(s):
        year,m = map(int,s.split('-')); return year*12+m-1
    timeline = [{'name':s['name'],'value':month(s['own']['start']),'lower':month(s['own']['start']),'upper':month(s['own']['end'])} for s in subjects]
    opt = charts.forest_plot(timeline,x_label='Saved window',zero_line=False)
    opt['xAxis'].update(min=min(r['lower'] for r in timeline), max=max(r['upper'] for r in timeline))
    opt['series'][0]['markArea'] = {'itemStyle':{'color':'#f4f5f7'},'data':[[{'xAxis':month(d['common_window']['start'])},{'xAxis':month(d['common_window']['end'])}]]}
    opt['series'][0]['markLine'] = {'data':[{'xAxis':month(manifest['static_core']['first_month'])}],'label':{'formatter':'Core starts'}}
    opt['_hub']['monthIndex'] = True
    opt['_hub']['height'] = 120 + 26 * len(timeline)
    opt['xAxis']['minInterval'] = 72
    opt['yAxis']['axisLabel'] = {'width': 110, 'overflow': 'truncate', 'interval': 0, 'fontSize': 10}
    opt['series'][0]['markLine']['label'] = {'show': False}  # named in the caption
    opt['_hub']['table'] = {'headers':['Subject','Start','End'],'rows':[[s['name'],s['own']['start'],s['own']['end']] for s in subjects]}
    out += chart('coverage','Own-window coverage',opt,f"Source: data/processed/hub/manifest.json and subjects/*.json; saved series named in each manifest entry. Core starts {manifest['static_core']['first_month']}; shaded: {d['common_window']['label']}.")
    out += forward_tracked_html()
    out += '<section><h2>Related pages</h2><ul><li><a href="../stage2_robustness.html">Stage-two robustness appendix</a></li>'
    if (DOCS/'methods'/stage2.TEACHING).exists():
        out += f'<li><a href="../{stage2.TEACHING}">Stage-two teaching note: the DeMiguel tilt</a></li>'
    out += '<li><a href="../justina_round1_scoreboard.html">Archive scoreboard</a></li><li><a href="../index.html">Methods index</a></li></ul></section></article>'
    return out


def forward_tracked_html():
    """Forward-tracked research lines (not ranked): figures from data/processed/stage2/demiguel_book_rule.json."""
    if not DEMIGUEL.exists():
        return ''
    d = json.loads(DEMIGUEL.read_text(encoding='utf-8'))
    a, b = d['book_rule']
    rows = [[f"({a['rule']}) {a['test']}", f"{pct(a['value'])} {a['unit']}", f"limit {pct(a['limit'])}", a['outcome']],
            [f"({b['rule']}) {b['test']}", f"CAGR {pct(b['cagr'])} vs static core {pct(b['core_cagr'])} at {integer(b['cost_bp_one_way'])} bp one-way",
             f"difference {pct(b['diff'])} ({pct(b['diff_at_5bp_one_way'])} at 5 bp one-way)", b['outcome']]]
    src = d['source']
    return ('<section id="forward-tracked"><h2>Forward-tracked research lines (not ranked)</h2>'
            f"<p><strong>{e(d['name'])}</strong> · <span class=\"badge\">{e(d['status'])}</span></p>"
            + p(d['status_note']) + p('Book-eligible: ' + ('yes' if d['book_eligible'] else 'no. It fails the CIO Book rule:'))
            + table(['Book rule', 'Value', 'Threshold / result', 'Outcome'], rows, 'DeMiguel tilt against the CIO Book rule')
            + p(b['core_basis'], 'muted') + p(d['fix_variants_note'])
            + p('Cost convention: ' + d['cost_convention'])
            + p(f"Source: {src['document']}, body sha256 {src['body_sha256_short']}; {src['window']}. "
                'Transcribed to data/processed/stage2/demiguel_book_rule.json.', 'muted')
            + '</section>')


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
