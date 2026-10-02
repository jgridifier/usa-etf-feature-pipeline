"""Pre-registered Schur complementary allocation gate (trial 12); research only, no live-book wiring.

Cotton, P. (2024), "Schur Complementary Allocation: A Unification of Hierarchical Risk
Parity and Minimum Variance Portfolios", arXiv:2411.05807v1. Recursive bisection of an
HRP single-linkage seriation, with Schur-augmented sub-covariances (Table 1):

    A_c(g) = A - g B D^-1 C,   b_A(g) = 1 - g B D^-1 1,
    A''    = A_c / (b_A b_A'),  1/nu(A') = 1' (A_c^-1 o b_A b_A') 1 = b_A' A_c^-1 b_A,

and symmetrically for D. g = 0 is the HRP-style recursion (the HRP null); g = 1 with
exact terminal min variance recovers min variance. Every parameter is pinned in
preregistration/schur_allocator.yaml; pure functions may run on synthetic data. Only
scripts/run_schur_gate.py authorizes a real-data run, after verifying the pinned design
and a clean git tree.
"""
from pathlib import Path
import io
import json
import subprocess

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform
from scipy.stats import kurtosis, skew

from . import epo_allocator as epo
from . import gate_metrics as gm, gate_results
from . import nonlinear_shrinkage_gmv_v3 as v3
from .monthly_panel import panel_provenance
from .portfolio import ledoit_wolf_cov
from .spectral_risk_parity import long_only_minvar, normalize_cov

ROOT = epo.ROOT
GATE_ID = 'schur_allocator'
METHOD = 'schur_g050'
PRIMARY = 'lw_minvar_156w'
HRP = 'hrp_g000'
EW = 'equal_weight'
BOOK1 = epo.BOOK1
CAPPED = (METHOD, PRIMARY, HRP, EW)
LOW_VOL = ('USMV', 'EFAV', 'SPHD')
EXCLUDED_TAGS = (gm.CASH_LIKE_COLUMN, gm.SHORT_DURATION_COLUMN, gm.NEAR_CASH_COLUMN)

GAMMA_SCALE = 0.5
B_MIN = 0.05
MAX_HALVINGS = 10
GAMMA_TOL, GAMMA_CAP, PD_REL_TOL = 1e-6, 1 - 1e-6, 1e-8
TERMINAL_SIZE = 5
LOW_VOL_CAP, NAME_CAP = 0.30, 0.20
CAP_TOL, CAP_MAX_PASSES = 1e-10, 100
WINDOW_WEEKS, NAME_FLOOR, MIN_MONTHS = 156, 60, 60
FIRST_DECISION, BOOK_WINDOW_START = '2016-10-31', '2021-02'
COST_BPS = 5
EFF_N_MIN, LOW_VOL_TRIPWIRE = 5.0, 0.30
TRIAL_COUNT = epo.TRIAL_COUNT + 1
assert TRIAL_COUNT == 12
BOOTSTRAP_REPS, BLOCK_SIZE, SEED = 5000, 4, 20261002
PREREG_PATH = Path('preregistration/schur_allocator.yaml')
PREREG_SHA256 = '7ebf8675b75b9fabc6906c4dabf995db36c6dc96eba962f5d036b0b4dc262ff3'
EPO_REGISTRY = 'data/processed/epo_allocator/trial_registry.csv'
BACKBONE_PATH = Path('data/processed/live/vol_target_oos_returns.csv')         # r_vt, net
BOOK2_PATH = Path('data/processed/live/skew_managed_gatefirst_returns.csv')    # r_method, net
OUT_DIR = Path('data/processed/schur_allocator')                                # the one canonical run
PreregistrationError = epo.PreregistrationError
drift_weights = epo.drift_weights
lw2008_sharpe_test = epo.lw2008_sharpe_test
lw2008_sharpe_bootstrap = epo.lw2008_sharpe_bootstrap
deflated_sharpe_bailey_lp = epo.deflated_sharpe_bailey_lp


def verify_preregistration(root=ROOT, prereg_path=PREREG_PATH, sha256=None):
    return epo.verify_preregistration(root=root, prereg_path=prereg_path,
                                      sha256=PREREG_SHA256 if sha256 is None else sha256)


RUN_MARKER = 'RUN_RESERVED.json'


def reserve_run(root=ROOT, out_dir=OUT_DIR, preregistration=None):
    """One run: atomically reserve the canonical output before any data is loaded.

    Refuses if the directory holds anything (a reservation or artifacts from an earlier,
    possibly interrupted, run). The marker is exclusive-created (O_EXCL), so concurrent
    invocations cannot both pass, and it is kept whether or not the run finishes.
    """
    out = Path(root) / out_dir
    out.mkdir(parents=True, exist_ok=True)
    if any(p.name != RUN_MARKER for p in out.iterdir()):
        raise PreregistrationError(f'gate already run: {out_dir} holds artifacts; a rerun needs a new ticket and adds a trial')
    try:
        with open(out / RUN_MARKER, 'x') as fh:
            json.dump(dict(gate_id=GATE_ID, reserved_at=pd.Timestamp.now(tz='UTC').isoformat(),
                           preregistration=preregistration), fh, indent=2, default=str)
    except FileExistsError as exc:
        raise PreregistrationError(f'gate already run or running: {out_dir}/{RUN_MARKER} exists; '
                                   'a rerun needs a new ticket and adds a trial') from exc
    return out / RUN_MARKER


# ----------------------------------------------------------------------------- universe
def schur_universe_tickers(universe):
    """epo_asset_class == equity, minus every cash_like / short_duration / near_cash name."""
    classes = gm.epo_asset_class(universe)
    equity = set(classes.index[classes.eq('equity')].astype(str).str.strip().str.upper())
    excluded = set().union(*(gm.tagged_tickers(universe, c) for c in EXCLUDED_TAGS))
    return frozenset(equity - excluded)


# ----------------------------------------------------------------------------- seriation
def seriation_order(cov):
    """HRP (De Prado 2016) single-linkage on d = sqrt(0.5 (1 - rho)); quasi-diagonal leaf order."""
    cov = np.asarray(cov, float)
    n = len(cov)
    if n == 1:
        return np.array([0])
    sd = np.sqrt(np.diag(cov))
    rho = np.clip(cov / np.outer(sd, sd), -1, 1)
    dist = np.sqrt(np.clip(0.5 * (1 - rho), 0, None))
    np.fill_diagonal(dist, 0)
    return leaves_list(linkage(squareform(dist, checks=False), method='single'))


def bisect(n):
    """Left child = first floor(n/2) names in seriation order (De Prado convention)."""
    return n // 2


# ----------------------------------------------------------------------------- Schur blocks
def is_pd(m, rel_tol=PD_REL_TOL):
    m = np.asarray(m, float)
    if not np.isfinite(m).all():
        return False
    scale = float(np.mean(np.diag(m)))
    if scale <= 0:
        return False
    return bool(np.linalg.eigvalsh(0.5 * (m + m.T)).min() >= rel_tol * scale)


def schur_blocks(A, B, D, gamma):
    """Table 1 / eqs. (10)-(11) and their D analogues: (A_c, b_A, D_c, b_D)."""
    C = B.T
    BDinv = np.linalg.solve(D, C).T          # B D^-1
    CAinv = np.linalg.solve(A, B).T          # C A^-1
    Ac = A - gamma * BDinv @ C
    Dc = D - gamma * CAinv @ B
    bA = 1 - gamma * BDinv.sum(axis=1)
    bD = 1 - gamma * CAinv.sum(axis=1)
    return 0.5 * (Ac + Ac.T), bA, 0.5 * (Dc + Dc.T), bD


def _pd_at(A, B, D, gamma, rel_tol):
    Ac, _, Dc, _ = schur_blocks(A, B, D, gamma)
    return is_pd(Ac, rel_tol) and is_pd(Dc, rel_tol)


def gamma_max(A, B, D, tol=GAMMA_TOL, cap=GAMMA_CAP, rel_tol=PD_REL_TOL):
    """Largest gamma in [0, cap] with A_c and D_c PD; bisection on [0, 1) to ``tol`` (footnote 2)."""
    if _pd_at(A, B, D, cap, rel_tol):
        return float(cap)
    lo, hi = 0.0, float(cap)
    if not _pd_at(A, B, D, lo, rel_tol):
        return 0.0
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if _pd_at(A, B, D, mid, rel_tol) else (lo, mid)
    return float(lo)


def split_gamma(A, B, D, *, gamma_scale=GAMMA_SCALE, b_min=B_MIN, max_halvings=MAX_HALVINGS,
                rel_tol=PD_REL_TOL, gmax=None):
    """gamma = scale * gamma_max, halved (at most ``max_halvings`` times) until A_c, D_c PD and b > b_min.

    Returns (gamma, blocks, record); gamma = 0 is plain HRP at the node.
    """
    gmax = gamma_max(A, B, D, rel_tol=rel_tol) if gmax is None else float(gmax)
    g0 = gamma_scale * gmax
    record = dict(gamma_max=gmax, gamma_initial=g0, n_halvings=0, reason='', hrp_fallback=False)
    if g0 <= 0:
        return 0.0, schur_blocks(A, B, D, 0.0), dict(record, gamma=0.0)
    gamma, reasons = g0, []
    for k in range(max_halvings + 1):
        blocks = schur_blocks(A, B, D, gamma)
        Ac, bA, Dc, bD = blocks
        why = [w for w, bad in (('A_c not PD', not is_pd(Ac, rel_tol)), ('D_c not PD', not is_pd(Dc, rel_tol)),
                                (f'b_A <= {b_min}', bool(np.any(bA <= b_min))),
                                (f'b_D <= {b_min}', bool(np.any(bD <= b_min)))) if bad]
        if not why:
            return gamma, blocks, dict(record, gamma=gamma, n_halvings=k, reason='; '.join(reasons))
        reasons.append(f'gamma={gamma:.6g}: ' + ', '.join(why))
        if k < max_halvings:
            gamma *= 0.5
    return 0.0, schur_blocks(A, B, D, 0.0), dict(record, gamma=0.0, n_halvings=max_halvings,
                                                 reason='; '.join(reasons), hrp_fallback=True)


# ----------------------------------------------------------------------------- recursion
def _terminal_minvar(Q):
    if len(Q) == 1:
        return np.ones(1)
    return long_only_minvar(normalize_cov(Q))


def schur_recursion(cov, *, gamma_scale=GAMMA_SCALE, terminal_size=TERMINAL_SIZE, terminal=None,
                    descale_by_b=True, b_min=B_MIN, max_halvings=MAX_HALVINGS, gamma_fixed=None,
                    log=None, _depth=0, _labels=None):
    """Weights in the order of ``cov`` (already seriated). Appends one record per split to ``log``.

    ``descale_by_b`` (engineering default, pending Quant): the child's weights w(A'') live in
    the b-scaled coordinates of A'' = A_c / (b b'), so they are divided elementwise by b_A
    before the group scale 1/nu(A') is applied; this is the identity that makes gamma = 1
    recover min variance. ``descale_by_b=False`` is the literal eq. (4)/(9) reading.
    ``gamma_fixed`` bypasses the gamma_max scale (tests only; the gate never sets it).
    """
    cov = np.asarray(cov, float)
    n = len(cov)
    terminal = _terminal_minvar if terminal is None else terminal
    labels = list(range(n)) if _labels is None else _labels
    if n <= terminal_size:
        return np.asarray(terminal(cov), float)
    n1 = bisect(n)
    A, B, D = cov[:n1, :n1], cov[:n1, n1:], cov[n1:, n1:]
    if gamma_fixed is not None:
        g = float(gamma_fixed)
        Ac, bA, Dc, bD = schur_blocks(A, B, D, g)
        ok = g == 0 or (is_pd(Ac) and is_pd(Dc) and np.all(bA > b_min) and np.all(bD > b_min))
        if not ok:
            raise ValueError('gamma_fixed fails the PD / b checks')
        rec = dict(gamma_max=np.nan, gamma_initial=g, gamma=g, n_halvings=0, reason='', hrp_fallback=False)
    else:
        g, (Ac, bA, Dc, bD), rec = split_gamma(A, B, D, gamma_scale=gamma_scale, b_min=b_min,
                                               max_halvings=max_halvings)
    if log is not None:
        log.append(dict(depth=_depth, n=n, n_left=n1, n_right=n - n1, first=labels[0], last=labels[-1],
                        fallback=bool(rec['n_halvings'] > 0 or rec['hrp_fallback']), **rec))
    kw = dict(gamma_scale=gamma_scale, terminal_size=terminal_size, terminal=terminal, descale_by_b=descale_by_b,
              b_min=b_min, max_halvings=max_halvings, gamma_fixed=gamma_fixed, log=log, _depth=_depth + 1)
    out = []
    for Qc, b, lab in ((Ac, bA, labels[:n1]), (Dc, bD, labels[n1:])):
        child = Qc / np.outer(b, b)                               # A'' (eq. 5, elementwise)
        inv_nu = float(b @ np.linalg.solve(Qc, b))                # 1/nu(A') = b' A_c^-1 b (eq. 8)
        if inv_nu <= 0:
            raise ValueError('non-positive group fitness')
        w = schur_recursion(child, _labels=lab, **kw)
        w = w / b if descale_by_b else w
        out.append(inv_nu * w / w.sum() if not descale_by_b else inv_nu * w)
    w = np.concatenate(out)
    if np.any(w < -1e-12) or w.sum() <= 0:
        raise ValueError('recursion produced negative weights')
    w = np.clip(w, 0, None)
    return w / w.sum()


def schur_weights(cov, *, gamma_scale=GAMMA_SCALE, order=None, log=None, **kw):
    """Seriate once on the full LW covariance, recurse, and map back to the input order."""
    cov = np.asarray(cov, float)
    order = seriation_order(cov) if order is None else np.asarray(order)
    w_ord = schur_recursion(cov[np.ix_(order, order)], gamma_scale=gamma_scale, log=log,
                            _labels=list(order), **kw)
    w = np.empty(len(cov))
    w[order] = w_ord
    return w


def hrp_weights(cov, **kw):
    """HRP null: the same seriation and recursion at gamma = 0 (A'' = A, b = 1)."""
    return schur_weights(cov, gamma_scale=0.0, **kw)


# ----------------------------------------------------------------------------- caps
def caps_feasible(tickers, low_vol=LOW_VOL, low_vol_cap=LOW_VOL_CAP, name_cap=NAME_CAP):
    n_low = sum(t in set(low_vol) for t in tickers)
    return (len(tickers) - n_low) * name_cap + min(low_vol_cap, n_low * name_cap) >= 1 - 1e-12


def apply_caps(weights, *, low_vol=LOW_VOL, low_vol_cap=LOW_VOL_CAP, name_cap=NAME_CAP,
               tol=CAP_TOL, max_passes=CAP_MAX_PASSES):
    """Combined low-vol <= 30%, single name <= 20%; excess pro rata to uncapped names, iterated.

    Capped names (and, once the group cap binds, every low-vol name) receive no redistribution.
    Returns (capped weights, report). Raises if infeasible or not converged in ``max_passes``.
    """
    w = pd.Series(weights, dtype=float).copy()
    if (w < -tol).any() or abs(w.sum() - 1) > 1e-8:
        raise ValueError('caps need long-only weights summing to one')
    w = w.clip(lower=0)
    if not caps_feasible(list(w.index), low_vol, low_vol_cap, name_cap):
        raise ValueError('caps infeasible for this name set')
    low = w.index.isin(list(low_vol))
    pre_low = float(w[low].sum())
    frozen = pd.Series(False, index=w.index)
    name_bound, low_bound = set(), False

    def spread(excess):
        free = ~frozen
        if not free.any():
            raise ValueError('caps infeasible: no uncapped names left')
        base = w[free]
        w.loc[free] += excess * (base / base.sum() if base.sum() > 0 else 1 / free.sum())

    for passes in range(1, max_passes + 1):
        breach = False
        lv = float(w[low].sum())
        if lv > low_vol_cap + tol:
            breach, low_bound = True, True
            w.loc[low] *= low_vol_cap / lv
            frozen |= low
            spread(lv - low_vol_cap)
        over = w > name_cap + tol
        if over.any():
            breach = True
            name_bound |= set(w.index[over])
            excess = float((w[over] - name_cap).sum())
            w.loc[over] = name_cap
            frozen |= over
            spread(excess)
        if not breach:
            return w, dict(low_vol_cap_binding=low_bound, name_cap_binding=sorted(name_bound),
                           passes=passes, low_vol_share_pre=pre_low, low_vol_share_post=float(w[low].sum()),
                           max_weight_pre=float(pd.Series(weights, dtype=float).max()),
                           max_weight_post=float(w.max()))
    raise ValueError(f'caps did not converge in {max_passes} passes')


def effective_n(weights):
    w = np.asarray(weights, float)
    return float(1 / np.sum(w * w))


# ----------------------------------------------------------------------------- backtest
def _validate_panels(weekly, monthly):
    months = monthly.index.to_period('M')
    if months.has_duplicates or (np.diff(months.asi8) != 1).any():
        raise ValueError('monthly panel must contain consecutive months')
    if not weekly.index.is_unique or not weekly.index.is_monotonic_increasing:
        raise ValueError('weekly index must be unique and increasing')
    for panel in (weekly, monthly):
        if (panel.empty or panel.index.hasnans or panel.columns.has_duplicates
                or np.isinf(panel.to_numpy()).any() or (panel < -1).any().any()):
            raise ValueError('invalid simple returns or panel')


def run_schur_backtest(weekly, monthly, universe, *, cost_bps=None, first_decision=None,
                       window_weeks=None, name_floor=None, min_months=None):
    # None reads the pinned module constants at call time.
    cost_bps = COST_BPS if cost_bps is None else cost_bps
    first_decision = FIRST_DECISION if first_decision is None else first_decision
    window_weeks = WINDOW_WEEKS if window_weeks is None else window_weeks
    name_floor = NAME_FLOOR if name_floor is None else name_floor
    min_months = MIN_MONTHS if min_months is None else min_months
    if cost_bps < 0 or window_weeks < 2 or name_floor < 1 or min_months < 0:
        raise ValueError('invalid configuration')
    monthly = monthly.sort_index()
    _validate_panels(weekly, monthly)
    weekly = weekly.loc[:monthly.index[-1] + pd.offsets.MonthEnd(0)]
    names = sorted(schur_universe_tickers(universe) & set(weekly) & set(monthly))
    rows, weights, counts, splits, caps, lowvol = [], [], [], [], [], []
    previous, previous_i = {}, {}
    for i in range(len(monthly) - 1):
        decision, date = monthly.index[i:i + 2]
        if decision.to_period('M') < pd.Timestamp(first_decision).to_period('M'):
            continue
        # Weekly rows dated on or before calendar month-end t-1 (a Good-Friday-labelled week
        # closes on the Thursday decision date, so it is complete and not look-ahead).
        win = weekly.loc[:decision + pd.offsets.MonthEnd(0), names].tail(window_weeks)
        live = [t for t in names if len(win) == window_weeks and win[t].notna().all()
                and win[t].std() > 1e-10 and monthly[t].iloc[:i + 1].count() >= min_months]
        skip = len(live) < name_floor
        counts.append(dict(decision_date=decision, date=date, n_eligible=len(live), below_floor=skip, skipped=skip))
        if skip:
            continue
        if monthly.loc[date, live].isna().any():
            raise ValueError(f'missing OOS return at {date}; explicit data repair required')
        win = win[live]
        cov = normalize_cov(ledoit_wolf_cov(win, force_shrinkage=True).to_numpy())
        order = seriation_order(cov)
        log = []
        raw = {METHOD: schur_weights(cov, order=order, log=log),
               HRP: hrp_weights(cov, order=order),
               PRIMARY: long_only_minvar(cov),
               EW: np.full(len(live), 1 / len(live))}
        n_splits = len(log)
        splits.extend(dict(decision_date=decision, date=date, strategy_id=METHOD, split=k,
                           first=live[r.pop('first')], last=live[r.pop('last')], **r) for k, r in enumerate(log))
        allocations = {}
        for sid, x in raw.items():
            target, rep = apply_caps(pd.Series(x, index=live))
            allocations[sid] = target
            caps.append(dict(decision_date=decision, date=date, strategy_id=sid, eff_N=effective_n(target),
                             n_splits=n_splits if sid == METHOD else np.nan,
                             **{k: (','.join(v) if isinstance(v, list) else v) for k, v in rep.items()}))
        book = pd.Series({'VOO': .7, 'QQQM': .2, 'IJR': .1})
        if set(book.index) <= set(monthly) and monthly.loc[date, book.index].notna().all():
            allocations[BOOK1] = book
        for sid, target in allocations.items():
            old = previous.get(sid, pd.Series(dtype=float))
            drift = old.copy()
            if not old.empty:
                for j in range(previous_i[sid] + 1, i + 1):
                    drift = drift_weights(drift, monthly.iloc[j])
            turnover = .5 * target.subtract(drift, fill_value=0).abs().sum()
            target_turn = .5 * target.subtract(old, fill_value=0).abs().sum()
            r = monthly.loc[date, target.index]
            gross = float(target @ r)
            if sid in CAPPED:
                lv = target.index.isin(list(LOW_VOL))
                end = target * (1 + r)
                lowvol.append(dict(decision_date=decision, date=date, strategy_id=sid,
                                   low_vol_share_target=float(target[lv].sum()),
                                   low_vol_share_drifted_month_end=float(end[lv].sum() / end.sum())))
            rows.append(dict(decision_date=decision, feature_end=win.index[-1], date=date, strategy_id=sid,
                             n_names=len(target), gross_return=gross, turnover=turnover,
                             turnover_target=target_turn, cost_return=turnover * cost_bps / 10000,
                             **{'return': gross - turnover * cost_bps / 10000}))
            weights.extend(dict(decision_date=decision, date=date, strategy_id=sid, ticker=t, weight=float(v))
                           for t, v in target.items())
            previous[sid], previous_i[sid] = target, i
    if not rows:
        raise ValueError('no eligible OOS months')
    split_cols = ['decision_date', 'date', 'strategy_id', 'split', 'first', 'last', 'depth', 'n', 'n_left',
                  'n_right', 'fallback', 'gamma_max', 'gamma_initial', 'gamma', 'n_halvings', 'reason', 'hrp_fallback']
    return dict(oos_returns=pd.DataFrame(rows), weights=pd.DataFrame(weights), name_counts=pd.DataFrame(counts),
                split_log=pd.DataFrame(splits, columns=split_cols), cap_report=pd.DataFrame(caps),
                low_vol_share=pd.DataFrame(lowvol))


# ----------------------------------------------------------------------------- tripwires
def tripwires(result, universe):
    """Checked before any test. Any failure = VOID."""
    caps = result['cap_report']
    eff = caps.loc[caps.strategy_id.eq(METHOD), 'eff_N']
    effn = dict(mean=float(eff.mean()), min=float(eff.min()), share_below=float((eff < EFF_N_MIN).mean()),
                threshold=EFF_N_MIN, ok=bool(eff.mean() >= EFF_N_MIN))
    composition = gm.composition_tripwire(result['weights'], universe, method=METHOD, primary_null=PRIMARY)
    lv = result['low_vol_share']
    worst = lv.groupby('strategy_id').low_vol_share_target.max()
    drifted = lv.groupby('strategy_id').low_vol_share_drifted_month_end.max()
    low = dict(max_target_by_strategy=worst.to_dict(), max_drifted_month_end_by_strategy_diagnostic=drifted.to_dict(),
               limit=LOW_VOL_TRIPWIRE, ok=bool((worst <= LOW_VOL_TRIPWIRE + 1e-9).all()))
    reasons = []
    if not effn['ok']:
        reasons.append(f"method mean effective N {effn['mean']:.3f} < {EFF_N_MIN}")
    if composition['status'] == 'VOID':
        reasons.append('composition tripwire VOID')
    if not low['ok']:
        reasons.append('low-vol target share > 30% in some month')
    return dict(status='VOID' if reasons else 'PASS', reasons=reasons, effective_n=effn,
                composition=composition, low_vol=low)


# ----------------------------------------------------------------------------- gate
def trial_registry_schur(method_sharpe, root=ROOT):
    """The 11 committed trials (HEAD:data/processed/epo_allocator/trial_registry.csv) + this one."""
    blob = subprocess.run(['git', 'show', f'HEAD:{EPO_REGISTRY}'], cwd=root, capture_output=True, check=True).stdout
    registry = pd.read_csv(io.BytesIO(blob))
    assert len(registry) == epo.TRIAL_COUNT == 11
    row = dict(trial_id=METHOD, line='schur', window_weeks=WINDOW_WEEKS, status='valid',
               Sharpe_exBIL_annual=float(method_sharpe), source='current Schur full-window method',
               preregistered=True, w=np.nan)
    registry = pd.concat([registry, pd.DataFrame([row])], ignore_index=True).assign(trial_count=TRIAL_COUNT)
    assert len(registry) == TRIAL_COUNT
    return registry


def summarize_schur(result, universe, rf, *, bootstrap_reps=BOOTSTRAP_REPS, root=ROOT):
    oos, weights = result['oos_returns'], result['weights']
    full = epo._summary(oos, weights, universe, rf, 'full window').assign(trial_count=TRIAL_COUNT)
    registry = trial_registry_schur(full.set_index('strategy_id').loc[METHOD, 'Sharpe_exBIL'], root=root)
    variance = v3.cross_trial_sharpe_var(registry)
    for idx, row in full.iterrows():
        r = oos.loc[oos.strategy_id.eq(row.strategy_id)].set_index('date')['return']
        ex = r.to_numpy() - gm.align_rf(r.index, rf).rf.to_numpy()
        full.loc[idx, 'DSR_exBIL'] = deflated_sharpe_bailey_lp(
            row.Sharpe_exBIL / np.sqrt(12), len(r), TRIAL_COUNT, variance,
            skew(ex, bias=False), kurtosis(ex, fisher=False, bias=False)) if len(r) >= 4 else np.nan
    full['sr_var_cross_trial_monthly'] = variance
    a = oos.loc[oos.strategy_id.eq(METHOD)].set_index('date')['return']
    b = oos.loc[oos.strategy_id.eq(PRIMARY)].set_index('date')['return']
    hac = lw2008_sharpe_test(a, b, rf)
    boot = lw2008_sharpe_bootstrap(a, b, rf, block_size=BLOCK_SIZE, reps=bootstrap_reps, seed=SEED)
    tests = pd.DataFrame([dict(strategy_id=METHOD, primary_null=PRIMARY,
                               p_one_sided_hac=hac['p_one_sided_a_gt_b'], p_two_sided_hac=hac['p_two_sided'],
                               p_one_sided_boot=boot['p_one_sided'], p_two_sided_boot=boot['p_two_sided'],
                               z_hac=hac['z'], z_boot=boot['z'], se_nat=boot['se_nat'], reps=bootstrap_reps,
                               block_size=BLOCK_SIZE, seed=SEED)])
    return full, tests, registry


def mechanical_reading(summary, tests):
    t = summary.set_index('strategy_id')
    m = t.loc[METHOD]
    row = tests.loc[tests.strategy_id.eq(METHOD) & tests.primary_null.eq(PRIMARY)]
    significant = bool(len(row) == 1 and row.iloc[0].p_one_sided_hac <= .05 and row.iloc[0].p_one_sided_boot <= .05)
    criteria = dict(c1=bool(m.Sharpe_exBIL > t.loc[PRIMARY].Sharpe_exBIL and significant),
                    c2=bool(m.Sharpe_exBIL >= t.loc[HRP].Sharpe_exBIL),
                    c3=bool(m.Sharpe_exBIL >= t.loc[EW].Sharpe_exBIL),
                    c4=bool(m.DSR_exBIL >= .95))
    return dict(criteria=criteria, mechanical='PASS' if all(criteria.values()) else 'FAIL',
                failing_criteria=[c for c, ok in criteria.items() if not ok])


def _load_reference(path, column):
    path = Path(path)
    if not path.exists():
        return None
    return pd.read_csv(path, parse_dates=['date']).drop_duplicates('date').set_index('date')[column].sort_index()


def _stats(r, rf):
    wealth = np.r_[1., (1 + r).cumprod()]
    return dict(n_months=len(r), start=str(r.index[0].date()), end=str(r.index[-1].date()),
                Sharpe_exBIL=gm.sharpe_exbil(r, rf), MaxDD=float((wealth / np.maximum.accumulate(wealth) - 1).min()),
                CAGR=float((1 + r).prod() ** (12 / len(r)) - 1))


def book_eligibility(label, oos, rf, backbone=None, book2=None, root=ROOT):
    """CIO rule, only after PASS: common window from 2021-02, net vs net."""
    if label != 'PASS':
        return dict(eligible=False, reason=f'gate label is {label}, not PASS; book comparison not computed', label=label)
    backbone = _load_reference(Path(root) / BACKBONE_PATH, 'r_vt') if backbone is None else backbone
    book2 = _load_reference(Path(root) / BOOK2_PATH, 'r_method') if book2 is None else book2
    series = {sid: oos.loc[oos.strategy_id.eq(sid)].set_index('date')['return'] for sid in (METHOD, BOOK1)}
    if backbone is None or book2 is None or series[BOOK1].empty:
        return dict(eligible=False, reason='reference series unavailable', label=label)
    series.update(backbone=backbone, book2=book2)
    by_month = {k: s.set_axis(pd.DatetimeIndex(s.index).to_period('M')) for k, s in series.items()}
    common = sorted(set.intersection(*(set(s.index) for s in by_month.values())))
    common = [p for p in common if p >= pd.Period(BOOK_WINDOW_START, 'M')]
    if len(common) < 12:
        return dict(eligible=False, reason='common window shorter than 12 months', label=label)
    stats = {}
    for k, s in by_month.items():
        r = s.loc[common]
        r.index = r.index.to_timestamp('M')
        stats[k] = _stats(r, rf)
    sharpe_ok = stats[METHOD]['Sharpe_exBIL'] > stats['backbone']['Sharpe_exBIL']
    dd_ok = stats[METHOD]['MaxDD'] >= stats[BOOK1]['MaxDD']
    reasons = [r for r, ok in (('Sharpe_exBIL not > Backbone', sharpe_ok), ('MaxDD worse than Book 1', dd_ok)) if not ok]
    return dict(eligible=not reasons, reason='; '.join(reasons) or 'PASS; beats Backbone on Sharpe_exBIL and MaxDD no worse than Book 1',
                label=label, window=f'{common[0]}..{common[-1]}', n_months=len(common), stats=stats,
                beats_backbone_sharpe=bool(sharpe_ok), maxdd_no_worse_than_book1=bool(dd_ok),
                book2='reference only')


def run_schur_gate(weekly, monthly, universe, *, rf=None, bootstrap_reps=BOOTSTRAP_REPS, root=ROOT):
    provenance = panel_provenance(monthly)
    gate_results.validate_monthly_panel(provenance)
    rf = gm.risk_free_monthly() if rf is None else rf
    result = run_schur_backtest(weekly, monthly, universe)
    result['monthly_panel_provenance'] = provenance
    result['monthly_panel_window'] = dict(start=str(monthly.index[0].date()), end=str(monthly.index[-1].date()),
                                          n_months=len(monthly))
    trip = result['tripwires'] = tripwires(result, universe)
    result['composition'] = trip['composition']
    sl = result['split_log']
    result['fallback_share'] = float(sl.fallback.mean()) if len(sl) else 0.0
    result['hrp_fallback_share'] = float(sl.hrp_fallback.mean()) if len(sl) else 0.0
    if trip['status'] == 'VOID':
        # Short-circuit: no Sharpe test, DSR or criterion is computed or reported as a result.
        result['summary'] = result['tests'] = result['trial_registry'] = pd.DataFrame()
        result['reading'] = dict(criteria=None, mechanical='VOID', tripwire_reasons=trip['reasons'])
    else:
        result['summary'], result['tests'], result['trial_registry'] = summarize_schur(
            result, universe, rf, bootstrap_reps=bootstrap_reps, root=root)
        result['reading'] = mechanical_reading(result['summary'], result['tests'])
    result['mechanical'] = result['reading']['mechanical']
    result['label'] = gm.final_gate_label(result['mechanical'], result['composition'])
    result['book_eligible'] = book_eligibility(result['label'], result['oos_returns'], rf, root=root)
    result['trial_count'] = TRIAL_COUNT
    result['preregistration'] = dict(path=str(PREREG_PATH), sha256=PREREG_SHA256, head_commit=None, verified=False)
    return result


# ----------------------------------------------------------------------------- report / writer
def gate_report_lines(result):
    trip, counts = result['tripwires'], result['name_counts']
    eligible = counts.loc[~counts.skipped, 'n_eligible']
    caps = result['cap_report']
    lines = ['# Schur complementary allocator (trial 12) — PENDING QUANT', '',
             f"**Label (mechanical + composition): {result['label']}**",
             v3.book_eligible_line(result['book_eligible']), '']
    lines += gm.composition_report_lines(result['composition'])
    e = trip['effective_n']
    lines += ['## Tripwires (checked first)', '',
              f"- Effective N (method, post-cap targets): mean {e['mean']:.3f}, min {e['min']:.3f}, "
              f"share of months < 5: {e['share_below']:.2%} (VOID if mean < 5).",
              f"- Low-vol target share max by strategy: {trip['low_vol']['max_target_by_strategy']} (limit 30%); "
              f"drifted month-end diagnostic: {trip['low_vol']['max_drifted_month_end_by_strategy_diagnostic']}.",
              f"- Tripwire status: {trip['status']} {trip['reasons'] or ''}", '',
              f"Gamma fallback share of splits: {result['fallback_share']:.2%}; HRP fallback share: "
              f"{result['hrp_fallback_share']:.2%}.",
              f"Eligible N per rebalance (min/mean/max): {eligible.min()} / {eligible.mean():.2f} / {eligible.max()}",
              'Skipped months: ' + (', '.join(counts.loc[counts.skipped, 'date'].astype(str)) or 'none')]
    for sid in CAPPED:
        c = caps.loc[caps.strategy_id.eq(sid)]
        lines.append(f"- Caps binding `{sid}`: low-vol {int(c.low_vol_cap_binding.sum())} months, "
                     f"single-name {int(c.name_cap_binding.astype(str).ne('').sum())} months.")
    for key in ('summary', 'tests', 'trial_registry', 'name_counts'):
        if not result[key].empty:
            lines += ['', f'## {key}', '', epo._markdown_table(result[key])]
    lines += ['', 'Criteria: ' + str(result['reading']),
              'DSR: Bailey–López de Prado (2014), N=12, registry cross-trial variance. One run; no sensitivities.']
    return lines


def write_schur_artifacts(result, out_dir='data/processed/schur_allocator'):
    gate_results.validate_monthly_panel(result.get('monthly_panel_provenance'))
    tables = {k: v for k, v in result.items() if isinstance(v, pd.DataFrame)}
    targets = ['gate_result.json', 'gate_report.md', 'composition_tripwire.csv'] + [f'{k}.csv' for k in tables]
    if any((Path(out_dir) / name).exists() for name in targets):
        raise FileExistsError('refusing to overwrite existing Schur artifacts')
    return gate_results.write_gate_results(
        out_dir, gate_id=GATE_ID, label=result['label'], mechanical=result['mechanical'],
        composition=result['composition'], monthly_panel=result['monthly_panel_provenance'], tables=tables,
        report=result['reading'], markdown_lines=gate_report_lines(result),
        fields=dict(book_eligible=result['book_eligible'], trial_count=TRIAL_COUNT,
                    preregistration=result['preregistration'],
                    tripwires={k: v for k, v in result['tripwires'].items() if k != 'composition'},
                    fallback_share=result['fallback_share'], hrp_fallback_share=result['hrp_fallback_share']))
