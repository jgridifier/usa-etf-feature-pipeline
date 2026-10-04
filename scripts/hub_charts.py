"""Portable chart options keep static pages and accessible tables in sync."""
import argparse
import json
from pathlib import Path

PALETTE = ['#1c2d6b', '#1a1410', '#858a94', '#5b6ba8', '#3f434a', '#b8bcc4']
THEME = {
    'color': PALETTE, 'backgroundColor': '#ffffff',
    'textStyle': {'color': '#3f434a'},
    'title': {'textStyle': {'color': '#1a1410'}},
    'legend': {'textStyle': {'color': '#3f434a'}, 'inactiveColor': '#b8bcc4',
               'borderColor': '#c3c7cf', 'inactiveBorderColor': '#b8bcc4',
               'pageIconColor': '#1c2d6b', 'pageIconInactiveColor': '#b8bcc4',
               'pageTextStyle': {'color': '#3f434a'}},
    'tooltip': {'backgroundColor': '#ffffff', 'borderColor': '#c3c7cf',
                'textStyle': {'color': '#1a1410'},
                'axisPointer': {'lineStyle': {'color': '#6b7079'},
                                'crossStyle': {'color': '#6b7079'}}},
    'markLine': {'lineStyle': {'color': '#6b7079'}, 'label': {'color': '#3f434a'}},
    'markArea': {'itemStyle': {'color': '#f4f5f7'}, 'label': {'color': '#6b7079'}},
    'dataZoom': {'backgroundColor': '#f4f5f7', 'fillerColor': '#b8bcc4',
                 'borderColor': '#c3c7cf', 'handleStyle': {'color': '#1c2d6b'}},
}
for _axis in ('categoryAxis', 'valueAxis', 'logAxis', 'timeAxis'):
    THEME[_axis] = {'axisLine': {'lineStyle': {'color': '#c3c7cf'}},
                    'axisTick': {'lineStyle': {'color': '#c3c7cf'}},
                    'axisLabel': {'color': '#6b7079'},
                    'nameTextStyle': {'color': '#3f434a'},
                    'splitLine': {'lineStyle': {'color': ['#c3c7cf']}}}


def _base(percent=False, item=False):
    return {'animation': False, 'aria': {'enabled': True},
            'tooltip': {'trigger': 'item' if item else 'axis', 'confine': True,
                        'triggerOn': 'mousemove|click'},
            'grid': {'left': 12, 'right': 16, 'top': 40, 'bottom': 56, 'containLabel': True},
            'legend': {'type': 'scroll', 'bottom': 0},
            '_hub': {'percent': percent, 'decimals': 2}, 'series': []}


def _table(option, headers, rows):
    option['_hub']['table'] = {'headers': headers, 'rows': rows}
    return option


def table_rows(option):
    """Return original values, including gaps and interval bounds, for HTML tables."""
    table = option['_hub']['table']
    return table['headers'], table['rows']


def _reference(axis):
    return {'symbol': ['none', 'none'], 'label': {'show': False},
            'lineStyle': {'color': '#6b7079', 'type': 'dashed'}, 'data': [{axis: 0}]}


def line_chart(dates, series, *, y_label, log_y=False, percent=False,
               mark_areas=None, band=None, zero_line=False):
    option = _base(percent)
    option.update(xAxis={'type': 'category', 'data': list(dates), 'boundaryGap': False},
                  yAxis={'type': 'log' if log_y else 'value', 'name': y_label},
                  dataZoom=[{'type': 'inside'}])
    for s in series:
        option['series'].append({'name': s['name'], 'type': 'line', 'data': list(s['values']),
                                 'connectNulls': False, 'showSymbol': False,
                                 'lineStyle': {'type': 'dashed' if s.get('dashed') else 'solid'}})
    if option['series']:
        if zero_line:
            option['series'][0]['markLine'] = _reference('yAxis')
        if mark_areas:
            option['series'][0]['markArea'] = {
                'itemStyle': {'color': '#f4f5f7', 'opacity': 0.6},
                'label': {'color': '#6b7079'},
                'data': [[{'name': a['name'], 'xAxis': a['start']}, {'xAxis': a['end']}]
                         for a in mark_areas]}
    headers = ['Date'] + [s['name'] for s in series]
    columns = [s['values'] for s in series]
    if band:
        lower, upper = band['lower'], band['upper']
        valid = [lo is not None and hi is not None for lo, hi in zip(lower, upper)]
        for suffix, values, opacity in (
            ('lower', [lo if ok else None for lo, ok in zip(lower, valid)], 0),
            ('range', [hi - lo if ok else None for lo, hi, ok in zip(lower, upper, valid)], 0.25),
        ):
            option['series'].append({'name': band['name'] + ' ' + suffix, 'type': 'line',
                                     'stack': '__hub_band', 'stackStrategy': 'all',
                                     'data': values, 'connectNulls': False, 'symbol': 'none',
                                     'lineStyle': {'opacity': 0}, 'silent': True,
                                     'tooltip': {'show': False},
                                     'areaStyle': {'color': '#858a94', 'opacity': opacity}})
        option['legend']['data'] = [s['name'] for s in series]
        headers += [band['name'] + ' lower', band['name'] + ' upper']
        columns += [lower, upper]
    return _table(option, headers, [[d] + [c[i] for c in columns] for i, d in enumerate(dates)])


def bar_chart(categories, series, *, y_label, percent=False, horizontal=False):
    option = _base(percent)
    category = {'type': 'category', 'data': list(categories)}
    value = {'type': 'value', 'name': y_label}
    option.update(xAxis=value if horizontal else category, yAxis=category if horizontal else value)
    option['series'] = [{'name': s['name'], 'type': 'bar', 'data': list(s['values'])} for s in series]
    return _table(option, ['Category'] + [s['name'] for s in series],
                  [[c] + [s['values'][i] for s in series] for i, c in enumerate(categories)])


def scatter_chart(points, *, x_label, y_label, percent=False, diagonal=False, quadrant_lines=False):
    option = _base(percent, True)
    option.update(xAxis={'type': 'value', 'name': x_label}, yAxis={'type': 'value', 'name': y_label})
    main = {'name': y_label, 'type': 'scatter',
            'data': [{'name': p['name'], 'value': [p['x'], p['y']]} for p in points]}
    option['series'] = [main]
    if quadrant_lines:
        main['markLine'] = _reference('xAxis')
        main['markLine']['data'].append({'yAxis': 0})
    if diagonal:
        values = [p[k] for p in points for k in ('x', 'y') if p[k] is not None]
        if values:
            main.setdefault('markLine', _reference('xAxis'))
            if not quadrant_lines:
                main['markLine']['data'] = []
            main['markLine']['data'].append([{'coord': [min(values), min(values)]},
                                             {'coord': [max(values), max(values)]}])
    return _table(option, ['Name', x_label, y_label], [[p['name'], p['x'], p['y']] for p in points])


def stacked_area(dates, series, *, y_label, percent=True):
    option = line_chart(dates, series, y_label=y_label, percent=percent)
    for s in option['series']:
        s.update(stack='total', areaStyle={'opacity': 0.4})
    return option


def forest_plot(rows, *, x_label, zero_line=True):
    option = _base(item=True)
    option.update(xAxis={'type': 'value', 'name': x_label},
                  yAxis={'type': 'category', 'data': [r['name'] for r in rows], 'inverse': True})
    points = {'name': x_label, 'type': 'scatter',
              'data': [[r['value'], i] for i, r in enumerate(rows)]}
    if zero_line:
        points['markLine'] = _reference('xAxis')
    option['series'] = [points]
    # An invisible offset and a thin stacked bar form each interval; scatter caps
    # keep the entire error-bar construction portable as JSON (including SSR).
    valid = [r['lower'] is not None and r['upper'] is not None for r in rows]
    for name, values, opacity in (
        ('Interval offset', [r['lower'] if ok else None for r, ok in zip(rows, valid)], 0),
        ('Interval', [r['upper'] - r['lower'] if ok else None for r, ok in zip(rows, valid)], 1),
    ):
        option['series'].append({'name': name, 'type': 'bar', 'stack': '__hub_interval',
                                 'stackStrategy': 'all', 'barWidth': 2, 'data': values,
                                 'silent': True, 'tooltip': {'show': False},
                                 'itemStyle': {'color': '#1c2d6b', 'opacity': opacity}})
    for bound in ('lower', 'upper'):
        option['series'].append({'name': 'Interval ' + bound, 'type': 'scatter',
                                 'data': [[r[bound] if ok else None, i]
                                          for i, (r, ok) in enumerate(zip(rows, valid))],
                                 'symbol': 'rect', 'symbolSize': [2, 10], 'silent': True,
                                 'itemStyle': {'color': '#1c2d6b'}, 'tooltip': {'show': False}})
    option['legend']['data'] = [x_label]
    return _table(option, ['Name', x_label, 'Lower', 'Upper'],
                  [[r['name'], r['value'], r['lower'], r['upper']] for r in rows])


def snapshot_options():
    dates = [f'2025-{m:02d}' for m in range(1, 7)]
    series = [{'name': 'Strategy', 'values': [0.1, 0.2, None, -0.1, 0.3, 0.4]},
              {'name': 'Benchmark', 'values': [0.05, 0.1, 0.15, 0.1, 0.2, 0.3], 'dashed': True}]
    return {
        'line_chart': line_chart(dates, series, y_label='Return', percent=True, zero_line=True,
                                 mark_areas=[{'name': 'Window', 'start': dates[1], 'end': dates[3]}],
                                 band={'name': 'Range', 'lower': [-0.1, 0, None, -0.2, 0.1, 0.2],
                                       'upper': [0.2, 0.3, None, 0.1, 0.4, 0.5]}),
        'bar_chart': bar_chart(dates, series, y_label='Return', percent=True, horizontal=True),
        'scatter_chart': scatter_chart([{'name': 'A', 'x': -0.1, 'y': 0.2},
                                         {'name': 'B', 'x': 0.3, 'y': 0.4},
                                         {'name': 'Gap', 'x': None, 'y': 0.1}],
                                        x_label='Benchmark', y_label='Strategy', percent=True,
                                        diagonal=True, quadrant_lines=True),
        'stacked_area': stacked_area(dates, series, y_label='Weight'),
        'forest_plot': forest_plot([{'name': 'A', 'value': 0.2, 'lower': -0.1, 'upper': 0.4},
                                    {'name': 'B', 'value': -0.1, 'lower': -0.3, 'upper': 0.1},
                                    {'name': 'Gap', 'value': None, 'lower': None, 'upper': None}],
                                   x_label='Estimate'),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-snapshots', action='store_true')
    if parser.parse_args().write_snapshots:
        directory = Path(__file__).resolve().parents[1] / 'tests/data/hub_chart_snapshots'
        directory.mkdir(parents=True, exist_ok=True)
        for name, option in snapshot_options().items():
            (directory / f'{name}.json').write_text(json.dumps(option, indent=2, allow_nan=False) + '\n')
