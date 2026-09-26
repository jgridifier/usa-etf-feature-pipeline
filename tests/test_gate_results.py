"""The shared writer enforces composition before any filesystem mutation."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.gate_results import GateResultError, validate_gate_record, write_gate_results


def composition(status='PASS'):
    return dict(status=status, computable=True, method='m', primary_null='p', method_share=0.,
                null_share=0., max_share=0., opt_out=False, opt_out_reason=None)


def write(out, **kwargs):
    args = dict(gate_id='fake', label='PASS', mechanical='PASS', composition=None,
                tables={'summary': pd.DataFrame({'x': [1]})}, report={}, markdown_lines=['test'])
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
    *[{'fields': {key: 'x'}} for key in ('label', 'mechanical', 'composition', 'gate_id')],
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
