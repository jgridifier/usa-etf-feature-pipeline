"""Stocks-only NLS GMV research gate.

Ledoit & Wolf (2020), AoS 48(5) 3043–3065; LW (2017), RFS 30(12)
4349–4388; LW (2011), Wilmott 2011(55) 86–89; LW (2008), JEF 15(5)
850–859; Bailey & López de Prado (2014), JPM 40(5) 94–107;
Clarke, de Silva & Thorley (2006), JPM 33(1) 10–24.
Research only; snapshot universe implies survivorship bias. Registry enabled:false.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
import json

import numpy as np
import pandas as pd
from scipy.special import ndtr, ndtri

from . import nonlinear_shrinkage_gmv as v1
from . import nonlinear_shrinkage_gmv_v2 as v2
from . import gate_metrics as gm
from . import gate_results
from .vol_target import annualized_vol, sharpe_rf0, newey_west_tstat, deflated_sharpe_approx

METHOD, PRIMARY = v1.METHOD, v1.PRIMARY
USMV_REF, ACWI_REF = 'buy_hold_usmv', 'buy_hold_acwi'
REF_TICKERS = {USMV_REF: 'USMV', ACWI_REF: 'ACWI'}
ROLES_V3 = {METHOD: 'method', PRIMARY: 'primary_null', 'erc_weekly': 'null', 'equal_weight': 'null',
            USMV_REF: 'reference (book-eligibility comparison)', ACWI_REF: 'reference'}
LOW_VOL_FUNDS = ('USMV', 'EFAV', 'GSWO')
TRIAL_COUNT_V3 = v2.TRIAL_COUNT_V2 + 2
assert TRIAL_COUNT_V3 == 8
NAME_FLOOR = 65
OOS_START, OOS_END = '2016-01', '2026-09'
BOOK2_SUBPERIOD = ('2021-02', '2026-09')
BOOTSTRAP_REPS, BLOCK_SIZE, SEED = 5000, 4, 20260926
GATE_ID = 'nonlinear_shrinkage_gmv_v3_equity_only'
TICKET = '/workspace/investments/justina_shortlist/ENGINEERING_TICKET_nonlinear_shrinkage_gmv_v3_equity_only.md'
STATUS = 'PENDING QUANT'
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class NLSGMVv3Trial:
    window_weeks: int = 156
    min_names: int = 65
    cost_bps: float = 5.0
    oos_start: str = '2016-01-01'
    oos_end: str = '2026-09-30'


PREREGISTERED_V3 = (NLSGMVv3Trial(156), NLSGMVv3Trial(260))


def final_month_unpriced(weekly, monthly, universe, trial=NLSGMVv3Trial()):
    """Names eligible at the last decision date that have no return in the final (partial) OOS month.

    The committed panel's 2026-09 row is the partial month to 2026-09-16. A name priced at the decision
    date but missing that partial-month return cannot be evaluated, so it is treated as not investable at
    the final rebalance only (method and every null alike) and listed in the report. Gaps anywhere else
    still stop the run (v2's "explicit data repair required").
    """
    monthly = monthly.sort_index()
    names = [t for t in sorted(gm.equity_only_tickers(universe)) if t in monthly and t in weekly]
    dates = [d for d in monthly.index if pd.Timestamp(trial.oos_start) <= d <= pd.Timestamp(trial.oos_end)]
    if not dates or dates[-1] != monthly.index[-1]:
        return pd.DataFrame(columns=['decision_date', 'date', 'ticker'])
    final = dates[-1]
    decision = monthly.index[monthly.index.get_loc(final) - 1]
    win = weekly.loc[:decision, names].tail(trial.window_weeks)
    live = win.columns[win.notna().all()]
    missing = [t for t in live if pd.isna(monthly.loc[final, t])]
    return pd.DataFrame(dict(decision_date=decision, date=final, ticker=missing),
                        columns=['decision_date', 'date', 'ticker'])


def run_nls_gmv_v3_trial(weekly, monthly, universe, trial=NLSGMVv3Trial()):
    eq = universe.loc[universe.Ticker.isin(gm.equity_only_tickers(universe))]
    unpriced = final_month_unpriced(weekly, monthly, universe, trial)
    if len(unpriced):
        # Mask only the weeks after the previous decision date, so the names drop out of the final window
        # alone; no earlier window (all end on or before the previous decision date) changes.
        decision = unpriced.decision_date.iloc[0]
        previous = monthly.index[monthly.index.get_loc(decision) - 1]
        weekly = weekly.copy()
        weekly.loc[(weekly.index > previous) & (weekly.index <= decision), list(unpriced.ticker)] = np.nan
    result = v2.run_nls_gmv_v2_trial(weekly, monthly, eq, None, v2.NLSGMVv2Trial(
        window_weeks=trial.window_weeks, min_names=trial.min_names, include_thin=True,
        exclude_categories=(), exclude_cash_like=False, cost_bps=trial.cost_bps,
        oos_start=trial.oos_start, oos_end=trial.oos_end))
    for key in ('oos_returns', 'weights'):
        result[key] = result[key].loc[result[key].strategy_id.ne(v2.REFERENCE)].copy()
    result['name_counts']['below_floor'] = result['name_counts'].n_eligible < trial.min_names
    result['final_month_unpriced'] = unpriced.assign(window_weeks=trial.window_weeks)
    method = result['oos_returns'].loc[result['oos_returns'].strategy_id.eq(METHOD)].sort_values('date')
    returns, weights = [], []
    for sid, ticker in REF_TICKERS.items():
        for i, row in enumerate(method.to_dict('records')):
            gross = monthly.loc[row['date'], ticker] if ticker in monthly else np.nan
            if pd.isna(gross):
                raise ValueError(f'missing reference return for {ticker} at {row["date"]}')
            turnover = .5 if i == 0 else 0.
            cost = turnover * trial.cost_bps / 10000
            returns.append({**row, 'strategy_id': sid, 'n_names': 1, 'gross_return': gross,
                            'turnover': turnover, 'cost_return': cost, 'return': gross - cost})
            weights.append(dict(decision_date=row['decision_date'], date=row['date'],
                                window_weeks=trial.window_weeks, strategy_id=sid, ticker=ticker, weight=1.))
    result['oos_returns'] = pd.concat([result['oos_returns'], pd.DataFrame(returns)], ignore_index=True)
    result['weights'] = pd.concat([result['weights'], pd.DataFrame(weights)], ignore_index=True)
    return result


def weekly_vs_monthly_coverage(weekly, monthly, universe):
    rows = []
    for ticker in sorted(gm.equity_only_tickers(universe)):
        fw = weekly[ticker].first_valid_index() if ticker in weekly else None
        fm = monthly[ticker].first_valid_index() if ticker in monthly else None
        if fw is not None and fm is not None and (fw - fm).days > 35:
            rows.append(dict(ticker=ticker, first_weekly=fw, first_monthly=fm, gap_days=(fw - fm).days))
    return pd.DataFrame(rows, columns=['ticker', 'first_weekly', 'first_monthly', 'gap_days'])


def lw2008_sharpe_test(a, b, rf=None):
    pair = pd.concat([pd.Series(a), pd.Series(b)], axis=1, join='inner').dropna()
    n = len(pair)
    if n < 12:
        raise ValueError('Sharpe test requires at least 12 aligned observations')
    rf = gm.risk_free_monthly() if rf is None else rf
    raw = pair.to_numpy(dtype=float) - gm.align_rf(pair.index, rf)['rf'].to_numpy()[:, None]
    if not np.isfinite(raw).all():
        raise ValueError('returns must be finite')
    scale = np.sqrt(np.mean(raw * raw))
    if scale <= 0:
        raise ValueError('Sharpe test requires positive variances')
    x = raw / scale
    mu, g = x.mean(0), (x*x).mean(0)
    var = g - mu*mu
    if np.any(var <= 0):
        raise ValueError('Sharpe test requires positive variances')
    s = np.sqrt(var)
    sr = mu/s
    delta = float(sr[0] - sr[1])
    y = np.c_[x-mu, x*x-g]
    grad = np.array([g[0]/s[0]**3, -g[1]/s[1]**3, -mu[0]/(2*s[0]**3), mu[1]/(2*s[1]**3)])
    psi, _ = v2._qs_hac(y, prewhiten=True)
    se = float(np.sqrt(max(0., grad @ psi @ grad)/n))
    if np.array_equal(raw[:, 0], raw[:, 1]):
        se, delta = 0., 0.
    z = v2._z(delta, se)
    return dict(n=n, sharpe_a_monthly=float(sr[0]), sharpe_b_monthly=float(sr[1]),
                diff_monthly=delta, se_hac=se, z=z, p_two_sided=float(2*ndtr(-abs(z))),
                p_one_sided_a_gt_b=float(ndtr(-z)))


def deflated_sharpe_bailey_lp(sr_monthly, n_obs, n_trials, sr_var_monthly, skew, kurt):
    if (not np.isfinite([sr_monthly, n_obs, n_trials, sr_var_monthly, skew, kurt]).all()
            or n_trials <= 1 or n_obs < 3 or sr_var_monthly < 0):
        return np.nan
    denom = 1 - skew*sr_monthly + (kurt-1)/4 * sr_monthly**2
    if denom <= 0:
        return np.nan
    gamma = .5772156649015329
    sr0 = np.sqrt(sr_var_monthly) * ((1-gamma)*ndtri(1-1/n_trials)
                                   + gamma*ndtri(1-1/(n_trials*np.e)))
    return float(ndtr((sr_monthly-sr0)*np.sqrt(n_obs-1)/np.sqrt(denom)))


def trial_registry_v3(v3_method_sharpes):
    old_path = ROOT / 'data/processed/nonlinear_shrinkage_gmv/oos_returns.csv'
    old = pd.read_csv(old_path, parse_dates=['date'])
    v2_path = ROOT / 'data/processed/nonlinear_shrinkage_gmv_v2/summary.csv'
    second = pd.read_csv(v2_path)
    rows = []
    for w, legacy in ((156, .796), (260, .733)):
        rows.append(dict(trial_id=f'v1_invalid_w{w}', line='v1', window_weeks=w,
                         status='invalid (numerical bug), counted', Sharpe_exBIL_annual=np.nan,
                         Sharpe_rf0_legacy_recorded=legacy, source='invalidated v1 legacy record'))
    for line in ('v1', 'v2', 'v3'):
        for w in (156, 260):
            if line == 'v1':
                sub = old.loc[old.window_weeks.eq(w) & old.strategy_id.eq(METHOD)]
                sr = gm.sharpe_exbil(sub.set_index('date')['return'])
                source = str(old_path.relative_to(ROOT))
            elif line == 'v2':
                sr = float(second.loc[second.window_weeks.eq(w) & second.strategy_id.eq(METHOD), 'Sharpe_exBIL'].iloc[0])
                source = str(v2_path.relative_to(ROOT))
            else:
                sr, source = v3_method_sharpes.get(w, np.nan), 'current v3 full-window method'
            rows.append(dict(trial_id=f'{line}_w{w}', line=line, window_weeks=w, status='valid',
                             Sharpe_exBIL_annual=sr, Sharpe_rf0_legacy_recorded=np.nan, source=source))
    registry = pd.DataFrame(rows).assign(preregistered=True, trial_count=8)
    assert len(registry) == 8
    return registry


def cross_trial_sharpe_var(registry):
    """Monthly sample variance; the two invalidated runs have no ex-BIL Sharpe."""
    sr = registry.Sharpe_exBIL_annual.to_numpy(dtype=float) / np.sqrt(12)
    sr = sr[np.isfinite(sr)]
    return float(np.var(sr, ddof=1)) if len(sr) > 1 else np.nan


def _period(frame, period):
    if period is None:
        return frame
    months = pd.DatetimeIndex(frame.date).to_period('M')
    return frame.loc[(months >= pd.Period(period[0])) & (months <= pd.Period(period[1]))]


def summarize_v3(oos, weights, name_counts, universe, trial_count, *, rf=None,
                 bootstrap_reps=BOOTSTRAP_REPS, period=None):
    rf = gm.risk_free_monthly() if rf is None else rf
    oos, weights, name_counts = (_period(f, period) for f in (oos, weights, name_counts))
    label = 'full 2016-01..2026-09' if period is None else f'book2 {period[0]}..{period[1]}'
    categories = universe.set_index('Ticker').Category
    rows, tests = [], []
    for (window, sid), sub in oos.groupby(['window_weeks', 'strategy_id']):
        sub = sub.sort_values('date')
        r = sub.set_index('date')['return']
        base = oos.loc[oos.window_weeks.eq(window) & oos.strategy_id.eq(PRIMARY)].set_index('date')['return']
        aligned = pd.concat([r, base], axis=1, join='inner').dropna()
        w = weights.loc[weights.window_weeks.eq(window) & weights.strategy_id.eq(sid)]
        n = w.date.nunique()
        hhi = w.assign(square=w.weight**2).groupby('date').square.sum()
        held = w.assign(held=w.weight > 1e-4).groupby('date').held.sum()
        cats = w.assign(category=w.ticker.map(categories)).groupby(['date', 'category']).weight.sum().unstack(fill_value=0)
        avg_cats = cats.mean().sort_values(ascending=False)
        holdings = (w.groupby('ticker').weight.sum()/n).sort_values(ascending=False)
        wealth = np.r_[1., (1+r).cumprod().to_numpy()]
        sr, sr0 = gm.sharpe_exbil(r, rf), sharpe_rf0(r)
        test = {k: np.nan for k in ('p_one_sided_hac', 'p_one_sided_boot', 'delta_log_var')}
        sp = np.nan
        if sid != PRIMARY and len(aligned) >= 12:
            test = v2.lw2011_variance_test(r, base, bootstrap_reps=bootstrap_reps, block_size=BLOCK_SIZE, seed=SEED)
            sp = lw2008_sharpe_test(r, base, rf)['p_two_sided']
            tests.append(dict(period=label, window_weeks=window, strategy_id=sid, primary_null=PRIMARY, **test))
        counts = name_counts.loc[name_counts.window_weeks.eq(window), 'n_eligible']
        rows.append(dict(period=label, period_role='full window' if period is None else 'sub-period (not a trial)',
                         window_weeks=window, strategy_id=sid, n_months=len(r), start=r.index.min(), end=r.index.max(),
                         AnnReturn=float((1+r).prod()**(12/len(r))-1), AnnVol=annualized_vol(r),
                         Sharpe_exBIL=sr, Sharpe_rf0_legacy=sr0,
                         MaxDD=float(np.min(wealth/np.maximum.accumulate(wealth)-1)),
                         turnover_per_year=sub.turnover.mean()*12, HHI_mean=hhi.mean(), eff_N_mean=(1/hhi).mean(),
                         names_held_mean=held.mean(), eff_N_category_mean=(1/(cats**2).sum(axis=1)).mean(),
                         largest_category=avg_cats.index[0], largest_category_share=avg_cats.iloc[0],
                         low_vol_share_mean=float(w.loc[w.ticker.isin(LOW_VOL_FUNDS), 'weight'].sum()/n),
                         **{f'{t.lower()}_share_mean': float(holdings.get(t, 0.)) for t in LOW_VOL_FUNDS},
                         top_holdings_avg='; '.join(f'{t} {v:.2%}' for t, v in holdings.head(5).items()),
                         **{k: test[k] for k in ('p_one_sided_hac', 'p_one_sided_boot', 'delta_log_var')},
                         p_gate=float(np.maximum(test['p_one_sided_hac'], test['p_one_sided_boot'])),
                         lw2008_p_vs_primary=sp,
                         NW_t_vs_primary=np.nan if sid == PRIMARY else newey_west_tstat(aligned.iloc[:, 0]-aligned.iloc[:, 1], lags=3),
                         DSR_exBIL_repo=deflated_sharpe_approx(sr/np.sqrt(12), len(r), trial_count),
                         DSR_exBIL_rf0_legacy=deflated_sharpe_approx(sr0/np.sqrt(12), len(r), trial_count),
                         role=ROLES_V3[sid], trial_count=trial_count, avg_N_eligible=counts.mean(),
                         min_N_eligible=counts.min(), max_N_eligible=counts.max()))
    return pd.DataFrame(rows), pd.DataFrame(tests)


def mechanical_reading_v3(summary, composition):
    windows = {}
    for window, sub in summary.groupby('window_weeks'):
        table = sub.set_index('strategy_id')
        m, p = table.loc[METHOD], table.loc[PRIMARY]
        windows[f'w{window}'] = dict(c1_vol_lower=bool(m.AnnVol < p.AnnVol),
            c1=bool(m.AnnVol < p.AnnVol and m.p_gate <= .05), c2=bool(m.Sharpe_exBIL >= p.Sharpe_exBIL),
            c3=bool(m.MaxDD >= p.MaxDD), c4=bool(m.DSR_exBIL >= .95),
            effN_method_ok=bool(m.eff_N_mean >= 5), effN_primary_ok=bool(p.eff_N_mean >= 5),
            raw={'method': m.to_dict(), 'primary': p.to_dict()})
    primary, sensitivity = windows.get('w156', {}), windows.get('w260', {})
    criteria = {c: bool(primary.get(c, False)) for c in ('c1', 'c2', 'c3', 'c4')}
    criteria['c5'] = bool(sensitivity.get('c1_vol_lower') and sensitivity.get('c2'))
    criteria['c6'] = bool(composition['computable'] and composition['method_share'] == 0
                          and composition['null_share'] == 0 and primary.get('effN_method_ok')
                          and primary.get('effN_primary_ok'))
    void = [f'void_{s}_effN' for s in ('method', 'primary')
            if primary and primary['raw'][s]['eff_N_mean'] < 5]
    failing = [c for c, passed in criteria.items() if not passed]
    mechanical = 'VOID' if void else 'FAIL' if any(not criteria[c] for c in ('c1', 'c2', 'c3', 'c4', 'c5')) else 'PASS'
    return dict(criteria=criteria, windows=windows, void_tripwires=void, failing_criteria=failing, mechanical=mechanical)


def book_eligibility(label, method_row, usmv_row, lw2008_p_vs_usmv):
    sm, su = float(method_row['Sharpe_exBIL']), float(usmv_row['Sharpe_exBIL'])
    dm, du = float(method_row['MaxDD']), float(usmv_row['MaxDD'])
    bs, bd = sm > su, dm > du
    eligible = label == 'PASS' and (bs or bd)
    if label != 'PASS':
        reason = f'gate label is {label}, not PASS'
    elif eligible:
        measures = ([f'Sharpe ex-BIL ({sm:.4f} vs {su:.4f})'] if bs else [])
        measures += [f'MaxDD ({dm:.4f} vs {du:.4f})'] if bd else []
        reason = 'beats buy-and-hold USMV on ' + ' and '.join(measures)
    else:
        reason = (f'PASS but does not beat buy-and-hold USMV on Sharpe ex-BIL ({sm:.4f} vs {su:.4f}) '
                  f'or MaxDD ({dm:.4f} vs {du:.4f}); research-only')
    return dict(eligible=eligible, reason=reason, sharpe_exbil_method=sm, sharpe_exbil_usmv=su,
                maxdd_method=dm, maxdd_usmv=du, beats_on_sharpe=bs, beats_on_maxdd=bd,
                lw2008_p_vs_usmv=lw2008_p_vs_usmv)


def book_eligible_line(be):
    return f"book_eligible: {'yes' if be['eligible'] else 'no'} ({be['reason']})"


def run_nls_gmv_v3_gate(weekly, monthly, universe, trials=PREREGISTERED_V3, extra_previews=(), *,
                        rf=None, bootstrap_reps=BOOTSTRAP_REPS):
    trials, extra_previews = tuple(trials), tuple(extra_previews)
    if not trials or len({t.window_weeks for t in trials}) != len(trials):
        raise ValueError('provide nonempty trials with unique window_weeks')
    count = v2.TRIAL_COUNT_V2 + len(trials) + len(extra_previews)
    if trials == PREREGISTERED_V3 and not extra_previews:
        assert count == 8
    rf = gm.risk_free_monthly() if rf is None else rf
    runs = [run_nls_gmv_v3_trial(weekly, monthly, universe, t) for t in trials]
    result = {k: pd.concat([r[k] for r in runs], ignore_index=True) for k in runs[0]}
    oos, weights, counts = (result[k] for k in ('oos_returns', 'weights', 'name_counts'))
    full, ft = summarize_v3(oos, weights, counts, universe, count, rf=rf, bootstrap_reps=bootstrap_reps)
    sub, st = summarize_v3(oos, weights, counts, universe, count, rf=rf,
                           bootstrap_reps=bootstrap_reps, period=BOOK2_SUBPERIOD)
    registry = trial_registry_v3(full.loc[full.strategy_id.eq(METHOD)].set_index('window_weeks').Sharpe_exBIL.to_dict())
    variance = cross_trial_sharpe_var(registry)
    summary = pd.concat([full, sub], ignore_index=True)
    dsr = []
    for row in summary.itertuples():
        r = oos.loc[oos.window_weeks.eq(row.window_weeks) & oos.strategy_id.eq(row.strategy_id)]
        r = r.loc[r.date.between(row.start, row.end)].set_index('date')['return']
        excess = pd.Series(r.to_numpy() - gm.align_rf(r.index, rf)['rf'].to_numpy())
        dsr.append(deflated_sharpe_bailey_lp(row.Sharpe_exBIL/np.sqrt(12), len(r), count, variance,
                                           excess.skew(), excess.kurt()+3))
    summary['DSR_exBIL'], summary['sr_var_cross_trial_monthly'] = dsr, variance
    # Preview windows are reported but cannot stand in for the registered 156/260 criteria.
    primary_window = 156 if 156 in weights.window_weeks.values else trials[0].window_weeks
    sensitivity_window = 260 if 260 in weights.window_weeks.values else trials[-1].window_weeks
    def composition(window):
        return gm.composition_tripwire(weights.loc[weights.window_weeks.eq(window)], universe,
                                       method=METHOD, primary_null=PRIMARY, max_share=0.)
    comp, comp260 = composition(primary_window), composition(sensitivity_window)
    full = summary.loc[summary.period.eq('full 2016-01..2026-09')]
    reading = mechanical_reading_v3(full, comp)
    label = gm.final_gate_label(reading['mechanical'], comp)
    primary_summary = full.loc[full.window_weeks.eq(primary_window)].set_index('strategy_id')
    r = oos.loc[oos.window_weeks.eq(primary_window)].pivot(index='date', columns='strategy_id', values='return')
    p = lw2008_sharpe_test(r[METHOD], r[USMV_REF], rf)['p_two_sided']
    book = book_eligibility(label, primary_summary.loc[METHOD], primary_summary.loc[USMV_REF], p)
    result.update(summary=summary, variance_tests=pd.concat([ft, st], ignore_index=True), trial_registry=registry,
                  composition=comp, composition_260w=comp260, mechanical_reading=reading, label=label,
                  book_eligible=book, coverage_gaps=weekly_vs_monthly_coverage(weekly, monthly, universe),
                  trial_count=count, trials=[asdict(t) for t in trials], extra_previews=list(extra_previews),
                  status=STATUS, ticket=TICKET, bootstrap_settings=dict(bootstrap_reps=bootstrap_reps,
                  block_size=BLOCK_SIZE, seed=SEED))
    result['report_lines'] = gate_report_lines(result)
    return result


def gate_report_lines(result):
    lines = ['# NLS GMV v3 equity-only research gate', '', 'Status: PENDING QUANT — mechanical reading only',
             f"**Label (mechanical + composition): {result['label']}**", book_eligible_line(result['book_eligible']), '',
             'Research only; snapshot universe implies survivorship bias. Registry enabled:false.', '']
    lines += gm.composition_report_lines(result['composition'])
    lines += ['Any composition share above 0% is VOID.', '']
    for window, counts in result['name_counts'].groupby('window_weeks'):
        skipped = ', '.join(pd.Timestamp(d).strftime('%Y-%m') for d in counts.loc[counts.below_floor, 'date']) or 'none'
        lines += [f'{window}w eligible N: min {counts.n_eligible.min()}, mean {counts.n_eligible.mean():.2f}, '
                  f'max {counts.n_eligible.max()}; skipped months: {skipped}.']
    lines += ['Coverage-gap names (>35 days): ' + (', '.join(result['coverage_gaps'].ticker) or 'none')]
    unpriced = result['final_month_unpriced'].drop_duplicates('ticker')
    lines += ['Not investable at the final rebalance (no return in the partial 2026-09 row, method and every null alike): '
              + (', '.join(unpriced.ticker) or 'none'), '']
    columns = [('AnnVol', 'AnnVol'), ('LW2011 p HAC', 'p_one_sided_hac'), ('LW2011 p boot', 'p_one_sided_boot'),
               ('LW2011 p gate', 'p_gate'), ('Sharpe ex-BIL', 'Sharpe_exBIL'), ('Sharpe legacy (rf=0)', 'Sharpe_rf0_legacy'),
               ('MaxDD', 'MaxDD'), (f"DSR ({result['trial_count']}, cross-trial V)", 'DSR_exBIL'),
               ('DSR (repo approx)', 'DSR_exBIL_repo'), ('eff N', 'eff_N_mean'), ('eff N category', 'eff_N_category_mean'),
               ('low-vol share', 'low_vol_share_mean'), ('names held', 'names_held_mean'), ('turnover/yr', 'turnover_per_year'),
               ('NW t', 'NW_t_vs_primary'), ('LW2008 p', 'lw2008_p_vs_primary')]
    labels = {METHOD: 'method', PRIMARY: 'primary null', 'erc_weekly': 'ERC', 'equal_weight': 'EW',
              USMV_REF: 'buy-and-hold USMV', ACWI_REF: 'buy-and-hold ACWI'}
    for (window, period), group in result['summary'].groupby(['window_weeks', 'period'], sort=False):
        lines += [f'## {window}w — {period}', '', '| Strategy | ' + ' | '.join(k for k, _ in columns) + ' |',
                  '|---|' + '---|'*len(columns)]
        table = group.set_index('strategy_id')
        for sid, name in labels.items():
            row = table.loc[sid]
            lines.append('| ' + name + ' | ' + ' | '.join(f'{row[k]:.4f}' if pd.notna(row[k]) else '—' for _, k in columns) + ' |')
        lines.append('')
    reading = result['mechanical_reading']
    lines += ['## Mechanical reading of the six criteria', '']
    for key, passed in reading['criteria'].items():
        lines.append(f'- {key}: {passed}')
    for window, check in reading['windows'].items():
        m, p = check['raw']['method'], check['raw']['primary']
        lines += [f"{window}: c1 vol {m['AnnVol']:.4f} < {p['AnnVol']:.4f}, p_gate {m['p_gate']:.4f} <= 0.05; "
                  f"c2 Sharpe {m['Sharpe_exBIL']:.4f} >= {p['Sharpe_exBIL']:.4f}; "
                  f"c3 MaxDD {m['MaxDD']:.4f} >= {p['MaxDD']:.4f}; c4 DSR {m['DSR_exBIL']:.4f} >= 0.95; "
                  f"eff N method {m['eff_N_mean']:.4f}, primary {p['eff_N_mean']:.4f} (floor 5)."]
    lines += ['c5: 260w volatility and Sharpe direction only; 260w effective-N tripwires are information only.',
              f"c6: composition method {result['composition']['method_share']:.4f}, null {result['composition']['null_share']:.4f}; "
              'both must equal zero, be computable, and both 156w effective N must be >= 5.', '',
              '## Book eligibility', '', book_eligible_line(result['book_eligible']),
              'LW2008 vs USMV (informational): ' + str(result['book_eligible']['lw2008_p_vs_usmv']),
              'Book comparison details: ' + json.dumps(v2._json_safe(result['book_eligible']), sort_keys=True), '',
              '## DSR notes and trial registry', '',
              f"V = {result['summary'].sr_var_cross_trial_monthly.iloc[0]:.8f}, sample variance of monthly Sharpes from the registry. "
              '6 of 8 trials have ex-BIL Sharpe in the preregistered run; the two invalidated trials have only legacy rf=0 records. '
              'DSR uses Bailey & López de Prado (2014); repo approximation is informational.', '',
              '| ' + ' | '.join(result['trial_registry'].columns) + ' |',
              '|' + '---|'*len(result['trial_registry'].columns)]
    lines += ['| ' + ' | '.join(str(v) for v in row) + ' |' for row in result['trial_registry'].itertuples(index=False, name=None)]
    lines += ['', '2026-09 is a partial month through 2026-09-16. Book 2 (2021-02..2026-09) is a sub-period (not a trial).',
              'Bootstrap settings: ' + json.dumps(result['bootstrap_settings']),
              'LW2008 Sharpe comparisons are informational and never change the label.', '']
    return lines


def write_v3_artifacts(result, out_dir='data/processed/nonlinear_shrinkage_gmv_v3'):
    keys = ('oos_returns', 'weights', 'summary', 'variance_tests', 'name_counts',
            'shrinkage_diagnostics', 'trial_registry', 'coverage_gaps', 'final_month_unpriced')
    report = {k: result[k] for k in ('trial_count', 'trials', 'mechanical_reading', 'status', 'ticket',
                                    'extra_previews', 'bootstrap_settings')}
    report['composition_260w'] = {k: v for k, v in result['composition_260w'].items() if k != 'table'}
    return gate_results.write_gate_results(out_dir, gate_id=GATE_ID, label=result['label'],
        mechanical=result['mechanical_reading']['mechanical'], composition=result['composition'],
        tables={k: result[k] for k in keys}, report=report, markdown_lines=result['report_lines'],
        fields={'book_eligible': result['book_eligible']})
