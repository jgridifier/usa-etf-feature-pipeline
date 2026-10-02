"""Offline synthetic tests; never run the real-data Schur gate."""
import hashlib
import importlib.util
import json
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest
import yaml

from usa_etf_features import schur_allocator as s, gate_metrics as gm
from usa_etf_features.monthly_panel import load_monthly_panel
from usa_etf_features.spectral_risk_parity import long_only_minvar, normalize_cov

PIN = 'c490d81b12c21edb4b254456ad27ab5575871db4bce3763981f9b466d5ef75f7'


# ----------------------------------------------------------------------------- pre-registration
def test_preregistration_pin_and_parameters():
    raw = (s.ROOT/s.PREREG_PATH).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PIN == s.PREREG_SHA256
    p = yaml.safe_load(raw)
    assert p['gate_id'] == s.GATE_ID and p['trial_count'] == s.TRIAL_COUNT == 12
    assert p['universe']['count'] == 98 and p['universe']['name_floor'] == s.NAME_FLOOR == 60
    assert tuple(p['universe']['low_vol_list']) == s.LOW_VOL
    assert p['covariance']['window_weeks'] == s.WINDOW_WEEKS == 156
    assert p['recursion']['terminal_block']['max_dim'] == s.TERMINAL_SIZE == 5
    g = p['gamma']
    assert g['scale'] == s.GAMMA_SCALE == .5 and g['max_halvings'] == s.MAX_HALVINGS == 10
    assert '1e-6' in g['gamma_max_search'] and '1 - 1e-6' in g['gamma_max_search'] and '1e-8' in g['pd_definition']
    assert s.GAMMA_TOL == 1e-6 and s.GAMMA_CAP == 1 - 1e-6 and s.PD_REL_TOL == 1e-8 and s.B_MIN == .05
    c = p['caps']
    assert (c['low_vol_combined_max'], c['single_name_max'], c['tolerance'], c['max_passes']) == \
        (s.LOW_VOL_CAP, s.NAME_CAP, s.CAP_TOL, s.CAP_MAX_PASSES)
    assert str(p['rebalance']['first_decision']) == s.FIRST_DECISION
    assert 'floor(n/2)' in p['seriation']['odd_sizes']
    assert p['engineering_defaults_pending_quant']['bootstrap_seed'] == s.SEED
    assert {'b_descaling', 'gamma_max_analytic', 'hrp_null_definition', 'low_vol_realized'} <= set(p['engineering_defaults_pending_quant'])
    assert 'One run' in p['no_reruns'] and 'no large pretrained' in p['method_constraint']['rule']


def test_universe_tags():
    u = pd.read_csv(s.ROOT/'data/raw/usa_universe_categorized.csv')
    names = s.schur_universe_tickers(u)
    assert len(names) == 98 and set(s.LOW_VOL) <= names
    assert not names & (gm.CASH_LIKE | gm.SHORT_DURATION | gm.NEAR_CASH)
    assert gm.epo_asset_class(u).loc[sorted(names)].eq('equity').all()


# ----------------------------------------------------------------------------- helpers
def cov_example(n=12, rho=.2, seed=1, noise=.03):
    rng = np.random.default_rng(seed)
    vol = rng.uniform(.8, 1.2, n)
    R = np.full((n, n), rho) + (1-rho)*np.eye(n)
    E = rng.normal(scale=noise, size=(n, n)); E = (E+E.T)/2; np.fill_diagonal(E, 0)
    return (R+E)*np.outer(vol, vol)


def de_prado_quasi_diag(link):
    """Verbatim getQuasiDiag (Lopez de Prado 2016, Snippet 16.2)."""
    link = link.astype(int)
    items = pd.Series([link[-1, 0], link[-1, 1]])
    num = link[-1, 3]
    while items.max() >= num:
        items.index = range(0, items.shape[0]*2, 2)
        df0 = items[items >= num]
        i, j = df0.index, df0.values-num
        items[i] = link[j, 0]
        df0 = pd.Series(link[j, 1], index=i+1)
        items = pd.concat([items, df0]).sort_index()
        items.index = range(items.shape[0])
    return items.tolist()


def naive_hrp(cov):
    """Independent eq. (4.1) recursion at gamma = 0: nu = MV variance of the raw block."""
    n = len(cov)
    if n <= 5:
        return long_only_minvar(normalize_cov(cov))
    k = n//2
    parts = []
    for idx in (slice(0, k), slice(k, n)):
        Q = cov[idx, idx]
        parts.append(naive_hrp(Q) * (np.ones(len(Q)) @ np.linalg.solve(Q, np.ones(len(Q)))))
    w = np.concatenate(parts)
    return w/w.sum()


def mv(cov):
    x = np.linalg.solve(cov, np.ones(len(cov)))
    return x/x.sum()


# ----------------------------------------------------------------------------- allocator
def test_seriation_matches_de_prado_and_bisection():
    from scipy.cluster.hierarchy import linkage
    from scipy.spatial.distance import squareform
    C = cov_example(15, seed=4, noise=.15)
    sd = np.sqrt(np.diag(C)); d = np.sqrt(.5*(1-C/np.outer(sd, sd))); np.fill_diagonal(d, 0)
    assert s.seriation_order(C).tolist() == de_prado_quasi_diag(linkage(squareform(d, checks=False), 'single'))
    assert [s.bisect(n) for n in (6, 7, 11)] == [3, 3, 5]


def test_gamma_zero_reproduces_hrp():
    C = cov_example(17, seed=3, noise=.1)
    order = s.seriation_order(C)
    expected = np.empty(17); expected[order] = naive_hrp(C[np.ix_(order, order)])
    np.testing.assert_allclose(s.hrp_weights(C), expected, atol=1e-9)
    np.testing.assert_allclose(s.schur_recursion(C[np.ix_(order, order)], gamma_fixed=0.), naive_hrp(C[np.ix_(order, order)]), atol=1e-9)
    log = []
    s.schur_weights(C, gamma_scale=0., log=log)
    assert log and all(r['gamma'] == 0 and not r['fallback'] for r in log)


def test_gamma_to_one_approaches_min_variance():
    C = cov_example(12)
    target = mv(C)
    assert target.min() > 0       # long-only MV is interior, so terminal long-only MV is exact
    errors = [np.abs(s.schur_recursion(C, gamma_fixed=g)-target).sum() for g in (0, .5, .9, .99, .999, 1-1e-6)]
    assert all(a > b for a, b in zip(errors, errors[1:]))
    assert errors[-1] < 1e-5
    # The pinned search caps gamma_max at 1 - 1e-6, so scale 1 is the same limit.
    assert np.abs(s.schur_weights(C, gamma_scale=1.)-target).sum() < 1e-4


def test_b_descaling_appendix_b():
    """Cotton Appendix B: equicorrelated 3x3 at gamma = 1 must give equal weights (MV)."""
    S = np.full((3, 3), .4) + .6*np.eye(3)
    exact = lambda Q: mv(Q)
    w = s.schur_recursion(S, terminal_size=2, gamma_fixed=1., terminal=exact)
    literal = s.schur_recursion(S, terminal_size=2, gamma_fixed=1., terminal=exact, descale_by_b=False)
    np.testing.assert_allclose(w, np.full(3, 1/3), atol=1e-12)
    assert np.abs(literal-1/3).max() > .05


def test_gamma_max_search_tolerance():
    A, D, B = np.eye(1), np.eye(1), np.array([[1.2]])        # indefinite joint matrix
    g = s.gamma_max(A, B, D)
    assert abs(g-(1-1e-8)/1.44) <= 2e-6 and g < 1/1.44
    C = cov_example(6)
    assert s.gamma_max(C[:3, :3], C[:3, 3:], C[3:, 3:]) == s.GAMMA_CAP


def test_pd_and_b_fallback_logged():
    # Name 1 is a 3x-vol near-copy of name 2: b_A = 1 - gamma * 2.7 fails at gamma = .5, passes at .25.
    vol = np.array([3., 1.]); C = np.array([[1, .9], [.9, 1]])*np.outer(vol, vol)
    g, _, rec = s.split_gamma(C[:1, :1], C[:1, 1:], C[1:, 1:])
    assert rec['n_halvings'] == 1 and np.isclose(g, rec['gamma_initial']/2) and 'b_A <= 0.05' in rec['reason']
    assert not rec['hrp_fallback']
    g, _, rec = s.split_gamma(C[:1, :1], C[:1, 1:], C[1:, 1:], max_halvings=0)
    assert g == 0 and rec['hrp_fallback'] and rec['reason'].count('gamma=') == 1
    # PD failure path: an indefinite block pair is detected and halved.
    A, D, B = np.eye(1), np.eye(1), np.array([[1.2]])
    g, _, rec = s.split_gamma(A, B, D, gamma_scale=1., gmax=1.)
    assert 'A_c not PD' in rec['reason'] and 'D_c not PD' in rec['reason'] and g == .5 < 1/1.44
    log = []
    s.schur_recursion(C, terminal_size=1, log=log)
    assert len(log) == 1 and log[0]['fallback'] and log[0]['n_halvings'] == 1


def test_caps_feasibility_and_binding_report():
    w = pd.Series({'USMV': .25, 'EFAV': .2, 'SPHD': .1, 'A': .25, 'B': .1, 'C': .05, 'D': .03, 'E': .02})
    capped, rep = s.apply_caps(w)
    assert np.isclose(capped.sum(), 1) and capped.max() <= .2 + 1e-10
    assert capped[list(s.LOW_VOL)].sum() <= .3 + 1e-10
    assert rep['low_vol_cap_binding'] and {'A', 'B'} <= set(rep['name_cap_binding']) and 'USMV' not in rep['name_cap_binding']
    assert rep['low_vol_share_pre'] == pytest.approx(.55) and rep['passes'] >= 2
    # Pro rata: uncapped names keep their relative weights.
    assert capped['D']/capped['E'] == pytest.approx(1.5)
    assert capped[['USMV', 'EFAV', 'SPHD']].to_numpy() / w[['USMV', 'EFAV', 'SPHD']].to_numpy() == pytest.approx(.3/.55)
    untouched, rep = s.apply_caps(pd.Series(np.full(10, .1), index=list('abcdefghij')))
    assert not rep['low_vol_cap_binding'] and rep['name_cap_binding'] == [] and rep['passes'] == 1
    with pytest.raises(ValueError, match='infeasible'):
        s.apply_caps(pd.Series(.25, index=list('abcd')))
    with pytest.raises(ValueError, match='infeasible'):
        s.apply_caps(pd.Series({'USMV': .4, 'EFAV': .3, 'A': .1, 'B': .1, 'C': .1}))
    with pytest.raises(ValueError, match='converge'):
        s.apply_caps(pd.Series([.9]+[.1/9]*9, index=list('abcdefghij')), max_passes=1)
    assert s.caps_feasible(['USMV', 'A', 'B', 'C', 'D'])


def test_effective_n():
    assert s.effective_n(np.full(8, 1/8)) == pytest.approx(8)
    assert s.effective_n([1, 0, 0]) == 1
    assert s.effective_n([.5, .25, .25]) == pytest.approx(1/.375)


# ----------------------------------------------------------------------------- synthetic panels
NAMES = ['VOO', 'QQQM', 'IJR', 'USMV', 'EFAV', 'SPHD', 'E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'AGG', 'BILX']


@pytest.fixture
def panels(tmp_path):
    rng = np.random.default_rng(43)
    dates = pd.date_range('2013-01-31', periods=115, freq='ME')
    common = rng.normal(.006, .03, (len(dates), 1))
    monthly = pd.DataFrame(common + rng.normal(0, .03, (len(dates), len(NAMES))), index=dates, columns=NAMES)
    path = tmp_path/'monthly.csv'; monthly.to_csv(path)
    monthly = load_monthly_panel(path, asof='2022-07-31')
    weeks = pd.date_range('2012-01-06', '2022-08-05', freq='W-FRI')
    f = rng.normal(.001, .015, (len(weeks), 1))
    weekly = pd.DataFrame(f*rng.uniform(.5, 1.5, len(NAMES)) + rng.normal(0, .015, (len(weeks), len(NAMES))),
                          index=weeks, columns=NAMES)
    n = len(NAMES)
    u = pd.DataFrame({'Ticker': NAMES, 'Category': 'Equity', 'epo_universe': True,
                      'epo_asset_class': ['equity']*14+['bond', 'equity'], 'equity_only': True,
                      'cash_like': [False]*15+[True], 'short_duration': False, 'near_cash': False})
    rf = pd.DataFrame({'rf': .001, 'source': 'synthetic'}, index=dates.to_period('M'))
    return weekly, monthly, u, rf


def small(monkeypatch):
    monkeypatch.setattr(s, 'NAME_FLOOR', 8)
    monkeypatch.setattr(s, 'MIN_MONTHS', 12)
    monkeypatch.setattr(s, 'FIRST_DECISION', '2020-01-31')


def test_backtest_universe_costs_and_logs(panels, monkeypatch):
    small(monkeypatch)
    w, m, u, rf = panels
    res = s.run_schur_backtest(w, m, u)
    held = set(res['weights'].loc[res['weights'].strategy_id.ne(s.BOOK1), 'ticker'])
    assert held == set(NAMES) - {'AGG', 'BILX'}
    oos = res['oos_returns']
    assert set(oos.strategy_id) == {*s.CAPPED, s.BOOK1}
    np.testing.assert_allclose(oos.cost_return, oos.turnover*5e-4)
    np.testing.assert_allclose(oos['return'], oos.gross_return-oos.cost_return)
    assert (oos.feature_end <= oos.decision_date).all() and (oos.date > oos.decision_date).all()
    capped = res['weights'].loc[res['weights'].strategy_id.isin(s.CAPPED)]
    for _, sub in capped.groupby(['date', 'strategy_id']).weight:
        assert np.isclose(sub.sum(), 1) and sub.max() <= .2 + 1e-9
    lv = res['low_vol_share']
    assert (lv.low_vol_share_target <= .3 + 1e-9).all()
    assert len(res['split_log']) and res['split_log'].gamma.between(0, .5).all()
    assert set(res['cap_report'].strategy_id) == set(s.CAPPED)


def test_no_look_ahead(panels, monkeypatch):
    small(monkeypatch)
    weekly, monthly, u, rf = panels
    base = s.run_schur_backtest(weekly, monthly, u)
    date = base['oos_returns'].date.min(); decision = base['oos_returns'].decision_date.min()
    cm = monthly.copy(); cm.loc[cm.index >= date] += .2
    cw = weekly.copy(); cw.loc[cw.index > decision] *= 3
    changed = s.run_schur_backtest(cw, cm, u)
    pick = lambda r: r['weights'].loc[r['weights'].date.eq(date)].reset_index(drop=True)
    pd.testing.assert_frame_equal(pick(base), pick(changed))


def test_tripwire_void_short_circuits_tests(panels, monkeypatch, tmp_path):
    small(monkeypatch)
    w, m, u, rf = panels
    monkeypatch.setattr(s, 'EFF_N_MIN', 1000.)
    def boom(*a, **k):
        pytest.fail('test computed after VOID tripwire')
    for name in ('lw2008_sharpe_test', 'lw2008_sharpe_bootstrap', 'deflated_sharpe_bailey_lp', 'summarize_schur'):
        monkeypatch.setattr(s, name, boom)
    res = s.run_schur_gate(w, m, u, rf=rf, bootstrap_reps=19)
    assert res['label'] == res['mechanical'] == 'VOID'
    assert res['tests'].empty and res['summary'].empty and res['reading']['criteria'] is None
    assert 'effective N' in res['tripwires']['reasons'][0]
    assert not res['book_eligible']['eligible'] and 'VOID' in res['book_eligible']['reason']
    s.write_schur_artifacts(res, tmp_path/'void')
    payload = json.loads((tmp_path/'void/gate_result.json').read_text())
    assert payload['label'] == 'VOID' and payload['report']['criteria'] is None


def test_low_vol_tripwire(panels, monkeypatch):
    small(monkeypatch)
    w, m, u, rf = panels
    res = s.run_schur_backtest(w, m, u)
    assert s.tripwires(res, u)['low_vol']['ok']
    res['low_vol_share'].loc[0, 'low_vol_share_target'] = .31
    t = s.tripwires(res, u)
    assert t['status'] == 'VOID' and 'low-vol' in t['reasons'][0]


def test_synthetic_gate_and_writer(panels, monkeypatch, tmp_path):
    small(monkeypatch)
    w, m, u, rf = panels
    dsr, calls = s.deflated_sharpe_bailey_lp, []
    def spy(sr, n, trials, *a):
        calls.append(trials); return dsr(sr, n, trials, *a)
    monkeypatch.setattr(s, 'deflated_sharpe_bailey_lp', spy)
    res = s.run_schur_gate(w, m, u, rf=rf, bootstrap_reps=19)
    assert res['tripwires']['status'] == 'PASS' and res['composition']['method_share'] == 0
    assert set(calls) == {12} and len(res['trial_registry']) == 12 == res['trial_count']
    assert res['trial_registry'].trial_id.iloc[-1] == s.METHOD
    assert res['label'] in {'PASS', 'FAIL'} and set(res['reading']['criteria']) == {'c1', 'c2', 'c3', 'c4'}
    assert len(res['tests']) == 1 and res['tests'].primary_null.item() == s.PRIMARY
    s.write_schur_artifacts(res, tmp_path/'out')
    with pytest.raises(FileExistsError):
        s.write_schur_artifacts(res, tmp_path/'out')
    payload = json.loads((tmp_path/'out/gate_result.json').read_text())
    assert payload['gate_id'] == 'schur_allocator' and payload['fields']['trial_count'] == 12
    assert payload['fields']['preregistration']['verified'] is False
    report = (tmp_path/'out/gate_report.md').read_text()
    assert 'Composition tripwire' in report and 'share of months < 5' in report and 'Caps binding' in report
    assert (tmp_path/'out/split_log.csv').exists() and (tmp_path/'out/cap_report.csv').exists()


def test_book_eligibility(panels, monkeypatch):
    oos = pd.DataFrame([dict(strategy_id=sid, date=d, **{'return': r})
                        for d in pd.date_range('2020-06-30', periods=30, freq='ME')
                        for sid, r in ((s.METHOD, .01), (s.BOOK1, .012))])
    oos.loc[oos.strategy_id.eq(s.METHOD) & oos.date.eq(pd.Timestamp('2022-01-31')), 'return'] = -.05
    oos.loc[oos.strategy_id.eq(s.BOOK1) & oos.date.eq(pd.Timestamp('2022-01-31')), 'return'] = -.08
    idx = pd.date_range('2021-02-26', periods=20, freq='BME')
    rng = np.random.default_rng(0)
    backbone = pd.Series(rng.normal(.0, .03, 20), index=idx)
    rf = pd.DataFrame({'rf': .001, 'source': 'x'}, index=pd.period_range('2020-01', periods=40, freq='M'))
    be = s.book_eligibility('PASS', oos, rf, backbone=backbone, book2=backbone)
    assert be['eligible'] and be['n_months'] == 20 and be['window'].startswith('2021-02')
    assert not s.book_eligibility('FAIL', oos, rf, backbone=backbone, book2=backbone)['eligible']
    worse = oos.copy(); worse.loc[worse.strategy_id.eq(s.METHOD) & worse.date.eq(pd.Timestamp('2022-01-31')), 'return'] = -.2
    be = s.book_eligibility('PASS', worse, rf, backbone=backbone, book2=backbone)
    assert not be['eligible'] and 'MaxDD' in be['reason']


# ----------------------------------------------------------------------------- guard
@pytest.fixture
def git_repo(tmp_path):
    if shutil.which('git') is None:
        pytest.skip('git not on PATH')
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, check=True, capture_output=True)
    git('init'); git('config', 'user.email', 'test@example.com'); git('config', 'user.name', 'Test')
    path = tmp_path/s.PREREG_PATH; path.parent.mkdir()
    path.write_bytes((s.ROOT/s.PREREG_PATH).read_bytes())
    (tmp_path/'tracked').write_text('original')
    git('add', '.'); git('commit', '-m', 'pin')
    return tmp_path, path, git


def test_guard_clean(git_repo):
    root, _, _ = git_repo
    p = s.verify_preregistration(root=root)
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
            path.write_bytes((s.ROOT/s.PREREG_PATH).read_bytes())
            git('update-index', '--assume-unchanged', str(s.PREREG_PATH))
    elif change == 'untracked':
        (root/'new').write_text('dirty')
    else:
        (root/'tracked').write_text('changed')
    with pytest.raises(s.PreregistrationError, match=match):
        s.verify_preregistration(root=root)
    spec = importlib.util.spec_from_file_location('run_schur_gate', s.ROOT/'scripts/run_schur_gate.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    def fail(*a, **kw):
        pytest.fail('data loaded before guard')
    monkeypatch.setattr(module, 'load_monthly_panel', fail)
    monkeypatch.setattr(module, 'run_schur_gate', fail)
    with pytest.raises(s.PreregistrationError, match=match):
        module.main([], root=root)


def test_script_refuses_rerun_before_load(git_repo, monkeypatch):
    root, _, git = git_repo
    out = root/s.OUT_DIR; out.mkdir(parents=True)
    (out/'gate_result.json').write_text('{}')
    git('add', '.'); git('commit', '-m', 'committed run')
    spec = importlib.util.spec_from_file_location('run_schur_gate', s.ROOT/'scripts/run_schur_gate.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    def fail(*a, **kw):
        pytest.fail('data loaded before the one-run check')
    monkeypatch.setattr(module, 'load_monthly_panel', fail)
    with pytest.raises(s.PreregistrationError, match='already run'):
        module.main([], root=root)
    with pytest.raises(SystemExit):
        module.main(['--out-dir', 'elsewhere'], root=root)


def test_script_refuses_wrong_pin(git_repo, monkeypatch):
    root, _, _ = git_repo
    monkeypatch.setattr(s, 'PREREG_SHA256', '0'*64)
    with pytest.raises(s.PreregistrationError, match='sha256'):
        s.verify_preregistration(root=root)
