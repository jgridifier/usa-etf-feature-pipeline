"""Pre-registered anchored EPO research gate; complete months, no live-book wiring.

Pedersen, Babu & Levine (2021), equations 19–23; Baltussen et al. (2021).
Pure backtests may use synthetic panels. Only the script authorizes a real-data
run, after checking the pinned design and clean git tree.
"""
from pathlib import Path
import hashlib
import io
import subprocess

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import skew, kurtosis

from . import gate_metrics as gm, gate_results
from . import nonlinear_shrinkage_gmv_v2 as v2
from . import nonlinear_shrinkage_gmv_v3 as v3
from .monthly_panel import panel_provenance
from .spectral_risk_parity import null_weights
from .vol_target import annualized_vol, sharpe_rf0

ROOT = Path(__file__).resolve().parents[2]
GATE_ID = 'epo_anchored_trend'
METHOD = 'epo_a_w075'
METHODS = ('epo_a_w075', 'epo_a_w050', 'epo_a_w090')
PRIMARY = 'lw_minvar_156w'
ANCHOR, TREND, EW, ERC = 'anchor_ivol', 'trend_ivol', 'equal_weight', 'erc_lw'
BOOK1 = 'book1_static_option_a'
W_GRID = (0.75, 0.50, 0.90)
WINDOW_WEEKS, NAME_FLOOR, MIN_MONTHS = 156, 100, 60
FIRST_DECISION, SUBPERIOD = '2016-10-31', '2021-02'
COST_BPS, STRESS_BPS = 5, (10, 25)
TRIAL_COUNT = v3.TRIAL_COUNT_V3 + len(W_GRID)
assert TRIAL_COUNT == 11
BOOTSTRAP_REPS, BLOCK_SIZE, SEED = 5000, 4, 20260930
PREREG_PATH = Path('preregistration/epo_allocator.yaml')
PREREG_SHA256 = 'c071017a22edb21e4ad5c89071194771074c03da5df9a8604baab36324332d75'
lw2008_sharpe_test = v3.lw2008_sharpe_test
deflated_sharpe_bailey_lp = v3.deflated_sharpe_bailey_lp
book_eligible_line = v3.book_eligible_line


class PreregistrationError(RuntimeError):
    pass


def verify_preregistration(root=ROOT, prereg_path=PREREG_PATH, sha256=PREREG_SHA256):
    root = Path(root)
    path = Path(prereg_path)
    path = path if path.is_absolute() else root / path
    try:
        relative = path.relative_to(root).as_posix()
        # Check bytes first so an uncommitted design edit specifically reports sha256.
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
            raise PreregistrationError('pre-registration sha256 differs from pinned design')
        def git(*args):
            r = subprocess.run(['git', *args], cwd=root, capture_output=True, check=True)
            return r.stdout
        if git('status', '--porcelain').strip():
            raise PreregistrationError('Working tree is not clean (dirty or untracked files)')
        if hashlib.sha256(git('show', f'HEAD:{relative}')).hexdigest() != sha256:
            raise PreregistrationError('HEAD pre-registration sha256 differs from pinned design')
        return dict(sha256=sha256, head_commit=git('rev-parse', 'HEAD').decode().strip(), path=relative,
                    verified=True)
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        raise PreregistrationError(f'pre-registration sha256/git verification failed: {exc}') from exc


def epo_inputs(weekly_window):
    x = np.asarray(weekly_window, float)
    if x.ndim != 2 or len(x) < 2 or not np.isfinite(x).all():
        raise ValueError('finite weekly matrix required')
    sigma = np.sqrt(52) * x.std(axis=0, ddof=1)
    if np.any(sigma <= 0):
        raise ValueError('positive volatility required')
    omega = .95 * np.atleast_2d(np.corrcoef(x, rowvar=False)) + .05 * np.eye(x.shape[1])
    return sigma, omega, sigma[:, None] * omega * sigma[None, :], np.diag(sigma**2)


def sigma_w(Sigma_tilde, V, w):
    if not 0 <= w <= 1:
        raise ValueError('w must be in [0,1]')
    return (1-w)*Sigma_tilde + w*V


def inverse_vol_anchor(sigma):
    inv = 1 / np.asarray(sigma, float)
    return inv / inv.sum()


def trend_signal(monthly_excess_window, sigma):
    """Twelve rows t-12..t-1; omit the last row, using weekly annual sigma."""
    x = np.asarray(monthly_excess_window, float)
    if x.shape[0] != 12 or not np.isfinite(x).all():
        raise ValueError('signal requires twelve complete months')
    return .1 * np.asarray(sigma) * np.sign(np.prod(1+x[:-1], axis=0)-1)


def epo_gamma(s, Sigma_w, Sigma_tilde, a):
    z = np.linalg.solve(Sigma_w, s)
    return float(np.sqrt(z @ Sigma_tilde @ z / (a @ Sigma_tilde @ a)))


def simple_epo(s, Sigma_w, gamma):
    return np.linalg.solve(Sigma_w, s) / gamma


def anchored_epo_closed_form(s, Sigma_w, V, a, w, gamma):
    return np.linalg.solve(Sigma_w, (1-w)*s/gamma + w*V@a)


def epo_long_only(s, Sigma_w, Sigma_tilde, V, a, w):
    s, a = np.asarray(s), np.asarray(a)
    gamma = epo_gamma(s, Sigma_w, Sigma_tilde, a)
    if not np.any(s):
        return a.copy(), dict(status='anchor (s=0)', message='anchor (s=0)', nit=0,
                              success=True, kkt_residual=0., gamma=0., anchor_held=True)
    scale = np.diag(Sigma_w).mean()
    cov = Sigma_w / scale
    mu = ((1-w)*s/gamma + w*V@a) / scale
    # Starting at a also demonstrates the w=1 optimum without a short circuit.
    fit = minimize(lambda x: .5*x@cov@x-x@mu, a, jac=lambda x: cov@x-mu,
                   bounds=[(0, 1)]*len(a), constraints={'type': 'eq', 'fun': lambda x: x.sum()-1,
                   'jac': lambda x: np.ones(len(x))}, method='SLSQP',
                   options={'maxiter': 1000, 'ftol': 1e-12})
    if not fit.success:
        raise ValueError(f'EPO solver failed: {fit.message}')
    x = np.clip(fit.x, 0, 1); x /= x.sum()
    grad = cov@x-mu
    free = (x > 1e-7) & (x < 1-1e-7)
    lam = -grad[free].mean() if free.any() else -grad[np.argmax(x)]
    stationarity = grad+lam
    residual = np.where(x <= 1e-7, np.minimum(stationarity, 0),
                        np.where(x >= 1-1e-7, np.maximum(stationarity, 0), stationarity))
    return x, dict(status=int(fit.status), message=str(fit.message), nit=int(fit.nit), success=True,
                   kkt_residual=float(np.max(np.abs(residual))), gamma=gamma, anchor_held=bool(w == 1))


def drift_weights(previous, returns):
    """Drift a target through realized returns; missing held prices require repair."""
    if previous.empty:
        return previous.copy()
    r = returns.reindex(previous.index)
    if r[previous > 0].isna().any():
        raise ValueError('missing drift return; explicit data repair required')
    drift = previous * (1+r.fillna(0))
    if drift.sum() <= 0:
        raise ValueError('portfolio lost all wealth; explicit data repair required')
    return drift/drift.sum()


def run_epo_backtest(weekly, monthly, universe, *, rf, w_grid=W_GRID, cost_bps=COST_BPS,
                     first_decision=FIRST_DECISION, window_weeks=None, name_floor=None, min_months=None):
    window_weeks = WINDOW_WEEKS if window_weeks is None else window_weeks
    name_floor = NAME_FLOOR if name_floor is None else name_floor
    min_months = MIN_MONTHS if min_months is None else min_months
    if tuple(w_grid) != W_GRID or cost_bps < 0 or window_weeks < 2 or name_floor < 1 or min_months < 0:
        raise ValueError('invalid or unregistered configuration')
    monthly = monthly.sort_index()
    months = monthly.index.to_period('M')
    if months.has_duplicates or (np.diff(months.asi8) != 1).any():
        raise ValueError('monthly panel must contain consecutive months')
    if not weekly.index.is_unique or not weekly.index.is_monotonic_increasing:
        raise ValueError('weekly index must be unique and increasing')
    for panel in (weekly, monthly):
        if panel.empty or panel.index.hasnans or panel.columns.has_duplicates or np.isinf(panel.to_numpy()).any() or (panel < -1).any().any():
            raise ValueError('invalid simple returns or panel')
    weekly = weekly.loc[:monthly.index[-1] + pd.offsets.MonthEnd(0)]
    names = sorted(gm.epo_universe_tickers(universe) & set(weekly) & set(monthly))
    rows, weights, counts, diagnostics, signals = [], [], [], [], []
    previous, previous_i = {}, {}
    for i in range(12-1, len(monthly)-1):
        decision, date = monthly.index[i:i+2]
        if decision.to_period('M') < pd.Timestamp(first_decision).to_period('M'):
            continue
        win = weekly.loc[:decision, names].tail(window_weeks)
        live = [t for t in names if len(win) == window_weeks and win[t].notna().all()
                and win[t].std() > 1e-10 and monthly[t].iloc[i-11:i+1].notna().all()
                and monthly[t].iloc[:i+1].count() >= min_months]
        skip = len(live) < name_floor
        counts.append(dict(decision_date=decision, date=date, n_eligible=len(live), below_floor=skip, skipped=skip))
        if skip:
            continue
        if monthly.loc[date, live].isna().any():
            raise ValueError(f'missing OOS return at {date}; explicit data repair required')
        win = win[live]
        sigma, _, cov, V = epo_inputs(win)
        a = inverse_vol_anchor(sigma)
        history = monthly[live].iloc[i-11:i+1]
        s = trend_signal(history.to_numpy()-gm.align_rf(history.index, rf).rf.to_numpy()[:, None], sigma)
        if not np.any(s):
            signals.append(dict(decision_date=decision, date=date, status='anchor (s=0)'))
        null = null_weights(win)
        positive = a*(s > 0)
        allocations = {PRIMARY: null['minvar_lw'], ERC: null['erc'], EW: null['equal_weight'],
                       ANCHOR: a, TREND: positive/positive.sum() if positive.sum() else a}
        for w, sid in zip(w_grid, METHODS):
            sw = sigma_w(cov, V, w)
            x, diag = epo_long_only(s, sw, cov, V, a, w)
            closed = anchored_epo_closed_form(s, sw, V, a, w, diag['gamma']) if np.any(s) else a
            projected = np.maximum(closed, 0)
            projected = projected/projected.sum() if projected.sum() else a
            diagnostics.append(dict(decision_date=decision, date=date, strategy_id=sid, w=w,
                projection_distance=.5*np.abs(x-projected).sum(), n_zero=int((x <= 1e-8).sum()),
                n_positive_signal=int((s > 0).sum()), **diag))
            allocations[sid] = x
        allocations = {sid: pd.Series(x, index=live) for sid, x in allocations.items()}
        # Monthly-rebalanced static Option A: min_count=3, equivalent to
        # strategy_registry._static_returns on monthly returns (before costs).
        book = pd.Series({'VOO': .7, 'QQQM': .2, 'IJR': .1})
        if set(book.index) <= set(monthly) and monthly.loc[date, book.index].notna().all():
            allocations[BOOK1] = book
        for sid, target in allocations.items():
            old = previous.get(sid, pd.Series(dtype=float))
            drift = old.copy()
            if not old.empty:
                # If a floor skip intervenes, compound all intervening returns.
                for j in range(previous_i[sid]+1, i+1):
                    drift = drift_weights(drift, monthly.iloc[j])
            turnover = .5*target.subtract(drift, fill_value=0).abs().sum()
            target_turn = .5*target.subtract(old, fill_value=0).abs().sum()
            gross = float(target @ monthly.loc[date, target.index])
            rows.append(dict(decision_date=decision, feature_end=win.index[-1], date=date, strategy_id=sid,
                n_names=len(target), gross_return=gross, turnover=turnover, turnover_target=target_turn,
                cost_return=turnover*cost_bps/10000, **{'return': gross-turnover*cost_bps/10000},
                return_10bp=gross-turnover*.001, return_25bp=gross-turnover*.0025))
            weights.extend(dict(decision_date=decision, date=date, strategy_id=sid, ticker=t, weight=float(v))
                           for t, v in target.items())
            previous[sid], previous_i[sid] = target, i
    if not rows:
        raise ValueError('no eligible OOS months')
    return dict(oos_returns=pd.DataFrame(rows), weights=pd.DataFrame(weights), name_counts=pd.DataFrame(counts),
                projection_diagnostics=pd.DataFrame(diagnostics),
                signal_log=pd.DataFrame(signals, columns=['decision_date', 'date', 'status']))


def _sharpe_moments(x):
    mu, g = x.mean(axis=-2), (x*x).mean(axis=-2)
    var = g-mu*mu
    if np.any(var <= 0):
        raise ValueError('Sharpe test requires positive variances')
    sd = np.sqrt(var)
    delta = mu[..., 0]/sd[..., 0]-mu[..., 1]/sd[..., 1]
    y = np.concatenate([x-mu[..., None, :], x*x-g[..., None, :]], axis=-1)
    grad = np.stack([g[..., 0]/sd[..., 0]**3, -g[..., 1]/sd[..., 1]**3,
                     -mu[..., 0]/(2*sd[..., 0]**3), mu[..., 1]/(2*sd[..., 1]**3)], axis=-1)
    return delta, y, grad


def lw2008_sharpe_bootstrap(a, b, rf, block_size=BLOCK_SIZE, reps=BOOTSTRAP_REPS, seed=SEED):
    """Paired studentized circular blocks, LW2008 §3.2 / Algorithm 3.1.

    The natural SE uses non-overlapping block sums of the moment influence;
    resampled statistics are centered at the original Sharpe difference.
    """
    pair = pd.concat([pd.Series(a), pd.Series(b)], axis=1, join='inner').dropna()
    n = len(pair)
    if n < 12 or int(block_size) != block_size or not 1 <= block_size <= n or int(reps) != reps or reps < 1:
        raise ValueError('requires >=12 observations, positive integer reps and valid block_size')
    x = pair.to_numpy(float)-gm.align_rf(pair.index, rf).rf.to_numpy()[:, None]
    if not np.isfinite(x).all():
        raise ValueError('returns must be finite')
    scale = np.sqrt(np.mean(x*x))
    if scale == 0:
        raise ValueError('Sharpe test requires positive variances')
    x /= scale
    delta, y, g = _sharpe_moments(x)
    nat = float(v2._natural_se(y, g, block_size))
    z = v2._z(float(delta), nat)
    rng = np.random.default_rng(seed)
    one = two = 0
    for start in range(0, reps, 256):
        m = min(256, reps-start)
        starts = rng.integers(n, size=(m, (n+block_size-1)//block_size))
        indices = ((starts[..., None]+np.arange(block_size)) % n).reshape(m, -1)[:, :n]
        ds, yy, gg = _sharpe_moments(x[indices])
        ses = v2._natural_se(yy, gg, block_size)
        centered = ds-delta
        zs = np.divide(centered, ses, out=np.zeros_like(ds), where=ses > 1e-14)
        degenerate = (ses <= 1e-14) & (np.abs(centered) > 1e-14)
        zs[degenerate] = np.copysign(np.inf, centered[degenerate])
        one += int((zs >= z).sum())
        two += int((np.abs(zs) >= abs(z)).sum())
    return dict(p_one_sided=(1+one)/(reps+1), p_two_sided=(1+two)/(reps+1),
                z=z, se_nat=nat, reps=reps, block_size=block_size, seed=seed)


def trial_registry_epo(method_sharpes):
    """Carry eight trials, taking the v3 numbers from the committed full-window CSV."""
    relative = 'data/processed/nonlinear_shrinkage_gmv_v3/summary.csv'
    blob = subprocess.run(['git', 'show', f'HEAD:{relative}'], cwd=ROOT,
                          capture_output=True, check=True).stdout
    table = pd.read_csv(io.BytesIO(blob))
    full = table.loc[table.period_role.eq('full window') & table.strategy_id.eq(v3.METHOD)]
    sharpes = {w: float(full.loc[full.window_weeks.eq(w), 'Sharpe_exBIL'].item()) for w in (156, 260)}
    registry = v3.trial_registry_v3(sharpes)
    registry.loc[registry.line.eq('v3'), 'source'] = 'HEAD:' + relative
    rows = [dict(trial_id=sid, line='epo', window_weeks=WINDOW_WEEKS, w=w, status='valid',
                 Sharpe_exBIL_annual=method_sharpes[sid], source='current EPO full-window method',
                 preregistered=True) for sid, w in zip(METHODS, W_GRID)]
    registry = pd.concat([registry, pd.DataFrame(rows)], ignore_index=True).assign(trial_count=TRIAL_COUNT)
    assert len(registry) == TRIAL_COUNT == 11
    return registry


def _summary(oos, weights, universe, rf, period_role):
    rows = []
    categories = universe.set_index('Ticker').Category
    for sid, sub in oos.groupby('strategy_id'):
        r = sub.sort_values('date').set_index('date')['return']
        w = weights.loc[weights.strategy_id.eq(sid) & weights.date.isin(r.index)]
        n = w.date.nunique()
        hhi = w.assign(square=w.weight**2).groupby('date').square.sum()
        cats = w.assign(category=w.ticker.map(categories).fillna('Unknown')).groupby(['date', 'category']).weight.sum().unstack(fill_value=0)
        avg = w.groupby('ticker').weight.sum()/n
        wealth = np.r_[1., (1+r).cumprod()]
        cagr = float((1+r).prod()**(12/len(r))-1)
        rows.append(dict(strategy_id=sid, period_role=period_role, n_months=len(r), start=r.index.min(), end=r.index.max(),
            CAGR=cagr, AnnReturn=cagr, AnnVol=annualized_vol(r), Sharpe_exBIL=gm.sharpe_exbil(r, rf),
            Sharpe_rf0_legacy=sharpe_rf0(r), MaxDD=float((wealth/np.maximum.accumulate(wealth)-1).min()),
            turnover_per_year=12*sub.turnover.mean(), HHI_mean=hhi.mean(), eff_N_mean=(1/hhi).mean(),
            names_held_mean=w.assign(held=w.weight > .001).groupby('date').held.sum().mean(),
            eff_N_category_mean=(1/(cats**2).sum(axis=1)).mean(), largest_single_name=avg.idxmax(),
            largest_single_name_share=avg.max(), largest_category=cats.mean().idxmax(),
            largest_category_share=cats.mean().max(), trial_count=TRIAL_COUNT))
    return pd.DataFrame(rows)


def summarize_epo(result, universe, rf, trial_count=TRIAL_COUNT, bootstrap_reps=BOOTSTRAP_REPS):
    if trial_count != TRIAL_COUNT:
        raise ValueError('pre-registered trial_count must be 11')
    oos, weights = result['oos_returns'], result['weights']
    full = _summary(oos, weights, universe, rf, 'full window')
    registry = trial_registry_epo(full.set_index('strategy_id').Sharpe_exBIL.to_dict())
    result['trial_registry'] = registry
    variance = v3.cross_trial_sharpe_var(registry)
    frames, tests = [], []
    for role, data in [('full window', oos), ('sub-period (not a trial)', oos.loc[oos.date >= pd.Timestamp(SUBPERIOD)])]:
        if data.empty:
            continue
        summary = full.copy() if role == 'full window' else _summary(data, weights, universe, rf, role)
        for idx, row in summary.iterrows():
            r = data.loc[data.strategy_id.eq(row.strategy_id)].set_index('date')['return']
            ex = r.to_numpy()-gm.align_rf(r.index, rf).rf.to_numpy()
            summary.loc[idx, 'DSR_exBIL'] = deflated_sharpe_bailey_lp(
                row.Sharpe_exBIL/np.sqrt(12), len(r), trial_count, variance,
                skew(ex, bias=False), kurtosis(ex, fisher=False, bias=False)) if len(r) >= 4 else np.nan
        summary['sr_var_cross_trial_monthly'] = variance
        frames.append(summary)
        for sid in METHODS:
            a = data.loc[data.strategy_id.eq(sid)].set_index('date')['return']
            for base in (PRIMARY, ANCHOR, TREND, EW, BOOK1):
                b = data.loc[data.strategy_id.eq(base)].set_index('date')['return']
                if len(a.index.intersection(b.index)) < 12:
                    continue
                hac = lw2008_sharpe_test(a, b, rf)
                boot = lw2008_sharpe_bootstrap(a, b, rf, reps=bootstrap_reps)
                tests.append(dict(period_role=role, strategy_id=sid, primary_null=base,
                    p_one_sided_hac=hac['p_one_sided_a_gt_b'], p_two_sided_hac=hac['p_two_sided'],
                    p_one_sided_boot=boot['p_one_sided'], p_two_sided_boot=boot['p_two_sided'],
                    z_hac=hac['z'], z_boot=boot['z'], se_nat=boot['se_nat'], reps=bootstrap_reps,
                    block_size=BLOCK_SIZE, seed=SEED))
    return pd.concat(frames, ignore_index=True), pd.DataFrame(tests, columns=[
        'period_role', 'strategy_id', 'primary_null', 'p_one_sided_hac', 'p_two_sided_hac',
        'p_one_sided_boot', 'p_two_sided_boot', 'z_hac', 'z_boot', 'se_nat', 'reps', 'block_size', 'seed'])


def category_spread(weights, universe):
    rows = []
    category = universe.set_index('Ticker').Category
    equity = gm.equity_only_tickers(universe)
    classes = gm.epo_asset_class(universe)
    for sid, w in weights.groupby('strategy_id'):
        n = w.date.nunique()
        for cat, total in w.assign(category=w.ticker.map(category).fillna('Unknown')).groupby('category').weight.sum().items():
            rows.append(dict(strategy_id=sid, grouping='Category (known mislabels)', group=cat, average_weight=total/n))
        groups = {'equity_only': w.ticker.isin(equity), 'rest': ~w.ticker.isin(equity),
                  'commodity': w.ticker.map(classes).eq('commodity'), 'ISTB/VCSH/SJNK': w.ticker.isin(['ISTB', 'VCSH', 'SJNK'])}
        for label, mask in groups.items():
            rows.append(dict(strategy_id=sid, grouping='exposure diagnostic', group=label, average_weight=w.loc[mask, 'weight'].sum()/n))
    return pd.DataFrame(rows)


def asset_class_mix(weights, universe):
    classes = gm.epo_asset_class(universe)
    rows = []
    for sid, w in weights.groupby('strategy_id'):
        mapped = w.ticker.map(classes)
        computable = bool(mapped.isin(['equity', 'bond', 'commodity']).all())
        rows.append(dict(strategy_id=sid, computable=computable, **{
            c: float(w.loc[mapped.eq(c), 'weight'].sum()/w.date.nunique()) if computable else np.nan
            for c in ('equity', 'bond', 'commodity')}))
    return pd.DataFrame(rows)


def mechanical_reading_epo(summary, tests, composition):
    if 'period_role' in summary:
        summary = summary.loc[summary.period_role.eq('full window')]
    table = summary.set_index('strategy_id')
    m, p = table.loc[METHOD], table.loc[PRIMARY]
    t = tests.loc[tests.strategy_id.eq(METHOD) & tests.primary_null.eq(PRIMARY)]
    if 'period_role' in t:
        t = t.loc[t.period_role.eq('full window')]
    significant = bool(len(t) == 1 and t.iloc[0].p_one_sided_hac <= .05 and t.iloc[0].p_one_sided_boot <= .05)
    criteria = dict(c1=bool(m.Sharpe_exBIL > p.Sharpe_exBIL and significant),
        c2=bool(m.Sharpe_exBIL >= table.loc[ANCHOR].Sharpe_exBIL),
        c3=bool(m.Sharpe_exBIL >= table.loc[EW].Sharpe_exBIL and m.Sharpe_exBIL >= table.loc[TREND].Sharpe_exBIL),
        c4=bool(m.DSR_exBIL >= .95),
        c5=bool(all(table.loc[sid].Sharpe_exBIL > p.Sharpe_exBIL for sid in METHODS[1:])),
        c6=bool(composition['computable'] and composition['method_share'] <= .5 and composition['null_share'] <= .5 and m.eff_N_mean >= 5))
    void = m.eff_N_mean < 5
    mechanical = 'VOID' if void else 'FAIL' if not all(criteria[c] for c in ('c1', 'c2', 'c3', 'c4', 'c5')) else 'PASS'
    return dict(criteria=criteria, mechanical=mechanical, failing_criteria=[c for c, ok in criteria.items() if not ok],
                effN_method=float(m.eff_N_mean), effN_primary_diagnostic=float(p.eff_N_mean))


def book_eligibility_epo(label, summary_full, book1_window_summary, asset_mix,
                         lw2008_p_vs_book1, lw2008_p_vs_anchor):
    full = summary_full.set_index('strategy_id')
    book = book1_window_summary.set_index('strategy_id') if not book1_window_summary.empty else pd.DataFrame()
    sm, sa = (float(full.loc[s].Sharpe_exBIL) for s in (METHOD, ANCHOR))
    bm = book.loc[METHOD] if METHOD in book.index else {}
    bb = book.loc[BOOK1] if BOOK1 in book.index else {}
    bs, br = float(bm.get('Sharpe_exBIL', np.nan)), float(bb.get('Sharpe_exBIL', np.nan))
    dm, dr = float(bm.get('MaxDD', np.nan)), float(bb.get('MaxDD', np.nan))
    equity = float(asset_mix.set_index('strategy_id').loc[METHOD, 'equity'])
    anchor_ok, sharpe_ok, dd_ok, growth_ok = sm > sa, bs > br, dm > dr, equity >= .5
    reasons = []
    if label != 'PASS':
        reasons.append(f'gate label is {label}, not PASS')
    if not anchor_ok:
        reasons.append('full OOS Sharpe_exBIL is not strictly greater than anchor_ivol')
    if not (sharpe_ok or dd_ok):
        reasons.append('does not beat Book 1 on Sharpe_exBIL or MaxDD (or comparison unavailable)')
    if not growth_ok:
        reasons.append('growth-mandate fit: equity share under 50% or not computable')
    return dict(eligible=not reasons, reason='; '.join(reasons) if reasons else 'PASS; beats anchor and Book 1; equity share >= 50%',
        label=label, sharpe_exbil_method=sm, sharpe_exbil_anchor=sa, beats_anchor=anchor_ok,
        book1_window_sharpe_method=bs, book1_window_sharpe_book1=br, maxdd_method=dm, maxdd_book1=dr,
        beats_on_sharpe=sharpe_ok, beats_on_maxdd=dd_ok, method_equity_share=equity, growth_mandate_fit=growth_ok,
        lw2008_p_vs_book1=lw2008_p_vs_book1, lw2008_p_vs_anchor=lw2008_p_vs_anchor)


def run_epo_gate(weekly, monthly, universe, *, rf=None, bootstrap_reps=BOOTSTRAP_REPS):
    provenance = panel_provenance(monthly)
    gate_results.validate_monthly_panel(provenance)
    rf = gm.risk_free_monthly() if rf is None else rf
    result = run_epo_backtest(weekly, monthly, universe, rf=rf)
    result['monthly_panel_provenance'] = provenance
    result['monthly_panel_window'] = dict(start=str(monthly.index[0].date()), end=str(monthly.index[-1].date()), n_months=len(monthly))
    result['summary'], result['tests'] = summarize_epo(result, universe, rf, bootstrap_reps=bootstrap_reps)
    result['composition'] = gm.composition_tripwire(result['weights'], universe, method=METHOD, primary_null=PRIMARY)
    result['reading'] = mechanical_reading_epo(result['summary'], result['tests'], result['composition'])
    result['mechanical'] = result['reading']['mechanical']
    result['label'] = gm.final_gate_label(result['mechanical'], result['composition'])
    result['category_spread'] = category_spread(result['weights'], universe)
    result['asset_class_mix'] = asset_class_mix(result['weights'], universe)
    oos = result['oos_returns']
    book_dates = oos.loc[oos.strategy_id.eq(BOOK1), 'date']
    overlap = oos.loc[oos.date.isin(book_dates) & oos.strategy_id.isin([METHOD, BOOK1])]
    result['book1_window_summary'] = _summary(overlap, result['weights'], universe, rf, 'Book 1 overlap')
    def p_vs(base):
        tests = result['tests']
        t = tests.loc[tests.period_role.eq('full window') & tests.strategy_id.eq(METHOD) & tests.primary_null.eq(base)]
        return float(t.p_one_sided_hac.iloc[0]) if len(t) else np.nan
    full = result['summary'].loc[result['summary'].period_role.eq('full window')]
    result['book_eligible'] = book_eligibility_epo(result['label'], full, result['book1_window_summary'],
                                                 result['asset_class_mix'], p_vs(BOOK1), p_vs(ANCHOR))
    result['trial_count'] = TRIAL_COUNT
    # Library/synthetic runs do not attest to a clean tree. The guarded script
    # replaces this record with verified HEAD provenance before writing.
    result['preregistration'] = dict(path=str(PREREG_PATH), sha256=PREREG_SHA256, head_commit=None, verified=False)
    stress = []
    for sid, sub in oos.groupby('strategy_id'):
        for bps in STRESS_BPS:
            r = sub.set_index('date')[f'return_{bps}bp']
            stress.append(dict(strategy_id=sid, cost_bps=bps, Sharpe_exBIL=gm.sharpe_exbil(r, rf),
                               CAGR=float((1+r).prod()**(12/len(r))-1)))
    result['cost_stress'] = pd.DataFrame(stress)
    return result


def _markdown_table(frame):
    """Small dependency-free Markdown renderer (pandas.to_markdown needs tabulate)."""
    def cell(value):
        return str(value).replace('|', r'\|').replace('\n', ' ')
    rows = [list(frame.columns), ['---'] * len(frame.columns)]
    rows.extend(frame.itertuples(index=False, name=None))
    return '\n'.join('| ' + ' | '.join(map(cell, row)) + ' |' for row in rows)


def gate_report_lines(result):
    counts = result['name_counts']
    eligible = counts.loc[~counts.skipped, 'n_eligible']
    lines = ['# Anchored EPO allocator — PENDING QUANT', '',
             f"**Label (mechanical + composition): {result['label']}**", book_eligible_line(result['book_eligible']), '']
    lines += gm.composition_report_lines(result['composition'])
    lines += [f"Monthly panel window: {result['monthly_panel_window']}",
              f"Eligible N per rebalance (min/mean/max): {eligible.min()} / {eligible.mean():.2f} / {eligible.max()}",
              'Skipped months: ' + (', '.join(counts.loc[counts.skipped, 'date'].astype(str)) or 'none'),
              'Sharpe_rf0_legacy is legacy (rf = 0). Category has known mislabels.']
    for key in ('name_counts', 'summary', 'tests', 'asset_class_mix', 'category_spread', 'book1_window_summary', 'cost_stress', 'trial_registry'):
        lines += ['', f'## {key}', '', _markdown_table(result[key])]
    lines += ['', 'Criteria: ' + str(result['reading']), '', '## Projection diagnostics', '',
              _markdown_table(result['projection_diagnostics'].groupby('strategy_id').agg(
                  distance_mean=('projection_distance', 'mean'), distance_max=('projection_distance', 'max'),
                  zero_mean=('n_zero', 'mean'), kkt_max=('kkt_residual', 'max'),
                  solver_success=('success', 'all'), anchor_months=('anchor_held', 'sum')).reset_index()),
              f"All-zero-signal months: {len(result['signal_log'])}.",
              'DSR: Bailey–López de Prado (2014), N=11; cross-trial monthly Sharpe variance excludes the two invalid runs with no ex-BIL Sharpe. Sub-period is not a trial.',
              'No reruns or retuning to chase significance. A not-significant edge is recorded as not significant. Any preview or rerun adds a trial and needs a new ticket.',
              "Jared's method rule: statistical or classical methods only; no large pretrained models or model downloads.",
              'VT and SPHD retain the pinned equity tags; the preregistration records a pending Quant ruling.']
    return lines


def write_epo_artifacts(result, out_dir='data/processed/epo_allocator'):
    gate_results.validate_monthly_panel(result.get('monthly_panel_provenance'))
    tables = {k: v for k, v in result.items() if isinstance(v, pd.DataFrame)}
    targets = ['gate_result.json', 'gate_report.md', 'composition_tripwire.csv'] + [f'{k}.csv' for k in tables]
    if any((Path(out_dir) / name).exists() for name in targets):
        raise FileExistsError('refusing to overwrite existing EPO artifacts')
    return gate_results.write_gate_results(out_dir, gate_id=GATE_ID, label=result['label'], mechanical=result['mechanical'],
        composition=result['composition'], monthly_panel=result['monthly_panel_provenance'],
        tables=tables, report=result['reading'],
        markdown_lines=gate_report_lines(result), fields=dict(book_eligible=result['book_eligible'], trial_count=TRIAL_COUNT,
        asset_class_mix=result['asset_class_mix'].to_dict('records'), preregistration=result['preregistration']))
