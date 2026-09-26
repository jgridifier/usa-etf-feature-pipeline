"""The shared writer enforces composition before any filesystem mutation."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.gate_results import GateResultError, validate_gate_record, write_gate_results
from usa_etf_features.monthly_panel import load_monthly_panel, panel_provenance

PANEL_CSV = Path(__file__).resolve().parents[1] / 'data/raw/usa_universe_panel_monthly_returns.csv'
PANEL = load_monthly_panel(PANEL_CSV)          # default: complete calendar months only


def composition(status='PASS'):
    return dict(status=status, computable=True, method='m', primary_null='p', method_share=0.,
                null_share=0., max_share=0., opt_out=False, opt_out_reason=None)


def write(out, **kwargs):
    args = dict(gate_id='fake', label='PASS', mechanical='PASS', composition=None,
                tables={'summary': pd.DataFrame({'x': [1]})}, report={}, markdown_lines=['test'],
                monthly_panel=PANEL)
    args.update(kwargs)
    return write_gate_results(out, **args)


def test_fake_gate_cannot_skip_tripwire(tmp_path):
    def new_gate_runner():
        return write(tmp_path / 'new')
    with pytest.raises(GateResultError, match='REFUSING TO RECORD.*composition_tripwire'):
        new_gate_runner()
    assert not (tmp_path / 'new').exists()


def test_pass_record_and_json_safe(tmp_path):
    c = composition()
    c['table'] = pd.DataFrame({'x': [2]})
    write(tmp_path, composition=c, report={'nan': np.nan, 'inf': np.inf, 'n': np.int64(2),
                                         'date': pd.Timestamp('2020-01-01')},
          fields={'book_eligible': {'eligible': True, 'reason': 'beats USMV'}})
    r = json.loads((tmp_path / 'gate_result.json').read_text())
    assert r['label'] == 'PASS' and r['fields']['book_eligible']['eligible']
    assert 'table' not in r['composition'] and (tmp_path / 'composition_tripwire.csv').exists()
    assert r['report'] == {'nan': None, 'inf': None, 'n': 2, 'date': '2020-01-01'}


def test_opt_out_and_unattached(tmp_path):
    write(tmp_path, composition_opt_out_reason='  ticket reason  ')
    assert json.loads((tmp_path / 'gate_result.json').read_text())['composition']['opt_out_reason'] == 'ticket reason'
    write(tmp_path, label='FAIL', mechanical='FAIL')
    assert json.loads((tmp_path / 'gate_result.json').read_text())['composition'] == {'status': 'NOT ATTACHED'}


@pytest.mark.parametrize('over', [
    {'composition_opt_out_reason': ''}, {'composition_opt_out_reason': '  '},
    {'composition': composition('VOID')}, {'composition': {}}, {'label': 'MAYBE'}, {'mechanical': 'pass'},
    {'composition': composition('OPTED OUT')},
    {'composition': composition(), 'composition_opt_out_reason': 'reason'},
    {'label': 'FAIL', 'mechanical': 'PASS'},
    {'label': 'FAIL', 'mechanical': 'PASS', 'composition_opt_out_reason': 'reason'},
    {'label': 'FAIL', 'mechanical': 'FAIL', 'fields': {'book_eligible': {'eligible': True, 'reason': 'x'}}},
    {'fields': {'book_eligible': {'eligible': False, 'reason': ''}}},
    *[{'fields': {key: 'x'}} for key in ('label', 'mechanical', 'composition', 'gate_id', 'monthly_panel')],
])
def test_invalid_records_write_nothing(tmp_path, over):
    with pytest.raises(GateResultError, match='REFUSING TO RECORD'):
        write(tmp_path / 'out', **over)
    assert not (tmp_path / 'out').exists()


def test_archived_refusal_changes_nothing():
    out = Path('data/processed/nonlinear_shrinkage_gmv_v2')
    def hashes():
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    before = hashes()
    with pytest.raises(FileExistsError):
        write(out, label='FAIL', mechanical='FAIL', composition=composition())
    assert hashes() == before


def test_default_load_records_dropped_partial_month(tmp_path):
    prov = panel_provenance(PANEL)
    assert prov.complete_months_only and prov.dropped_partial_month == '2026-09' and prov.source_asof == '2026-09-16'
    assert PANEL.index.max() < pd.Timestamp('2026-09-01')
    write(tmp_path, label='FAIL', mechanical='FAIL')
    r = json.loads((tmp_path / 'gate_result.json').read_text())
    assert r['monthly_panel'] == dict(source=PANEL_CSV.name, complete_months_only=True,
                                      dropped_partial_month='2026-09', source_asof='2026-09-16',
                                      partial_month_reason=None)
    report = (tmp_path / 'gate_report.md').read_text()
    assert '- dropped_partial_month: 2026-09' in report and '- source_asof: 2026-09-16' in report


@pytest.mark.parametrize('panel', [pd.read_csv(PANEL_CSV, index_col=0, parse_dates=True), None,
                                   PANEL.copy().pipe(lambda f: f.attrs.clear() or f)])
def test_raw_read_csv_panel_refused(tmp_path, panel):
    def runner_that_bypasses_the_loader():
        return write(tmp_path / 'out', label='FAIL', mechanical='FAIL', monthly_panel=panel)
    with pytest.raises(GateResultError, match='REFUSING TO RECORD.*load_monthly_panel'):
        runner_that_bypasses_the_loader()
    assert not (tmp_path / 'out').exists()


LEGACY = load_monthly_panel(PANEL_CSV, complete_months_only=False)


@pytest.mark.parametrize('reason', [None, '', '   ', 7])
def test_legacy_panel_requires_written_reason(tmp_path, reason):
    with pytest.raises(GateResultError, match='REFUSING TO RECORD.*partial_month_reason'):
        write(tmp_path / 'out', label='FAIL', mechanical='FAIL', monthly_panel=LEGACY, partial_month_reason=reason)
    assert not (tmp_path / 'out').exists()


def test_reason_on_complete_panel_refused(tmp_path):
    with pytest.raises(GateResultError, match='REFUSING TO RECORD.*partial_month_reason'):
        write(tmp_path / 'out', label='FAIL', mechanical='FAIL', partial_month_reason='not needed')
    assert not (tmp_path / 'out').exists()


def test_legacy_panel_with_reason_recorded_and_printed(tmp_path, caplog):
    write(tmp_path, label='FAIL', mechanical='FAIL', monthly_panel=LEGACY, partial_month_reason='  ticket 12  ')
    r = json.loads((tmp_path / 'gate_result.json').read_text())
    assert r['monthly_panel'] == dict(source=PANEL_CSV.name, complete_months_only=False, dropped_partial_month=None,
                                      source_asof='2026-09-16', partial_month_reason='ticket 12')
    assert '- partial-month opt-out reason: ticket 12' in (tmp_path / 'gate_report.md').read_text()
    assert 'ticket 12' in caplog.text
