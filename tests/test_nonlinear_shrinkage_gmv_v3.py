"""Synthetic v3 research gate checks; never runs the real-data gate."""
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm
from threadpoolctl import threadpool_limits

from usa_etf_features import gate_metrics as gm
from usa_etf_features import nonlinear_shrinkage_gmv_v3 as v3
from usa_etf_features.strategy_registry import load_strategy_registry


@pytest.fixture(autouse=True)
def small_blas_pool():
    with threadpool_limits(limits=1):
        yield


def test_equity_tag_stored():
    u = pd.read_csv('data/raw/usa_universe_categorized.csv')
    assert gm.equity_only_tickers(u) == gm.EQUITY_ONLY and len(gm.EQUITY_ONLY) == 96
    for tag in gm.COMPOSITION_TAG_COLUMNS:
        assert not gm.EQUITY_ONLY & gm.tagged_tickers(u, tag)
    assert gm.equity_only_tickers(u.assign(equity_only=u.Ticker.eq('BIL'))) == {'BIL'}
    assert 'equity_only' not in gm.COMPOSITION_TAG_COLUMNS


def rf_for(index):
    return pd.DataFrame({'rf': 0., 'source': 'synthetic'}, index=pd.PeriodIndex(index, freq='M'))


def test_lw2008_properties():
    rng = np.random.default_rng(4)
    dates = pd.date_range('1980-01-31', periods=500, freq='ME')
    a, b = (pd.Series(x, dates) for x in (rng.normal(.025, .03, 500), rng.normal(0, .04, 500)))
    rf = rf_for(dates)
    same = v3.lw2008_sharpe_test(a, a, rf)
    assert same['p_two_sided'] == 1 and same['se_hac'] == same['z'] == 0
    one, reverse, scaled = (v3.lw2008_sharpe_test(x, y, rf) for x, y in ((a, b), (b, a), (a*10, b*10)))
    assert one['p_two_sided'] < .001
    assert one['z'] == pytest.approx(-reverse['z'])
    assert one['z'] == pytest.approx(scaled['z'])
    with pytest.raises(ValueError, match='12'):
        v3.lw2008_sharpe_test(a[:11], b[:11], rf)


def test_dsr_formula_and_monotonicity():
    sr, t, n, var, skew, kurt = .5, 129, 8, .02, -.3, 4.
    gamma = .5772156649015329
    sr0 = np.sqrt(var)*((1-gamma)*norm.ppf(1-1/n)+gamma*norm.ppf(1-1/(n*np.e)))
    expected = norm.cdf((sr-sr0)*np.sqrt(t-1)/np.sqrt(1-skew*sr+(kurt-1)/4*sr**2))
    f = v3.deflated_sharpe_bailey_lp
    assert f(sr, t, n, var, skew, kurt) == pytest.approx(expected)
    assert f(sr, t, n, var*2, skew, kurt) < expected
    assert f(sr, t, n*2, var, skew, kurt) < expected
    for args in ((sr, 2, n, var, skew, kurt), (sr, t, 1, var, skew, kurt),
                 (sr, t, n, -1, skew, kurt), (sr, t, n, np.inf, skew, kurt), (1, t, n, var, 10, 3)):
        assert np.isnan(f(*args))


def summary(over=None):
    rows = []
    for w in (156, 260):
        for sid in (v3.METHOD, v3.PRIMARY):
            m = sid == v3.METHOD
            row = dict(window_weeks=w, strategy_id=sid, AnnVol=.08 if m else .09,
                       Sharpe_exBIL=.6 if m else .5, MaxDD=-.1 if m else -.2,
                       DSR_exBIL=.96, eff_N_mean=8., p_gate=.04 if w == 156 else .9)
            row.update((over or {}).get((w, sid), {}))
            rows.append(row)
    return pd.DataFrame(rows)


def comp():
    return dict(status='PASS', computable=True, method_share=0., null_share=0.)


def test_mechanical_pass_direction_and_void():
    r = v3.mechanical_reading_v3(summary(), comp())
    assert r['mechanical'] == 'PASS' and all(r['criteria'].values())
    assert v3.mechanical_reading_v3(summary({(260, v3.METHOD): {'eff_N_mean': 2}}), comp())['mechanical'] == 'PASS'
    r = v3.mechanical_reading_v3(summary({(156, v3.METHOD): {'eff_N_mean': 4.9}}), comp())
    assert r['mechanical'] == 'VOID'
    c = dict(comp(), status='VOID', method_share=.001)
    r = v3.mechanical_reading_v3(summary(), c)
    assert not r['criteria']['c6'] and gm.final_gate_label(r['mechanical'], c) == 'VOID'


@pytest.mark.parametrize('window,over,criterion', [
    (156, {'p_gate': .051}, 'c1'), (156, {'AnnVol': .1}, 'c1'),
    (156, {'Sharpe_exBIL': .4}, 'c2'), (156, {'MaxDD': -.3}, 'c3'),
    (156, {'DSR_exBIL': .94}, 'c4'), (260, {'AnnVol': .1}, 'c5'),
    (260, {'Sharpe_exBIL': .4}, 'c5'),
])
def test_mechanical_failing_criteria(window, over, criterion):
    r = v3.mechanical_reading_v3(summary({(window, v3.METHOD): over}), comp())
    assert r['mechanical'] == 'FAIL' and criterion in r['failing_criteria']


@pytest.mark.parametrize('label,sr,dd,eligible', [('FAIL', .8, -.1, False), ('PASS', .8, -.3, True),
                                                ('PASS', .4, -.1, True), ('PASS', .4, -.3, False)])
def test_book_eligibility_separate(label, sr, dd, eligible):
    original = label
    be = v3.book_eligibility(label, {'Sharpe_exBIL': sr, 'MaxDD': dd},
                             {'Sharpe_exBIL': .6, 'MaxDD': -.2}, .4)
    assert be['eligible'] == eligible and label == original
    assert v3.book_eligible_line(be) == f"book_eligible: {'yes' if eligible else 'no'} ({be['reason']})"
    if label == 'PASS' and not eligible:
        assert 'research-only' in be['reason']


@pytest.fixture
def panel():
    rng = np.random.default_rng(15)
    names = ['USMV', 'ACWI', 'EFAV'] + sorted(gm.EQUITY_ONLY - {'USMV', 'ACWI', 'EFAV'})[:9] + ['BIL', 'SHY']
    vol = np.r_[np.full(12, .025), .0001, .0002]
    weekly = pd.DataFrame(rng.normal(.02, 1, (480, len(names))) * vol,
                          index=pd.date_range('2013-01-04', periods=480, freq='W-FRI'), columns=names)
    monthly = pd.DataFrame(rng.normal(.15, 1, (120, len(names))) * vol*2,
                           index=pd.date_range('2013-01-31', periods=120, freq='ME'), columns=names)
    u = pd.DataFrame({'Ticker': names, 'Category': ['Equity']*12+['Cash', 'Bond']})
    for col in gm.COMPOSITION_TAG_COLUMNS:
        u[col] = u.Ticker.isin({'cash_like': gm.CASH_LIKE, 'short_duration': gm.SHORT_DURATION, 'near_cash': gm.NEAR_CASH}[col])
    u['equity_only'] = u.Ticker.isin(gm.EQUITY_ONLY)
    trial = v3.NLSGMVv3Trial(26, min_names=8, oos_start='2020-01-01', oos_end='2022-01-31')
    return weekly, monthly, u, trial, rf_for(monthly.index)


@pytest.mark.parametrize('windows', [(26, 30), (156, 260)])
def test_synthetic_gate_and_leakage(panel, tmp_path, windows):
    weekly, monthly, u, trial, rf = panel
    trial = replace(trial, window_weeks=windows[0])
    result = v3.run_nls_gmv_v3_gate(weekly, monthly, u, (trial, replace(trial, window_weeks=windows[1])),
                                   extra_previews=('preview',), rf=rf, bootstrap_reps=19)
    assert result['trial_count'] == 9
    assert not result['weights'].ticker.isin(['BIL', 'SHY']).any()
    c = result['composition']
    assert c['status'] == 'PASS' and c['method_share'] == c['null_share'] == 0
    lines = result['report_lines']
    i = lines.index(f"**Label (mechanical + composition): {result['label']}**")
    assert lines[i+1].startswith('book_eligible:')
    v3.write_v3_artifacts(result, tmp_path)
    record = json.loads((tmp_path / 'gate_result.json').read_text())
    assert 'book_eligible' in record['fields']
    assert record['label'] == gm.final_gate_label(record['mechanical'], record['composition'])
    ref_window = windows[0]
    refs = result['oos_returns'].query('strategy_id == @v3.USMV_REF and window_weeks == @ref_window').sort_values('date')
    assert refs.turnover.iloc[0] == .5 and refs.turnover.iloc[1:].eq(0).all()
    assert refs.cost_return.iloc[0] == .00025
    before = v3.run_nls_gmv_v3_trial(weekly, monthly, u, trial)['weights']
    cut = before.decision_date.min()
    changed = monthly.copy()
    changed.loc[changed.index > cut] *= 1.5
    after = v3.run_nls_gmv_v3_trial(weekly, changed, u, trial)['weights']
    pd.testing.assert_frame_equal(before.loc[before.decision_date.eq(cut)].reset_index(drop=True),
                                  after.loc[after.decision_date.eq(cut)].reset_index(drop=True))
    broken = monthly.copy()
    broken.loc[refs.date.iloc[0], 'USMV'] = np.nan
    with pytest.raises(ValueError, match='missing'):
        v3.run_nls_gmv_v3_trial(weekly, broken, u, trial)


def test_coverage(panel):
    weekly, monthly, u, _, _ = panel
    weekly.loc[weekly.index < '2014-01-01', 'ACWI'] = np.nan
    gaps = v3.weekly_vs_monthly_coverage(weekly, monthly, u)
    assert gaps.ticker.tolist() == ['ACWI'] and gaps.gap_days.iloc[0] > 35


def test_registry_and_archived_manifest():
    specs = {s.id: s for s in load_strategy_registry('config/strategies.yaml')}
    assert not specs[v3.GATE_ID].enabled
    assert specs[v3.GATE_ID].default_params['min_names'] == 65
    assert not specs['nonlinear_shrinkage_gmv'].enabled
    assert specs['nonlinear_shrinkage_gmv'].default_params['min_names'] == 100
    assert specs['nonlinear_shrinkage_gmv_v2_excash'].default_params['min_names'] == 95
    assert len(json.loads(Path('tests/data/archived_csv_sha256.json').read_text())['files']) == 78
    reg = v3.trial_registry_v3({156: .6, 260: .5})
    assert len(reg) == 8 and reg.Sharpe_exBIL_annual.notna().sum() == 6
    assert v3.cross_trial_sharpe_var(reg) == pytest.approx((reg.Sharpe_exBIL_annual/np.sqrt(12)).var(ddof=1))


def test_final_partial_month_unpriced_names_drop_out_of_last_rebalance_only(panel):
    weekly, monthly, u, trial, _ = panel
    monthly = monthly.loc[:weekly.index[-1]]                               # weekly data covers every window
    trial = replace(trial, oos_start='2021-01-01', oos_end='2022-12-31')   # runs to the panel's last row
    name = sorted(gm.EQUITY_ONLY - {'USMV', 'ACWI', 'EFAV'})[0]
    clean = v3.run_nls_gmv_v3_trial(weekly, monthly, u, trial)
    assert clean['final_month_unpriced'].empty
    gap = monthly.copy()
    gap.iloc[-1, gap.columns.get_loc(name)] = np.nan
    listed = v3.final_month_unpriced(weekly, gap, u, trial)
    assert listed.ticker.tolist() == [name] and listed.date.iloc[0] == monthly.index[-1]
    out = v3.run_nls_gmv_v3_trial(weekly, gap, u, trial)
    last = out['weights'].decision_date.max()
    assert not out['weights'].loc[out['weights'].decision_date.eq(last)].ticker.eq(name).any()
    earlier = lambda w: w.loc[w.decision_date.lt(last)].reset_index(drop=True)
    pd.testing.assert_frame_equal(earlier(clean['weights']), earlier(out['weights']))
    counts = out['name_counts'].set_index('decision_date').n_eligible
    assert counts[last] == clean['name_counts'].set_index('decision_date').n_eligible[last] - 1
    mid = monthly.copy()
    mid.iloc[-3, mid.columns.get_loc(name)] = np.nan   # a gap before the final month still needs data repair
    with pytest.raises(ValueError, match='missing OOS return'):
        v3.run_nls_gmv_v3_trial(weekly, mid, u, trial)


V3_DIR = Path('data/processed/nonlinear_shrinkage_gmv_v3')


def test_committed_v3_composition_reads_zero_percent():
    """Ticket: the composition tripwire on the committed v3 run reads 0.0% for the method and the primary null."""
    u = pd.read_csv('data/raw/usa_universe_categorized.csv')
    weights = pd.read_csv(V3_DIR / 'weights.csv')
    for window in (156, 260):
        c = gm.composition_tripwire(weights.loc[weights.window_weeks.eq(window)], u,
                                    method=v3.METHOD, primary_null=v3.PRIMARY, max_share=0.)
        assert c['status'] == 'PASS' and c['computable']
        assert c['method_share'] == 0.0 and c['null_share'] == 0.0
    assert weights.ticker.isin(gm.equity_only_tickers(u)).all()
    record = json.loads((V3_DIR / 'gate_result.json').read_text())
    assert record['composition']['status'] == 'PASS'
    assert record['composition']['method_share'] == record['composition']['null_share'] == 0.0


def test_committed_v3_book_eligible_is_its_own_field_and_never_the_label():
    record = json.loads((V3_DIR / 'gate_result.json').read_text())
    assert record['gate_id'] == v3.GATE_ID
    assert record['label'] == gm.final_gate_label(record['mechanical'], record['composition'])
    be = record['fields']['book_eligible']
    assert set(be) >= {'eligible', 'reason', 'lw2008_p_vs_usmv'} and 'book_eligible' not in record['report']
    assert be['eligible'] is False and be['reason'] == f"gate label is {record['label']}, not PASS"
    lines = (V3_DIR / 'gate_report.md').read_text().splitlines()
    i = lines.index(f"**Label (mechanical + composition): {record['label']}**")
    assert lines[i + 1] == v3.book_eligible_line(be)
    assert record['report']['trial_count'] == 8
    counts = pd.read_csv(V3_DIR / 'name_counts.csv')
    c156 = counts.loc[counts.window_weeks.eq(156)]
    assert len(c156) == 129 and not c156.skipped.any() and c156.n_eligible.between(65, 94).all()


def test_quant_verdict_and_archive_card():
    assert v3.VERDICT_LABEL == 'VOID: concentrated holdings (effective N under 5)' and v3.STATUS == v3.VERDICT_LABEL
    assert json.loads((V3_DIR / 'verdict.json').read_text()) == v3.VERDICT
    assert v3.VERDICT['final_trial_count'] == v3.TRIAL_COUNT_V3 == 8
    specs = {s.id: s for s in load_strategy_registry('config/strategies.yaml')}
    assert not specs[v3.GATE_ID].enabled and v3.VERDICT_LABEL in specs[v3.GATE_ID].display_name
    cards = {c['id']: c for c in json.loads(Path('apps/pages/src/data/archive_verdicts.json').read_text())['cards']}
    card = cards['nls_gmv_v3']
    assert card['badge'] == 'VOID' and card['verdict'].startswith(v3.VERDICT_LABEL)
    assert 'failed all six' in card['verdict'] and 'no v4' in card['measured']['text']
    assert 'in-sample reference only, not a sleeve candidate' in card['measured']['text']
    s = pd.read_csv(V3_DIR / 'summary.csv')
    s = s.loc[s.window_weeks.eq(156) & s.period.str.startswith('full')].set_index('strategy_id')
    rows = {r['label']: r for r in card['rows']}
    for label, sid in (('NLS GMV v3 (156w, method)', v3.METHOD), ('Weekly LW MinVar (primary null)', v3.PRIMARY),
                       ('USMV buy-and-hold (in-sample reference only)', v3.USMV_REF)):
        assert rows[label]['sharpe'] == f"{s.loc[sid, 'Sharpe_exBIL']:.2f} (legacy {s.loc[sid, 'Sharpe_rf0_legacy']:.2f})"
        assert rows[label]['maxdd'] == f"{s.loc[sid, 'MaxDD']:.1%}".replace('-', '−')
    assert f"{s.loc[v3.METHOD, 'eff_N_mean']:.2f}" in card['verdict'] and f"{s.loc[v3.PRIMARY, 'eff_N_mean']:.2f}" in card['verdict']
    low = sorted(round(100 * s.loc[k, ['usmv_share_mean', 'efav_share_mean']].sum()) for k in (v3.METHOD, v3.PRIMARY))
    assert f"{low[0]}–{low[1]}%" in card['verdict']
    assert Path('docs/methods/allocation_alpha_nonlinear_shrinkage_gmv.html').exists()
