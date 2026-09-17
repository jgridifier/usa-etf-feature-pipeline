"""Spectral panel math, calendar alignment and anti-lookahead checks."""
import numpy as np
import pandas as pd
import pytest
from sklearn.covariance import LedoitWolf

from usa_etf_features.spectral_risk_parity import (
    SpectralTrial, run_spectral_trial, run_spectral_grid, read_returns, null_weights,
)
from usa_etf_features.portfolio import ledoit_wolf_cov
from usa_etf_features.strategy_registry import load_strategy_registry
from usa_etf_features.walkforward import assert_no_same_period_leakage


@pytest.fixture
def panel():
    rng = np.random.default_rng(72)
    names = [f"T{i}" for i in range(110)]
    factors = rng.normal(0, .025, (120, 3))
    r = factors @ rng.uniform(.1, 1, (3, 110)) + rng.normal(.003, .018, (120, 110))
    returns = pd.DataFrame(r, index=pd.date_range('2010-01-31', periods=120, freq='ME'), columns=names)
    uni = pd.DataFrame({'Ticker': names, 'Category': [f'Category{i % 5}' for i in range(110)]})
    coverage = pd.DataFrame({'ticker': names, 'thin_lt5y': False, 'adv_proxy': 2e7})
    return returns, uni, coverage


def test_name_weights_leakage_and_nulls(panel):
    returns, uni, cov = panel
    result = run_spectral_trial(returns.iloc[:63], uni, cov)
    weights = result['weights']
    assert weights.n_names.min() >= 100
    assert (weights.weight >= 0).all()
    assert np.allclose(weights.groupby(['strategy_id', 'date']).weight.sum(), 1)
    oos = result['oos_returns']
    assert oos.groupby('strategy_id').size().nunique() == 1
    for row in oos.itertuples():
        assert_no_same_period_leakage(row.decision_date, row.feature_end, row.label_start, row.date)
    assert result['summary'].DSR.notna().all()
    assert result['summary'].n_trials.eq(4).all()
    assert np.allclose(oos.cost_return, oos.turnover * .0005)
    changed = returns.iloc[:63].copy()
    changed.iloc[60:] += .2
    other = run_spectral_trial(changed, uni, cov)
    pd.testing.assert_frame_equal(weights[weights.date == weights.date.min()],
                                  other['weights'][other['weights'].date == weights.date.min()])
    assert not np.allclose(oos['return'], other['oos_returns']['return'])


def test_sleeves_and_grid(panel):
    r, u, c = panel
    result = run_spectral_grid(r.iloc[:63], u, c, [SpectralTrial(mode='sleeve'), SpectralTrial(mode='sleeve', gamma=.5)])
    assert result['summary'].n_trials.eq(8).all()
    assert len(result['trial_registry']) == 8
    assert result['eigen_diagnostics'].n_sleeves.eq(5).all()
    w = result['weights'].merge(u, left_on='ticker', right_on='Ticker')
    assert w.groupby(['strategy_id', 'date', 'Category']).weight.nunique().eq(1).all()


def test_gates_missing_and_months(panel):
    r, u, c = panel
    with pytest.raises(ValueError, match='N=99'):
        run_spectral_trial(r.iloc[:, :99], u, c)
    r.iloc[60, 0] = np.nan
    with pytest.raises(ValueError, match='missing OOS'):
        run_spectral_trial(r, u, c)
    with pytest.raises(ValueError, match='calendar month'):
        run_spectral_trial(r.drop(r.index[20]), u, c)


def test_lw_high_dimension_and_erc(panel):
    r, _, _ = panel
    win = r.iloc[:60]
    cov = ledoit_wolf_cov(win, force_shrinkage=True).to_numpy()
    assert np.allclose(cov, LedoitWolf().fit(win).covariance_)
    weights = null_weights(win)
    erc = weights['erc']; risk = erc * (cov @ erc)
    assert np.max(np.abs(risk / risk.sum() - 1 / len(erc))) < 1e-5
    ew = weights['equal_weight']; mv = weights['minvar_lw']
    assert mv @ cov @ mv <= ew @ cov @ ew


def test_registry_and_partial_loader(tmp_path):
    spec = next(s for s in load_strategy_registry('config/strategies.yaml') if s.id == 'spectral_risk_parity')
    assert spec.enabled and '1610.08818' in spec.method_citation
    assert spec.method_citation_id == 'adia_spectral_rp_2026_agp_1610_08818'
    path = tmp_path / 'returns.csv'
    pd.DataFrame({'A': [.1, .2]}, index=['2026-08-31', '2026-09-16']).to_csv(path)
    assert len(read_returns(path)) == 1


def test_registry_entrypoint_panel_and_daily(panel, tmp_path):
    from dataclasses import replace
    from usa_etf_features.strategy_registry import spectral_risk_parity
    r, u, c = panel
    r = r.iloc[:63]
    universe = tmp_path / 'universe.csv'
    coverage = tmp_path / 'coverage.csv'
    returns = tmp_path / 'returns.csv'
    u.to_csv(universe, index=False)
    c.to_csv(coverage, index=False)
    r.to_csv(returns)
    spec = next(s for s in load_strategy_registry('config/strategies.yaml') if s.id == 'spectral_risk_parity')
    spec = replace(spec, default_params={'returns_csv': str(returns), 'coverage_csv': str(coverage)})
    result = spectral_risk_parity(pd.DataFrame(), spec, universe_csv=universe, asof=r.index[-1])
    assert result.weights.weight.sum() == pytest.approx(1)
    assert result.diagnostics.n_trials.eq(4).all()
    assert result.returns.date.max() <= r.index[-1]
    # Daily input sampled from a monthly price path exercises monthly_returns wiring.
    prices = (1 + r).cumprod() * 100
    prices.loc[r.index[0] - pd.offsets.MonthEnd()] = 100
    prices = prices.sort_index().resample('D').ffill()
    spec = replace(spec, default_params={})
    result = spectral_risk_parity(prices, spec, universe_csv=universe)
    assert not result.returns.empty
