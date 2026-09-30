"""Offline synthetic tests; never run the real-data EPO gate."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest
import yaml

from usa_etf_features import epo_allocator as e, gate_metrics as gm
from usa_etf_features.monthly_panel import load_monthly_panel
from usa_etf_features.gate_results import GateResultError

PIN = 'c071017a22edb21e4ad5c89071194771074c03da5df9a8604baab36324332d75'


def test_universe_and_preregistration():
    raw = (e.ROOT/e.PREREG_PATH).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PIN == e.PREREG_SHA256
    p = yaml.safe_load(raw)
    u = pd.read_csv(e.ROOT/'data/raw/usa_universe_categorized.csv')
    expected = gm.EQUITY_ONLY | frozenset(p['universe']['added_tickers'])
    tagged = gm.epo_universe_tickers(u)
    assert tagged == gm.EPO_UNIVERSE == expected and len(tagged) == 135
    assert tagged >= gm.EQUITY_ONLY
    assert not tagged & (gm.CASH_LIKE | gm.SHORT_DURATION | gm.NEAR_CASH)
    assert not tagged & set('APRH APRJ JAJL JANH JANJ JULH JULJ OCTH OCTJ QTAP QTJL QTOC SFLR SPUT TFJL XBJA XDQQ XDSQ XTAP XTJA XTJL XTOC XUSP KMAY RFLR VIXY AAAU GBND GCAL GCOR GEMD GHYB GIGB GIGL GIND GINN GMNY GMUB GPIQ GPRF GSC GSEU GSEW GSJY GTEK GTIP GVIP GVUS GXUS TRTY'.split())
    assert not tagged & set(u.loc[u.Category.isin(['Defined Outcome / Buffer / Structured', 'Crypto / Digital Assets']), 'Ticker'])
    classes = gm.epo_asset_class(u)
    assert set(classes.loc[list(tagged)]) == {'equity', 'bond', 'commodity'}
    assert classes.loc[list(gm.EQUITY_ONLY)].eq('equity').all()
    assert classes.loc[~classes.index.isin(tagged)].eq('').all()
    assert set(classes.index[classes.eq('bond')]) == gm.EPO_BOND == set(p['asset_class']['bond'])
    assert set(classes.index[classes.eq('commodity')]) == gm.EPO_COMMODITY == set(p['asset_class']['commodity'])
    assert u.set_index('Ticker').loc['VT', 'Category'] == 'Municipal Bonds'
    assert classes['VT'] == 'equity'
    flipped = u.copy(); flipped.loc[flipped.Ticker.eq('VT'), 'epo_universe'] = False
    assert gm.epo_universe_tickers(flipped) == tagged-{'VT'}
    flipped['Category'] = 'garbage'
    pd.testing.assert_series_equal(classes, gm.epo_asset_class(flipped))
    assert gm.EPO_UNIVERSE_COLUMN not in gm.COMPOSITION_TAG_COLUMNS
    assert (p['method']['w_grid']['primary'], *p['method']['w_grid']['sensitivities']) == e.W_GRID
    assert p['trial_count'] == e.TRIAL_COUNT == 11
    assert p['universe']['name_floor'] == e.NAME_FLOOR == 100
    assert p['universe']['count'] == 135 and len(p['universe']['exclusions']) == 6
    assert '12-1' in p['signal']['name'] and 'BIL' in p['signal']['name']
    assert 'strictly greater' in p['book_eligibility']['cio_condition_1_anchor']
    assert 'growth-mandate fit' in p['book_eligibility']['cio_condition_2_asset_mix']
    assert 'No reruns' in p['no_reruns'] and 'no large pretrained' in p['method_constraint']['rule']
    assert e.WINDOW_WEEKS == 156 and e.MIN_MONTHS == 60


@pytest.fixture
def toy():
    rng = np.random.default_rng(19)
    weekly = rng.normal(size=(156, 3)) * [.01, .025, .04]
    sigma, omega, cov, V = e.epo_inputs(weekly)
    return sigma, cov, V, e.inverse_vol_anchor(sigma), np.array([.01, -.02, .03])


@pytest.mark.parametrize('w', [0., .5, .75, .9, 1.])
def test_math_and_qp(toy, w):
    sigma, cov, V, a, s = toy
    sw = e.sigma_w(cov, V, w); gamma = e.epo_gamma(s, sw, cov, a)
    simple = e.simple_epo(s, sw, gamma)
    np.testing.assert_allclose(simple, np.linalg.solve(sw, s)/gamma)
    np.testing.assert_allclose(simple@cov@simple, a@cov@a)
    closed = e.anchored_epo_closed_form(s, sw, V, a, w, gamma)
    np.testing.assert_allclose(closed, np.linalg.solve(sw, (1-w)*s+gamma*w*V@a)/gamma)
    x, diag = e.epo_long_only(s, sw, cov, V, a, w)
    y, _ = e.epo_long_only(3.4*s, sw, cov, V, a, w)
    np.testing.assert_allclose(x, y, atol=1e-8)
    assert x.min() >= 0 and x.sum() == pytest.approx(1)
    assert diag['kkt_residual'] < 3e-6
    if w == 1:
        np.testing.assert_allclose(x, a, atol=1e-8, rtol=0)
        np.testing.assert_allclose(closed, a)
        np.testing.assert_allclose(simple, np.linalg.solve(V, s)/gamma)
        assert diag['nit'] >= 1  # the actual SLSQP ran; no w=1 shortcut
    if w == 0:
        np.testing.assert_allclose(simple, np.linalg.solve(cov, s)/gamma)


def test_zero_signal_and_signal_lag(toy):
    sigma, cov, V, a, s = toy
    x, d = e.epo_long_only(s*0, cov, cov, V, a, .75)
    np.testing.assert_array_equal(x, a)
    assert d['status'] == 'anchor (s=0)'
    history = np.full((12, 3), .01); history[:, 1] = -.01; history[:, 2] = 0
    expected = .1*sigma*np.array([1, -1, 0])
    np.testing.assert_allclose(e.trend_signal(history, sigma), expected)
    history[-1] = [-.9, 5, 1]
    np.testing.assert_allclose(e.trend_signal(history, sigma), expected)


@pytest.fixture
def panels(tmp_path):
    rng = np.random.default_rng(41)
    names = ['VOO', 'QQQM', 'IJR', 'VT', 'SPHD', 'AGG', 'BND', 'GLD']
    dates = pd.date_range('2013-01-31', periods=115, freq='ME')
    monthly = pd.DataFrame(rng.normal(.006, .04, (len(dates), len(names))), index=dates, columns=names)
    path = tmp_path/'monthly.csv'; monthly.to_csv(path)
    monthly = load_monthly_panel(path, asof='2022-07-31')
    weeks = pd.date_range('2012-01-06', '2022-08-05', freq='W-FRI')
    weekly = pd.DataFrame(rng.normal(.001, .02, (len(weeks), len(names))), index=weeks, columns=names)
    u = pd.DataFrame({'Ticker': names, 'Category': ['Equity']*5+['Bond']*2+['Commodity'],
                      'epo_universe': True, 'epo_asset_class': ['equity']*5+['bond']*2+['commodity'],
                      'equity_only': [True]*3+[False]*5, 'cash_like': False,
                      'short_duration': False, 'near_cash': False})
    rf = pd.DataFrame({'rf': .001, 'source': 'synthetic'}, index=dates.to_period('M'))
    return weekly, monthly, u, rf


def backtest(panels, **kwargs):
    w, m, u, rf = panels
    return e.run_epo_backtest(w, m, u, rf=rf, name_floor=5, min_months=12,
                               first_decision='2021-01-31', **kwargs)


def test_leakage_calendar_turnover(panels):
    base = backtest(panels)
    weekly, monthly, u, rf = panels
    date = base['oos_returns'].date.min(); decision = base['oos_returns'].decision_date.min()
    changed_m = monthly.copy(); changed_m.loc[date] += .3
    changed_w = weekly.copy(); changed_w.loc[changed_w.index > decision] *= 3
    changed = backtest((changed_w, changed_m, u, rf))
    pd.testing.assert_frame_equal(base['weights'].query('date == @date').reset_index(drop=True),
                                  changed['weights'].query('date == @date').reset_index(drop=True))
    w = base['weights'].query('strategy_id != @e.BOOK1')
    assert w.groupby(['date', 'strategy_id']).ticker.apply(tuple).groupby('date').nunique().eq(1).all()
    assert base['oos_returns'].groupby('strategy_id').date.apply(tuple).nunique() == 1
    np.testing.assert_allclose(base['oos_returns'].query('date == @date').turnover, .5)
    old = pd.Series({'A': .5, 'B': .5})
    drift = e.drift_weights(old, pd.Series({'A': .2, 'B': -.2}))
    np.testing.assert_allclose(drift, [.6, .4])
    assert .5*(old-drift).abs().sum() == pytest.approx(.1)
    second = base['oos_returns'].loc[lambda f: f.strategy_id.eq(e.ANCHOR)].iloc[1]
    prev = base['weights'].query('strategy_id == @e.ANCHOR and date == @date').set_index('ticker').weight
    target = base['weights'].loc[lambda f: f.strategy_id.eq(e.ANCHOR) & f.date.eq(second.date)].set_index('ticker').weight
    expected = .5*(target-e.drift_weights(prev, monthly.loc[second.decision_date])).abs().sum()
    assert second.turnover == pytest.approx(expected)
    assert second['return'] == pytest.approx(second.gross_return-.0005*expected)
    assert second.return_25bp == pytest.approx(second.gross_return-.0025*expected)
    composition = gm.composition_tripwire(base['weights'], u, method=e.METHOD, primary_null=e.PRIMARY)
    assert composition['method_share'] == composition['null_share'] == 0


def test_zero_signal_logged_and_missing_evaluation(panels):
    weekly, monthly, u, rf = panels
    flat = monthly.copy(); flat[:] = .001
    result = backtest((weekly, flat, u, rf))
    assert len(result['signal_log']) == len(result['name_counts'])
    assert result['projection_diagnostics'].anchor_held.all()
    missing = monthly.copy(); missing.loc['2021-02-28', 'VOO'] = np.nan
    with pytest.raises(ValueError, match='explicit data repair required'):
        backtest((weekly, missing, u, rf))


def test_bootstrap():
    rng = np.random.default_rng(45)
    index = pd.date_range('2000-01-31', periods=180, freq='ME')
    rf = pd.DataFrame({'rf': 0}, index=index.to_period('M'))
    a = pd.Series(rng.normal(.002, .04, len(index)), index=index)
    b = pd.Series(rng.normal(.002, .04, len(index)), index=index)
    same = e.lw2008_sharpe_bootstrap(a, a, rf, reps=99)
    assert same['z'] == 0 and same['se_nat'] < 1e-14 and same['p_one_sided'] == 1
    ab = e.lw2008_sharpe_bootstrap(a, b, rf, reps=199)
    ba = e.lw2008_sharpe_bootstrap(b, a, rf, reps=199)
    assert ab['z'] == pytest.approx(-ba['z'])
    assert ab['p_two_sided'] == ba['p_two_sided']
    assert ab['p_one_sided']+ba['p_one_sided'] == pytest.approx(201/200)
    strong = e.lw2008_sharpe_bootstrap(a+.04, b, rf, reps=199)
    assert strong['p_one_sided'] <= .01
    rejected = 0
    for _ in range(40):
        x, y = rng.normal(0, .04, (2, len(index)))
        p = e.lw2008_sharpe_bootstrap(pd.Series(x, index=index), pd.Series(y, index=index), rf, reps=99)['p_one_sided']
        rejected += p <= .05
    assert rejected <= 7  # broad deterministic size check, not a precision calibration


@pytest.fixture
def git_repo(tmp_path):
    if shutil.which('git') is None:
        pytest.skip('git not on PATH')
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, check=True, capture_output=True)
    git('init'); git('config', 'user.email', 'test@example.com'); git('config', 'user.name', 'Test')
    path = tmp_path/e.PREREG_PATH; path.parent.mkdir()
    path.write_bytes((e.ROOT/e.PREREG_PATH).read_bytes())
    (tmp_path/'tracked').write_text('original')
    git('add', '.'); git('commit', '-m', 'pin')
    return tmp_path, path, git


def test_guard_clean(git_repo):
    root, _, _ = git_repo
    p = e.verify_preregistration(root=root)
    assert p['sha256'] == PIN and p['verified'] and len(p['head_commit']) == 40


@pytest.mark.parametrize('change', ['uncommitted', 'committed', 'untracked', 'unstaged', 'head_mismatch'])
def test_guard_and_script_before_load(git_repo, monkeypatch, change):
    root, path, git = git_repo
    match = 'sha256' if change in ('uncommitted', 'committed', 'head_mismatch') else 'not clean'
    if change in ('uncommitted', 'committed', 'head_mismatch'):
        path.write_text(path.read_text()+'\n')
        if change != 'uncommitted':
            git('add', '.'); git('commit', '-m', 'changed')
        if change == 'head_mismatch':
            path.write_bytes((e.ROOT/e.PREREG_PATH).read_bytes())
            # Hide the disk change from status, still require the HEAD blob pin.
            git('update-index', '--assume-unchanged', str(e.PREREG_PATH))
    elif change == 'untracked':
        (root/'new').write_text('dirty')
    else:
        (root/'tracked').write_text('changed')
    with pytest.raises(e.PreregistrationError, match=match):
        e.verify_preregistration(root=root)
    spec = importlib.util.spec_from_file_location('run_epo_gate', e.ROOT/'scripts/run_epo_gate.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    def fail(*a, **kw):
        pytest.fail('data loaded before guard')
    monkeypatch.setattr(module, 'load_monthly_panel', fail)
    with pytest.raises(e.PreregistrationError, match=match):
        module.main([], root=root)


def eligibility_data():
    full = pd.DataFrame([dict(strategy_id=e.METHOD, Sharpe_exBIL=1.), dict(strategy_id=e.ANCHOR, Sharpe_exBIL=.8)])
    book = pd.DataFrame([dict(strategy_id=e.METHOD, Sharpe_exBIL=1., MaxDD=-.1),
                         dict(strategy_id=e.BOOK1, Sharpe_exBIL=.9, MaxDD=-.2)])
    mix = pd.DataFrame([dict(strategy_id=e.METHOD, equity=.5)])
    return full, book, mix


@pytest.mark.parametrize('failure', ['label', 'equal_anchor', 'growth', 'book', 'none', 'dd_only', 'sharpe_only', 'all'])
def test_book_eligibility(failure):
    full, book, mix = eligibility_data(); label = 'PASS'
    if failure in ('label', 'all'): label = 'FAIL'
    if failure in ('equal_anchor', 'all'): full.loc[1, 'Sharpe_exBIL'] = 1.
    if failure in ('growth', 'all'): mix.loc[0, 'equity'] = .49
    if failure in ('book', 'all'): book.loc[0, ['Sharpe_exBIL', 'MaxDD']] = [.9, -.2]
    if failure == 'dd_only': book.loc[0, 'Sharpe_exBIL'] = .8
    if failure == 'sharpe_only': book.loc[0, 'MaxDD'] = -.3
    be = e.book_eligibility_epo(label, full, book, mix, .9, .9)
    assert be['eligible'] == (failure in ('none', 'dd_only', 'sharpe_only'))
    assert be['label'] == label
    if failure in ('growth', 'all'): assert 'growth-mandate fit' in be['reason']
    if failure == 'all':
        assert be['reason'].startswith('gate label')
        assert 'anchor' in be['reason'] and 'Book 1' in be['reason']


def test_synthetic_gate_writer(panels, monkeypatch, tmp_path):
    weekly, monthly, u, rf = panels
    monkeypatch.setattr(e, 'NAME_FLOOR', 5)
    monkeypatch.setattr(e, 'MIN_MONTHS', 12)
    dsr = e.deflated_sharpe_bailey_lp
    calls = []
    def spy(sr, n, trials, *args):
        calls.append(trials)
        return dsr(sr, n, trials, *args)
    monkeypatch.setattr(e, 'deflated_sharpe_bailey_lp', spy)
    result = e.run_epo_gate(weekly, monthly, u, rf=rf, bootstrap_reps=19)
    assert calls and set(calls) == {11}
    assert result['trial_count'] == len(result['trial_registry']) == 11
    assert result['trial_registry'].loc[lambda f: f.line.eq('v3'), 'source'].str.startswith('HEAD:').all()
    e.write_epo_artifacts(result, tmp_path/'out')
    with pytest.raises(FileExistsError, match='overwrite'):
        e.write_epo_artifacts(result, tmp_path/'out')
    payload = json.loads((tmp_path/'out/gate_result.json').read_text())
    assert payload['monthly_panel']['complete_months_only']
    assert payload['fields']['trial_count'] == 11
    assert payload['fields']['preregistration']['sha256'] == PIN
    assert payload['fields']['preregistration']['verified'] is False
    report = (tmp_path/'out/gate_report.md').read_text()
    assert f"**Label (mechanical + composition): {result['label']}**\nbook_eligible:" in report
    assert '0.00%' in report and 'asset_class_mix' in report
    for sid in (e.METHOD, e.PRIMARY, e.ANCHOR): assert sid in report
    broken = dict(result, monthly_panel_provenance=pd.read_csv(tmp_path/'monthly.csv'))
    with pytest.raises(GateResultError, match='provenance'):
        e.write_epo_artifacts(broken, tmp_path/'bad')
    broken = dict(result, book_eligible={'eligible': True, 'reason': 'invalid'}, label='FAIL', mechanical='FAIL')
    with pytest.raises(GateResultError, match='unless label is PASS'):
        e.write_epo_artifacts(broken, tmp_path/'bad2')
    summary = result['summary'].copy()
    summary.loc[summary.strategy_id.eq(e.METHOD), 'eff_N_mean'] = 4.99
    assert e.mechanical_reading_epo(summary, result['tests'], result['composition'])['mechanical'] == 'VOID'


def test_registry():
    from usa_etf_features.strategy_registry import load_strategy_registry
    entry = next(s for s in load_strategy_registry(e.ROOT/'config/strategies.yaml') if s.id == e.GATE_ID)
    assert not entry.enabled
    assert '10.1080/0015198X.2020.1854543' in entry.method_citation
    assert '10.1016/j.jfineco.2021.06.030' in entry.method_citation


def test_gate_criteria_and_label_order():
    rows = [dict(strategy_id=sid, Sharpe_exBIL=sr, DSR_exBIL=.96, eff_N_mean=6.)
            for sid, sr in [(e.METHOD, 1.), (e.PRIMARY, .5), (e.ANCHOR, 1.),
                            (e.TREND, .8), (e.EW, .9), (e.METHODS[1], .6), (e.METHODS[2], .7)]]
    summary = pd.DataFrame(rows)
    tests = pd.DataFrame([dict(strategy_id=e.METHOD, primary_null=e.PRIMARY,
                               p_one_sided_hac=.05, p_one_sided_boot=.05)])
    comp = dict(computable=True, method_share=0., null_share=0., status='PASS')
    reading = e.mechanical_reading_epo(summary, tests, comp)
    assert all(reading['criteria'].values()) and reading['mechanical'] == 'PASS'
    summary.loc[summary.strategy_id.eq(e.PRIMARY), 'eff_N_mean'] = 1
    assert e.mechanical_reading_epo(summary, tests, comp)['mechanical'] == 'PASS'
    for col in ['p_one_sided_hac', 'p_one_sided_boot']:
        failed = tests.copy(); failed[col] = .051
        assert e.mechanical_reading_epo(summary, failed, comp)['mechanical'] == 'FAIL'
    missing = dict(comp, computable=False, method_share=np.nan, status='NOT COMPUTABLE')
    r = e.mechanical_reading_epo(summary, tests, missing)
    assert not r['criteria']['c6']
    assert gm.final_gate_label(r['mechanical'], missing) == gm.INCOMPLETE_LABEL
    contaminated = dict(comp, method_share=.51, status='VOID')
    r = e.mechanical_reading_epo(summary, tests, contaminated)
    assert gm.final_gate_label(r['mechanical'], contaminated) == 'VOID'


@pytest.mark.parametrize('bad', ['gap', 'inf', 'below_minus_one', 'duplicate_week'])
def test_backtest_input_validation(panels, bad):
    weekly, monthly, u, rf = panels
    if bad == 'gap': monthly = monthly.drop(monthly.index[10])
    elif bad == 'inf': monthly = monthly.copy(); monthly.iloc[10, 0] = np.inf
    elif bad == 'below_minus_one': weekly = weekly.copy(); weekly.iloc[10, 0] = -1.01
    else: weekly = pd.concat([weekly.iloc[:1], weekly])
    with pytest.raises(ValueError):
        backtest((weekly, monthly, u, rf))


def test_skips_eligibility_and_book_reference(panels):
    weekly, monthly, u, rf = panels
    weekly = weekly.copy()
    # Force precisely the first rebalance below the floor, then recover.
    cutoff = weekly.index[weekly.index <= pd.Timestamp('2021-01-31')][-156]
    weekly.loc[cutoff, ['VOO', 'QQQM', 'IJR', 'VT']] = np.nan
    result = backtest((weekly, monthly, u, rf))
    assert result['name_counts'].iloc[0].skipped
    assert result['name_counts'].iloc[0].n_eligible == 4
    assert not result['name_counts'].iloc[1].skipped
    book = result['oos_returns'].loc[lambda x: x.strategy_id.eq(e.BOOK1)]
    expected = monthly.loc[book.date, ['VOO', 'QQQM', 'IJR']].mul([.7, .2, .1]).sum(axis=1, min_count=3)
    np.testing.assert_allclose(book.gross_return, expected)
    # The named reference can start later without shortening every other strategy.
    monthly = monthly.copy(); monthly.loc[:'2021-02-28', 'QQQM'] = np.nan
    result = backtest((panels[0], monthly, u, rf))
    book = result['oos_returns'].loc[lambda x: x.strategy_id.eq(e.BOOK1)]
    assert book.date.min() == pd.Timestamp('2021-03-31')
    assert result['oos_returns'].date.min() == pd.Timestamp('2021-02-28')


def test_inputs_sigma_ddof(toy):
    x = np.array([[.01, .02, -.03], [.02, .01, .03], [-.01, .03, .02], [.04, -.01, .01]])
    sigma, omega, cov, V = e.epo_inputs(x)
    np.testing.assert_allclose(sigma, np.sqrt(52)*x.std(axis=0, ddof=1))
    np.testing.assert_allclose(omega, .95*np.corrcoef(x, rowvar=False)+.05*np.eye(3))
    np.testing.assert_allclose(cov, np.diag(sigma)@omega@np.diag(sigma))
    np.testing.assert_allclose(V, np.diag(sigma**2))
