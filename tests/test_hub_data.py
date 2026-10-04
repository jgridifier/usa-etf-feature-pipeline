"""Results hub data (PR A): recomputed from saved artifacts only, and matching the committed JSON.

Guards the CIO/CoS rulings (hub_plan.md §14): static core = Book 1 (S1) and only from 2020-11; stand-in core is a
sensitivity; leaderboard ranked by CAGR difference vs the core over the common 65 months; VOID runs carry no
Sharpe or DSR and are not ranked; Backbone headline is the live 0.86; every head-to-head carries a power caveat;
regime / stress cells never blank and never backfilled.
"""
import json
import math
from pathlib import Path

import pandas as pd
import pytest

from usa_etf_features import hub_data as hd

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / 'data/processed/hub'
ALLOWED_COVERAGE = ('in window', 'not in window')


@pytest.fixture(scope='module')
def built():
    return hd.build(ROOT)


def _load(name):
    return json.loads((HUB / name).read_text(encoding='utf-8'))


def _close(a, b, path='$'):
    if isinstance(a, dict):
        assert set(a) == set(b), (path, set(a) ^ set(b))
        for k in a:
            _close(a[k], b[k], f'{path}.{k}')
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            _close(x, y, f'{path}[{i}]')
    elif isinstance(a, float) or isinstance(b, float):
        assert a is not None and b is not None, path
        assert b == pytest.approx(a, abs=1e-7, rel=1e-7), path
    else:
        assert a == b, path


def _walk(obj, path='$'):
    yield path, obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f'{path}.{k}')
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f'{path}[{i}]')


def test_committed_hub_json_recomputes_from_saved_artifacts(built):
    roundtrip = json.loads(json.dumps(built['manifest'], ensure_ascii=False))
    _close(roundtrip, _load('manifest.json'))
    _close(json.loads(json.dumps(built['leaderboard'])), _load('leaderboard.json'))
    for sid, s in built['subjects'].items():
        _close(json.loads(json.dumps(s)), _load(f'subjects/{sid}.json'), sid)
    committed = sorted(p.stem for p in (HUB / 'subjects').glob('*.json'))
    assert committed == sorted(hd.SUBJECT_IDS)
    for name, df in (('static_core_monthly.csv', built['static_core']), ('market_regimes.csv', built['regimes'])):
        c = pd.read_csv(HUB / name, index_col=0)
        assert list(c.index) == [str(m) for m in df.index]
        for col in df.columns:
            if df[col].dtype.kind == 'f':
                assert c[col].to_numpy() == pytest.approx(df[col].to_numpy(dtype=float), abs=1e-9, nan_ok=True), (name, col)


def test_manifest_covers_all_14_subjects_and_names_real_files():
    m = _load('manifest.json')
    ids = [s['id'] for s in m['subjects']]
    assert len(ids) == 14 and len(set(ids)) == 14
    groups = pd.Series([s['group'] for s in m['subjects']]).value_counts().to_dict()
    assert groups == {'fail': 7, 'void': 3, 'audit_null': 1, 'live_book': 2, 'overlay_record': 1}
    for s in m['subjects']:
        df = pd.read_csv(ROOT / s['series']['file'], nrows=5, low_memory=False)
        assert s['series']['col'] in df.columns, s['id']
        for n in s['nulls']:
            assert n.get('col', s['series']['col']) in df.columns, (s['id'], n)
        for k in ('weights', 'trials'):
            f = (s.get(k) or {}).get('file')
            assert f is None or (ROOT / f).exists(), (s['id'], f)
        for k in ('prereg', 'verdict'):
            assert s.get(k) is None or (ROOT / s[k]).exists(), (s['id'], s[k])


def test_labels_unchanged_and_archive_counts_still_7_3_1():
    arch = json.loads((ROOT / hd.ARCHIVE).read_text())
    badges = {c['id']: c['badge'] for c in arch['cards']}
    assert pd.Series(list(badges.values())).value_counts().to_dict() == {'FAIL': 7, 'VOID': 3, 'AUDIT NULL': 1}
    m = _load('manifest.json')
    for s in m['subjects']:
        if s['card']:
            assert s['label'] == badges[s['card']], s['id']
    labels = {s['id']: s['label'] for s in m['subjects']}
    assert labels['book1'] == labels['book2'] == 'LIVE BOOK' and labels['skew_overlay'] == 'gate-first PASS'
    assert set(badges) == {s['card'] for s in m['subjects'] if s['card']}


def test_static_core_is_book1_s1_from_2020_11(built):
    core = built['static_core']
    s1 = core['static_core_s1'].dropna()
    assert str(s1.index.min()) == hd.CORE_START == '2020-11' and len(s1) == 71
    assert hd.CORE_WEIGHTS == {'VOO': 0.7, 'QQQM': 0.2, 'IJR': 0.1}
    assert hd.STANDIN_WEIGHTS == {'IVV': 0.7, 'QQQ': 0.2, 'IJR': 0.1}
    vt = pd.read_csv(ROOT / 'data/processed/live/vol_target_oos_returns.csv', parse_dates=['date'])
    opt_a = pd.Series(vt.r_option_a.to_numpy(), index=vt.date.dt.to_period('M'))
    j = pd.concat([s1, opt_a], axis=1, join='inner')
    assert len(j) == 68 and (j.iloc[:, 0] - j.iloc[:, 1]).abs().max() < 1e-12
    pdv = core['static_core_panel_derived'].dropna()
    diff = (pdv.reindex(s1.index) - s1).abs()
    assert list(diff[diff > 1e-6].index.astype(str)) == ['2026-09']   # panel's last month has an earlier as-of; else ~1e-7 price rounding
    assert str(core['standin_core'].dropna().index.min()) == '2000-06'
    for sid, s in built['subjects'].items():
        cov = s['vs_core']['own_window']['coverage']
        assert cov['k'] == s['vs_core']['own_window']['n'], sid
        assert all(m >= '2020-11' for m in (s['curves']['growth_vs_core'] or {}).get('months', [])), sid


def test_recorded_figures_reproduce(built):
    S = built['subjects']
    schur = pd.read_csv(ROOT / 'data/processed/schur_allocator/summary.csv').set_index('strategy_id')
    assert S['schur']['own']['sharpe_exbil'] == pytest.approx(schur.loc['schur_g050', 'Sharpe_exBIL'], abs=1e-9)
    assert S['schur']['own']['maxdd'] == pytest.approx(schur.loc['schur_g050', 'MaxDD'], abs=1e-9)
    epo = pd.read_csv(ROOT / 'data/processed/epo_allocator/trial_registry.csv').set_index('trial_id')
    assert S['epo']['own']['sharpe_exbil'] == pytest.approx(epo.loc['epo_a_w075', 'Sharpe_exBIL_annual'], abs=1e-9)
    site = json.loads((ROOT / hd.SITE_SHARPE).read_text())['books']
    assert round(S['backbone']['own']['sharpe_exbil'], 4) == site['uncond_vt_audit_null']['exbil'] == 0.8615
    assert round(S['book2']['own']['sharpe_exbil'], 4) == site['book2_vt_x_gatefirst']['exbil']
    b1 = hd.window(hd.monthly_series(ROOT, 'data/processed/live/strategy_returns.csv', 'return', {'strategy_id': 'static_option_a'})[0],
                   '2021-02', '2026-09')
    assert round(hd.stats(b1, hd.risk_free(ROOT))['sharpe_exbil'], 4) == site['book1_static_core']['exbil']


def test_backbone_headline_ruling_d2():
    h = _load('subjects/backbone.json')['headline']
    assert h['headline']['sharpe_exbil'] == 0.8615 and h['headline']['n_months'] == 68
    assert h['frozen_snapshot']['sharpe_exbil'] == 0.8274 and 'Frozen snapshot' in h['frozen_snapshot']['label']
    assert h['recorded']['value'].startswith('0.839') and 'archive card' in h['recorded']['label']


def test_leaderboard_ranked_by_cagr_diff_common_65_months_void_unranked():
    L = _load('leaderboard.json')
    assert (L['common_window']['start'], L['common_window']['end'], L['common_window']['months']) == ('2021-04', '2026-08', 65)
    assert '2021-04 to 2026-08 (65 months)' in L['common_window']['label']
    assert L['ranked_by'].startswith('CAGR difference') and L['sortable'] == ['cagr_diff', 'sharpe_diff', 'maxdd_diff']
    rows = L['rows']
    assert [r['cagr_diff'] for r in rows] == sorted((r['cagr_diff'] for r in rows), reverse=True)
    assert all(r['n'] == 65 and r['start'] == '2021-04' and r['end'] == '2026-08' for r in rows + L['void'])
    ranked = [r for r in rows if not r['is_benchmark']]
    assert [r['rank'] for r in ranked] == list(range(1, len(ranked) + 1)) and len(ranked) == 10
    b1 = next(r for r in rows if r['id'] == 'book1')
    assert b1['rank'] is None and b1['cagr_diff'] == 0 and b1['sharpe_diff'] == 0
    assert sorted(r['id'] for r in L['void']) == ['nls_v1', 'nls_v2', 'nls_v3']
    for r in L['void']:
        assert 'rank' not in r and 'sharpe_exbil' not in r and 'sharpe_diff' not in r
    for r in rows + L['void']:
        assert r['page'] == f"methods/results/{r['id']}.html"
        assert r['power']['n'] == 65 and r['power']['text'].startswith('65 paired months')


def test_void_subjects_carry_no_sharpe_and_no_dsr():
    for sid in ('nls_v1', 'nls_v2', 'nls_v3'):
        s = _load(f'subjects/{sid}.json')
        assert s['dsr'] is None and s['rolling_sharpe'] is None and s['verdict']['banner']
        assert s['verdict']['void_reason']
        bad = [p for p, v in _walk(s) if p.split('.')[-1].startswith(('sharpe', 'detectable_sharpe')) and v is not None
               and not p.endswith(('sharpe_test', ))]
        assert not bad, (sid, bad[:5])
        assert not any(g['gate'].startswith('DSR') for g in s['gates'])
        assert s['curves']['growth']['subject'] and s['curves']['drawdown']['subject'] and s['weights']['top']


def test_every_head_to_head_carries_a_power_caveat():
    for sid in hd.SUBJECT_IDS:
        s = _load(f'subjects/{sid}.json')
        h2h = [(p, v) for p, v in _walk(s) if isinstance(v, dict) and 'n' in v and 'diff' in v]
        assert h2h, sid
        for p, h in h2h:
            pw = h['power']
            assert pw['n'] == h['n'] and pw['text'].startswith(f"{h['n']} paired months"), (sid, p)
            if h['n'] >= hd.MIN_SHARPE_MONTHS and 'identical' not in pw['text']:
                g = pw.get('detectable_sharpe_gap', pw.get('detectable_ann_return_gap'))
                assert g is not None and g > 0, (sid, p)


def test_regime_and_stress_cells_never_blank_never_backfilled():
    for sid in hd.SUBJECT_IDS:
        s = _load(f'subjects/{sid}.json')
        months = set(s['months'])
        for row in s['regimes'] + s['stress']:
            for key, e in row['series'].items():
                st = e['coverage']['status']
                assert st in ALLOWED_COVERAGE or st.startswith('partly in window ('), (sid, row.get('name'), st)
                if e['coverage']['k'] == 0:
                    assert set(e) == {'coverage'}, (sid, key)
                else:
                    assert e['cumulative_return'] is not None
            assert row['vs_core_power']['text']
        for w in s['stress']:
            for m, v in zip(w['path']['months'], w['path']['subject']):
                assert (v is None) == (m not in months), (sid, w['window'], m)
            for m, v in zip(w['path']['months'], w['path']['core']):
                assert v is None or m >= '2020-11', (sid, w['window'], m)
    schur = {w['window']: w for w in _load('subjects/schur.json')['stress']}
    assert schur['gfc']['series']['subject']['coverage']['status'] == 'not in window'
    assert schur['euro_2011']['series']['subject']['coverage']['status'] == 'not in window'
    b2 = {w['window']: w for w in _load('subjects/book2.json')['stress']}
    assert b2['gfc']['series']['subject']['coverage']['status'] == 'not in window'
    ft = {w['window']: w for w in _load('subjects/ft_med.json')['stress']}
    assert ft['dotcom']['series']['subject']['coverage']['status'].startswith('partly in window')
    assert ft['gfc']['series']['core']['coverage']['status'] == 'not in window'


def test_stress_windows_follow_ruling_d7():
    w = {x['id']: x for x in _load('manifest.json')['stress_windows']}
    assert (w['gfc']['start'], w['gfc']['end']) == ('2007-11', '2009-02')
    assert (w['bear_2022']['start'], w['bear_2022']['end']) == ('2022-01', '2022-09')
    assert (w['covid']['start'], w['covid']['end']) == ('2020-01', '2020-03')
    assert w['euro_2011']['rule'] == w['tariff_2025']['rule'] == 'named'
    assert all(x['spy_drawdown'] <= -0.10 for x in w.values() if x['rule'] != 'named')


def test_partial_final_months_are_dropped_not_paired():
    ft = _load('subjects/ft_med.json')
    assert ft['partial_months_dropped'] == ['2026-09'] and ft['months'][-1] == '2026-08'
    assert _load('subjects/schur.json')['partial_months_dropped'] == []


def test_dsr_recorded_with_basis_and_recompute_slot(tmp_path):
    for sid in ('spectral_rp', 'regime_dual', 'vcfc', 'ft_med', 'rr_erc'):
        d = _load(f'subjects/{sid}.json')['dsr']
        assert d['basis'] == 'rf = 0 basis' and d['dsr_exbil_recomputed'] is None and 'pending' in d['recompute_note']
    assert _load('subjects/schur.json')['dsr']['basis'] == 'Sharpe ex-BIL basis'
    slot = tmp_path / hd.DSR_RECOMPUTE
    slot.parent.mkdir(parents=True)
    slot.write_text('subject_id,dsr_exbil,trial_count\nft_med,0.5,1\n')
    assert hd.load_recompute(tmp_path) == {'ft_med': dict(dsr_exbil=0.5, trial_count=1, source=hd.DSR_RECOMPUTE)}


def test_standin_core_is_sensitivity_only():
    for sid in hd.SUBJECT_IDS:
        v = _load(f'subjects/{sid}.json')['vs_core']
        assert 'Sensitivity only' in v['standin_sensitivity']['label']
    L = _load('leaderboard.json')
    assert 'IVV' not in json.dumps(L) and 'static_option_a' in L['benchmark']


def test_timing_audit_passes_where_saved():
    for sid in hd.SUBJECT_IDS:
        t = _load(f'subjects/{sid}.json')['timing_audit']
        if sid == 'book1':
            assert t['status'] == 'not applicable', t   # fixed weights: no decision data to leak
            continue
        assert t['status'] == 'pass' and t['n'] > 0, sid
    assert _load('subjects/schur.json')['timing_audit']['scope'] == 'full'
    assert _load('subjects/ft_med.json')['timing_audit']['scope'].startswith('partial')
