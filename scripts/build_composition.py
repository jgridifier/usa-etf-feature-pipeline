#!/usr/bin/env python3
"""Composition over time: month-by-month saved target weights for the Books, EPO and archived methods.

Every weight is read from a committed weights / run-output file (never typed, never reconstructed).
Charts plot the saved TARGET weights at each rebalance, on the holding month they earn. Bands:
  1. Cash-like: any ticker tagged cash_like, short_duration or near_cash (the composition tripwire's
     own tags, gate_metrics.COMPOSITION_TAG_COLUMNS via gate_metrics.tagged_tickers);
  2. otherwise the stored epo_asset_class (equity / bond / commodity);
  3. otherwise "Untagged". Category is never used to assign a band.
Output: docs/data/composition_over_time.json and docs/methods/composition_over_time.html.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

from usa_etf_features import gate_metrics as gm

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / 'data' / 'processed'
UNIVERSE = ROOT / 'data' / 'raw' / 'usa_universe_categorized.csv'
ARCHIVE_JSON = ROOT / 'apps' / 'pages' / 'src' / 'data' / 'archive_verdicts.json'
PAGE = 'methods/composition_over_time.html'
DATA = 'data/composition_over_time.json'

BANDS = ['Cash-like', 'Bond', 'Commodity', 'Equity', 'Untagged']   # stacked bottom -> top
BAND_COLORS = {'Cash-like': '#cfd8e3', 'Bond': '#7f9cc0', 'Commodity': '#4a5a6e', 'Equity': '#1f3a5f',
               'Untagged': '#a3a3a3'}
TICKER_COLORS = ['#0b1f3a', '#2f5687', '#5d8bc4', '#b3c8e6', '#3f6fa8', '#86a9d6', '#1f3a5f', '#2b2b2b',
                 '#555555', '#7a7a7a', '#a0a0a0', '#c4ccd6']
FIXED_COLORS = {'BIL': '#ffffff', 'XSD': '#000000', 'Other': '#e6e9ee'}
ALWAYS_OWN_LINE = ('XSD',)          # CIO: never folded into Other
TOP_N = 10
CASH_LIMIT = gm.COMPOSITION_MAX_SHARE
SUM_TOL = 1e-6
TARGET_LABEL = 'target weights at rebalance, source: {}'
LIVE = P / 'live'
# The published outputs the Books page reads (scripts/build_pages.py LIVE_SOURCES), per Books chart.
BOOKS_PAGE_SOURCES = {
    'book1': 'data/processed/live/vol_target_oos_returns.csv',
    'book2': 'data/processed/live/skew_managed_gatefirst_returns.csv',
    'backbone': 'data/processed/live/vol_target_oos_returns.csv',
}
BOOK1_REBUILD_NOTE = 'EPO-gate rebuild of the 70/20/10 mix, from Nov 2020'


def live_book1_weights() -> str | None:
    """A per-month Book 1 (static Option A) weights file in the published live outputs, if one exists."""
    for f in sorted(LIVE.glob('*weights*.csv')):
        cols = pd.read_csv(f, nrows=0).columns
        ids = pd.read_csv(f, usecols=[c for c in ('strategy_id', 'trial_id') if c in cols]) if \
            {'strategy_id', 'trial_id'} & set(cols) else pd.DataFrame()
        if any(ids[c].astype(str).str.fullmatch(r'(book1_)?static_option_a').any() for c in ids.columns):
            return f.name
    return None


# ------------------------------------------------------------------ bands
def band_map(universe: pd.DataFrame) -> dict:
    """ticker -> band. Order: tripwire tags first, then epo_asset_class, else Untagged."""
    cash = frozenset().union(*(gm.tagged_tickers(universe, c) for c in gm.COMPOSITION_TAG_COLUMNS))
    cls = gm.epo_asset_class(universe)
    out = {}
    for t in universe['Ticker'].astype(str).str.strip().str.upper():
        if t in cash:
            out[t] = 'Cash-like'
        elif isinstance(cls.get(t), str) and cls.get(t).strip():
            out[t] = cls.get(t).strip().capitalize()
        else:
            out[t] = 'Untagged'
    return out


def band_of(ticker: str, bands: dict) -> str:
    return bands.get(str(ticker).strip().upper(), 'Untagged')   # sleeves / unknown keys: never inferred


# ------------------------------------------------------------------ loaders (long: month, ticker, weight)
def _month(s):
    return pd.to_datetime(s).dt.to_period('M').astype(str)


def long_weights(rel, *, filters, ticker='ticker', month='date', weight='weight'):
    d = pd.read_csv(P / rel, low_memory=False)
    for k, v in filters.items():
        d = d.loc[d[k].astype(str).eq(str(v))]
    if d.empty:
        raise ValueError(f'no rows in {rel} for {filters}')
    return pd.DataFrame({'month': _month(d[month]), 'ticker': d[ticker].astype(str),
                         'weight': d[weight].astype(float).fillna(0.0)})


def wide_weights(rel, *, filters, month='eval_date'):
    d = pd.read_csv(P / rel, low_memory=False)
    for k, v in filters.items():
        d = d.loc[d[k].astype(str).eq(str(v))]
    if d.empty:
        raise ValueError(f'no rows in {rel} for {filters}')
    cols = [c for c in d.columns if c.startswith('w_')]
    x = d[[month] + cols].melt(id_vars=month, var_name='ticker', value_name='weight')
    return pd.DataFrame({'month': _month(x[month]), 'ticker': x['ticker'].str[2:],
                         'weight': x['weight'].astype(float).fillna(0.0)})


# ------------------------------------------------------------------ run-output metrics (never computed here)
def _row(rel, **match):
    d = pd.read_csv(P / rel, low_memory=False)
    for k, v in match.items():
        d = d.loc[d[k].astype(str).eq(str(v))]
    return d.iloc[0] if len(d) else None


def metric(rel, col, **match):
    r = _row(rel, **match)
    if r is None or col not in r.index or pd.isna(r[col]):
        return None
    return dict(value=float(r[col]), source=f'data/processed/{rel}:{col}')


# ------------------------------------------------------------------ verdicts
def archive_badges() -> dict:
    cards = json.loads(ARCHIVE_JSON.read_text(encoding='utf-8'))['cards']
    return {c['id']: c['badge'] for c in cards}


def gate_report_verdict(rel) -> str:
    v = json.loads((P / rel).read_text(encoding='utf-8'))['verdict']
    return v['verdict'] if isinstance(v, dict) else v


# ------------------------------------------------------------------ specs
def specs() -> list[dict]:
    badges = archive_badges()
    epo_verdict = json.loads((P / 'epo_allocator/verdict.json').read_text(encoding='utf-8'))['verdict']
    epo = 'epo_allocator/weights.csv'

    def epo_spec(sid, name, badge, *, optional=False, group='epo', default='class', cid=None):
        return dict(id=cid or f'epo_{sid}', group=group, name=name, badge=badge, optional=optional, default_view=default,
                    source=f'data/processed/{epo}', load=lambda sid=sid: long_weights(epo, filters={'strategy_id': sid}),
                    metrics=dict(equity=metric('epo_allocator/asset_class_mix.csv', 'equity', strategy_id=sid),
                                 eff_n=metric('epo_allocator/summary.csv', 'eff_N_mean', strategy_id=sid, period_role='full window'),
                                 turnover=metric('epo_allocator/summary.csv', 'turnover_per_year', strategy_id=sid, period_role='full window')))

    def book1_spec():
        # CIO: Books charts read the published live outputs the Books page uses. The live run publishes
        # Book 1 as returns only (vol_target_oos_returns.csv:r_option_a), with no per-month weights, so the
        # chart keeps the EPO-gate rebuild of the same fixed mix and says so.
        live = live_book1_weights()
        if live is not None:
            return dict(id='book1', group='books', name='Book 1 (static core: VOO / QQQM / IJR)', badge='LIVE BOOK',
                        default_view='ticker', optional=False, source=f'data/processed/live/{live}',
                        books_source=BOOKS_PAGE_SOURCES['book1'],
                        load=lambda: wide_weights(f'live/{live}', filters={}),
                        metrics=dict(equity=None, eff_n=None, turnover=None))
        s = epo_spec('book1_static_option_a', 'Book 1 (static core: VOO / QQQM / IJR)', 'LIVE BOOK', group='books',
                     default='ticker', cid='book1')
        s.update(source_note=BOOK1_REBUILD_NOTE, books_source=BOOKS_PAGE_SOURCES['book1'])
        return s

    def nls(version, rel_dir, badge, window, *, optional=False):
        rel = f'{rel_dir}/weights.csv'
        flt = {'strategy_id': 'nonlinear_shrinkage_gmv', 'window_weeks': window}
        summary = f'{rel_dir}/summary.csv'
        match = dict(strategy_id='nonlinear_shrinkage_gmv', window_weeks=window)
        if version == 'v3':
            match['period_role'] = pd.read_csv(P / summary).period_role.iloc[0]
        return dict(id=f'nls_gmv_{version}_{window}w', group='archive', optional=optional, default_view='class',
                    name=f'NLS GMV {version} ({window}w{", method" if not optional else ", sensitivity"})', badge=badge,
                    source=f'data/processed/{rel}', load=lambda: long_weights(rel, filters=flt),
                    metrics=dict(equity=None, eff_n=metric(summary, 'eff_N_mean', **match),
                                 turnover=metric(summary, 'turnover_per_year', **match)))

    v1 = gate_report_verdict('nonlinear_shrinkage_gmv/gate_report.json')
    v2 = gate_report_verdict('nonlinear_shrinkage_gmv_v2/gate_report.json')
    vcfc = 'VCFC_option_a_vt_L21_C12_g0p5_mkt_vol'
    out = [
        # Books: open on tickers, BIL its own band/line.
        book1_spec(),
        dict(id='book2', group='books', name='Book 2 (backbone × gate-first skew overlay)', badge='LIVE BOOK',
             default_view='ticker', optional=False, source='data/processed/live/skew_managed_gatefirst_weights.csv',
             load=lambda: wide_weights('live/skew_managed_gatefirst_weights.csv', filters={}), gate=True,
             books_source=BOOKS_PAGE_SOURCES['book2'],
             metrics=dict(equity=None, eff_n=None,
                          turnover=metric('live/skew_managed_gatefirst_summary.csv', 'turnover_per_year'))),
        dict(id='backbone', group='books', name='Backbone (unconditional vol-target)', badge=badges['uncond_book2_vt'],
             default_view='ticker', optional=False, source='data/processed/live/vol_target_monthly_weights.csv',
             load=lambda: wide_weights('live/vol_target_monthly_weights.csv', filters={}),
             books_source=BOOKS_PAGE_SOURCES['backbone'],
             metrics=dict(equity=None, eff_n=None,
                          turnover=metric('live/vol_target_oos_summary.csv', 'turnover_per_year'))),
        # EPO and its baselines: open on asset classes.
        epo_spec('epo_a_w075', 'Anchored EPO, w = 0.75 (method)', epo_verdict),
        epo_spec('anchor_ivol', '1/σ anchor (EPO at w = 1)', 'BASELINE'),
        epo_spec('lw_minvar_156w', 'Weekly LW MinVar (primary null)', 'BASELINE'),
        epo_spec('equal_weight', 'Equal weight', 'BASELINE'),
        epo_spec('trend_ivol', 'Trend names at inverse vol', 'BASELINE'),
        epo_spec('epo_a_w050', 'Anchored EPO, w = 0.50 (sensitivity)', epo_verdict, optional=True),
        epo_spec('epo_a_w090', 'Anchored EPO, w = 0.90 (sensitivity)', epo_verdict, optional=True),
        epo_spec('erc_lw', 'Equal risk contribution (LW)', 'BASELINE', optional=True),
        # Archived methods with saved weights.
        dict(id='spectral_rp', group='archive', name='Spectral Risk Parity (name mode)', badge=badges['spectral_rp'],
             default_view='class', optional=False, source='data/processed/spectral_rp/name/weights.csv',
             load=lambda: long_weights('spectral_rp/name/weights.csv', filters={'strategy_id': 'spectral_risk_parity__0'}),
             metrics=dict(equity=None, eff_n=None,
                          turnover=metric('spectral_rp/name/summary.csv', 'turnover_per_year', strategy_id='spectral_risk_parity__0'))),
        dict(id='regime_dual', group='archive', name='Regime-Aware dual (vol_corr_spread ERC, name level)',
             badge=badges['regime_dual'], default_view='class', optional=False,
             source='data/processed/regime_dual/name_level/regime_dual_monthly_weights.csv',
             load=lambda: long_weights('regime_dual/name_level/regime_dual_monthly_weights.csv',
                                       filters={'trial_id': 'k2_vol_corr_spread_erc'}, ticker='asset'),
             metrics=dict(equity=None, eff_n=None,
                          turnover=metric('regime_dual/name_level/regime_dual_summary.csv', 'turnover_per_year',
                                          trial_id='k2_vol_corr_spread_erc'))),
        dict(id='vcfc', group='archive', name='#13 VCFC (headline trial L21 / C12 / g 0.5)', badge=badges['vcfc'],
             default_view='class', optional=False, source='data/processed/vol_cond_factor_corr/vol_cfc_monthly_weights.csv',
             load=lambda: wide_weights('vol_cond_factor_corr/vol_cfc_monthly_weights.csv', filters={'trial_id': vcfc}),
             metrics=dict(equity=None, eff_n=None,
                          turnover=metric('vol_cond_factor_corr/vol_cfc_oos_summary.csv', 'turnover_per_year', trial_id=vcfc))),
        dict(id='ft_med', group='archive', name='#4 FT-MED (category sleeves)', badge=badges['ft_med'],
             default_view='class', optional=False, source='data/processed/ft_med/ft_med_monthly_weights.csv', sleeves=True,
             load=lambda: wide_weights('ft_med/ft_med_monthly_weights.csv', filters={'trial_id': 'ft_med_ef21_fc60_sample_sleeves'}),
             metrics=dict(equity=None, eff_n=None,
                          turnover=metric('ft_med/ft_med_oos_summary.csv', 'turnover_per_year', trial_id='ft_med_ef21_fc60_sample_sleeves'))),
        dict(id='rr_erc_b', group='archive', name='#3 RR-ERC Path B (LOIM parity, category sleeves)', badge=badges['rr_erc'],
             default_view='class', optional=False, source='data/processed/rr_erc/rr_erc_monthly_weights.csv', sleeves=True,
             load=lambda: wide_weights('rr_erc/rr_erc_monthly_weights.csv', filters={'trial_id': 'rr_erc_pathB_loim_vols_histfreq_cat'}),
             metrics=dict(equity=None, eff_n=None,
                          turnover=metric('rr_erc/rr_erc_oos_summary.csv', 'turnover_per_year', trial_id='rr_erc_pathB_loim_vols_histfreq_cat'))),
        dict(id='rr_erc_a', group='archive', name='#3 RR-ERC Path A (stress overlay, category sleeves)', badge=badges['rr_erc'],
             default_view='class', optional=True, source='data/processed/rr_erc/rr_erc_monthly_weights.csv', sleeves=True,
             load=lambda: wide_weights('rr_erc/rr_erc_monthly_weights.csv', filters={'trial_id': 'rr_erc_pathA_stress_sw12_lam25_cat'}),
             metrics=dict(equity=None, eff_n=None,
                          turnover=metric('rr_erc/rr_erc_oos_summary.csv', 'turnover_per_year', trial_id='rr_erc_pathA_stress_sw12_lam25_cat'))),
        nls('v1', 'nonlinear_shrinkage_gmv', v1, 156),
        nls('v2', 'nonlinear_shrinkage_gmv_v2', v2, 156),
        nls('v3', 'nonlinear_shrinkage_gmv_v3', badges['nls_gmv_v3'], 156),
        nls('v1', 'nonlinear_shrinkage_gmv', v1, 260, optional=True),
        nls('v2', 'nonlinear_shrinkage_gmv_v2', v2, 260, optional=True),
        nls('v3', 'nonlinear_shrinkage_gmv_v3', badges['nls_gmv_v3'], 260, optional=True),
    ]
    # Composition read from the VOID runs' own output (why they were voided).
    for s in out:
        if s['id'] == 'nls_gmv_v2_156w':
            s['void_composition'] = metric('nonlinear_shrinkage_gmv_v2/summary.csv', 'short_duration_share_mean',
                                           strategy_id='nonlinear_shrinkage_gmv', window_weeks=156)
            s['void_composition_label'] = 'short-duration share'
            s['void_kind'] = 'v2'
        if s['id'] == 'nls_gmv_v1_156w':
            s['void_composition'] = metric('nonlinear_shrinkage_gmv/composition.csv', 'cash_like_category_weight',
                                           strategy_id='nonlinear_shrinkage_gmv', window_weeks=156)
            s['void_composition_label'] = 'cash-like category share'
            s['void_kind'] = 'v1'
    return out


def not_saved() -> list[dict]:
    """Recorded runs whose weights were never saved (never reconstructed here)."""
    reg = pd.read_csv(P / 'epo_allocator/trial_registry.csv')
    rows = reg.loc[reg.status.astype(str).str.startswith('invalid')]
    return [dict(id=r.trial_id, name=f'NLS GMV v1, {int(r.window_weeks)}w (invalidated legacy run)',
                 badge='INVALID', reason=f'{r.status}; {r.source}. Counted as a trial; no weights file exists.',
                 source='data/processed/epo_allocator/trial_registry.csv') for r in rows.itertuples()]


# ------------------------------------------------------------------ series
def tag_shares(pivot: pd.DataFrame, universe: pd.DataFrame) -> dict:
    """Average share of each tripwire tag (and their union) over the chart's months, from the weights."""
    sets = {c: gm.tagged_tickers(universe, c) for c in gm.COMPOSITION_TAG_COLUMNS}
    union = frozenset().union(*sets.values())
    out = {c: float(pivot[[t for t in pivot.columns if t in tk]].sum(axis=1).mean()) for c, tk in sets.items()}
    out['union'] = float(pivot[[t for t in pivot.columns if t in union]].sum(axis=1).mean())
    out['near_cash_tickers'] = sorted(sets[gm.NEAR_CASH_COLUMN])
    return out


def pct1(x: float) -> str:
    return f'{100 * x:.1f}%'


def void_lines(c: dict) -> list[str]:
    """Quant's wording for the GMV v1 / v2 VOID cards; every figure is read from the weights / run output."""
    t, rec = c['tag_shares'], c['void_composition']['value']
    if c['void_kind'] == 'v1':
        first = (f"{pct1(t['union'])} cash-like under today's tags ({pct1(t[gm.CASH_LIKE_COLUMN])} BIL-type cash). "
                 f"The {pct1(rec)} recorded at the time used the old Category labels.")
    else:
        first = (f"{pct1(t['union'])} under today's tags: {pct1(t[gm.SHORT_DURATION_COLUMN])} short-duration plus "
                 f"{pct1(t[gm.NEAR_CASH_COLUMN])} near-cash ({'/'.join(t['near_cash_tickers'])}). "
                 f"The {pct1(rec)} recorded at the time came before the near-cash tag existed.")
    if not (t['union'] > CASH_LIMIT and rec > CASH_LIMIT):
        raise ValueError(f"{c['id']}: 'above 50% either way' no longer holds")
    return [first, 'Above 50% either way; the VOID verdict is unchanged.']


def build_chart(spec: dict, bands: dict, gate_months: list[str] | None, universe: pd.DataFrame | None = None) -> dict:
    w = spec['load']()
    dup = w.duplicated(['month', 'ticker'])
    if dup.any():   # e.g. 156w and 260w GMV windows on the same dates: never stack two runs in one chart
        raise ValueError(f"{spec['id']}: {int(dup.sum())} duplicate (month, ticker) rows; filter the run "
                         f"(window_weeks / strategy / trial) before charting")
    months = sorted(w['month'].unique())
    pivot = w.pivot(index='month', columns='ticker', values='weight').reindex(months).fillna(0.0)
    sums = pivot.sum(axis=1)
    cls = {b: [0.0] * len(months) for b in BANDS}
    by_band = pivot.T.groupby(pivot.columns.map(lambda t: band_of(t, bands))).sum().T
    for b in BANDS:
        if b in by_band:
            cls[b] = [float(x) for x in by_band[b]]
    avg = pivot.mean().sort_values(ascending=False)
    held = avg[avg > 0]
    own = [t for t in held.index[:TOP_N]]
    for t in ALWAYS_OWN_LINE + (('BIL',) if spec['group'] == 'books' else ()):
        if t in held.index and t not in own:
            own.append(t)
    rest = [t for t in pivot.columns if t not in own]
    tick = {t: [float(x) for x in pivot[t]] for t in own}
    tick['Other'] = [float(x) for x in pivot[rest].sum(axis=1)] if rest else [0.0] * len(months)
    last = pivot.iloc[-1]
    latest = [dict(ticker=t, weight=float(last[t])) for t in last.sort_values(ascending=False).index if last[t] > 1e-6]
    m = spec['metrics']
    return dict(
        id=spec['id'], group=spec['group'], name=spec['name'], badge=spec['badge'], optional=spec['optional'],
        default_view=spec['default_view'], source=spec['source'], label=TARGET_LABEL.format(spec['source']),
        sleeves=bool(spec.get('sleeves')), months=months, data_through=months[-1],
        class_series=cls, ticker_series=tick, other_members=[dict(ticker=t) for t in rest],
        sum_min=float(sums.min()), sum_max=float(sums.max()),
        gate_on_months=[x for x in (gate_months or []) if x in months] if spec.get('gate') else None,
        metrics={k: (None if v is None else v) for k, v in m.items()},
        avg_cash_like=float(np.mean(cls['Cash-like'])),
        void_composition=spec.get('void_composition'), void_composition_label=spec.get('void_composition_label'),
        void_kind=spec.get('void_kind'),
        tag_shares=tag_shares(pivot, universe) if universe is not None else None,
        books_source=spec.get('books_source'), source_note=spec.get('source_note'),
        latest=dict(month=months[-1], rows=latest),
    )


def gate_on_months() -> list[str]:
    """Book 2 gate on, from the gate output: holding months (eval_date) where gate_binding is True."""
    g = pd.read_csv(P / 'live/skew_managed_gatefirst_weights.csv')
    on = g.loc[g['gate_binding'].astype(str).str.lower().eq('true')]
    return sorted(_month(on['eval_date']).unique())


def build_data() -> dict:
    universe = pd.read_csv(UNIVERSE)
    bands = band_map(universe)
    gates = gate_on_months()
    charts = [build_chart(s, bands, gates, universe) for s in specs()]
    return dict(
        note=('Saved target weights at each rebalance, plotted on the holding month. Bands: cash-like = tripwire tags '
              '(cash_like, short_duration, near_cash); otherwise epo_asset_class; otherwise Untagged (Category never used).'),
        bands=BANDS, cash_limit=CASH_LIMIT, top_n=TOP_N, always_own_line=list(ALWAYS_OWN_LINE),
        gate_on_months=gates, charts=charts, not_saved=not_saved())


# ------------------------------------------------------------------ rendering
W, H, L, R, T, B = 340, 170, 30, 6, 8, 18


def _xy(i, n, v):
    x = L + (W - L - R) * (i / max(n - 1, 1))
    y = T + (H - T - B) * (1 - v)
    return x, y


def svg_stack(months, series: dict, colors: dict, *, gate=None, limit=None, title=''):
    n = len(months)
    cum = np.zeros(n)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(title)}" class="cot-svg">']
    for name, vals in series.items():
        v = np.asarray(vals, float)
        if not v.any():
            continue
        lo, hi = cum.copy(), cum + v
        top = [_xy(i, n, min(hi[i], 1.0)) for i in range(n)]
        bot = [_xy(i, n, min(lo[i], 1.0)) for i in reversed(range(n))]
        pts = ' '.join(f'{x:.1f},{y:.1f}' for x, y in top + bot)
        parts.append(f'<polygon points="{pts}" fill="{colors[name]}" stroke="#1f3a5f" stroke-width="0.3"/>')
        cum = hi
    if gate:
        idx = [i for i, m in enumerate(months) if m in set(gate)]
        step = (W - L - R) / max(n - 1, 1)
        for i in idx:
            x = _xy(i, n, 0)[0] - step / 2
            parts.append(f'<rect x="{x:.1f}" y="{T}" width="{step:.2f}" height="{H - T - B}" class="cot-gate-on" fill="#000000" fill-opacity="0.28"/>')
    for frac in (0, 0.5, 1):
        y = _xy(0, n, frac)[1]
        parts.append(f'<text x="{L - 3}" y="{y + 3:.1f}" text-anchor="end" class="cot-axis">{int(frac * 100)}%</text>')
    years = sorted({m[:4] for m in months})
    stepy = max(1, len(years) // 5)
    for yr in years[::stepy]:
        i = next(i for i, m in enumerate(months) if m.startswith(yr))
        x = _xy(i, n, 0)[0]
        parts.append(f'<text x="{x:.1f}" y="{H - 5}" text-anchor="middle" class="cot-axis">{yr}</text>')
    if limit is not None:
        y = _xy(0, n, limit)[1]
        parts.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" stroke="#000000" stroke-width="1" '
                     f'stroke-dasharray="4 3"/>')
    parts.append(f'<rect x="{L}" y="{T}" width="{W - L - R}" height="{H - T - B}" fill="none" stroke="#1f3a5f" stroke-width="0.6"/>')
    parts.append('</svg>')
    return ''.join(parts)


# VT is also the Vanguard Total World ETF ticker; the site never shows it bare (tests/test_no_bare_vt_label.py).
DISPLAY_NAMES = {'VT': 'Vanguard Total World ETF'}


def display(name: str) -> str:
    return DISPLAY_NAMES.get(name, name)


def ticker_colors(names):
    out, k = {}, 0
    for t in names:
        if t in FIXED_COLORS:
            out[t] = FIXED_COLORS[t]
        else:
            out[t] = TICKER_COLORS[k % len(TICKER_COLORS)]
            k += 1
    return out


def legend(series: dict, colors: dict):
    items = []
    for name, vals in series.items():
        avg = float(np.mean(vals)) if len(vals) else 0.0
        if avg <= 0:
            continue
        items.append(f'<li><span class="cot-sw" style="background:{colors[name]}"></span>{escape(display(name))} '
                     f'<span class="muted">{100 * avg:.1f}%</span></li>')
    return '<ul class="cot-legend">' + ''.join(items) + '</ul>'


def fmt_metric(m, kind):
    if m is None:
        return 'not recorded'
    v = m['value']
    return f'{100 * v:.1f}%' if kind == 'pct' else f'{v:.2f}'


def chart_html(c: dict, gate_label: str) -> str:
    tick_names = list(c['ticker_series'])
    tcol = ticker_colors(tick_names)
    view_class = svg_stack(c['months'], c['class_series'], BAND_COLORS, gate=c['gate_on_months'], limit=CASH_LIMIT,
                           title=f"{c['name']}: asset-class bands")
    view_tick = svg_stack(c['months'], c['ticker_series'], tcol, gate=c['gate_on_months'],
                          title=f"{c['name']}: top holdings")
    badge_cls = 'badge badge-fail' if c['badge'] in ('FAIL', 'VOID', 'INVALID') else 'badge'
    rid = f"cot-{c['id']}"
    cls_checked = ' checked' if c['default_view'] == 'class' else ''
    tick_checked = ' checked' if c['default_view'] == 'ticker' else ''
    m = c['metrics']
    line = (f"Average equity share: {fmt_metric(m['equity'], 'pct')} · effective N: {fmt_metric(m['eff_n'], 'num')} · "
            f"turnover per year: {fmt_metric(m['turnover'], 'num')} (from the run output)")
    void = ''
    if c.get('void_kind'):
        void = (f'<div class="cot-void"><p><strong>Why {escape(c["badge"])}:</strong></p>'
                + ''.join(f'<p>{escape(x)}</p>' for x in void_lines(c)) + '</div>')
    gate = ''
    if c['gate_on_months']:
        gate = f'<p class="muted cot-gate">Shaded: months the skew gate was on ({escape(gate_label)}), read from the gate output.</p>'
    sleeves = ('<p class="muted">Holdings are category sleeves (constituents were not saved), so they sit in the '
               'Untagged band; BIL is a ticker.</p>') if c['sleeves'] else ''
    rows = [[display(r['ticker']), f"{100 * r['weight']:.1f}%"] for r in c['latest']['rows'][:15]]
    more = len(c['latest']['rows']) - len(rows)
    table = ('<div class="table-scroll" tabindex="0" role="region" aria-label="Latest weights">'
             f'<table><caption>Latest month’s weights · data through {escape(month_label(c["data_through"]))}'
             + (f' · {more} smaller holdings not shown' if more > 0 else '') + '</caption>'
             '<thead><tr><th scope="col">Holding</th><th scope="col">Weight</th></tr></thead><tbody>'
             + ''.join(f'<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>' for a, b in rows)
             + '</tbody></table></div>')
    return (
        f'<article class="feature-card cot-card" id="{rid}" data-default-view="{c["default_view"]}">'
        f'<span class="{badge_cls}">{escape(c["badge"])}</span>'
        f'<h3>{escape(c["name"])}</h3>'
        f'<p class="metric-sub cot-label">{escape(c["label"])}</p>'
        + (f'<p class="cot-source-note">{escape(c["source_note"])}</p>' if c.get('source_note') else '')
        + f'<div class="cot-toggle" role="radiogroup" aria-label="View">'
        f'<input type="radio" id="{rid}-class" name="{rid}" value="class"{cls_checked}>'
        f'<label for="{rid}-class">Asset classes</label>'
        f'<input type="radio" id="{rid}-tick" name="{rid}" value="ticker"{tick_checked}>'
        f'<label for="{rid}-tick">Top holdings</label>'
        f'<div class="cot-view cot-view-class">{view_class}{legend(c["class_series"], BAND_COLORS)}'
        f'<p class="muted cot-limit">Dashed line: {int(100 * CASH_LIMIT)}% limit on the cash-like band (bottom).</p></div>'
        f'<div class="cot-view cot-view-ticker">{view_tick}{legend(c["ticker_series"], tcol)}'
        f'<p class="muted">Top {TOP_N} holdings by average weight; XSD always its own line'
        + ('; BIL its own band' if c['group'] == 'books' else '') + '; the rest is Other.</p></div>'
        '</div>'
        + gate + void + sleeves
        + f'<p class="cot-metrics">{escape(line)}</p>' + table + '</article>'
    )


def not_saved_html(n: dict) -> str:
    return (f'<article class="feature-card cot-card cot-not-saved" id="cot-{escape(n["id"])}">'
            f'<span class="badge badge-fail">{escape(n["badge"])}</span><h3>{escape(n["name"])}</h3>'
            f'<p><strong>Weights not saved.</strong> {escape(n["reason"])}</p>'
            f'<p class="muted">Source: {escape(n["source"])}. Nothing is reconstructed.</p></article>')


def month_label(m: str) -> str:
    return pd.Period(m, 'M').strftime('%b %Y')


STYLE = """<style>
.cot-card h3{margin:.4rem 0 .2rem}
.cot-svg{width:100%;height:auto;display:block;margin:.5rem 0}
.cot-axis{font-size:9px;fill:#333333;font-family:Inter,system-ui,sans-serif}
.cot-toggle input{position:absolute;opacity:0;width:1px;height:1px}
.cot-toggle label{display:inline-block;padding:.25rem .6rem;margin:.2rem .3rem .2rem 0;border:1px solid #1f3a5f;
  font-size:.8rem;cursor:pointer;color:#1f3a5f;background:#ffffff}
.cot-toggle input:checked+label{background:#1f3a5f;color:#ffffff}
.cot-toggle input:focus-visible+label{outline:2px solid #000000;outline-offset:2px}
.cot-view{display:none}
.cot-toggle input[value=class]:checked~.cot-view-class,.cot-toggle input[value=ticker]:checked~.cot-view-ticker{display:block}
.cot-legend{list-style:none;padding:0;margin:.2rem 0;display:flex;flex-wrap:wrap;gap:.2rem .8rem;font-size:.8rem}
.cot-sw{display:inline-block;width:.8rem;height:.8rem;border:1px solid #1f3a5f;margin-right:.3rem;vertical-align:-1px}
.cot-card p{font-size:.85rem;line-height:1.45}
.cot-metrics{font-size:.85rem}
.cot-source-note{font-weight:600;color:#0b1f3a}
.cot-void{border-left:3px solid #000000;padding-left:.6rem;margin:.5rem 0}
.cot-void p{margin:.2rem 0}
.cot-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(300px,100%),1fr));gap:1rem}
.cot-grid>*{min-width:0}
.cot-card{overflow-wrap:anywhere}
.cot-more>summary{cursor:pointer;margin:.8rem 0;font-weight:600}
@media (max-width:640px){.cot-grid{grid-template-columns:1fr}}
</style>"""


def build_page(page_shell, write_page, data: dict | None = None) -> dict:
    data = data or build_data()
    gates = data['gate_on_months']
    gate_label = f'{month_label(gates[0])} to {month_label(gates[-1])}' if gates else 'none'
    charts = data['charts']

    def section(group, title, intro):
        main = [c for c in charts if c['group'] == group and not c['optional']]
        extra = [c for c in charts if c['group'] == group and c['optional']]
        html = f'<h2 id="{group}">{escape(title)}</h2><p>{intro}</p><div class="cot-grid">' + ''.join(
            chart_html(c, gate_label) for c in main) + '</div>'
        if extra:
            html += ('<details class="cot-more"><summary>Sensitivities and other runs (' + str(len(extra)) + ')</summary>'
                     '<div class="cot-grid">' + ''.join(chart_html(c, gate_label) for c in extra) + '</div></details>')
        return html

    content = (
        '<section class="band"><div class="band-inner">'
        '<p><span class="badge">Research record · not investment advice</span></p>'
        '<h1>Composition over time</h1>'
        '<p class="lede">What each strategy held, month by month, as if it had been run live from its start date. '
        'Every weight is read from the saved weights file named on each chart; nothing is reconstructed.</p>'
        '<div class="callout"><strong>How to read it.</strong> Charts plot the saved target weights at each rebalance, '
        'on the month they earn. Bands, bottom to top: cash-like (any fund tagged cash-like, short-duration or near-cash, '
        'the composition tripwire’s own tags, with a dashed line at the 50% limit), then bond, commodity and equity from '
        'the stored asset-class tag, and Untagged for anything else. Fund categories are never used to guess a band. '
        'The Books open on holdings; the allocators open on asset classes. Badges are each run’s archive verdict.</div>'
        + section('books', 'Books', 'The two live Books and the backbone they are measured against.')
        + section('epo', 'Anchored EPO and its baselines', 'The archived EPO gate run: the method and the baselines it was judged against.')
        + section('archive', 'Archived methods', 'Every archived method with saved weights, at its headline configuration.')
        + ('<h2 id="not-saved">Weights not saved</h2><div class="cot-grid">'
           + ''.join(not_saved_html(n) for n in data['not_saved']) + '</div>' if data['not_saved'] else '')
        + '<p class="muted">Source data: docs/data/composition_over_time.json, generated from the files named on each chart.</p>'
        '</div></section>'
    )
    write_page(PAGE, page_shell('Composition over time', content, prefix='../', active='methods/index.html',
                                extra_head=STYLE, include_charts=False))
    return data


def write_data(docs: Path, data: dict) -> None:
    path = docs / DATA
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
