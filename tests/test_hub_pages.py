"""PR C: saved-data provenance, page contract, accessible chart fallbacks."""
import copy
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_hub_pages as hub
import build_pages
import hub_charts


@pytest.fixture(scope='module')
def built():
    out = {}
    paths = hub.build_hub_pages(build_pages.page_shell, lambda path, html: out.__setitem__(path,html))
    assert paths == list(out)
    return out


def main_text(raw):
    raw = raw[raw.index('<main'):raw.index('</main>')]
    raw = re.sub(r'<script\b.*?</script>', '', raw, flags=re.S)
    return unescape(re.sub(r'<[^>]*>', ' ', raw))


def figures(value):
    # Dates and numeric fragments embedded in identifiers are labels, not figures.
    value = re.sub(r'\b\d{4}-\d{2}(?:-\d{2})?\b', '', value)
    return set(re.findall(r'(?<![\w.])[+−-]?\d+(?:\.\d+)?%?(?!\w|\.\d)',value))


def allowed_numbers(value):
    if isinstance(value,dict):
        return set().union(*(allowed_numbers(v) for v in value.values()))
    if isinstance(value,list):
        return set().union(*(allowed_numbers(v) for v in value))
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        result = {hub.num(value),hub.pct(value)}
        if int(value)==value: result.add(hub.integer(value))
        return result
    # Recorded verdicts, power sentences, dates and source identifiers are saved
    # prose too. Preserve their numbers verbatim rather than manufacturing leaves.
    return figures(value) if isinstance(value,str) else set()


@pytest.mark.parametrize('id',('index',*hub.PILOTS))
def test_rebuild_and_every_visible_figure_from_json(built,id):
    path = f'methods/results/{id}.html'
    assert built[path] == (ROOT/'docs'/path).read_text()
    manifest = hub.load('manifest')
    data = hub.load('leaderboard' if id=='index' else 'subjects/'+id)
    inputs = [data]
    if id=='index':
        archive = json.loads((ROOT/'apps/pages/src/data/archive_verdicts.json').read_text())
        inputs += [manifest,dict(hub.Counter(c['badge'] for c in archive['cards']))]
        inputs += [json.loads(hub.DEMIGUEL.read_text())]
    else:
        inputs += [next(s for s in manifest['subjects'] if s['id']==id)]
    allowed = allowed_numbers(inputs)
    actual = figures(main_text(built[path]))
    assert actual <= allowed, actual-allowed


def test_changed_data_changes_rendering():
    data = hub.load('subjects/schur')
    altered = copy.deepcopy(data)
    altered['vs_core']['common_window']['diff']['cagr'] = -0.876
    before = hub.subject_body(data,hub.load('manifest'))
    after = hub.subject_body(altered,hub.load('manifest'))
    assert before != after and hub.pct(-0.876) in main_text('<main>'+after+'</main>')


def test_leaderboard_contract(built):
    raw = built['methods/results/index.html']
    data = hub.load('leaderboard')
    assert raw.index(data['common_window']['label']) < raw.index('<table')
    assert data['benchmark'] in main_text(raw)
    ranked = re.search(r'<tbody id="ranked-body">(.*?)</tbody>',raw,re.S)[1]
    rows = re.findall(r'<tr data-subject="([^"]+)".*?</tr>',ranked,re.S)
    assert rows == [r['id'] for r in sorted(data['rows'],key=lambda r:r['cagr_diff'],reverse=True)]
    benchmark = re.search(r'<tr data-subject="book1".*?</tr>',ranked,re.S)[0]
    assert '<td>—</td>' in benchmark and 'benchmark (zero line)' in benchmark
    void = re.search(r'<table id="void-table">(.*?)</table>',raw,re.S)[1]
    assert 'Sharpe' not in void and 'DSR' not in void
    for row in data['void']:
        assert f'data-subject="{row["id"]}"' not in ranked
        assert f'data-subject="{row["id"]}"' in void
    for key in ('cagrDiff','sharpeDiff','maxddDiff'):
        assert f'data-key="{key}"' in raw
    assert 'aria-sort="descending"' in raw
    for row in data['rows']:
        assert f'href="{row["id"]}.html"' in raw if row['id'] in hub.PILOTS else f'href="{row["id"]}.html"' not in raw
    assert 'Backbone' in ranked
    for r in data['rows']:
        assert r['power']['text'] in main_text(raw)


class ChartParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.details = []; self.charts = []; self.slots = []; self.scripts = []
    def handle_starttag(self,tag,attrs):
        attrs = dict(attrs)
        if tag=='details':
            self.details.append(attrs)
            if attrs.get('class')=='hub-chart': self.slots.append(attrs)
        if 'data-hub-chart' in attrs:
            assert any(d.get('class')=='hub-chart' for d in self.details)
            assert attrs.get('role')=='img' and attrs.get('aria-label')
            self.charts.append(attrs['data-hub-chart'])
        if tag=='script' and 'src' in attrs: self.scripts.append(attrs['src'])
    def handle_endtag(self,tag):
        if tag=='details': self.details.pop()


@pytest.mark.parametrize('id',hub.PILOTS)
def test_subject_order_slots_and_power(built,id):
    raw = built[f'methods/results/{id}.html']
    positions = [raw.index(f'<section id="{anchor}"><h2>{title}</h2>') for anchor,title in hub.SECTIONS]
    assert positions == sorted(positions)
    assert re.search(r'<section[^>]*><h2>(.*?)</h2>',raw)[1]=='Result vs the static core'
    parser = ChartParser(); parser.feed(raw)
    assert [s['id'] for s in parser.slots]==[f'chart-{n}' for n in range(1,17)]
    assert 'open' in parser.slots[0] and all('open' not in s for s in parser.slots[1:])
    assert raw.count('<summary>Data table</summary>')==len(parser.charts)
    d = hub.load('subjects/'+id)
    comparisons = [c for c in d['vs_core'].values() if c] + d['vs_nulls']
    visible = main_text(raw)
    assert visible.count('detect a Sharpe gap of about') >= len(comparisons)
    for c in comparisons:
        assert c['power']['text'] in visible
        assert str(c['power']['n']) in c['power']['text']
        assert hub.num(c['power']['detectable_sharpe_gap']) in c['power']['text']
    for r in d['regimes']+d['stress']:
        assert r['vs_core_power']['text'] in visible
        for v in r['series'].values(): assert v['coverage']['status'] in visible
    assert 'single path, no test' in visible


@pytest.mark.parametrize('id',('index',*hub.PILOTS))
def test_scripts_palette_and_labels(built,id):
    raw = built[f'methods/results/{id}.html']
    parser = ChartParser(); parser.feed(raw)
    assert parser.scripts == ['../../assets/vendor/echarts-6.1.0.custom.min.js','../../assets/hub-theme.js','../../assets/hub-charts.js','../../assets/nav.js']
    assert not re.search(r'\bVT\b',main_text(raw))
    for script in parser.scripts:
        assert raw.count(f'src="{script}" defer')==1
    for payload in re.findall(r'<script type="application/json"[^>]*>(.*?)</script>',raw,re.S):
        option = json.loads(payload)
        assert option['color']==hub.PALETTE
        headers, rows = hub_charts.table_rows(option)
        assert headers and rows
    assert 'width:100%;height:300px' in raw and 'height:260px' in raw
    assert 'overflow-x:auto' in raw


def test_dsr_display(built):
    raw = built['methods/results/book2.html']
    d = hub.load('subjects/book2')['dsr']
    primary = hub.num(d['grid_reference']['dsr_exbil'])
    recorded = hub.num(d['grid_reference']['dsr_rf0_recorded'])
    dsr_table = re.search(r'<table><caption>DSR</caption>.*?</table>',raw,re.S)[0]
    assert dsr_table.index(primary) < dsr_table.index(recorded+' (as recorded)')
    assert d['grid_reference']['error_note'] in main_text(raw)
    # Book 2's DSR note (from #53): eligibility never rested on DSR (N = 1, PSR only).
    assert d['note'] in main_text(raw) and 'Eligibility never rested on DSR' in raw
    schur = hub.load('subjects/schur')['dsr']
    assert schur['recorded'] in main_text(built['methods/results/schur.html'])
    assert schur['recorded_basis'] in main_text(built['methods/results/schur.html'])


def test_null_safe_chart_inputs_and_generic_subjects():
    manifest = hub.load('manifest')
    for entry in manifest['subjects']:
        assert hub.subject_body(hub.load('subjects/'+entry['id']),manifest)
    d = hub.load('subjects/schur')
    for key in ('curves','rolling_sharpe','calendar_years','scatter_vs_core','turnover','weights','regimes','stress','trials','dsr'):
        d[key] = None
    raw = hub.subject_charts(d)
    assert raw.count('class="hub-chart"')==16
    assert 'Not saved for this run: Source: data/processed/schur_allocator/weights.csv' in raw


def test_demiguel_forward_tracked_from_data(built):
    raw = built['methods/results/index.html']
    d = json.loads(hub.DEMIGUEL.read_text())
    section = re.search(r'<section id="forward-tracked">.*?</section>', raw, re.S)[0]
    text = main_text('<main>' + section + '</main>')
    a, b = d['book_rule']
    for v in (a['value'], a['limit'], b['cagr'], b['core_cagr'], b['diff']):
        assert hub.pct(v) in text
    assert 'forward-tracked research line' in text and 'Not a holdout candidate' in text
    assert d['source']['body_sha256_short'] in text and 'two-way' in text
    ranked = re.search(r'<tbody id="ranked-body">(.*?)</tbody>', raw, re.S)[1]
    assert 'demiguel' not in ranked.lower()
    assert f'href="../{hub.stage2.TEACHING}"' in raw and 'stage2_demiguel_kwz' not in raw
