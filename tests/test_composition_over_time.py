"""Composition over time page (docs/methods/composition_over_time.html).

Weights come from the saved weights files, bands follow Quant's order (tripwire tags, then
epo_asset_class, else Untagged; never Category), badges are the archive verdicts.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_composition as bc  # noqa: E402
from usa_etf_features import gate_metrics as gm  # noqa: E402

DOCS = ROOT / 'docs'
PAGE = (DOCS / bc.PAGE).read_text(encoding='utf-8')
DATA = json.loads((DOCS / bc.DATA).read_text(encoding='utf-8'))
CHARTS = {c['id']: c for c in DATA['charts']}
UNIVERSE = pd.read_csv(bc.UNIVERSE)


def card(cid: str) -> str:
    m = re.search(rf'<article class="feature-card cot-card[^"]*" id="cot-{re.escape(cid)}".*?</article>', PAGE, re.S)
    assert m, cid
    return m.group(0)


@pytest.fixture(scope='module')
def fresh():
    return bc.build_data()


def test_committed_json_matches_a_fresh_build(fresh):
    assert json.loads(json.dumps(fresh)) == DATA


def test_expected_strategies_present():
    for cid in ('book1', 'book2', 'backbone', 'epo_epo_a_w075', 'epo_anchor_ivol', 'epo_lw_minvar_156w',
                'epo_equal_weight', 'epo_trend_ivol', 'spectral_rp', 'regime_dual', 'vcfc', 'ft_med', 'rr_erc_b',
                'nls_gmv_v1_156w', 'nls_gmv_v2_156w', 'nls_gmv_v3_156w'):
        assert cid in CHARTS, cid
        assert f'id="cot-{cid}"' in PAGE


# ------------------------------------------------------------- weights == source
@pytest.mark.parametrize('spec', bc.specs(), ids=lambda s: s['id'])
def test_chart_weights_match_source(spec):
    c = CHARTS[spec['id']]
    assert (ROOT / c['source']).is_file()
    w = spec['load']().groupby(['month', 'ticker'])['weight'].sum().unstack(fill_value=0.0)
    assert list(w.index) == c['months']
    for t, vals in c['ticker_series'].items():
        expect = w[[m['ticker'] for m in c['other_members']]].sum(axis=1) if t == 'Other' else w[t]
        np.testing.assert_allclose(vals, expect.to_numpy(), atol=1e-12, err_msg=t)
    last = w.iloc[-1]
    for r in c['latest']['rows']:
        assert r['weight'] == pytest.approx(float(last[r['ticker']]), abs=1e-12)
    assert c['data_through'] == c['months'][-1] == c['latest']['month']


def test_book2_matches_raw_wide_file():
    raw = pd.read_csv(ROOT / 'data/processed/live/skew_managed_gatefirst_weights.csv')
    raw['m'] = pd.to_datetime(raw['eval_date']).dt.to_period('M').astype(str)
    c = CHARTS['book2']
    assert c['months'] == list(raw['m'])
    for t in ('VOO', 'QQQM', 'IJR', 'BIL'):
        np.testing.assert_allclose(c['ticker_series'][t], raw[f'w_{t}'].to_numpy(), atol=1e-12)


def test_epo_method_matches_raw_long_file():
    raw = pd.read_csv(ROOT / 'data/processed/epo_allocator/weights.csv', low_memory=False)
    raw = raw[raw.strategy_id == 'epo_a_w075']
    raw = raw.assign(m=pd.to_datetime(raw['date']).dt.to_period('M').astype(str))
    last = raw[raw.m == raw.m.max()].groupby('ticker')['weight'].sum()
    got = {r['ticker']: r['weight'] for r in CHARTS['epo_epo_a_w075']['latest']['rows']}
    assert got == pytest.approx(last[last > 1e-6].to_dict(), abs=1e-12)


@pytest.mark.parametrize('cid', sorted(CHARTS))
def test_each_month_sums_to_100pct(cid):
    c = CHARTS[cid]
    for series in (c['class_series'], c['ticker_series']):
        tot = np.sum([v for v in series.values()], axis=0)
        np.testing.assert_allclose(tot, 1.0, atol=bc.SUM_TOL)
    assert abs(c['sum_min'] - 1) < bc.SUM_TOL and abs(c['sum_max'] - 1) < bc.SUM_TOL


# ------------------------------------------------------------- labels / views
@pytest.mark.parametrize('cid', sorted(CHARTS))
def test_label_is_target_weights_with_source(cid):
    c = CHARTS[cid]
    assert c['label'] == f"target weights at rebalance, source: {c['source']}"
    assert f'<p class="metric-sub cot-label">{c["label"]}</p>' in card(cid)
    assert 'drift' not in card(cid).lower()


def test_default_views_and_bil_line():
    for cid, c in CHARTS.items():
        assert c['default_view'] == ('ticker' if c['group'] == 'books' else 'class'), cid
        checked = 'tick' if c['default_view'] == 'ticker' else 'class'
        assert f'id="cot-{cid}-{checked}" name="cot-{cid}" value="{c["default_view"]}" checked' in card(cid)
    for cid in ('book2', 'backbone'):
        assert 'BIL' in CHARTS[cid]['ticker_series']


def test_xsd_never_in_other():
    held = 0
    for cid, c in CHARTS.items():
        assert 'XSD' not in {m['ticker'] for m in c['other_members']}, cid
        if any('XSD' == r['ticker'] for r in c['latest']['rows']) or 'XSD' in c['ticker_series']:
            held += 1
            assert 'XSD' in c['ticker_series'], cid
    assert held > 0


def test_ticker_view_is_top10_plus_other():
    for cid, c in CHARTS.items():
        names = [t for t in c['ticker_series'] if t not in ('Other', 'XSD', 'BIL')]
        assert len(names) <= bc.TOP_N, cid
        assert list(c['ticker_series'])[-1] == 'Other'


# ------------------------------------------------------------- gate shading
def test_gate_shading_matches_gate_output():
    g = pd.read_csv(ROOT / 'data/processed/live/skew_managed_gatefirst_weights.csv')
    on = g[g['gate_binding'].astype(str).str.lower() == 'true']
    expect = sorted(pd.to_datetime(on['eval_date']).dt.to_period('M').astype(str).unique())
    assert DATA['gate_on_months'] == expect
    assert (expect[0], expect[-1], len(expect)) == ('2021-10', '2023-12', 27)
    assert CHARTS['book2']['gate_on_months'] == expect
    assert all(c['gate_on_months'] is None for cid, c in CHARTS.items() if cid != 'book2')
    assert card('book2').count('class="cot-gate-on"') == 2 * len(expect)       # both views
    assert 'Oct 2021 to Dec 2023' in card('book2')


# ------------------------------------------------------------- not saved
def test_not_saved_cards():
    reg = pd.read_csv(ROOT / 'data/processed/epo_allocator/trial_registry.csv')
    invalid = set(reg.loc[reg.status.astype(str).str.startswith('invalid'), 'trial_id'])
    assert invalid and {n['id'] for n in DATA['not_saved']} == invalid
    for tid in invalid:
        assert tid not in CHARTS
        assert 'Weights not saved.' in card(tid)


# ------------------------------------------------------------- bands
def _toy(**cols):
    base = dict(Ticker=['AAA'], Category=['US Large Blend'], epo_asset_class=[''],
                cash_like=[False], short_duration=[False], near_cash=[False])
    base.update({k: [v] for k, v in cols.items()})
    return pd.DataFrame(base)


@pytest.mark.parametrize('cols, band', [
    (dict(cash_like=True, epo_asset_class='equity'), 'Cash-like'),
    (dict(short_duration=True, epo_asset_class='bond'), 'Cash-like'),
    (dict(near_cash=True), 'Cash-like'),
    (dict(epo_asset_class='equity'), 'Equity'),
    (dict(epo_asset_class='bond'), 'Bond'),
    (dict(epo_asset_class='commodity'), 'Commodity'),
    (dict(), 'Untagged'),
    (dict(Category='US Treasuries / Govt / Cash-like'), 'Untagged'),
    (dict(Category='Commodities / Metals'), 'Untagged'),
])
def test_band_assignment_order(cols, band):
    assert bc.band_map(_toy(**cols)) == {'AAA': band}


def test_band_tags_are_the_tripwire_definition():
    bands = bc.band_map(UNIVERSE)
    tagged = frozenset().union(*(gm.tagged_tickers(UNIVERSE, c) for c in gm.COMPOSITION_TAG_COLUMNS))
    assert {t for t, b in bands.items() if b == 'Cash-like'} == tagged
    for t in ('BIL', 'SHY', 'SPTS', 'FTSL'):
        assert bands[t] == 'Cash-like', t
    cls = gm.epo_asset_class(UNIVERSE)
    for t, b in bands.items():
        if t not in tagged:
            want = str(cls.get(t) or '').strip().capitalize() or 'Untagged'
            assert b == want, t


def test_category_never_used_for_bands():
    shuffled = UNIVERSE.copy()
    shuffled['Category'] = 'US Treasuries / Govt / Cash-like'
    assert bc.band_map(shuffled) == bc.band_map(UNIVERSE)
    assert bc.band_map(UNIVERSE.drop(columns=['Category'])) == bc.band_map(UNIVERSE)
    assert 'Category' not in Path(bc.__file__).read_text(encoding='utf-8').split('def band_map')[1].split('def band_of')[0].replace(
        'Category is never', '')


def test_sleeve_keys_fall_in_untagged():
    for cid in ('ft_med', 'rr_erc_b'):
        c = CHARTS[cid]
        nonbil = 1 - np.asarray(c['ticker_series'].get('BIL', [0.0] * len(c['months'])))
        np.testing.assert_allclose(np.asarray(c['class_series']['Untagged']) + np.asarray(c['class_series']['Cash-like']),
                                   1.0, atol=1e-9)
        assert np.all(np.asarray(c['class_series']['Untagged']) <= nonbil + 1e-9)


def test_cash_limit_line_on_class_view():
    assert bc.CASH_LIMIT == gm.COMPOSITION_MAX_SHARE == 0.5
    for cid in CHARTS:
        view = card(cid).split('cot-view-class')[1].split('cot-view-ticker')[0]
        assert view.count('stroke-dasharray="4 3"') == 1, cid
        assert 'stroke-dasharray' not in card(cid).split('cot-view-ticker')[1], cid


# ------------------------------------------------------------- badges
def test_badges_are_archive_verdicts():
    arc = json.loads(bc.ARCHIVE_JSON.read_text(encoding='utf-8'))
    for cid in ('nls_gmv_v1_156w', 'nls_gmv_v2_156w', 'nls_gmv_v1_260w', 'nls_gmv_v2_260w'):
        run = 'nonlinear_shrinkage_gmv' if '_v1_' in cid else 'nonlinear_shrinkage_gmv_v2'
        rep = json.loads((ROOT / 'data/processed' / run / 'gate_report.json').read_text(encoding='utf-8'))
        v = rep['verdict']['verdict'] if isinstance(rep['verdict'], dict) else rep['verdict']
        assert v == 'VOID'
        assert CHARTS[cid]['badge'] == 'VOID'
        assert '>VOID</span>' in card(cid) and '>FAIL</span>' not in card(cid)
    epo = json.loads((ROOT / 'data/processed/epo_allocator/verdict.json').read_text(encoding='utf-8'))
    assert 'FAIL' in json.dumps(epo)
    assert CHARTS['epo_epo_a_w075']['badge'] == 'FAIL'
    assert arc  # archive file readable


def test_void_runs_show_why():
    s = pd.read_csv(ROOT / 'data/processed/nonlinear_shrinkage_gmv_v2/summary.csv')
    s = s[(s.strategy_id == 'nonlinear_shrinkage_gmv') & (s.window_weeks == 156)]
    v2 = CHARTS['nls_gmv_v2_156w']['void_composition']['value']
    assert v2 == pytest.approx(float(s['short_duration_share_mean'].iloc[0]))
    assert 0.83 < v2 < 0.85
    assert f'short-duration share {100 * v2:.1f}%' in card('nls_gmv_v2_156w')
    assert 'Why VOID:' in card('nls_gmv_v1_156w')
    for cid in ('nls_gmv_v1_156w', 'nls_gmv_v2_156w'):
        assert CHARTS[cid]['avg_cash_like'] > bc.CASH_LIMIT


def test_metrics_line_from_run_output_or_not_recorded():
    for cid, c in CHARTS.items():
        for k, m in c['metrics'].items():
            if m is not None:
                src = m['source'].split(':')[0]
                assert (ROOT / src).is_file(), (cid, src)
        assert 'Average equity share:' in card(cid)
    assert 'not recorded' in card('book2')


def test_vt_ticker_never_bare():
    assert bc.display('VT') != 'VT' and bc.display('XSD') == 'XSD'


def test_linked_from_methods_and_books():
    assert 'composition_over_time.html' in (DOCS / 'methods/index.html').read_text(encoding='utf-8')
    books = (ROOT / 'apps/pages/src/pages/Books.tsx').read_text(encoding='utf-8')
    assert './methods/composition_over_time.html' in books
