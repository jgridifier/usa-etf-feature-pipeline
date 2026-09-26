"""Enforced results writer for v3 and every future gate runner.

Archived v1/v2 writers keep their own paths and are not changed or re-scored.
"""
from pathlib import Path
import json

import pandas as pd

from .gate_metrics import INCOMPLETE_LABEL, final_gate_label
from .nonlinear_shrinkage_gmv_v2 import _json_safe

VALID_LABELS = {"PASS", "FAIL", "VOID", INCOMPLETE_LABEL}


class GateResultError(RuntimeError):
    """A gate record violates the reporting contract."""


def validate_gate_record(*, label, mechanical, composition, composition_opt_out_reason=None, fields=None):
    def refuse(message):
        raise GateResultError("REFUSING TO RECORD: " + message)

    if label not in VALID_LABELS or mechanical not in {"PASS", "FAIL", "VOID"}:
        refuse("invalid label or mechanical reading")
    reason = composition_opt_out_reason
    if reason is not None and (not isinstance(reason, str) or not reason.strip()):
        refuse("composition_tripwire opt-out reason must be non-empty")
    if composition is not None:
        if reason is not None:
            refuse("provide composition or an opt-out reason, not both")
        required = {"status", "computable", "method", "primary_null", "method_share", "null_share",
                    "max_share", "opt_out", "opt_out_reason"}
        if not isinstance(composition, dict) or not required.issubset(composition):
            refuse("composition_tripwire record is malformed")
        if composition['status'] not in {"PASS", "VOID", "NOT COMPUTABLE", "OPTED OUT"}:
            refuse("invalid composition status")
        r = composition['opt_out_reason']
        if composition['status'] == 'OPTED OUT' and (not isinstance(r, str) or not r.strip()):
            refuse("composition opt-out reason must be non-empty")
        effective = final_gate_label(mechanical, composition)
        record = {k: v for k, v in composition.items() if k != 'table'}
    else:
        if label == 'PASS' and reason is None:
            refuse("PASS requires composition_tripwire or a written opt-out reason")
        effective = mechanical
        record = ({'status': 'OPTED OUT', 'opt_out': True, 'opt_out_reason': reason.strip()}
                  if reason is not None else {'status': 'NOT ATTACHED'})
    if label != effective:
        refuse("label is inconsistent with mechanical reading + composition")
    if fields is not None:
        if not isinstance(fields, dict) or {'label', 'mechanical', 'composition', 'gate_id'} & fields.keys():
            refuse("fields contains reserved keys or is not a dict")
        if 'book_eligible' in fields:
            be = fields['book_eligible']
            if (not isinstance(be, dict) or not isinstance(be.get('eligible'), bool)
                    or not isinstance(be.get('reason'), str) or not be['reason'].strip()):
                refuse("book_eligible requires eligible bool and non-empty reason")
            if be['eligible'] and label != 'PASS':
                refuse("book_eligible cannot be true unless label is PASS")
    return record


def write_gate_results(out_dir, *, gate_id, label, mechanical, composition, tables, report,
                       markdown_lines, fields=None, composition_opt_out_reason=None) -> Path:
    record = validate_gate_record(label=label, mechanical=mechanical, composition=composition,
                                 fields=fields, composition_opt_out_reason=composition_opt_out_reason)
    out = Path(out_dir)
    tables = dict(tables)
    if composition is not None and isinstance(composition.get('table'), pd.DataFrame):
        tables['composition_tripwire'] = composition['table']
    if any(Path(name).name != name or name in {'.', '..'} for name in tables):
        raise GateResultError('REFUSING TO RECORD: table names must be simple filenames')
    targets = [out / f'{name}.csv' for name in tables] + [out / 'gate_result.json', out / 'gate_report.md']
    processed = Path(__file__).resolve().parents[2] / 'data/processed'
    if out.resolve().is_relative_to(processed.resolve()) and any(p.exists() for p in targets):
        raise FileExistsError('refusing to overwrite existing processed artifacts')
    payload = json.dumps(_json_safe(dict(gate_id=gate_id, label=label, mechanical=mechanical,
                                        composition=record, fields=fields or {}, report=report)),
                         indent=2, allow_nan=False)
    out.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(out / f'{name}.csv', index=False, date_format='%Y-%m-%d')
    (out / 'gate_result.json').write_text(payload + '\n')
    (out / 'gate_report.md').write_text('\n'.join(markdown_lines) + '\n')
    return out
