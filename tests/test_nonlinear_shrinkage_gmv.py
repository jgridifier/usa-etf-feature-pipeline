"""Synthetic clean-room math, leakage, geometry and research gate tests."""
from dataclasses import replace
import json

import numpy as np
import pandas as pd
import pytest
from scipy.integrate import quad
from sklearn.covariance import LedoitWolf
from threadpoolctl import threadpool_limits

from usa_etf_features.nonlinear_shrinkage_gmv import (
    METHOD, PRIMARY, REFERENCE, NLSGMVTrial, nonlinear_shrinkage_cov,
    nonlinear_shrinkage_spectrum, epanechnikov_hilbert, run_nls_gmv_trial,
    run_nls_gmv_gate, write_gate_artifacts, summarize_gate,
)
from usa_etf_features.strategy_registry import load_strategy_registry, enabled_strategies


@pytest.fixture(autouse=True)
def small_blas_pool():
    with threadpool_limits(limits=1):
        yield


def test_estimator():
    r = np.random.default_rng(17).normal(size=(156, 125))
    cov = nonlinear_shrinkage_cov(r)
    sp = nonlinear_shrinkage_spectrum(r)
    assert sp['n_eff'] == 155
    assert sp['c'] == 125 / 155
    assert np.allclose(cov, cov.T)
    assert np.linalg.eigvalsh(cov).min() > 0
    _, U = np.linalg.eigh(np.cov(r, rowvar=False))
    rotated = U.T @ cov @ U
    assert np.linalg.norm(rotated - np.diag(np.diag(rotated))) < 1e-10 * np.linalg.norm(cov)
    assert np.allclose(nonlinear_shrinkage_cov(3.2 * r), 3.2**2 * cov)
    assert np.array_equal(nonlinear_shrinkage_cov(r[:130]), nonlinear_shrinkage_cov(r[:130].copy()))
    assert nonlinear_shrinkage_spectrum(r, demean=False)['n_eff'] == 156
    for bad in (r[:125], r[:126], np.empty((10, 0)), np.full((156, 125), np.nan), np.zeros((156, 125))):
        with pytest.raises(ValueError):
            nonlinear_shrinkage_cov(bad)


def test_monte_carlo_losses():
    losses = []
    p, T = 125, 156
    for seed in range(60):
        rng = np.random.default_rng(seed)
        U, _ = np.linalg.qr(rng.normal(size=(p, p)))
        spectrum = np.r_[50., 10., 8., 5., np.linspace(.5, 1.5, p - 4)]
        population = (U * spectrum) @ U.T
        r = (rng.normal(size=(T, p)) * np.sqrt(spectrum)) @ U.T
        estimates = (nonlinear_shrinkage_cov(r), LedoitWolf().fit(r).covariance_, np.cov(r, rowvar=False))
        ones = np.ones(p)
        optimal_var = 1 / (ones @ np.linalg.solve(population, ones))
        row = []
        for estimate in estimates:
            w = np.linalg.solve(estimate, ones)
            w /= w.sum()
            row.append([np.sum((estimate - population)**2), (w @ population @ w) / optimal_var])
        losses.append(row)
    mean = np.mean(losses, axis=0)
    assert np.all(mean[0] < mean[1]), mean
    assert np.all(mean[1] < mean[2]), mean


def test_kernel_quadrature():
    a = np.sqrt(5)
    def kernel(t):
        return 3 / (4 * a) * (1 - t*t / 5)
    for x in (-5., -2., -.3, 0., .7, 2., 4.):
        integral = quad(kernel, -a, a, weight='cauchy', wvar=x, epsabs=1e-12)[0] / np.pi
        assert epanechnikov_hilbert(x) == pytest.approx(integral, abs=1e-8)
    assert np.allclose(epanechnikov_hilbert(np.array([-a, a])), -3 * np.array([-a, a]) / (10 * np.pi))
    lam = np.array([.2, .7, 1., 2., 8.])
    h = 155**(-1/3)
    def density(x):
        z = (x - lam) / (lam * h)
        return np.mean(3 / (4 * a * lam * h) * np.maximum(0., 1 - z*z / 5))
    edges = np.sort(np.r_[lam * (1 - a*h), lam * (1 + a*h)])
    assert quad(density, edges.min(), edges.max(), points=edges, epsabs=1e-10)[0] == pytest.approx(1., abs=1e-8)


def test_hilbert_far_field_is_numerically_stable():
    # Regression: the closed form cancels catastrophically for |x| >> sqrt(5)
    # (wrong by orders of magnitude at |x| ~ 1e7). Cross-check vs. quadrature.
    a = np.sqrt(5)
    def kernel(t):
        return 3 / (4 * a) * (1 - t*t / 5)
    for x in (3., 9.999, 10., 10.001, 50., 1e3, 1e5, 1e7, 1e8, 1e10):
        for signed in (x, -x):
            integral = quad(kernel, -a, a, weight='cauchy', wvar=signed, epsabs=0, epsrel=1e-13)[0] / np.pi
            assert epanechnikov_hilbert(signed) == pytest.approx(integral, rel=1e-9)
    assert epanechnikov_hilbert(1e12) == pytest.approx(-1 / (np.pi * 1e12), rel=1e-9)
    grid = np.array([[1e8, 2.], [0., -1e8]])
    assert epanechnikov_hilbert(grid).shape == grid.shape


def test_estimator_on_widely_dispersed_spectrum():
    # Asset variances spanning ~7 decades (cash-like to crypto-like), as in the ETF panel.
    rng = np.random.default_rng(3)
    p, T = 110, 156
    vols = np.sqrt(np.logspace(-8, -2, p))
    loadings = rng.normal(size=p) * vols
    r = rng.normal(size=(T, 1)) * loadings + rng.normal(size=(T, p)) * vols
    sp = nonlinear_shrinkage_spectrum(r)
    lam, d = sp['sample_eigenvalues'], sp['shrunk_eigenvalues']
    assert np.isfinite(d).all() and (d > 0).all()
    # Isolated top eigenvalues stay close to their sample values; trace roughly kept.
    assert 0.5 < d[-1] / lam[-1] < 1.5
    assert 0.8 < d.sum() / lam.sum() < 1.25
    cov = nonlinear_shrinkage_cov(r)
    sample_diag = np.diag(np.cov(r, rowvar=False))
    assert 0.5 < cov[-1, -1] / sample_diag[-1] < 2


@pytest.fixture
def panel():
    rng = np.random.default_rng(29)
    names = [f'T{i}' for i in range(105)]
    weekly = pd.DataFrame(rng.normal(.001, .025, (400, 105)),
                          index=pd.date_range('2014-01-03', periods=400, freq='W-FRI'), columns=names)
    monthly = pd.DataFrame(rng.normal(.004, .04, (90, 105)),
                           index=pd.date_range('2014-01-31', periods=90, freq='BME'), columns=names)
    uni = pd.DataFrame({'Ticker': names, 'Category': 'Equity'})
    coverage = pd.DataFrame({'ticker': names, 'thin_lt5y': False, 'adv_proxy': 1e7})
    trial = NLSGMVTrial(120, oos_start='2020-01-31', oos_end='2020-03-31')
    return weekly, monthly, uni, coverage, trial


def test_leakage_and_geometry(panel):
    weekly, monthly, uni, coverage, trial = panel
    result = run_nls_gmv_trial(*panel)
    oos, weights = result['oos_returns'], result['weights']
    d = weights.decision_date.min()
    rng = np.random.default_rng(1)
    for cut in sorted(weights.decision_date.unique()):
        # Perturb every weekly and monthly return strictly after the rebalance date.
        changed_w, changed_m = weekly.copy(), monthly.copy()
        for frame in (changed_w, changed_m):
            mask = frame.index > cut
            frame.loc[mask] = 3 * frame.loc[mask] + rng.normal(0, .01, frame.loc[mask].shape)
        other = run_nls_gmv_trial(changed_w, changed_m, uni, coverage, trial)
        before = weights.loc[weights.decision_date.eq(cut)]
        after = other['weights'].loc[other['weights'].decision_date.eq(cut)]
        assert set(before.strategy_id) == {METHOD, PRIMARY, 'erc_weekly', 'equal_weight'}
        pd.testing.assert_frame_equal(before, after)
    assert weights.strategy_id.nunique() == 4
    assert (oos.feature_end <= oos.decision_date).all()
    assert set(oos.date) == set(monthly.loc[trial.oos_start:trial.oos_end].index)
    assert np.allclose(oos.loc[oos.decision_date.eq(d)].turnover, .5)
    assert np.allclose(oos.cost_return, oos.turnover * .0005)
    assert np.allclose(weights.groupby(['date', 'strategy_id']).weight.sum(), 1)
    assert weights.weight.between(0, 1).all()
    broken = weekly.copy()
    broken.loc['2020-01-03', broken.columns[:6]] = np.nan
    with pytest.raises(ValueError, match='N=99'):
        run_nls_gmv_trial(broken, monthly, uni, coverage, trial)
    with pytest.raises(ValueError, match='empty OOS'):
        run_nls_gmv_trial(weekly, monthly, uni, coverage, replace(trial, oos_start='2030-01-01'))
    with pytest.raises(ValueError, match='weekly index'):
        run_nls_gmv_trial(weekly.iloc[::-1], monthly, uni, coverage, trial)
    with pytest.raises(ValueError, match='calendar month'):
        run_nls_gmv_trial(weekly, monthly.drop(monthly.index[10]), uni, coverage, trial)
    missing = monthly.copy()
    missing.loc[trial.oos_start, missing.columns[0]] = np.nan
    with pytest.raises(ValueError, match='missing OOS'):
        run_nls_gmv_trial(weekly, missing, uni, coverage, trial)


def test_gate_reports(panel, tmp_path):
    weekly, monthly, uni, coverage, trial = panel
    # Independent reference-only fixture, with the archive's strategy identifier.
    dates = monthly.loc[trial.oos_start:trial.oos_end].index
    reference = pd.DataFrame({'date': dates, 'decision_date': monthly.index[monthly.index.get_indexer(dates) - 1],
                              'strategy_id': 'minvar_lw__0', 'n_names': 105,
                              'return': [.01, -.005, .02], 'turnover': [.5, .05, .04]})
    reference.to_csv(tmp_path / 'oos_returns.csv', index=False)
    pd.DataFrame([{'date': d, 'strategy_id': 'minvar_lw__0', 'ticker': t, 'weight': 1/105}
                  for d in dates for t in weekly.columns]).to_csv(tmp_path / 'weights.csv', index=False)
    trials = (trial, replace(trial, window_weeks=130))
    result = run_nls_gmv_gate(weekly, monthly, uni, coverage, trials, tmp_path)
    assert result['trial_count'] == 4  # 2 configs + 2 invalidated-run configs (Quant ruling)
    assert set(result['summary'].role) == {'method', 'null', 'primary_null', 'reference_only'}
    assert len(result['summary']) == 10
    assert result['summary'].n_months.eq(3).all()
    assert result['weekly_vs_monthly_lw'].n_common_months.eq(3).all()
    assert result['summary'].loc[result['summary'].strategy_id.eq(PRIMARY), 'NW_t_vs_minvar_lw_weekly'].isna().all()
    assert result['summary'].loc[result['summary'].strategy_id.eq(REFERENCE), 'avg_N_eligible'].eq(105).all()
    write_gate_artifacts(result, tmp_path / 'out')
    report = json.loads((tmp_path / 'out/gate_report.json').read_text())
    assert report['trial_count'] == 4
    assert report['verdict'] == 'VOID' and report['dsr_decisive'] is False
    assert report['trial_count_breakdown'] == {'preregistered_configs': 2, 'extra_previews': 0, 'invalidated_run_configs': 2}
    assert not result['summary'].DSR_decisive.any()
    assert report['summary'][0]['start'] == '2020-01-31'
    md = (tmp_path / 'out/gate_report.md').read_text()
    assert 'reference only' in md and 'VOID — cash-dominated, no evidence of estimator edge' in md
    assert 'non-decisive' in md and 'PASS' not in md.replace('Not PASS', '')
    assert 'Holdings composition' in md
    assert set(result['composition'].strategy_id) >= {METHOD, PRIMARY, REFERENCE}
    assert run_nls_gmv_gate(weekly, monthly, uni, coverage, trials, tmp_path, extra_previews=['x'])['trial_count'] == 5
    assert run_nls_gmv_gate(weekly, monthly, uni, coverage, trials, tmp_path, disclosed_runs=())['trial_count'] == 2


def test_registry():
    import usa_etf_features.strategy_registry as registry
    specs = load_strategy_registry('config/strategies.yaml')
    spec = next(s for s in specs if s.id == METHOD)
    assert spec.enabled is False
    assert spec not in enabled_strategies(specs)
    assert spec.entrypoint == 'usa_etf_features.strategy_registry:nonlinear_shrinkage_gmv'
    assert callable(registry.nonlinear_shrinkage_gmv)
    import inspect
    assert spec.entrypoint in inspect.getsource(registry._strategy_current_result)


def test_registry_adapter_asof(panel, tmp_path):
    from usa_etf_features.strategy_registry import nonlinear_shrinkage_gmv
    weekly, monthly, uni, coverage, _ = panel
    for name, frame in (('weekly', weekly), ('monthly', monthly)):
        frame.to_csv(tmp_path / f'{name}.csv')
    uni.to_csv(tmp_path / 'universe.csv', index=False)
    coverage.to_csv(tmp_path / 'coverage.csv', index=False)
    spec = next(s for s in load_strategy_registry('config/strategies.yaml') if s.id == METHOD)
    spec = replace(spec, default_params={**spec.default_params,
                   'weekly_csv': str(tmp_path / 'weekly.csv'), 'monthly_csv': str(tmp_path / 'monthly.csv'),
                   'coverage_csv': str(tmp_path / 'coverage.csv'), 'oos_start': '2020-01-31'})
    result = nonlinear_shrinkage_gmv(pd.DataFrame(), spec, universe_csv=tmp_path / 'universe.csv', asof='2020-03-16')
    assert result.weights.weight.sum() == pytest.approx(1.)
    assert result.returns.date.max() == pd.Timestamp('2020-02-28')
    assert result.diagnostics.window_weeks.eq(156).all()
    assert result.diagnostics.trial_count.eq(4).all()


def test_metrics_starting_wealth_and_alignment():
    from usa_etf_features.vol_target import newey_west_tstat, deflated_sharpe_approx
    dates = pd.date_range('2020-01-31', periods=4, freq='BME')
    returns = {METHOD: [-.1, .04, -.02, .08], PRIMARY: [-.08, .03, -.01, .06]}
    oos = pd.DataFrame([dict(window_weeks=156, strategy_id=s, date=d, n_names=2,
                            turnover=.5 if i == 0 else .1, **{'return': r[i]})
                        for s, r in returns.items() for i, d in enumerate(dates)])
    weights = pd.DataFrame([dict(window_weeks=156, strategy_id=s, date=d, ticker=t, weight=w)
                           for s in returns for d in dates for t, w in [('A', .25), ('B', .75)]])
    summary = summarize_gate(oos.sample(frac=1, random_state=42), weights, 2).set_index('strategy_id')
    row = summary.loc[METHOD]
    assert row.MaxDD == pytest.approx(-.1)
    assert row.AnnReturn == pytest.approx(np.prod(1 + np.array(returns[METHOD]))**3 - 1)
    assert row.OOS_var_monthly == pytest.approx(np.var(returns[METHOD], ddof=1))
    assert row.OOS_var_ann == pytest.approx(12 * row.OOS_var_monthly)
    assert row.HHI_mean == pytest.approx(.625)
    assert row.eff_N_mean == pytest.approx(1.6)
    assert row.turnover_per_year == pytest.approx(2.4)
    difference = pd.Series(np.array(returns[METHOD]) - returns[PRIMARY])
    assert row.NW_t_vs_minvar_lw_weekly == pytest.approx(newey_west_tstat(difference, lags=3))
    assert row.DSR == pytest.approx(deflated_sharpe_approx(row.Sharpe_rf0 / np.sqrt(12), 4, 2))
