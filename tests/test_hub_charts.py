"""Portable options and a shared restrained palette prevent browser/export drift."""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.hub_charts import THEME, snapshot_options, table_rows, line_chart, bar_chart

ALLOWED = {'#1a1410', '#3f434a', '#6b7079', '#c3c7cf', '#f4f5f7', '#1c2d6b',
           '#0e1a42', '#858a94', '#5b6ba8', '#b8bcc4', '#ffffff', '#000000'}


def test_theme_parity_and_colors():
    js = (ROOT / 'docs/assets/hub-theme.js').read_text()
    assert json.loads(re.search(r'const HUB_THEME = (\{.*\});', js, re.S)[1]) == THEME
    def check_colors(value, color_field=False):
        if isinstance(value, dict):
            for key, child in value.items():
                check_colors(child, key.lower().endswith('color'))
        elif isinstance(value, list):
            for child in value:
                check_colors(child, color_field)
        elif color_field:
            assert re.fullmatch(r'#[0-9a-fA-F]{6}', value), value
            assert value in ALLOWED or value[1:3] == value[3:5] == value[5:7]

    check_colors(THEME)


def test_snapshots_and_accessibility():
    for name, option in snapshot_options().items():
        encoded = json.dumps(option, indent=2, allow_nan=False) + '\n'
        assert encoded == (ROOT / f'tests/data/hub_chart_snapshots/{name}.json').read_text()
        assert option['animation'] is False
        assert option['aria']['enabled']
        assert 'click' in option['tooltip']['triggerOn']
        headers, rows = table_rows(option)
        assert rows and all(len(row) == len(headers) for row in rows)
        assert any(None in row for row in rows)
        for series in option['series']:
            if series['type'] == 'line':
                assert series['connectNulls'] is False


def test_optional_axes_and_original_values():
    series = [{'name': 'A', 'values': [1.234567, None, 3]}]
    option = line_chart(['a', 'b', 'c'], series, y_label='Value', log_y=True)
    assert option['yAxis']['type'] == 'log'
    assert option['series'][0]['data'] == series[0]['values']
    assert table_rows(option)[1][1] == ['b', None]
    assert bar_chart(['a', 'b', 'c'], series, y_label='Value')['xAxis']['type'] == 'category'
