"""Quant's September stats recompute is applied as ruled (CIO/PM, 2026-10-04) and nowhere else.

Source: data/processed/hub/sept_fix_stat_recompute.csv (vendored verbatim, sha256 fe895441…), applied by
scripts/apply_sept_fix_stat_recompute.py. Checks the vendored bytes, that every applied summary field equals
the CSV's new_value, that the skew-managed NW t vs EW / MinVar / ERC carry their 67-month (to 2026-08) label,
that the 86 archived DSR rows are complete-months-only rows ending 2026-08-31, that the #6 grid DSR reads
0.5625 everywhere the hub shows it (0.53 survives only as the superseded value), and that the E6 lab note renders.
"""
from __future__ import annotations

import hashlib
import html as htmllib
import json
import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / 'data' / 'processed' / 'hub'
SRC = HUB / 'sept_fix_stat_recompute.csv'
NOTES = HUB / 'sept_fix_stat_recompute_NOTES.md'
SRC_SHA = 'fe8954415fa028f954cc662d79d52689e1c3e6a93caf5233f1ba539a460f1f3c'
NOTES_SHA = '6fa41fc1d3f7c3539bedb75ce44ea177041cfab6cea39c3c5969e9943a680e9e'
SPEC6 = 'SM_option_a_vt_L63_SL21_g0p5_realizedamaya_cvar5'
APPLIED = {
    'data/processed/live/vol_target_oos_summary.csv': ['Sharpe_CI_L', 'Sharpe_CI_U'],
    'docs/data/vol_target_oos_summary.csv': ['Sharpe_CI_L', 'Sharpe_CI_U'],
    'data/processed/live/skew_managed_gatefirst_summary.csv': ['Sharpe_CI_L', 'Sharpe_CI_U', 'OOS_skewness',
                                                               'OOS_pct_neg_months', 'NW_t_vs_EW', 'NW_t_vs_MinVar', 'NW_t_vs_ERC'],
}
EXPECTED = {  # old -> new, as reported to PM
    ('data/processed/live/vol_target_oos_summary.csv', 'Sharpe_CI_L'): 0.2868385869,
    ('data/processed/live/vol_target_oos_summary.csv', 'Sharpe_CI_U'): 2.046157119,
    ('data/processed/live/skew_managed_gatefirst_summary.csv', 'Sharpe_CI_L'): 0.5268445551,
    ('data/processed/live/skew_managed_gatefirst_summary.csv', 'Sharpe_CI_U'): 2.221127833,
    ('data/processed/live/skew_managed_gatefirst_summary.csv', 'OOS_skewness'): 0.1621248349,
    ('data/processed/live/skew_managed_gatefirst_summary.csv', 'OOS_pct_neg_months'): 0.3529411765,
    ('data/processed/live/skew_managed_gatefirst_summary.csv', 'NW_t_vs_EW'): 1.990039955,
    ('data/processed/live/skew_managed_gatefirst_summary.csv', 'NW_t_vs_MinVar'): 2.888134571,
    ('data/processed/live/skew_managed_gatefirst_summary.csv', 'NW_t_vs_ERC'): 2.216736315,
}


@pytest.fixture(scope='module')
def q():
    return pd.read_csv(SRC, dtype=str, keep_default_na=False)


def _summary(rel):
    df = pd.read_csv(ROOT / rel, dtype=str, keep_default_na=False)
    assert len(df) == 1
    return df.iloc[0]


def test_vendored_source_is_byte_for_byte():
    assert hashlib.sha256(SRC.read_bytes()).hexdigest() == SRC_SHA
    assert hashlib.sha256(NOTES.read_bytes()).hexdigest() == NOTES_SHA
    script = (ROOT / 'scripts' / 'apply_sept_fix_stat_recompute.py').read_text(encoding='utf-8')
    assert SRC_SHA in script


@pytest.mark.parametrize('rel', sorted(APPLIED))
def test_summary_fields_equal_quants_new_values(q, rel):
    row = _summary(rel)
    for f in APPLIED[rel]:
        src = q[(q.file == rel) & (q.field == f)]
        assert len(src) == 1, (rel, f)
        assert float(row[f]) == pytest.approx(float(src.iloc[0].new_value), abs=1e-12), (rel, f)
        exp = EXPECTED.get((rel.replace('docs/data/', 'data/processed/live/'), f))
        assert exp is not None and float(row[f]) == pytest.approx(exp, abs=1e-9), (rel, f)


def test_both_vol_target_summary_copies_agree():
    a, b = _summary('data/processed/live/vol_target_oos_summary.csv'), _summary('docs/data/vol_target_oos_summary.csv')
    assert a.to_dict() == b.to_dict()


def test_skew_nulls_t_stats_are_labelled_67_months_to_2026_08(q):
    row = _summary('data/processed/live/skew_managed_gatefirst_summary.csv')
    label = row['NW_t_vs_nulls_window']
    assert '67 months' in label and 'to 2026-08' in label and '2021-02..2026-08' in label
    assert 'awaits a re-run' in label and 'fe895441' in label
    for f in ('NW_t_vs_EW', 'NW_t_vs_MinVar', 'NW_t_vs_ERC'):
        src = q[(q.file == 'data/processed/live/skew_managed_gatefirst_summary.csv') & (q.field == f)].iloc[0]
        assert src.window_end == '2026-08' and int(src['T']) == 67, f


def test_out_of_scope_fields_are_untouched(q):
    """CVaR5 and NW t vs Book 2 / Option A were not part of the ruling; their values stay as committed."""
    skew = _summary('data/processed/live/skew_managed_gatefirst_summary.csv')
    for f in ('OOS_CVaR5', 'NW_t_vs_Book2'):
        src = q[(q.file == 'data/processed/live/skew_managed_gatefirst_summary.csv') & (q.field == f)]
        if len(src) and f in skew:
            assert float(skew[f]) == pytest.approx(float(src.iloc[0].old_value), abs=1e-6), f


def test_dsr_archive_rows_are_complete_months_only(q):
    d = pd.read_csv(HUB / 'dsr_exbil_recompute.csv', dtype=str, keep_default_na=False)
    assert '2026-09-16' not in set(d.window_end)
    rows = q[q.field == 'dsr_exbil [complete months only]'].set_index('subject')
    assert len(rows) == 86
    hit = d[d.trial.isin(rows.index)]
    assert len(hit) == 86
    for _, r in hit.iterrows():
        s = rows.loc[r.trial]
        assert r.window_end == '2026-08-31' and int(r['T']) == int(s['T']), r.trial
        assert float(r.dsr_exbil) == pytest.approx(float(s.new_value), abs=1e-12), r.trial
        assert r.rf_file.startswith('data/raw/usa_universe_panel_monthly_returns.csv (BIL')
        for c in ('dsr_exbil_blp_ownvar', 'own_registry_var_monthly', 'skew', 'kurt', 'bil_share'):
            assert r[c] == '', (r.trial, c)
    six = d[d.trial == SPEC6].iloc[0]
    assert float(six.dsr_exbil) == pytest.approx(0.5625, abs=1e-4) and int(six['T']) == 67
    assert (HUB / 'dsr_exbil_recompute.csv').read_bytes().count(b'\r\n') == len(d) + 1  # CRLF kept


@pytest.mark.parametrize('sid', ['backbone', 'book2', 'skew_overlay'])
def test_hub_shows_corrected_grid_dsr(sid):
    d = json.loads((HUB / 'subjects' / f'{sid}.json').read_text(encoding='utf-8'))['dsr']
    ref = d.get('corrected') or d.get('grid_reference')
    assert ref['trial'] == SPEC6 and ref['dsr_exbil'] == pytest.approx(0.5625, abs=1e-4)
    assert ref['months'] == 67 and ref['window'] == '2021-02 to 2026-08'
    text = json.dumps(d, ensure_ascii=False).replace('supersedes 0.53', '')
    assert not re.search(r'(?<![\d.])0\.53(?:3|\d{0,2})(?!\d)', text), sid


def test_admission_dsr_row_reads_corrected_056():
    adm = json.dumps(json.loads((HUB / 'book2_admission.json').read_text(encoding='utf-8')), ensure_ascii=False)
    assert 'corrected 0.56 ex-BIL on complete months' in adm and 'supersedes 0.53' in adm
    assert not re.search(r'(?<![\d.])0\.53(?!\d)', adm.replace('supersedes 0.53', ''))


def _text(path):
    s = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', path.read_text(encoding='utf-8'), flags=re.S)
    return ' '.join(htmllib.unescape(re.sub(r'<[^>]+>', ' ', s)).split())


def test_book2_page_dsr_mentions_only_the_corrected_value():
    t = _text(ROOT / 'docs' / 'methods' / 'results' / 'book2.html')
    assert '0.56 corrected' in t or 'corrected 0.56' in t
    for m in re.finditer(r'DSR[^.]{0,160}', t):
        assert not re.search(r'(?<![\d.])0\.53(?!\d)', m.group(0).replace('supersedes 0.53', '')), m.group(0)


def test_addendum3_e6_lab_note_renders_after_the_as_recorded_value():
    t = _text(ROOT / 'docs' / 'methods' / 'stage2_addendum3.html')
    i, j = t.find('it is 0.533 at N = 72'), t.find('Lab note: 0.563 on complete months')
    assert 0 <= i < j, (i, j)
    assert "Quant's Sept recompute, sha fe895441… ) supersedes 0.533." in t or "Quant's Sept recompute, sha fe895441…) supersedes 0.533." in t
