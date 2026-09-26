"""NLS GMV v2 (ex-cash) gate: LW (2011) variance test, VOID tripwires, name floor, ex-cash universe."""
from dataclasses import replace
import inspect
import json

import numpy as np
import pandas as pd
import pytest
from threadpoolctl import threadpool_limits

from usa_etf_features import nonlinear_shrinkage_gmv as v1
from usa_etf_features.gate_metrics import CASH_LIKE, SHORT_DURATION, sharpe_exbil
from usa_etf_features.nonlinear_shrinkage_gmv_v2 import (
    METHOD, PRIMARY, REFERENCE, NLSGMVv2Trial, PREREGISTERED_V2, TRIAL_COUNT_V2, DECISION_RULE,
    lw2011_variance_test, mechanical_reading, run_nls_gmv_v2_trial, run_nls_gmv_v2_gate, write_v2_artifacts,
)
from usa_etf_features.strategy_registry import load_strategy_registry, enabled_strategies


@pytest.fixture(autouse=True)
def small_blas_pool():
    with threadpool_limits(limits=1):
        yield


# ----------------------------------------------------------------- LW (2011) variance test
def _iid_delta_se(a, b):
    """Independent iid delta-method SE: numerical gradient of log var ratio x moment covariance."""
    x = np.c_[a, b]
    m = np.r_[x.mean(0), (x * x).mean(0)]
    f = lambda v: np.log(v[2] - v[0] ** 2) - np.log(v[3] - v[1] ** 2)
    grad = np.array([(f(m + h) - f(m - h)) / (2 * 1e-7) for h in np.eye(4) * 1e-7])
    y = np.c_[x, x * x]
    return np.sqrt(grad @ np.cov(y, rowvar=False, ddof=1) @ grad / len(a))


def test_lw2011_detects_lower_variance_and_is_antisymmetric():
    rng = np.random.default_rng(5)
    b = rng.normal(.005, .04, 600)
    a = .7 * rng.normal(.005, .04, 600)
    t = lw2011_variance_test(a, b, bootstrap_reps=999)
    assert t['delta_log_var'] < 0 and t['vol_a_ann'] < t['vol_b_ann']
    assert t['p_one_sided_hac'] < .01 and t['p_one_sided_boot'] < .01
    s = lw2011_variance_test(b, a, bootstrap_reps=999)
    assert s['delta_log_var'] == pytest.approx(-t['delta_log_var'], abs=1e-14)
    assert s['p_one_sided_hac'] == pytest.approx(1 - t['p_one_sided_hac'], abs=1e-12)
    assert s['p_one_sided_boot'] > .99


def test_lw2011_scale_invariant_and_iid_se_matches_independent_formula():
    rng = np.random.default_rng(11)
    a, b = rng.normal(.01, .03, 80), rng.normal(.008, .035, 80)
    base = lw2011_variance_test(a, b, bootstrap_reps=199)
    scaled = lw2011_variance_test(7.5 * a, 7.5 * b, bootstrap_reps=199)
    for k in ('delta_log_var', 'z_hac', 'p_one_sided_hac', 'p_one_sided_boot', 'bandwidth'):
        assert scaled[k] == pytest.approx(base[k], rel=1e-9, abs=1e-12)
    iid = lw2011_variance_test(a, b, hac=False, bootstrap_reps=0)
    assert iid['se_hac'] == pytest.approx(_iid_delta_se(a, b), rel=1e-6)
    assert np.isnan(iid['p_one_sided_boot'])
    raw = lw2011_variance_test(a, b, prewhiten=False, bootstrap_reps=0)
    assert raw['se_hac'] > 0 and np.isfinite(raw['bandwidth'])


def test_lw2011_size_under_null_hac():
    rejections, n = 0, 300
    for seed in range(n):
        rng = np.random.default_rng(1000 + seed)
        e = rng.normal(0, .03, (121, 2))
        x = np.zeros_like(e)
        for t in range(1, 121):
            x[t] = .3 * x[t - 1] + e[t]
        rejections += lw2011_variance_test(x[1:, 0], x[1:, 1], bootstrap_reps=0)['p_one_sided_hac'] <= .10
    assert .04 <= rejections / n <= .18


def test_lw2011_bootstrap_reproducible_and_edge_cases():
    rng = np.random.default_rng(2)
    a, b = rng.normal(0, .02, 65), rng.normal(0, .025, 65)
    one, two = (lw2011_variance_test(a, b, bootstrap_reps=499) for _ in range(2))
    assert one == two
    assert 0 < one['p_one_sided_boot'] <= 1 and one['block_size'] == 4 and one['seed'] == 20260926
    with pytest.raises(ValueError, match='12'):
        lw2011_variance_test(a[:11], b[:11])
    same = lw2011_variance_test(a, a, bootstrap_reps=99)
    assert same['delta_log_var'] == 0 and same['p_one_sided_hac'] == .5
    # Aligned on dates (inner join) before testing.
    idx = pd.date_range('2020-01-31', periods=65, freq='BME')
    sa, sb = pd.Series(a, idx), pd.Series(b, idx).iloc[3:]
    assert lw2011_variance_test(sa, sb, bootstrap_reps=0)['n'] == 62


# --------------------------------------------------------------------- mechanical reading
def _summary(over):
    base = {
        156: {METHOD: dict(AnnVol=.08, p_gate=.05, Sharpe_exBIL=.60, MaxDD=-.10, short_duration_share_mean=.10, eff_N_mean=8.),
              PRIMARY: dict(AnnVol=.09, p_gate=np.nan, Sharpe_exBIL=.55, MaxDD=-.12, short_duration_share_mean=.10, eff_N_mean=9.),
              'erc_weekly': dict(AnnVol=.10, p_gate=.9, Sharpe_exBIL=.50, MaxDD=-.15, short_duration_share_mean=.05, eff_N_mean=30.)},
        260: {METHOD: dict(AnnVol=.08, p_gate=.2, Sharpe_exBIL=.60, MaxDD=-.10, short_duration_share_mean=.10, eff_N_mean=8.),
              PRIMARY: dict(AnnVol=.09, p_gate=np.nan, Sharpe_exBIL=.55, MaxDD=-.12, short_duration_share_mean=.10, eff_N_mean=9.),
              'erc_weekly': dict(AnnVol=.10, p_gate=.9, Sharpe_exBIL=.50, MaxDD=-.15, short_duration_share_mean=.05, eff_N_mean=30.)},
    }
    for (window, sid, key), value in over.items():
        base[window][sid][key] = value
    return pd.DataFrame([dict(window_weeks=w, strategy_id=s, **v) for w, d in base.items() for s, v in d.items()])


def _reading(over=None):
    return mechanical_reading(_summary(over or {}))


def test_mechanical_pass_only_when_all_criteria_hold():
    r = _reading()
    assert r['overall'] == 'PASS' and r['failing_criteria'] == [] and r['void_tripwires'] == []
    assert _reading({(156, METHOD, 'p_gate'): .10})['overall'] == 'PASS'          # boundary passes
    assert _reading({(156, METHOD, 'p_gate'): .1001})['failing_criteria'] == ['c1']
    assert _reading({(156, METHOD, 'AnnVol'): .095})['failing_criteria'] == ['c1']  # p small but vol higher
    assert _reading({(156, METHOD, 'Sharpe_exBIL'): .54})['failing_criteria'] == ['c2']
    assert _reading({(156, METHOD, 'Sharpe_exBIL'): .55})['overall'] == 'PASS'   # >= primary is enough
    assert _reading({(156, 'erc_weekly', 'Sharpe_exBIL'): .60})['failing_criteria'] == ['c2']  # must be > ERC
    assert _reading({(156, METHOD, 'MaxDD'): -.13})['failing_criteria'] == ['c3']
    assert _reading({(260, METHOD, 'AnnVol'): .091})['failing_criteria'] == ['c4']
    assert _reading({(260, METHOD, 'Sharpe_exBIL'): .50})['failing_criteria'] == ['c4']
    # c4 is direction only: a large 260w p does not fail it.
    assert _reading({(260, METHOD, 'p_gate'): .9})['overall'] == 'PASS'


@pytest.mark.parametrize('over, wire', [
    ({(156, METHOD, 'short_duration_share_mean'): .51}, 'void_method_short_duration'),
    ({(156, METHOD, 'eff_N_mean'): 4.99}, 'void_method_effN'),
    ({(156, PRIMARY, 'short_duration_share_mean'): .60}, 'void_primary_short_duration'),
    ({(156, PRIMARY, 'eff_N_mean'): 4.0}, 'void_primary_effN'),
])
def test_void_tripwires_override_pass(over, wire):
    r = _reading(over)
    assert r['overall'] == 'VOID' and r['void_tripwires'] == [wire]
    r = _reading({**over, (156, METHOD, 'MaxDD'): -.5})  # VOID also overrides FAIL
    assert r['overall'] == 'VOID'


def test_void_boundaries_and_260w_tripwire_is_information_only():
    assert _reading({(156, METHOD, 'short_duration_share_mean'): .50})['overall'] == 'PASS'
    assert _reading({(156, METHOD, 'eff_N_mean'): 5.0})['overall'] == 'PASS'
    assert _reading({(156, PRIMARY, 'short_duration_share_mean'): .50, (156, PRIMARY, 'eff_N_mean'): 5.0})['overall'] == 'PASS'
    r = _reading({(260, METHOD, 'eff_N_mean'): 3.0})
    assert r['overall'] == 'PASS' and r['sensitivity_260w_tripwires'] == ['void_method_effN']
    assert 'p_gate = max(p_one_sided_hac, p_one_sided_boot) <= 0.10' in DECISION_RULE


# ------------------------------------------------------------------------ runner geometry
@pytest.fixture
def panel():
    rng = np.random.default_rng(29)
    cash, short = ['BIL', 'SGOV', 'SHV'], ['SHY', 'SPTS']
    names = [f'T{i}' for i in range(100)] + cash + short
    vol = np.r_[np.full(100, .025), np.full(3, .0005), np.full(2, .004)]
    weekly = pd.DataFrame(rng.normal(.001, 1, (400, len(names))) * vol,
                          index=pd.date_range('2014-01-03', periods=400, freq='W-FRI'), columns=names)
    monthly = pd.DataFrame(rng.normal(.004, 1, (90, len(names))) * vol * 2,
                           index=pd.date_range('2014-01-31', periods=90, freq='BME'), columns=names)
    uni = pd.DataFrame({'Ticker': names, 'Category': ['Equity'] * 50 + ['Bonds'] * 50 + ['Cash'] * 3 + ['Bonds'] * 2,
                        'cash_like': [t in CASH_LIKE for t in names],
                        'short_duration': [t in SHORT_DURATION for t in names]})
    coverage = pd.DataFrame({'ticker': names, 'thin_lt5y': False, 'adv_proxy': 1e7})
    trial = NLSGMVv2Trial(120, oos_start='2020-01-31', oos_end='2020-12-31')
    rf = pd.DataFrame({'rf': .001, 'source': 'BIL'}, index=pd.PeriodIndex(monthly.index, freq='M'))
    return weekly, monthly, uni, coverage, trial, rf


def test_ex_cash_universe_shared_by_every_strategy(panel):
    weekly, monthly, uni, coverage, trial, _ = panel
    result = run_nls_gmv_v2_trial(weekly, monthly, uni, coverage, trial)
    w = result['weights']
    assert not w.ticker.isin(CASH_LIKE).any()
    assert set(w.strategy_id) == {METHOD, PRIMARY, 'erc_weekly', 'equal_weight', REFERENCE}
    for _, g in w.groupby('decision_date'):
        sets = {s: frozenset(x.ticker) for s, x in g.groupby('strategy_id')}
        assert len(set(sets.values())) == 1          # same eligible set for all, incl. reference
        assert len(sets[METHOD]) == 102               # 100 + 2 short-duration, no cash-like
    assert result['name_counts'].n_eligible.eq(102).all() and not result['name_counts'].skipped.any()
    oos = result['oos_returns']
    assert np.allclose(oos.cost_return, oos.turnover * .0005)
    assert np.allclose(w.groupby(['date', 'strategy_id']).weight.sum(), 1)
    assert (oos.feature_end <= oos.decision_date).all()
    with pytest.raises(ValueError):
        run_nls_gmv_v2_trial(weekly, monthly, uni, coverage, replace(trial, below_floor='raise'))


def test_name_floor_skips_and_lists_months(panel):
    weekly, monthly, uni, coverage, trial, _ = panel
    trial = replace(trial, min_names=100)
    broken = weekly.copy()
    # A gap in 3 names on the first week of the 2020-01 decision window sits inside the 120-week
    # windows of the 2019-12 and 2020-01 decisions only, so those two have N = 99 < 100.
    gap = weekly.loc[:'2020-01-31'].tail(120).index[0]
    broken.loc[gap, ['T0', 'T1', 'T2']] = np.nan
    result = run_nls_gmv_v2_trial(broken, monthly, uni, coverage, trial)
    counts = result['name_counts'].set_index('decision_date')
    skipped = counts.index[counts.skipped]
    assert list(skipped.strftime('%Y-%m')) == ['2019-12', '2020-01']
    assert counts.loc[skipped, 'n_eligible'].eq(99).all() and counts.loc[~counts.skipped, 'n_eligible'].eq(102).all()
    assert counts.below_100.equals(counts.n_eligible < 100) and len(counts) == 12
    oos = result['oos_returns']
    assert not oos.decision_date.isin(skipped).any()          # skipped for ALL strategies
    assert oos.groupby('decision_date').strategy_id.nunique().eq(5).all()
    first = oos.loc[oos.decision_date.eq(oos.decision_date.min())]
    assert np.allclose(first.turnover, .5)                     # initial entry after the skipped months
    # Floor 99 keeps every month.
    assert not run_nls_gmv_v2_trial(broken, monthly, uni, coverage, replace(trial, min_names=99))['name_counts'].skipped.any()
    everything = weekly.copy()
    everything.loc[weekly.index[-1], ['T0', 'T1', 'T2']] = np.nan
    everything.loc[gap, ['T0', 'T1', 'T2']] = np.nan
    with pytest.raises(ValueError, match='every rebalance'):
        run_nls_gmv_v2_trial(everything, monthly, uni, coverage, replace(trial, oos_end='2020-02-29'))


def test_leakage_every_strategy_incl_reference(panel):
    weekly, monthly, uni, coverage, trial, _ = panel
    trial = replace(trial, oos_end='2020-03-31')
    base = run_nls_gmv_v2_trial(weekly, monthly, uni, coverage, trial)['weights']
    rng = np.random.default_rng(1)
    for cut in sorted(base.decision_date.unique()):
        cw, cm = weekly.copy(), monthly.copy()
        for frame in (cw, cm):
            mask = frame.index > cut
            frame.loc[mask] = 3 * frame.loc[mask] + rng.normal(0, .01, frame.loc[mask].shape)
        other = run_nls_gmv_v2_trial(cw, cm, uni, coverage, trial)['weights']
        pd.testing.assert_frame_equal(base.loc[base.decision_date.eq(cut)].reset_index(drop=True),
                                      other.loc[other.decision_date.eq(cut)].reset_index(drop=True))


def test_gate_trial_count_summary_and_artifacts(panel, tmp_path):
    weekly, monthly, uni, coverage, trial, rf = panel
    trials = (trial, replace(trial, window_weeks=130))
    result = run_nls_gmv_v2_gate(weekly, monthly, uni, coverage, trials, rf=rf)
    assert result['trial_count'] == v1.TRIAL_COUNT + 2 == TRIAL_COUNT_V2 == 6
    assert run_nls_gmv_v2_gate(weekly, monthly, uni, coverage, trials, ['x'], rf=rf)['trial_count'] == 7
    s = result['summary']
    assert set(s.role) == {'method', 'primary_null', 'null', 'reference_only'}
    assert s.cash_like_share_mean.eq(0).all() and not s.DSR_decisive.any()
    for _, row in s.iterrows():
        r = result['oos_returns'].query('window_weeks == @row.window_weeks and strategy_id == @row.strategy_id')
        assert row.Sharpe_exBIL == pytest.approx(sharpe_exbil(r.set_index('date')['return'], rf), rel=1e-12)
    assert s.loc[s.strategy_id.eq(PRIMARY), 'p_gate'].isna().all()
    m = s.loc[s.strategy_id.eq(METHOD)].iloc[0]
    assert m.p_gate == max(m.p_one_sided_hac, m.p_one_sided_boot)
    assert (s.short_duration_share_mean.between(0, 1)).all() and (s.eff_N_mean >= 1).all()
    assert len(result['variance_tests']) == 8           # 4 non-primary strategies x 2 windows
    assert result['mechanical_reading']['overall'] in {'PASS', 'FAIL', 'VOID'}
    write_v2_artifacts(result, tmp_path / 'out')
    report = json.loads((tmp_path / 'out/gate_report.json').read_text())
    assert report['trial_count'] == 6 and report['dsr_decisive'] is False and report['status'].startswith('PENDING')
    md = (tmp_path / 'out/gate_report.md').read_text()
    for needle in ('PENDING', 'Quant decides', 'reference only', 'LW2011', 'skipped months: none', 'months under 100'):
        assert needle in md
    assert PREREGISTERED_V2 == (NLSGMVv2Trial(156), NLSGMVv2Trial(260))
    assert PREREGISTERED_V2[0].min_names == 95 and PREREGISTERED_V2[0].exclude_cash_like


def test_write_refuses_to_overwrite_archived_processed_dir():
    with pytest.raises(FileExistsError):
        write_v2_artifacts({}, 'data/processed/nonlinear_shrinkage_gmv')


def test_registry_v2_disabled_and_v1_unchanged():
    import usa_etf_features.strategy_registry as registry
    specs = load_strategy_registry('config/strategies.yaml')
    v2 = next(s for s in specs if s.id == 'nonlinear_shrinkage_gmv_v2_excash')
    assert v2.enabled is False and v2 not in enabled_strategies(specs)
    assert v2.default_params['min_names'] == 95 and v2.default_params['exclude_cash_like'] is True
    assert v2.entrypoint in inspect.getsource(registry._strategy_current_result)
    old = next(s for s in specs if s.id == 'nonlinear_shrinkage_gmv')
    assert old.enabled is False and old.default_params['min_names'] == 100
