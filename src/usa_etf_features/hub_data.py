"""Methods results hub: data layer (PR A of the hub plan, /workspace/investments/hub_plan.md).

Builds every figure the hub pages show from SAVED artifacts only: committed OOS return series, weights,
trial registries, gate outputs and archive cards, plus the saved monthly panel for the static core's
stand-in sensitivity and the SPY regime reference. No strategy, gate or optimizer is re-run.

The static core is THE benchmark (Book 1, ``static_option_a``: 70% VOO / 20% QQQM / 10% IJR, monthly
rebalanced, gross). Its returns are the saved live series S1 (``live/strategy_returns.csv``); it exists from
2020-11 (QQQM's first full month). Months before that are "not in window". A stand-in core
(70% IVV / 20% QQQ / 10% IJR from the saved panel) is a labelled sensitivity only and never replaces S1.

Rulings applied (CoS + CIO, 2026-10-04): leaderboard ranked by CAGR difference vs the core over the common
65 months (2021-04..2026-08); VOID runs carry no Sharpe and no DSR and sit below the ranking; the Backbone
headline is the live 0.86 (site_sharpe.json). DSRs (Quant + CIO, 2026-10-04): where Quant's ex-BIL recompute
has a row, the corrected dsr_exbil is primary and the recorded value sits beside it "as recorded", with a one-line
error note; no verdict changes.
"""
from __future__ import annotations

import csv
import json
import re
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import gate_metrics as gm
from . import monthly_panel as mp
from .nonlinear_shrinkage_gmv_v3 import lw2008_sharpe_test
from .vol_target import newey_west_tstat

ROOT = Path(__file__).resolve().parents[2]
P = 'data/processed/'
PANEL = 'data/raw/usa_universe_panel_monthly_returns.csv'
TRIAL_COUNTS = 'data/processed/hub/trial_counts.json'
ADMISSION = {'book2': 'data/processed/hub/book2_admission.json'}
TURNOVER_CONVENTION = 'one-way, ½·Σ|Δw| per year'
ARCHIVE = 'apps/pages/src/data/archive_verdicts.json'
SITE_SHARPE = P + 'cash_null_audit/site_sharpe.json'
DSR_RECOMPUTE = P + 'hub/dsr_exbil_recompute.csv'   # Quant's ex-BIL DSR recompute (verbatim copy; see .PROVENANCE.md)

COMMON_WINDOW = ('2021-04', '2026-08')
CORE_START = '2020-11'
CORE_WEIGHTS = {'VOO': 0.70, 'QQQM': 0.20, 'IJR': 0.10}
STANDIN_WEIGHTS = {'IVV': 0.70, 'QQQ': 0.20, 'IJR': 0.10}
ALPHA, POWER = 0.05, 0.80
Z_POWER = float(norm.ppf(1 - ALPHA) + norm.ppf(POWER))
ROLL = 36
MIN_SHARPE_MONTHS = 12
NW_LAGS = 3
STRESS_THRESHOLD = -0.10
DD_STATES = (('Up', -0.05), ('Correction', -0.20))   # drawdown > -5% Up; > -20% Correction; else Bear
NAMED_WINDOWS = (
    dict(id='euro_2011', name='2011 euro crisis / US downgrade', start='2011-05', end='2011-09', rule='named'),
    dict(id='tariff_2025', name='2025 tariff shock', start='2025-02', end='2025-04', rule='named'),
)
STRESS_NAMES = {'1998-07': ('ltcm_1998', 'LTCM 1998'), '2000-09': ('dotcom', 'Dot-com bear'),
                '2007-11': ('gfc', 'GFC'), '2018-10': ('q4_2018', 'Q4 2018'), '2020-01': ('covid', 'COVID'),
                '2022-01': ('bear_2022', '2022 inflation bear')}

LEGACY = 'rf = 0 basis'
EXBIL = 'Sharpe ex-BIL basis'


def prose(text):
    """Display text: the bare internal 'VT' label becomes 'vol-target backbone' (ids such as VT_option_a stay)."""
    if not isinstance(text, str):
        return text
    text = re.sub(r'\bBook-2 VT\b', 'vol-target backbone', text)
    return re.sub(r'(?<![\w-])VT(?![\w-])', 'vol-target backbone', text)


def _f(*parts):
    return P + '/'.join(parts)


# One entry per hub subject. `card` links the archive card; series specs name the saved file and column.
SUBJECTS = [
    dict(id='book1', name='Book 1 (static core: VOO / QQQM / IJR)', group='live_book', label='LIVE BOOK', card=None,
         series=dict(file=_f('live', 'strategy_returns.csv'), filters={'strategy_id': 'static_option_a'}, col='return',
                     turnover='turnover'),
         nulls=[], weights=dict(kind='static', weights=CORE_WEIGHTS),
         timing=dict(file=_f('live', 'strategy_returns.csv'), filters={'strategy_id': 'static_option_a'}, static=True),
         trials=None, prereg=None, pages=dict(books='index.html#/books')),
    dict(id='book2', name='Book 2 (vol-target backbone × gate-first skew overlay)', group='live_book', label='LIVE BOOK',
         card=None, related='skew_overlay',
         series=dict(file=_f('live', 'skew_managed_gatefirst_returns.csv'), col='r_method', turnover='turnover'),
         nulls=[dict(key='backbone', label='Backbone', col='r_null_a', primary=True),
                dict(key='ew', label='Equal weight', col='r_null_c'),
                dict(key='minvar', label='LW MinVar', col='r_null_d'),
                dict(key='erc', label='ERC', col='r_null_e')],
         weights=dict(kind='wide', file=_f('live', 'skew_managed_gatefirst_weights.csv')),
         timing=dict(file=_f('live', 'skew_managed_gatefirst_returns.csv')),
         summary=dict(file=_f('live', 'skew_managed_gatefirst_summary.csv')),
         trials=dict(file=_f('skewness_managed', 'skew_managed_oos_summary.csv'), id='trial_id', sharpe='Sharpe_rf0', basis=LEGACY,
                     chosen='SM_option_a_vt_L63_SL21_g0p5_realizedamaya_cvar5'),
         prereg=None, pages=dict(books='index.html#/books', teaching='methods/skewness_managed_stub.html')),
    dict(id='skew_overlay', name='#6 Skew overlay: the gate-first research record', group='overlay_record',
         label='gate-first PASS', card=None, related='book2',
         series=dict(file=_f('skewness_managed', 'skew_managed_gatefirst_returns.csv'), col='r_method', turnover='turnover'),
         nulls=[dict(key='backbone', label='Backbone (research, cash 0)', col='r_null_a', primary=True),
                dict(key='ew', label='Equal weight', col='r_null_c'),
                dict(key='minvar', label='LW MinVar', col='r_null_d'),
                dict(key='erc', label='ERC', col='r_null_e')],
         weights=dict(kind='wide', file=_f('skewness_managed', 'skew_managed_gatefirst_weights.csv')),
         timing=dict(file=_f('skewness_managed', 'skew_managed_gatefirst_returns.csv')),
         summary=dict(file=_f('skewness_managed', 'skew_managed_gatefirst_summary.csv')),
         trials=dict(file=_f('skewness_managed', 'skew_managed_oos_summary.csv'), id='trial_id', sharpe='Sharpe_rf0', basis=LEGACY,
                     chosen='SM_option_a_vt_L63_SL21_g0p5_realizedamaya_cvar5'),
         prereg=None, pages=dict(teaching='methods/skewness_managed_stub.html')),
    dict(id='backbone', name='Backbone (unconditional vol-target)', group='audit_null', card='uncond_book2_vt',
         series=dict(file=_f('live', 'vol_target_oos_returns.csv'), col='r_vt', turnover='turnover'),
         nulls=[],
         sensitivities=[dict(key='frozen', label='Frozen snapshot (research run, cash 0)',
                             file=_f('vol_target_oos_returns.csv'), col='r_vt')],
         weights=dict(kind='wide', file=_f('live', 'vol_target_monthly_weights.csv')),
         timing=dict(file=_f('live', 'vol_target_oos_returns.csv')),
         trials=None, prereg=None, pages=dict(teaching='methods/allocation_alpha_vol_target.html')),
    dict(id='spectral_rp', name='Spectral Risk Parity (name mode)', group='fail', card='spectral_rp',
         series=dict(file=_f('spectral_rp', 'name', 'oos_returns.csv'), filters={'strategy_id': 'spectral_risk_parity__0'},
                     col='return', turnover='turnover'),
         nulls=[dict(key='minvar', label='LW MinVar', filters={'strategy_id': 'minvar_lw__0'}, primary=True),
                dict(key='erc', label='ERC', filters={'strategy_id': 'erc__0'}),
                dict(key='ew', label='Equal weight', filters={'strategy_id': 'equal_weight__0'})],
         sensitivities=[dict(key='sleeve', label='Sleeve mode (sensitivity)', file=_f('spectral_rp', 'sleeve', 'oos_returns.csv'),
                             filters={'strategy_id': 'spectral_risk_parity__0'}, col='return')],
         weights=dict(kind='long', file=_f('spectral_rp', 'name', 'weights.csv'), filters={'strategy_id': 'spectral_risk_parity__0'}),
         timing=dict(file=_f('spectral_rp', 'name', 'oos_returns.csv'), filters={'strategy_id': 'spectral_risk_parity__0'}),
         trials=None, dsr_basis=LEGACY, prereg=None, pages=dict(teaching='methods/spectral_risk_parity_adia.html')),
    dict(id='regime_dual', name='Regime-Aware Dual-Regime', group='fail', card='regime_dual',
         series=dict(file=_f('regime_dual', 'regime_dual_oos_returns.csv'), filters={'trial_id': 'k2_vol_corr_spread_erc'},
                     col='return', turnover='turnover'),
         nulls=[dict(key='erc', label='Unconditional ERC', filters={'trial_id': 'unconditional_erc'}, primary=True),
                dict(key='ew', label='Unconditional EW', filters={'trial_id': 'unconditional_ew'})],
         weights=dict(kind='long', file=_f('regime_dual', 'regime_dual_monthly_weights.csv'),
                      filters={'trial_id': 'k2_vol_corr_spread_erc'}, ticker='asset'),
         timing=dict(file=_f('regime_dual', 'regime_dual_oos_returns.csv'), filters={'trial_id': 'k2_vol_corr_spread_erc'}),
         trials=dict(file=_f('regime_dual', 'regime_dual_trial_registry.csv'), id='trial_id', sharpe='Sharpe', basis=LEGACY,
                     chosen='k2_vol_corr_spread_erc'),
         dsr_basis=LEGACY, prereg=None, pages=dict(teaching='methods/regime_aware_dual_regime_allocation.html')),
    dict(id='vcfc', name='#13 Vol-cond-factor-corr (VCFC)', group='fail', card='vcfc',
         series=dict(file=_f('vol_cond_factor_corr', 'vol_cfc_oos_returns.csv'),
                     filters={'trial_id': 'VCFC_option_a_vt_L21_C12_g0p5_mkt_vol'}, col='r_method', turnover='turnover'),
         nulls=[dict(key='backbone', label='Backbone (research, cash 0)', col='r_null_a', primary=True),
                dict(key='ew', label='Equal-weight sleeves', col='r_null_c')],
         weights=dict(kind='wide', file=_f('vol_cond_factor_corr', 'vol_cfc_monthly_weights.csv'),
                      filters={'trial_id': 'VCFC_option_a_vt_L21_C12_g0p5_mkt_vol'}),
         timing=dict(file=_f('vol_cond_factor_corr', 'vol_cfc_oos_returns.csv'),
                     filters={'trial_id': 'VCFC_option_a_vt_L21_C12_g0p5_mkt_vol'}),
         trials=dict(file=_f('vol_cond_factor_corr', 'vol_cfc_oos_summary.csv'), id='trial_id', sharpe='Sharpe_rf0', basis=LEGACY,
                     chosen='VCFC_option_a_vt_L21_C12_g0p5_mkt_vol'),
         dsr_basis=LEGACY, prereg=None, pages=dict(teaching='methods/allocation_alpha_vol_cond_factor_corr.html')),
    dict(id='ft_med', name='#4 Forecast-tangency MED (FT-MED)', group='fail', card='ft_med',
         series=dict(file=_f('ft_med', 'ft_med_oos_returns.csv'), col='r_method', turnover='turnover'),
         nulls=[dict(key='ew', label='Equal weight', col='r_null_a', primary=True),
                dict(key='minvar', label='LW MinVar', col='r_null_b'),
                dict(key='erc', label='ERC', col='r_null_c'),
                dict(key='mvo', label='LW MVO', col='r_null_d')],
         weights=dict(kind='wide', file=_f('ft_med', 'ft_med_monthly_weights.csv')),
         timing=dict(file=_f('ft_med', 'ft_med_oos_returns.csv')),
         trials=dict(file=_f('ft_med', 'ft_med_oos_summary.csv'), id='trial_id', sharpe='Sharpe_rf0', basis=LEGACY,
                     chosen='ft_med_ef21_fc60_sample_sleeves'),
         dsr_basis=LEGACY, prereg=None, pages=dict(teaching='methods/allocation_alpha_forecast_tangency_med.html')),
    dict(id='rr_erc', name='#3 Regime-resilient ERC (RR-ERC), Path B', group='fail', card='rr_erc',
         series=dict(file=_f('rr_erc', 'rr_erc_oos_returns.csv'), filters={'trial_id': 'rr_erc_pathB_loim_vols_histfreq_cat'},
                     col='r_method', turnover='turnover'),
         nulls=[dict(key='erc', label='Unconditional ERC', col='r_null_a', primary=True),
                dict(key='ew', label='Equal weight', col='r_null_b'),
                dict(key='minvar', label='LW MinVar', col='r_null_c')],
         sensitivities=[dict(key='path_a', label='Path A stress overlay (degenerate: equals unconditional ERC)',
                             file=_f('rr_erc', 'rr_erc_oos_returns.csv'),
                             filters={'trial_id': 'rr_erc_pathA_stress_sw12_lam25_cat'}, col='r_method')],
         weights=dict(kind='wide', file=_f('rr_erc', 'rr_erc_monthly_weights.csv'),
                      filters={'trial_id': 'rr_erc_pathB_loim_vols_histfreq_cat'}),
         timing=dict(file=_f('rr_erc', 'rr_erc_oos_returns.csv'), filters={'trial_id': 'rr_erc_pathB_loim_vols_histfreq_cat'}),
         trials=dict(file=_f('rr_erc', 'rr_erc_oos_summary.csv'), id='trial_id', sharpe='Sharpe_rf0', basis=LEGACY,
                     chosen='rr_erc_pathB_loim_vols_histfreq_cat'),
         dsr_basis=LEGACY, prereg=None, pages=dict(teaching='methods/allocation_alpha_regime_resilient_erc.html')),
    dict(id='epo', name='Bet 1 anchored EPO (12-1 trend signal)', group='fail', card='epo_anchored_trend',
         series=dict(file=_f('epo_allocator', 'oos_returns.csv'), filters={'strategy_id': 'epo_a_w075'}, col='return',
                     turnover='turnover'),
         nulls=[dict(key='minvar', label='Weekly LW MinVar', filters={'strategy_id': 'lw_minvar_156w'}, primary=True),
                dict(key='anchor', label='1/σ anchor', filters={'strategy_id': 'anchor_ivol'}),
                dict(key='ew', label='Equal weight', filters={'strategy_id': 'equal_weight'}),
                dict(key='erc', label='ERC (LW)', filters={'strategy_id': 'erc_lw'})],
         sensitivities=[dict(key=f'w{w}', label=f'EPO w = 0.{w} (sensitivity)', file=_f('epo_allocator', 'oos_returns.csv'),
                             filters={'strategy_id': f'epo_a_w0{w}'}, col='return') for w in ('50', '90')],
         weights=dict(kind='long', file=_f('epo_allocator', 'weights.csv'), filters={'strategy_id': 'epo_a_w075'}),
         timing=dict(file=_f('epo_allocator', 'oos_returns.csv'), filters={'strategy_id': 'epo_a_w075'}),
         trials=dict(file=_f('epo_allocator', 'trial_registry.csv'), id='trial_id', sharpe='Sharpe_exBIL_annual', basis=EXBIL,
                     chosen='epo_a_w075'),
         dsr_basis=EXBIL, prereg='preregistration/epo_allocator.yaml', verdict=_f('epo_allocator', 'verdict.json'),
         pages=dict(teaching='methods/allocation_alpha_epo.html', results='methods/allocation_alpha_epo_results.html')),
    dict(id='schur', name='Bet 1 Schur complementary allocator', group='fail', card='schur_allocator',
         series=dict(file=_f('schur_allocator', 'oos_returns.csv'), filters={'strategy_id': 'schur_g050'}, col='return',
                     turnover='turnover'),
         nulls=[dict(key='minvar', label='LW MinVar (capped QP)', filters={'strategy_id': 'lw_minvar_156w'}, primary=True),
                dict(key='hrp', label='HRP (Schur γ = 0)', filters={'strategy_id': 'hrp_g000'}),
                dict(key='ew', label='Equal weight (capped)', filters={'strategy_id': 'equal_weight'})],
         weights=dict(kind='long', file=_f('schur_allocator', 'weights.csv'), filters={'strategy_id': 'schur_g050'}),
         timing=dict(file=_f('schur_allocator', 'oos_returns.csv'), filters={'strategy_id': 'schur_g050'}),
         trials=dict(file=_f('schur_allocator', 'trial_registry.csv'), id='trial_id', sharpe='Sharpe_exBIL_annual', basis=EXBIL,
                     chosen='schur_g050'),
         dsr_basis=EXBIL, prereg='preregistration/schur_allocator.yaml', verdict=_f('schur_allocator', 'verdict.json'),
         pages=dict(teaching='methods/allocation_alpha_schur.html', results='methods/allocation_alpha_schur_results.html')),
]
for _v, _dir, _card in (('1', 'nonlinear_shrinkage_gmv', 'nls_gmv_v1'), ('2', 'nonlinear_shrinkage_gmv_v2', 'nls_gmv_v2'),
                        ('3', 'nonlinear_shrinkage_gmv_v3', 'nls_gmv_v3')):
    _flt = {'window_weeks': 156, 'strategy_id': 'nonlinear_shrinkage_gmv'}
    SUBJECTS.append(dict(
        id=f'nls_v{_v}', name=f'Bet 1 NLS GMV v{_v} (156-week window)', group='void', card=_card,
        series=dict(file=_f(_dir, 'oos_returns.csv'), filters=_flt, col='return', turnover='turnover'),
        nulls=[dict(key='minvar', label='Weekly LW MinVar', filters={'window_weeks': 156, 'strategy_id': 'minvar_lw_weekly'}, primary=True),
               dict(key='ew', label='Equal weight', filters={'window_weeks': 156, 'strategy_id': 'equal_weight'}),
               dict(key='erc', label='ERC (weekly)', filters={'window_weeks': 156, 'strategy_id': 'erc_weekly'})],
        sensitivities=[dict(key='w260', label='260-week window (sensitivity)', file=_f(_dir, 'oos_returns.csv'),
                            filters={'window_weeks': 260, 'strategy_id': 'nonlinear_shrinkage_gmv'}, col='return')],
        weights=dict(kind='long', file=_f(_dir, 'weights.csv'), filters=_flt),
        timing=dict(file=_f(_dir, 'oos_returns.csv'), filters=_flt),
        trials=(dict(file=_f(_dir, 'trial_registry.csv'), id='trial_id', sharpe='Sharpe_exBIL_annual', basis=EXBIL, chosen='v3_w156')
                if _v == '3' else None),
        dsr_basis=EXBIL if _v != '1' else LEGACY, prereg=None,
        verdict=_f(_dir, 'verdict.json') if _v == '3' else None,
        pages=dict(teaching='methods/allocation_alpha_nonlinear_shrinkage_gmv.html')))
SUBJECT_IDS = [s['id'] for s in SUBJECTS]
GROUP_ORDER = ('live_book', 'overlay_record', 'audit_null', 'fail', 'void')


# ---------- loading ----------

def _read(root, rel, cache):
    if rel not in cache:
        cache[rel] = pd.read_csv(Path(root) / rel, low_memory=False)
    return cache[rel]


def _filter(df, filters):
    for k, v in (filters or {}).items():
        df = df.loc[df[k] == v]
    return df


LIVE_DIR = P + 'live/'
LIVE_CORE = (LIVE_DIR + 'strategy_returns.csv', 'return', {'strategy_id': 'static_option_a'})
LIVE_REPAIR_LOG = 'data/processed/live/partial_month_repair.json'
LIVE_FIX_NOTE = ('The live-book files were built from daily closes with the live loader default, which keeps an '
                 'incomplete final month (rotation.month_end_trading_dates(complete_months_only=False)), so their '
                 '2026-09 row is a partial-September return labelled 2026-09-30. The value matches neither the '
                 'complete-month panel nor the panel\'s earlier 2026-09-16 cut, and the daily closes behind it were not '
                 'saved, so the exact cut-off is not recoverable. The complete-month panel '
                 '(load_monthly_panel(complete_months_only=True), the PR #41 rule) is used for that month.')


def live_core_fixes(root, cache=None):
    """Months where the saved live core differs from the complete-month panel core (70/20/10 VOO/QQQM/IJR).

    Returns {month: dict(live=..., panel=...)}. Any other month must agree to 1e-6 (else ValueError)."""
    cache = {} if cache is None else cache
    key = ('__live_fix__', str(root))
    if key in cache:
        return cache[key]
    live, _ = _monthly_raw(root, *LIVE_CORE, cache)
    panel = mp.load_monthly_panel(Path(root) / PANEL, complete_months_only=True)
    r = panel[list(CORE_WEIGHTS)].mul(pd.Series(CORE_WEIGHTS), axis=1).sum(axis=1, min_count=len(CORE_WEIGHTS))
    pc = pd.Series(r.to_numpy(), index=panel.index.to_period('M')).dropna()
    both = pd.concat([live, pc], axis=1, join='inner').dropna()
    diff = (both.iloc[:, 0] - both.iloc[:, 1]).abs()
    bad = diff[diff > 1e-6]
    if len(bad) and str(bad.index.min()) < '2026-09':
        raise ValueError(f'live core differs from the complete-month panel before 2026-09: {list(map(str, bad.index))}')
    fixes = {m: dict(live=float(both.loc[m].iloc[0]), panel=float(both.loc[m].iloc[1])) for m in bad.index}
    cache[key] = fixes
    return fixes


def monthly_series(root, rel, col, filters=None, cache=None):
    """Saved monthly returns, complete months only; live-book rows built from a partial month are repaired.

    For files under data/processed/live/, a month listed by live_core_fixes is rebuilt from the complete-month
    panel when the saved value is mechanically the core (it equals the saved live core: full exposure, no cost);
    otherwise that month is dropped and reported."""
    cache = {} if cache is None else cache
    s, dropped = _monthly_raw(root, rel, col, filters, cache)
    if rel.startswith(LIVE_DIR):
        for m, fx in live_core_fixes(root, cache).items():
            if m in s.index:
                if abs(s[m] - fx['live']) < 1e-12:
                    s[m] = fx['panel']
                else:
                    s = s.drop(m)
                    dropped = sorted(set(dropped) | {str(m)})
    return s, dropped


def _monthly_raw(root, rel, col, filters=None, cache=None):
    """Saved monthly returns as a month-indexed Series, complete months only.

    A row whose date falls before the 25th is a partial month (several archived runs end on 2026-09-16).
    It is dropped and reported, never paired with a complete month of another series."""
    cache = {} if cache is None else cache
    df = _filter(_read(root, rel, cache), filters)
    dates = pd.to_datetime(df['date'])
    partial = dates.dt.day < 25
    s = pd.Series(df[col].to_numpy(dtype=float), index=dates.dt.to_period('M'))
    dropped = sorted({str(p) for p in s.index[partial.to_numpy()]})
    s = s[~partial.to_numpy()]
    if s.index.has_duplicates:
        raise ValueError(f'duplicate months in {rel} {filters}')
    return s.sort_index().dropna(), dropped


def load_panel(root):
    """The saved monthly panel through the PR #41 loader (incomplete final month cut off)."""
    return mp.load_monthly_panel(Path(root) / PANEL, complete_months_only=True)


def risk_free(root):
    bil = gm.load_bil_monthly(Path(root) / PANEL)
    tb = gm.load_tb3ms(Path(root) / 'data/raw/fred_tb3ms.csv')
    rf = gm.risk_free_monthly(bil, tb)
    return rf


def rf_series(rf, months):
    al = gm.align_rf(months.to_timestamp('M'), rf)
    return pd.Series(al['rf'].to_numpy(dtype=float), index=months)


def static_core(root, cache):
    """S1, the saved live Book 1 series; the panel-derived core and the stand-in core for reference."""
    s1, dropped = monthly_series(root, *LIVE_CORE, cache)
    panel = load_panel(root)
    months = panel.index.to_period('M')

    def fixed(weights):
        r = panel[list(weights)].mul(pd.Series(weights), axis=1).sum(axis=1, min_count=len(weights))
        return pd.Series(r.to_numpy(), index=months).dropna()
    fixes = live_core_fixes(root, cache)      # empty once scripts/repair_live_partial_month.py has run
    corrections = [dict(month=str(m), live_file=_r(v['live']), complete_month_panel=_r(v['panel']),
                        action='rebuilt from the complete-month panel at load time', note=LIVE_FIX_NOTE)
                   for m, v in sorted(fixes.items())]
    log = Path(root) / LIVE_REPAIR_LOG
    if log.exists():
        rep = json.loads(log.read_text(encoding='utf-8'))
        corrections += [dict(month=rep['month'], live_file=_r(rep['partial_month_core']),
                             complete_month_panel=_r(rep['complete_month_panel_core']),
                             action='rebuilt in the live files by scripts/repair_live_partial_month.py', note=LIVE_FIX_NOTE,
                             log=LIVE_REPAIR_LOG, cells_changed=len(rep['changes']))]
    return dict(s1=s1, s1_dropped=dropped, panel_derived=fixed(CORE_WEIGHTS), standin=fixed(STANDIN_WEIGHTS),
                corrections=corrections)


# ---------- statistics ----------

def _r(x, nd=10):
    if x is None:
        return None
    x = float(x)
    return None if not math.isfinite(x) else round(x, nd)


def stats(r, rf, *, sharpe=True):
    r = r.dropna()
    n = len(r)
    if n == 0:
        return dict(n=0)
    total = float((1 + r).prod() - 1)
    curve = (1 + r).cumprod()
    out = dict(n=n, start=str(r.index.min()), end=str(r.index.max()), total_return=_r(total),
               cagr=_r((1 + total) ** (12 / n) - 1), ann_vol=_r(r.std(ddof=1) * math.sqrt(12)) if n > 1 else None,
               maxdd=_r(float((curve / curve.cummax().clip(lower=1.0) - 1).min())))
    if sharpe:
        ex = r - rf_series(rf, r.index)
        out['sharpe_exbil'] = _r(ex.mean() * 12 / (ex.std(ddof=1) * math.sqrt(12))) if n >= MIN_SHARPE_MONTHS else None
    return out


def head_to_head(a, b, rf, *, sharpe=True):
    """Paired months of a vs b: stats for both, differences, HAC tests and the power caveat."""
    pair = pd.concat([a, b], axis=1, join='inner').dropna()
    n = len(pair)
    out = dict(n=n)
    if n == 0:
        return out
    sa, sb = stats(pair.iloc[:, 0], rf, sharpe=sharpe), stats(pair.iloc[:, 1], rf, sharpe=sharpe)
    out.update(start=sa['start'], end=sa['end'], a=sa, b=sb,
               diff=dict(total_return=_r(sa['total_return'] - sb['total_return']), cagr=_r(sa['cagr'] - sb['cagr']),
                         maxdd=_r(sa['maxdd'] - sb['maxdd']), maxdd_note='single path, no test'))
    d = pair.iloc[:, 0] - pair.iloc[:, 1]
    if n >= MIN_SHARPE_MONTHS and d.abs().max() > 0:
        t = newey_west_tstat(d, lags=NW_LAGS)
        se_mean = abs(float(d.mean()) / t) if t and math.isfinite(t) and t != 0 else None
        out['return_test'] = dict(nw_t=_r(t), lags=NW_LAGS, p_two_sided=_r(2 * norm.sf(abs(t))) if math.isfinite(t) else None,
                                  detectable_ann_return_gap=_r(Z_POWER * se_mean * 12) if se_mean else None)
    if sharpe:
        out['diff']['sharpe_exbil'] = (_r(sa['sharpe_exbil'] - sb['sharpe_exbil'])
                                       if sa.get('sharpe_exbil') is not None and sb.get('sharpe_exbil') is not None else None)
        if n >= MIN_SHARPE_MONTHS and d.abs().max() > 0:
            idx = pair.index.to_timestamp('M')
            t = lw2008_sharpe_test(pd.Series(pair.iloc[:, 0].to_numpy(), idx), pd.Series(pair.iloc[:, 1].to_numpy(), idx), rf)
            se_ann = t['se_hac'] * math.sqrt(12)
            out['sharpe_test'] = dict(z=_r(t['z']), p_one_sided=_r(t['p_one_sided_a_gt_b']),
                                      p_two_sided=_r(2 * norm.sf(abs(t['z']))), significant_5pct_two_sided=bool(2 * norm.sf(abs(t['z'])) < 0.05),
                                      se_hac_annual=_r(se_ann),
                                      detectable_sharpe_gap=_r(Z_POWER * se_ann))
    out['power'] = power_caveat(out, sharpe)
    return out


def power_caveat(h, sharpe=True):
    n = h['n']
    if n < MIN_SHARPE_MONTHS:
        return dict(n=n, text=f'{n} paired months: too few months for a test.')
    if sharpe and h.get('sharpe_test'):
        g = h['sharpe_test']['detectable_sharpe_gap']
        return dict(n=n, detectable_sharpe_gap=g,
                    text=f'{n} paired months can only detect a Sharpe gap of about {g:.2f} (one-sided 5%, 80% power).')
    rt = h.get('return_test') or {}
    g = rt.get('detectable_ann_return_gap')
    if g is None:
        return dict(n=n, text=f'{n} paired months: the two series are identical, so there is no gap to test.')
    return dict(n=n, detectable_ann_return_gap=g,
                text=f'{n} paired months can only detect an annual return gap of about {100 * g:.1f} points '
                     '(one-sided 5%, 80% power).')


def window(s, start, end):
    return s[(s.index >= pd.Period(start, 'M')) & (s.index <= pd.Period(end, 'M'))]


# ---------- regimes and stress windows ----------

def market_regimes(root):
    spy = load_panel(root)['SPY'].dropna()
    spy.index = spy.index.to_period('M')
    curve = (1 + spy).cumprod()
    dd = curve / curve.cummax().clip(lower=1.0) - 1
    vol = spy.rolling(12).std(ddof=1) * math.sqrt(12)
    med = float(vol.median())
    state = pd.Series('Bear', index=dd.index)
    state[dd > DD_STATES[1][1]] = 'Correction'
    state[dd > DD_STATES[0][1]] = 'Up'
    vstate = pd.Series(np.where(vol.isna(), None, np.where(vol > med, 'High vol', 'Low vol')), index=vol.index)
    df = pd.DataFrame(dict(spy_return=spy, spy_drawdown=dd, drawdown_state=state, spy_vol_12m=vol, vol_state=vstate))
    return df, med


def stress_windows(regimes):
    dd = regimes['spy_drawdown']
    out, i, idx = [], 0, list(dd.index)
    while i < len(idx):
        if dd.iloc[i] < 0 and (i == 0 or dd.iloc[i - 1] == 0):
            j, trough = i, i
            while j < len(idx) and dd.iloc[j] < 0:
                if dd.iloc[j] < dd.iloc[trough]:
                    trough = j
                j += 1
            if dd.iloc[trough] <= STRESS_THRESHOLD:
                start = str(idx[i])
                wid, name = STRESS_NAMES.get(start, (f'episode_{start}', f'SPY drawdown from {start}'))
                out.append(dict(id=wid, name=name, start=start, end=str(idx[trough]), rule='SPY month-end drawdown ≥ 10%',
                                spy_drawdown=_r(dd.iloc[trough])))
            i = j
        else:
            i += 1
    spy = regimes['spy_return']
    for w in NAMED_WINDOWS:
        r = window(spy, w['start'], w['end'])
        out.append(dict(w, spy_cumulative=_r((1 + r).prod() - 1)))
    return sorted(out, key=lambda w: w['start'])


def coverage(s, months):
    k = int(pd.Index(months).isin(s.index).sum())
    m = len(months)
    status = 'not in window' if k == 0 else ('in window' if k == m else f'partly in window ({k} of {m} months)')
    return dict(k=k, m=m, status=status)


def paired_blocks(pseries, s, s1, months, rf, sharpe):
    """Regime / stress cells on PAIRED months (CIO review of #55, item 5).

    `series`: method, core and primary null on the same months (those all three cover).
    `series_ex_core`: where the core is absent (it starts 2020-11), method and null on their shared months.
    `own_coverage`: each series' own coverage of the regime/window, reported beside the paired figures."""
    def common(keys):
        return [m for m in months if all(m in pseries[k].index for k in keys)]
    paired = common(list(pseries))
    h = head_to_head(s[s.index.isin(paired)], s1[s1.index.isin(paired)], rf, sharpe=sharpe)
    empty = {k: dict(coverage=dict(k=0, m=0, status='not in window')) for k in pseries}
    out = dict(paired_months=len(paired), paired_window=(f'{paired[0]} to {paired[-1]}' if paired else None),
               own_coverage={k: coverage(x, months) for k, x in pseries.items()},
               series=period_block(pseries, paired, rf, sharpe=sharpe) if paired else empty,
               vs_core_power=power_caveat(h, sharpe) if h['n'] else dict(n=0, text='core not in window'))
    rest = {k: v for k, v in pseries.items() if k != 'core'}
    ex = common(list(rest))
    if not paired and ex and len(rest) > 1:
        out['series_ex_core'] = dict(months=len(ex), window=f'{ex[0]} to {ex[-1]}',
                                     series=period_block(rest, ex, rf, sharpe=sharpe))
    return out


def period_block(series, months, rf, *, sharpe):
    """Per-series figures over a regime/window month set; nothing outside a series' saved months."""
    out = {}
    for key, s in series.items():
        cov = coverage(s, months)
        sub = s[s.index.isin(months)]
        entry = dict(coverage=cov)
        if cov['k']:
            entry['cumulative_return'] = _r((1 + sub).prod() - 1)
            entry['ann_vol'] = _r(sub.std(ddof=1) * math.sqrt(12)) if cov['k'] > 1 else None
            if sharpe:
                ex = sub - rf_series(rf, sub.index)
                entry['sharpe_exbil'] = (_r(ex.mean() * 12 / (ex.std(ddof=1) * math.sqrt(12)))
                                         if cov['k'] >= MIN_SHARPE_MONTHS else None)
        out[key] = entry
    return out


# ---------- weights, turnover, timing ----------

def weights_long(root, spec, cache):
    df = _filter(_read(root, spec['file'], cache), spec.get('filters'))
    if spec['kind'] == 'long':
        tick = spec.get('ticker', 'ticker')
        w = df.pivot_table(index='date', columns=tick, values='weight', aggfunc='sum').fillna(0.0)
    else:
        cols = [c for c in df.columns if c.startswith('w_')]
        # Wide files: `date` is the decision date and `eval_date` the month earning the return; index by the
        # return month so weights line up with returns (and with the long files, whose `date` is the return month).
        w = df.set_index('eval_date' if 'eval_date' in df.columns else 'date')[cols].astype(float).fillna(0.0)
        w.columns = [c[2:] for c in cols]
    w.index = pd.to_datetime(w.index).to_period('M')
    w = w.groupby(level=0).last().sort_index()
    return w


def weights_block(root, subject, months, cache, top=8):
    spec = subject['weights']
    if spec['kind'] == 'static':
        w = pd.DataFrame([spec['weights']] * len(months), index=months)
        basis = 'fixed target weights, rebalanced monthly (drift between rebalances not shown)'
    else:
        w = weights_long(root, spec, cache)
        basis = f"saved weights ({spec['file']})"
    avg = w.mean().sort_values(ascending=False)
    keep = [c for c in avg.index[:top] if avg[c] > 0]
    other = w.drop(columns=keep).sum(axis=1)
    series = {c: [_r(v, 6) for v in w[c]] for c in keep}
    if (other.abs() > 1e-12).any():
        series['Other'] = [_r(v, 6) for v in other]
    eff_n = 1.0 / (w.pow(2).sum(axis=1))
    return dict(source=spec.get('file', 'data/processed/live/cio_registry.yaml'), basis=basis,
                months=[str(m) for m in w.index], top=series,
                effective_n=[_r(v, 4) for v in eff_n], largest_weight=[_r(v, 6) for v in w.max(axis=1)],
                n_rebalances=len(w))


def timing_audit(root, spec, cache):
    df = _filter(_read(root, spec['file'], cache), spec.get('filters'))
    if spec.get('static'):
        return dict(status='not applicable', basis='fixed weights: no estimated inputs, so nothing can leak', n=0,
                    source=spec['file'])
    if 'decision_date' not in df.columns or df['decision_date'].isna().all():
        return dict(status='not saved', basis='no decision date saved', n=0, source=spec['file'])
    d = pd.to_datetime(df['decision_date']).dt.to_period('M')
    r = pd.to_datetime(df['date']).dt.to_period('M')
    ok = (r > d)
    basis = 'decision month before return month'
    if 'feature_end' in df.columns:
        fe = pd.to_datetime(df['feature_end'])
        ok &= fe <= pd.to_datetime(df['decision_date']) + pd.offsets.MonthEnd(0)
        basis = 'feature cut-off on or before the decision month-end, and decision month before return month'
        full = True
    else:
        full = False
    return dict(status='pass' if bool(ok.all()) else 'fail', n=int(len(df)), n_fail=int((~ok).sum()), basis=basis,
                scope='full' if full else 'partial: feature cut-off not saved', source=spec['file'])


# ---------- per subject ----------

def _curve(s):
    return [_r(v, 8) for v in (1 + s).cumprod()]


def _dd(s):
    c = (1 + s).cumprod()
    return [_r(v, 8) for v in c / c.cummax().clip(lower=1.0) - 1]


def rolling_sharpe(s, rf):
    ex = s - rf_series(rf, s.index)
    m = ex.rolling(ROLL).mean() * 12
    sd = ex.rolling(ROLL).std(ddof=1) * math.sqrt(12)
    return m / sd


def _on(s, months):
    return [_r(s.get(m), 8) if m in s.index else None for m in months]


def calendar_years(a, b):
    pair = pd.concat([a, b], axis=1, join='inner').dropna()
    rows = []
    for y, g in pair.groupby(pair.index.year):
        rows.append(dict(year=int(y), months=len(g), subject=_r((1 + g.iloc[:, 0]).prod() - 1),
                         core=_r((1 + g.iloc[:, 1]).prod() - 1), partial=len(g) < 12))
    return rows


def card_for(archive, cid):
    return next((c for c in archive['cards'] if c['id'] == cid), None) if cid else None


# Which recompute row is each subject's headline DSR (Quant + CIO ruling, 2026-10-04).
# 'chosen' = the subject's chosen trial id; prefixes pick the sleeve / name-level vintage the card cites.
DSR_MATCH = {
    'vcfc': 'chosen', 'rr_erc': 'chosen', 'regime_dual': 'sleeve:{chosen}',
    'spectral_rp': 'name:spectral_risk_parity__0',
    'backbone': 'SM_option_a_vt_L63_SL21_g0p5_realizedamaya_cvar5',   # card: "1.00 (#6 overlay; trial_count=72)"
}
# The #6 gate-first spec has N = 1 (no DSR defined); its grid row is shown for reference.
DSR_GRID_REFERENCE = {'book2': 'SM_option_a_vt_L63_SL21_g0p5_realizedamaya_cvar5',
                      'skew_overlay': 'SM_option_a_vt_L63_SL21_g0p5_realizedamaya_cvar5'}
UNIT_NOTE = 'Recorded value used an annual Sharpe in a monthly formula; corrected value shown.'
BASIS_NOTE = 'Recorded on an rf = 0 basis; corrected to the Sharpe ex-BIL basis.'
NO_VERDICT_CHANGE = 'No verdict changes: every method affected had already failed other gates.'


def _recompute_entry(row):
    note = UNIT_NOTE if str(row.get('recorded_unit_note') or '').strip() not in ('', 'nan') else BASIS_NOTE
    return dict(trial=row['trial'], dsr_exbil=_r(float(row['dsr_exbil']), 4), dsr_rf0_recorded=_r(float(row['dsr_rf0_recorded']), 4),
                sharpe_exbil=_r(float(row['sharpe_exbil']), 4), sharpe_rf0_recorded=_r(float(row['sharpe_rf0_recorded']), 4),
                n_trials=int(row['N_used']), months=int(row['T']), window=f"{row['window_start'][:7]} to {row['window_end'][:7]}",
                error_note=note, recorded_unit_note=str(row.get('recorded_unit_note') or '') or None, source=DSR_RECOMPUTE)


def dsr_block(subject, card, summary, recompute, chosen=None):
    if subject['group'] == 'void':
        return None
    recorded = card.get('dsr') if card else None
    if recorded is None and summary is not None and 'DSR' in summary:
        v = float(summary['DSR'])
        recorded = (f"{v:.2f}" if np.isfinite(v) else 'not defined') + f" (trial_count={int(summary['trial_count'])})"
    basis = subject.get('dsr_basis', LEGACY)
    if subject['id'] == 'backbone':
        basis = 'recorded on the archive card for the #6 overlay, rf = 0 basis'
    out = dict(recorded=recorded, recorded_basis=basis, primary=None, primary_basis=None, corrected=None,
               grid_reference=None, note=None)
    key = DSR_MATCH.get(subject['id'])
    if key:
        key = (chosen or '') if key == 'chosen' else key.format(chosen=chosen or '')
        row = recompute.get(key)
        if row is None:
            raise ValueError(f"{subject['id']}: no DSR recompute row for {key!r}")
        out.update(corrected=_recompute_entry(row), primary=_r(float(row['dsr_exbil']), 4),
                   primary_basis='Sharpe ex-BIL basis (corrected; Quant recompute)', note=NO_VERDICT_CHANGE)
    elif subject['id'] in DSR_GRID_REFERENCE and DSR_GRID_REFERENCE[subject['id']] in recompute:
        g = _recompute_entry(recompute[DSR_GRID_REFERENCE[subject['id']]])
        out.update(grid_reference=g, recorded='not defined (N = 1)', recorded_basis=None,
                   note=('Eligibility never rested on DSR: the gate-first spec has N = 1, so no DSR is defined and only '
                         f"PSR applies. The #6 grid row for this spec (N = {g['n_trials']}) is shown for reference: "
                         f"{g['dsr_exbil']:.2f} corrected (Sharpe ex-BIL), {g['dsr_rf0_recorded']:.2f} as recorded."))
    elif 'ex-BIL' in basis:
        m = re.match(r'\s*(\d+(?:\.\d+)?)', recorded or '')
        out.update(primary=float(m.group(1)) if m else None, primary_basis=basis,
                   note='Already recorded on the Sharpe ex-BIL basis; not part of the recompute.')
    return out


def gates_block(subject, card, timing, vs_primary, verdict, gate_result, dsr=None):
    partial = timing['status'] == 'pass' and str(timing.get('scope') or '').startswith('partial')
    rows = [dict(gate='Leakage / timing', value=f"{timing['n'] - timing.get('n_fail', 0)} of {timing['n']} rows pass"
                 if timing['n'] else timing['status'], outcome='partial pass' if partial else timing['status'], basis=timing['basis'], scope=timing.get('scope'),
                 source=timing.get('source'))]
    if card:
        rows.append(dict(gate='Null comparison (recorded)', value=card.get('nw_t'), outcome=card.get('badge'),
                         source=ARCHIVE + f"#{card['id']}"))
    if vs_primary and vs_primary.get('n') and subject['group'] != 'void':
        st = vs_primary.get('sharpe_test') or {}
        rows.append(dict(gate='Null comparison (hub recompute, Sharpe ex-BIL)', null=vs_primary['label'],
                         value=dict(diff=vs_primary['diff'].get('sharpe_exbil'), z=st.get('z'), p_one_sided=st.get('p_one_sided'),
                                    p_two_sided=st.get('p_two_sided'), significant_5pct_two_sided=st.get('significant_5pct_two_sided')),
                         power=vs_primary['power']['text'], source='hub_data.head_to_head'))
    if subject['group'] != 'void':
        corr = (dsr or {}).get('corrected')
        grid = (dsr or {}).get('grid_reference')
        if grid and not corr:
            rows.append(dict(gate='DSR / C4', value='not defined (N = 1; PSR only)', basis='gate-first spec, N = 1',
                             as_recorded=None, error_note=None, rule=None,
                             grid_reference=dict(trial=grid['trial'], n_trials=grid['n_trials'], dsr_exbil=grid['dsr_exbil'],
                                                 as_recorded=grid['dsr_rf0_recorded'], error_note=grid['error_note']),
                             note=dsr['note']))
            corr = False
    if subject['group'] != 'void' and corr is not False:
        rows.append(dict(gate='DSR / C4', value=corr['dsr_exbil'] if corr else (card or {}).get('dsr'),
                         basis=(dsr or {}).get('primary_basis') if corr else subject.get('dsr_basis', LEGACY),
                         as_recorded=(card or {}).get('dsr') if corr else None, error_note=corr['error_note'] if corr else None,
                         rule='DSR ≥ 0.95 (C4, pre-registered)' if subject.get('prereg') else None))
    emp = dict(gate='Empirical gate (recorded criteria and tripwires)', outcome=(card or {}).get('badge') or subject.get('label'),
               value=prose((verdict or {}).get('verdict_label') or (card or {}).get('verdict')))
    if gate_result:
        emp.update(mechanical=gate_result.get('mechanical'), composition=(gate_result.get('composition') or {}).get('status'),
                   tripwires=((gate_result.get('fields') or {}).get('tripwires') or {}).get('status'))
    rows.append(emp)
    return rows


def compute_subject(root, subject, ctx):
    cache, rf, core = ctx['cache'], ctx['rf'], ctx['core']
    void = subject['group'] == 'void'
    sharpe = not void
    spec = subject['series']
    s, dropped = monthly_series(root, spec['file'], spec['col'], spec.get('filters'), cache)
    card = card_for(ctx['archive'], subject.get('card'))
    label = card['badge'] if card else subject['label']
    nulls = {}
    for n in subject['nulls']:
        if 'col' in n:
            ns, _ = monthly_series(root, spec['file'], n['col'], spec.get('filters'), cache)
        else:
            ns, _ = monthly_series(root, spec['file'], spec['col'], n['filters'], cache)
        nulls[n['key']] = (n, ns)
    s1 = core['s1']
    vs_core = dict(
        own_window=head_to_head(s, s1, rf, sharpe=sharpe),
        common_window=head_to_head(window(s, *COMMON_WINDOW), window(s1, *COMMON_WINDOW), rf, sharpe=sharpe),
        standin_sensitivity=head_to_head(s, core['standin'], rf, sharpe=sharpe),
    )
    vs_core['own_window']['coverage'] = coverage(s1, list(s.index))
    vs_core['standin_sensitivity']['label'] = ('Sensitivity only: stand-in core 70% IVV / 20% QQQ / 10% IJR, monthly '
                                               'rebalanced, gross, from the saved panel. It never replaces the static core.')
    vs_nulls = []
    for key, (n, ns) in nulls.items():
        h = head_to_head(s, ns, rf, sharpe=sharpe)
        h.update(key=key, label=n['label'], primary=bool(n.get('primary')))
        vs_nulls.append(h)
    primary = next((h for h in vs_nulls if h['primary']), None)
    sens = []
    for sp in subject.get('sensitivities', []):
        ss, sd = monthly_series(root, sp['file'], sp['col'], sp.get('filters'), cache)
        sens.append(dict(key=sp['key'], label=sp['label'], source=sp['file'], own=stats(ss, rf, sharpe=sharpe),
                         vs_core=head_to_head(ss, s1, rf, sharpe=sharpe), partial_months_dropped=sd))
    months = list(s.index)
    mstr = [str(m) for m in months]
    core_on = s1.reindex(months)
    series_out = dict(subject=_on(s, months), core=_on(s1, months), standin_core=_on(core['standin'], months),
                      **{k: _on(ns, months) for k, (_, ns) in nulls.items()})
    curves = dict(growth=dict(subject=_curve(s)),
                  growth_vs_core=None, drawdown=dict(subject=_dd(s)))
    pair_core = pd.concat([s, s1], axis=1, join='inner').dropna()
    if len(pair_core):
        pc_months = [str(m) for m in pair_core.index]
        ex = pair_core.iloc[:, 0] - pair_core.iloc[:, 1]
        curves['growth_vs_core'] = dict(months=pc_months, subject=_curve(pair_core.iloc[:, 0]), core=_curve(pair_core.iloc[:, 1]),
                                        cumulative_excess=[_r(v, 8) for v in (1 + pair_core.iloc[:, 0]).cumprod() - (1 + pair_core.iloc[:, 1]).cumprod()],
                                        rolling_12m_excess=[_r(v, 8) for v in
                                                            ((1 + pair_core.iloc[:, 0]).rolling(12).apply(np.prod, raw=True)
                                                             - (1 + pair_core.iloc[:, 1]).rolling(12).apply(np.prod, raw=True))],
                                        drawdown_core=_dd(pair_core.iloc[:, 1]), drawdown_subject=_dd(pair_core.iloc[:, 0]))
    pair_cw = pd.concat([window(s, *COMMON_WINDOW), window(s1, *COMMON_WINDOW)], axis=1, join='inner').dropna()
    curves['common_window_excess'] = dict(
        months=[str(m) for m in pair_cw.index],
        cumulative_excess=[_r(v, 8) for v in (1 + pair_cw.iloc[:, 0]).cumprod() - (1 + pair_cw.iloc[:, 1]).cumprod()],
        note='Growth of $1 in the subject minus the static core, both rebased at the start of the common window',
    ) if len(pair_cw) else None
    for k, (_, ns) in nulls.items():
        al = ns.reindex(months)
        curves['growth'][k] = _curve(al.dropna()) if al.notna().all() else None
        curves['drawdown'][k] = _dd(al.dropna()) if al.notna().all() else None
    rolling = None
    if sharpe and len(s) >= ROLL:
        rolling = dict(window_months=ROLL, subject=_on(rolling_sharpe(s, rf), months),
                       **{k: _on(rolling_sharpe(ns, rf), months) for k, (_, ns) in nulls.items()})
        if len(pair_core) >= ROLL:
            rs, rc = rolling_sharpe(pair_core.iloc[:, 0], rf), rolling_sharpe(pair_core.iloc[:, 1], rf)
            rolling['core'] = _on(rc, months)
            g = vs_core['own_window'].get('sharpe_test', {}).get('se_hac_annual')
            band = _r(Z_POWER * g * math.sqrt(len(pair_core) / ROLL)) if g else None
            rolling['diff_vs_core'] = dict(months=[str(m) for m in pair_core.index], values=[_r(v, 8) for v in rs - rc],
                                           detectable_gap_36m=band,
                                           band_note='± detectable Sharpe gap scaled to a 36-month window from the full paired HAC SE')
    turnover = None
    if spec.get('turnover'):
        tv, _ = monthly_series(root, spec['file'], spec['turnover'], spec.get('filters'), cache)
        tv = tv.reindex(months)
        turnover = dict(months=mstr, per_rebalance=[_r(v, 8) for v in tv],
                        per_year=_r(tv.mean() * 12) if tv.notna().any() else None,
                        basis='one-way turnover per monthly rebalance, as saved; per year = mean × 12',
                        nulls_note='Nulls saved as returns only' if any('col' in n for n in subject['nulls']) else None)
    weights = weights_block(root, subject, months, cache)
    regimes = ctx['regimes']
    regime_rows = []
    pseries = {'subject': s, 'core': s1}
    if primary:
        pseries['primary_null'] = nulls[primary['key']][1]
    for col in ('drawdown_state', 'vol_state'):
        for val in [v for v in regimes[col].dropna().unique()]:
            rm = list(regimes.index[regimes[col] == val])
            regime_rows.append(dict(kind=col, regime=str(val), months_total=len(rm),
                                    **paired_blocks(pseries, s, s1, rm, rf, sharpe)))
    stress_rows = []
    for w in ctx['stress']:
        wm = list(pd.period_range(w['start'], w['end'], freq='M'))
        stress_rows.append(dict(window=w['id'], name=w['name'], start=w['start'], end=w['end'], months_total=len(wm),
                                **paired_blocks(pseries, s, s1, wm, rf, sharpe),
                                path=dict(months=[str(m) for m in wm], subject=_on(s, wm), core=_on(s1, wm))))
    trials = None
    if subject.get('trials') and not void:   # VOID: no Sharpe rows (D4)
        t = subject['trials']
        df = _read(root, t['file'], cache)
        trials = dict(source=t['file'], basis=t['basis'], chosen=t['chosen'],
                      rows=[dict(trial_id=str(r[t['id']]), sharpe=_r(r[t['sharpe']]) if pd.notna(r[t['sharpe']]) else None)
                            for _, r in df.iterrows()])
    summary = None
    if subject.get('summary'):
        summary = _read(root, subject['summary']['file'], cache).iloc[0].to_dict()
    verdict = json.loads((Path(root) / subject['verdict']).read_text()) if subject.get('verdict') else None
    gate_result = None
    gr_path = Path(root) / Path(spec['file']).parent / 'gate_result.json'
    if gr_path.exists():
        gate_result = json.loads(gr_path.read_text())
    timing = timing_audit(root, subject['timing'], cache)
    dsr = dsr_block(subject, card, summary, ctx['recompute'], (trials or {}).get('chosen'))
    out = dict(
        id=subject['id'], name=subject['name'], group=subject['group'], label=label, card=subject.get('card'),
        related=subject.get('related'), pages=subject.get('pages', {}),
        verdict=dict(label=(verdict or {}).get('verdict_label') or label,
                     text=prose((verdict or {}).get('verdict_line') or (card or {}).get('verdict')),
                     detail=prose((card or {}).get('detail')),
                     void_reason=(card or {}).get('void_reason') if void else None,
                     banner='Reported for transparency; the test design was void.' if void else None),
        sources=dict(series=spec['file'], filters=spec.get('filters'), column=spec['col'],
                     weights=subject['weights'].get('file'), trials=(subject.get('trials') or {}).get('file'),
                     prereg=subject.get('prereg'), verdict=subject.get('verdict'), archive_card=ARCHIVE if card else None,
                     core='data/processed/live/strategy_returns.csv (static_option_a, S1)',
                     regimes=PANEL + ' (SPY)', rf='BIL from the saved panel; FRED TB3MS/1200 before BIL\'s first full month'),
        own=stats(s, rf, sharpe=sharpe), partial_months_dropped=dropped,
        vs_core=vs_core, vs_nulls=vs_nulls, sensitivities=sens,
        months=mstr, series=series_out, curves=curves, rolling_sharpe=rolling, calendar_years=calendar_years(s, s1),
        scatter_vs_core=dict(months=[str(m) for m in pair_core.index], subject=[_r(v, 8) for v in pair_core.iloc[:, 0]],
                             core=[_r(v, 8) for v in pair_core.iloc[:, 1]],
                             correlation=_r(pair_core.corr().iloc[0, 1]) if len(pair_core) > 2 else None,
                             beta=_r(np.cov(pair_core.iloc[:, 0], pair_core.iloc[:, 1], ddof=1)[0, 1] / pair_core.iloc[:, 1].var(ddof=1))
                             if len(pair_core) > 2 else None),
        turnover=turnover, weights=weights, regimes=regime_rows, stress=stress_rows, trials=trials,
        dsr=dsr,
        gates=gates_block(subject, card, timing, primary, verdict, gate_result, dsr),
        timing_audit=timing,
    )
    if void:
        out['suppressed'] = 'VOID: no Sharpe and no DSR rows (CIO ruling D4)'
    if subject['id'] == 'backbone':
        out['headline'] = backbone_headline(root, card)
    if subject['id'] in ('book2', 'skew_overlay'):
        out['vintage_note'] = ('Book 2 is the live refresh of the #6 spec. Its monthly returns equal the frozen research '
                               'record month for month through 2026-08; the record ends with a partial 2026-09 (as of '
                               '2026-09-16), which the hub drops. The nulls differ: the record\'s backbone used cash 0.')
    if subject['id'] == 'book1':
        out['benchmark_note'] = ('Book 1 is the static core: its difference against the core is zero by definition. '
                                 'It was not gated: no pre-registered null, trial count or DSR.')
        out['reference'] = []
    return out


def backbone_headline(root, card):
    site = json.loads((Path(root) / SITE_SHARPE).read_text())['books']
    live, frozen = site['uncond_vt_audit_null'], site['uncond_vt_committed_cash0']
    rec = next((r for r in (card or {}).get('rows', []) if r.get('role') == 'null'), {})
    return dict(
        headline=dict(sharpe_exbil=live['exbil'], n_months=live['n_months'], window=live['window'],
                      label='Live vol-target backbone, current BIL', source=SITE_SHARPE + ' books.uncond_vt_audit_null'),
        frozen_snapshot=dict(sharpe_exbil=frozen['exbil'], n_months=frozen['n_months'], window=frozen['window'],
                             label='Frozen snapshot (research run, cash 0)', source=SITE_SHARPE + ' books.uncond_vt_committed_cash0'),
        recorded=dict(value=rec.get('sharpe'), label='As recorded on the archive card (archive BIL as of 2026-09-16)',
                      window=(card or {}).get('detail'), source=ARCHIVE + '#uncond_book2_vt'))


def leaderboard(subjects):
    rows, void = [], []
    for s in subjects:
        cw = s['vs_core']['common_window']
        row = dict(id=s['id'], name=s['name'], group=s['group'], label=s['label'], page=f"methods/results/{s['id']}.html",
                   n=cw.get('n'), start=cw.get('start'), end=cw.get('end'))
        if cw.get('n'):
            row.update(total_return=cw['a']['total_return'], cagr=cw['a']['cagr'], maxdd=cw['a']['maxdd'],
                       cagr_diff=cw['diff']['cagr'], total_return_diff=cw['diff']['total_return'], maxdd_diff=cw['diff']['maxdd'],
                       power=cw['power'], own_window=dict(n=s['vs_core']['own_window'].get('n'), months=len(s['months']),
                                                         cagr_diff=(s['vs_core']['own_window'].get('diff') or {}).get('cagr')),
                       excess_spark=(s['curves']['common_window_excess'] or {}).get('cumulative_excess'),
                       excess_spark_months=(s['curves']['common_window_excess'] or {}).get('months'))
            if s['group'] != 'void':
                row.update(sharpe_exbil=cw['a'].get('sharpe_exbil'), sharpe_diff=cw['diff'].get('sharpe_exbil'))
        (void if s['group'] == 'void' else rows).append(row)
    rows.sort(key=lambda r: (-(r['cagr_diff'] if r.get('cagr_diff') is not None else -1e9), r['id']))
    rank = 0
    for r in rows:
        r['is_benchmark'] = r['id'] == 'book1'   # the zero line (D13): shown in place, not ranked
        if not r['is_benchmark']:
            rank += 1
        r['rank'] = None if r['is_benchmark'] else rank
    return dict(
        common_window=dict(start=COMMON_WINDOW[0], end=COMMON_WINDOW[1],
                           months=len(pd.period_range(COMMON_WINDOW[0], COMMON_WINDOW[1], freq='M')),
                           label=f'Common window: {COMMON_WINDOW[0]} to {COMMON_WINDOW[1]} '
                                 f"({len(pd.period_range(COMMON_WINDOW[0], COMMON_WINDOW[1], freq='M'))} months), "
                                 'the months every subject and the static core share'),
        benchmark='Static core (Book 1): 70% VOO / 20% QQQM / 10% IJR, monthly rebalanced, gross '
                  '(data/processed/live/strategy_returns.csv, static_option_a)',
        ranked_by='CAGR difference vs the static core over the common window',
        sortable=['cagr_diff', 'sharpe_diff', 'maxdd_diff'],
        rows=rows, void=void, void_note='VOID runs are not ranked (CIO ruling D4).')


def load_recompute(root):
    """Quant's ex-BIL DSR recompute (118 rows), keyed by trial id. Copied verbatim; see dsr_exbil_recompute.PROVENANCE.md."""
    p = Path(root) / DSR_RECOMPUTE
    if not p.exists():
        return {}
    with p.open(newline='', encoding='utf-8') as f:
        return {r['trial']: r for r in csv.DictReader(f)}


def build(root=ROOT):
    root = Path(root)
    cache = {}
    regimes, vol_median = market_regimes(root)
    ctx = dict(cache=cache, rf=risk_free(root), core=static_core(root, cache), regimes=regimes,
               archive=json.loads((root / ARCHIVE).read_text()), recompute=load_recompute(root))
    ctx['stress'] = stress_windows(regimes)
    subjects = [compute_subject(root, s, ctx) for s in SUBJECTS]
    core = ctx['core']
    core_df = pd.DataFrame(dict(static_core_s1=core['s1'], static_core_panel_derived=core['panel_derived'],
                                standin_core=core['standin']))
    core_df.index.name = 'month'
    labels = {s['id']: s['label'] for s in subjects}
    manifest = dict(
        note='Results hub data. Saved artifacts only; nothing re-run. Generated by scripts/build_hub_data.py.',
        static_core=dict(definition='Book 1, static_option_a: 70% VOO / 20% QQQM / 10% IJR, monthly rebalanced, gross',
                         defined_in=['data/processed/live/cio_registry.yaml', 'src/usa_etf_features/strategy_registry.py'],
                         series='data/processed/live/strategy_returns.csv (static_option_a)', first_month=CORE_START,
                         partial_months_dropped=core['s1_dropped'], corrections=core['corrections'],
                         version_label='live core (VOO / QQQM / IJR)',
                         standin='70% IVV / 20% QQQ / 10% IJR from ' + PANEL + ', sensitivity only',
                         standin_version_label='stand-in core (IVV / QQQ / IJR)'),
        common_window=list(COMMON_WINDOW), rf='BIL from the saved panel; FRED TB3MS/1200 before BIL\'s first full month',
        power=dict(alpha=ALPHA, power=POWER, z=Z_POWER), rolling_window_months=ROLL, min_sharpe_months=MIN_SHARPE_MONTHS,
        regimes=dict(source=PANEL + ' (SPY)', drawdown_states='Up: drawdown > −5%; Correction: −5% to −20%; Bear: ≤ −20%',
                     vol_states='SPY trailing 12-month realized vol above / below its median', vol_median=_r(vol_median)),
        stress_windows=ctx['stress'],
        dsr_recompute_slot=DSR_RECOMPUTE,
        trial_counts=json.loads((Path(root) / TRIAL_COUNTS).read_text(encoding='utf-8')),
        trial_counts_source=TRIAL_COUNTS,
        cost_basis='The static core is gross (no costs); method series are net of the costs saved with each run.',
        turnover_convention=TURNOVER_CONVENTION,
        subjects=[dict(id=s['id'], name=s['name'], group=s['group'], label=labels[s['id']], card=s.get('card'),
                       series=s['series'], nulls=s['nulls'], weights={k: v for k, v in s['weights'].items() if k != 'weights'},
                       trials=s.get('trials'), prereg=s.get('prereg'), verdict=s.get('verdict'),
                       sensitivities=s.get('sensitivities', []), pages=s.get('pages', {})) for s in SUBJECTS],
    )
    for subj in subjects:
        adm = ADMISSION.get(subj['id'])
        if adm:
            subj['admission'] = dict(json.loads((Path(root) / adm).read_text(encoding='utf-8')), source=adm)
    reg_df = regimes.copy()
    reg_df.index.name = 'month'
    return dict(manifest=manifest, leaderboard=leaderboard(subjects), subjects={s['id']: s for s in subjects},
                static_core=core_df, regimes=reg_df)
