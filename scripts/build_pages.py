#!/usr/bin/env python3
"""Build the committed research lab (stdlib only): copy CSVs → viz JSON → HTML."""
from __future__ import annotations

import csv
import json
import re
import shutil
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_JSON = ROOT / 'apps' / 'pages' / 'src' / 'data' / 'archive_verdicts.json'
DOCS = ROOT / 'docs'
DATA = DOCS / 'data'
ASSETS = DOCS / 'assets'
DISCLAIMER = 'Research only; not investment advice; experimental panel; no performance guarantees.'

# Optional CIO shortlist inputs (graceful skip if absent).
CIO = Path('/workspace/investments/cio_book_shortlist')
CIO_COPIES = [
    (CIO / 'shortlist_comparison.csv', 'shortlist_comparison.csv'),
    (CIO / 'book1_static_option_a_weights.csv', 'book1_static_option_a_weights.csv'),
    (CIO / 'book2_vol_target_option_a_weights.csv', 'book2_vol_target_option_a_weights.csv'),
    (CIO / 'run_latest' / 'strategy_comparison.csv', 'strategy_comparison.csv'),
    (CIO / 'run_latest' / 'suggested_weights.csv', 'suggested_weights.csv'),
    (CIO / 'run_latest' / 'strategy_diagnostics.csv', 'strategy_diagnostics.csv'),
]

NAV = [
    ('index.html', 'Home'),
    ('index.html#/books', 'Books'),
    ('index.html#/runs', 'Runs'),
    ('explorer/index.html', 'Explorer'),
    ('methods/index.html', 'Methods'),
]


def read_csv(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        return []
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_json(name: str, payload: object) -> None:
    path = DATA / name
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def copy_cio_inputs() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    for src, dest_name in CIO_COPIES:
        if src.is_file():
            shutil.copy2(src, DATA / dest_name)


def cumprod_wealth(returns: list[float]) -> list[float]:
    wealth = [1.0]
    w = 1.0
    for r in returns:
        w *= 1.0 + r
        wealth.append(w)
    return wealth  # length = n+1 with t0=1; we align to dates below


def drawdowns(wealth: list[float]) -> list[float]:
    out = []
    peak = wealth[0]
    for w in wealth:
        peak = max(peak, w)
        out.append(w / peak - 1.0)
    return out


def build_viz() -> None:
    """Exact column wiring for CIO charts — do not invent series."""
    oos = read_csv('vol_target_oos_returns.csv')
    # Prefer primary trial if multiple; current archive is one trial.
    if oos:
        trial = oos[0]['trial_id']
        oos = [r for r in oos if r['trial_id'] == trial]

    dates = [r['date'] for r in oos]
    r_vt = [float(r['r_vt']) for r in oos]
    r_a = [float(r['r_option_a']) for r in oos]
    # Wealth starts at 1.0 on the day before first return; plot against return dates
    # as end-of-period wealth after each month.
    w_vt, w_a = 1.0, 1.0
    equity_vt, equity_a = [], []
    for rv, ra in zip(r_vt, r_a):
        w_vt *= 1.0 + rv
        w_a *= 1.0 + ra
        equity_vt.append(w_vt)
        equity_a.append(w_a)
    dd_vt = drawdowns(equity_vt)
    dd_a = drawdowns(equity_a)
    write_json('viz_equity_drawdown.json', {
        'source': 'vol_target_oos_returns.csv',
        'columns': {'vol_target': 'r_vt', 'static_option_a': 'r_option_a'},
        'citation': 'Moreira & Muir (2017)',
        'callout': 'Path/risk improvement, not return alpha (NW t ≈ 0)',
        'dates': dates,
        'equity': {
            'vol_target_option_a': equity_vt,
            'static_option_a': equity_a,
        },
        'drawdown': {
            'vol_target_option_a': dd_vt,
            'static_option_a': dd_a,
        },
        'max_dd': {
            'vol_target_option_a': min(dd_vt) if dd_vt else None,
            'static_option_a': min(dd_a) if dd_a else None,
        },
    })

    weights = read_csv('vol_target_monthly_weights.csv')
    if weights and oos:
        weights = [r for r in weights if r['trial_id'] == oos[0]['trial_id']]
    write_json('viz_ft_history.json', {
        'source': 'vol_target_monthly_weights.csv (+ f on oos returns)',
        'dates': [r['date'] for r in weights],
        'f': [float(r['f']) for r in weights],
        'w_BIL': [float(r['w_BIL']) for r in weights],
        'sigma_hat': [float(r['sigma_hat']) for r in weights],
    })

    # Current weight bars: latest as-of from monthly weights + static template + suggested
    latest = weights[-1] if weights else None
    books = {
        'static_option_a': {
            'label': 'Book 1 — Static Option A',
            'asof': '',
            'weights': {'VOO': 0.7, 'QQQM': 0.2, 'IJR': 0.1},
        },
    }
    if latest:
        books['vol_target_option_a'] = {
            'label': 'Book 2 — Vol-target Option A',
            'asof': latest['date'],
            'eval_date': latest.get('eval_date', ''),
            'f': float(latest['f']),
            'weights': {
                'VOO': float(latest['w_VOO']),
                'QQQM': float(latest['w_QQQM']),
                'IJR': float(latest['w_IJR']),
                'BIL': float(latest['w_BIL']),
            },
        }
    suggested = read_csv('suggested_weights.csv')
    xsd_sleeve = [r for r in suggested if r['strategy_id'] == 'score_rotate_xsd']
    if xsd_sleeve:
        books['score_rotate_xsd'] = {
            'label': 'Optional gated sleeve — XSD',
            'asof': xsd_sleeve[0].get('asof') or xsd_sleeve[0].get('date', ''),
            'rotate_on': xsd_sleeve[0].get('rotate_on', ''),
            'weights': {r['ticker']: float(r['weight']) for r in xsd_sleeve},
        }
    write_json('viz_weights.json', {'books': books})

    # XSD ON/OFF from strategy_diagnostics (on / rotate_on) — snapshot only today
    diag = read_csv('strategy_diagnostics.csv')
    xsd_rows = [r for r in diag if r.get('strategy_id') == 'score_rotate_xsd']
    if xsd_rows:
        row = xsd_rows[0]
        on_raw = (row.get('on') or '').strip()
        rotate_raw = (row.get('rotate_on') or '').strip()
        # Normalize bool-ish
        def as_bool(v: str):
            if v == '':
                return None
            return v.lower() in ('1', 'true', 'yes', 'on')
        on_val = as_bool(on_raw)
        if on_val is None:
            on_val = as_bool(rotate_raw)
        write_json('viz_xsd_timeline.json', {
            'available': False,
            'note': 'No historical XSD ON/OFF series published yet in run_latest diagnostics; showing latest snapshot only.',
            'source': 'strategy_diagnostics.csv',
            'snapshot': {
                'strategy_id': 'score_rotate_xsd',
                'date': row.get('date', ''),
                'on': on_val,
                'on_raw': on_raw,
                'rotate_on': rotate_raw or None,
                'ticker': row.get('ticker', 'XSD'),
                'vol_ok': row.get('vol_ok', ''),
                'raw_on': row.get('raw_on', ''),
            },
            'dates': [],
            'xsd_on': [],
        })
    else:
        write_json('viz_xsd_timeline.json', {
            'available': False,
            'note': 'No series yet — strategy_diagnostics.csv has no score_rotate_xsd row.',
            'source': 'strategy_diagnostics.csv',
            'snapshot': None,
            'dates': [],
            'xsd_on': [],
        })

    # Comparison table: prefer strategy_comparison, fall back to shortlist
    comparison = read_csv('strategy_comparison.csv') or read_csv('shortlist_comparison.csv')
    # Filter to CIO shortlist books when full registry present
    shortlist_ids = {'static_option_a', 'vol_target_option_a', 'score_rotate_xsd'}
    short = [r for r in comparison if r['strategy_id'] in shortlist_ids]
    if not short:
        short = comparison
    labels = {
        'static_option_a': 'Book 1 — Static Option A',
        'vol_target_option_a': 'Book 2 — Vol-target Option A',
        'score_rotate_xsd': 'Optional gated sleeve — XSD',
        'm3_p2_core_rotate': 'M3 P2 (held off)',
    }
    stances = {
        'static_option_a': 'Benchmark policy baseline',
        'vol_target_option_a': 'Default research path — risk path, not return alpha',
        'score_rotate_xsd': 'Optional gated sleeve',
        'm3_p2_core_rotate': 'Held off the shortlist',
    }
    rows_out = []
    for r in short:
        sid = r['strategy_id']
        nw = r.get('NW_t_vs_option_a', '')
        rows_out.append({
            'strategy_id': sid,
            'label': labels.get(sid, sid),
            'AnnReturn': float(r['AnnReturn']),
            'AnnVol': float(r['AnnVol']),
            'MaxDD': float(r['MaxDD']),
            'Sharpe_rf0': float(r['Sharpe_rf0']),
            'NW_t_vs_option_a': float(nw) if nw not in ('', None) else None,
            'turnover_per_year': float(r['turnover_per_year']) if r.get('turnover_per_year') not in ('', None) else None,
            'n_months': int(float(r['n_months'])) if r.get('n_months') else None,
            'start_date': r.get('start_date', ''),
            'end_date': r.get('end_date', ''),
            'stance': stances.get(sid, ''),
        })
    write_json('viz_comparison.json', {
        'source': 'strategy_comparison.csv' if (DATA / 'strategy_comparison.csv').exists() else 'shortlist_comparison.csv',
        'rows': rows_out,
    })

    # Metrics for home cards from oos summary + comparison
    summary = read_csv('vol_target_oos_summary.csv')
    metrics = {}
    if summary:
        s = summary[0]
        metrics = {
            'trial_id': s['trial_id'],
            'AnnReturn_vt': float(s['AnnReturn']),
            'AnnVol_vt': float(s['AnnVol']),
            'MaxDD_vt': float(s['MaxDD']),
            'Sharpe_vt': float(s['Sharpe_rf0']),
            'AnnReturn_a': float(s['OptionA_AnnReturn']),
            'AnnVol_a': float(s['OptionA_AnnVol']),
            'MaxDD_a': float(s['OptionA_MaxDD']),
            'Sharpe_a': float(s['OptionA_Sharpe_rf0']),
            'NW_t': float(s['NW_t_vs_OptionA']),
            'n_months': int(float(s['n_months'])),
            'start_date': s['start_date'],
            'end_date': s['end_date'],
            'mean_f': float(s['mean_f']),
            'pct_months_f_lt_1': float(s['pct_months_f_lt_1']),
        }
    write_json('viz_metrics.json', metrics)


def refresh_weights_snapshot() -> None:
    weights = read_csv('vol_target_monthly_weights.csv')
    summary = read_csv('vol_target_oos_summary.csv')
    if not weights or not summary:
        return
    primary = summary[0]['trial_id']
    latest = max((r for r in weights if r['trial_id'] == primary), key=lambda r: r['date'])
    snapshot = DATA / 'latest_weights_snapshot.csv'
    with snapshot.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['strategy_id', 'decision_date', 'eval_date', 'ticker', 'weight', 'basis'])
        for ticker, weight in [('VOO', .7), ('QQQM', .2), ('IJR', .1)]:
            writer.writerow(['static_option_a', '', '', ticker, weight, 'static research template'])
        for ticker in ['VOO', 'QQQM', 'IJR', 'BIL']:
            writer.writerow([
                'vol_target_option_a', latest['date'], latest['eval_date'], ticker,
                latest['w_' + ticker], 'historical OOS sample: ' + primary,
            ])


def nav_html(prefix: str = '', active: str = '') -> str:
    links = []
    for path, label in NAV:
        href = prefix + path
        cls = ' class="is-active"' if active == path else ''
        links.append(f'<a href="{href}"{cls}>{escape(label)}</a>')
    return (
        '<header class="site-header">'
        '<div class="site-header-inner">'
        '<a class="brand" href="' + prefix + 'index.html">USA ETF Lab</a>'
        '<button type="button" class="nav-toggle" aria-expanded="false" '
        'aria-controls="site-nav" aria-label="Open menu">'
        '<span class="nav-toggle-bars" aria-hidden="true"></span>'
        '</button>'
        '<nav class="site-nav" id="site-nav" aria-label="Main">'
        + ''.join(links)
        + '</nav>'
        '</div></header>'
    )

def table_html(headers, rows, caption: str) -> str:
    return (
        f'<div class="table-scroll" tabindex="0" role="region" aria-label="{escape(caption)}">'
        f'<table><caption>{escape(caption)}</caption><thead><tr>'
        + ''.join(f'<th scope="col">{escape(str(h))}</th>' for h in headers)
        + '</tr></thead><tbody>'
        + ''.join(
            '<tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in row) + '</tr>'
            for row in rows
        )
        + '</tbody></table></div>'
    )


def csv_table(path: Path, prefix: str = 'data/') -> str:
    with path.open(newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    if not rows:
        return ''
    return (
        table_html(rows[0], rows[1:], path.stem.replace('_', ' '))
        + f'<p class="dl"><a href="{prefix}{escape(path.name)}">Download CSV</a></p>'
    )


def page_shell(
    title: str,
    content: str,
    prefix: str = '',
    active: str = '',
    extra_head: str = '',
    include_charts: bool = False,
) -> str:
    scripts = ''
    if include_charts:
        scripts = (
            '<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>'
            f'<script src="{prefix}assets/app.js" defer></script>'
        )
    fonts = (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,400;0,500;0,600;1,400;1,600'
        '&family=Playfair+Display:wght@700;900'
        '&family=Inter:wght@400;500;600;700'
        '&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
    )
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | USA ETF Lab</title>
{fonts}
<link rel="stylesheet" href="{prefix}assets/style.css">
{extra_head}
</head>
<body>
{nav_html(prefix, active)}
<main class="page">
{content}
</main>
<footer class="site-footer">
<p>{escape(DISCLAIMER)}</p>
<p class="muted">Static GitHub Pages · Research only</p>
</footer>
{scripts}
<script src="{prefix}assets/nav.js" defer></script>
</body>
</html>
'''


def write_page(rel: str, html: str) -> None:
    path = DOCS / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding='utf-8')


def fmt_pct(x: float | None, digits: int = 1) -> str:
    if x is None:
        return '—'
    return f'{100 * x:.{digits}f}%'


def fmt_num(x: float | None, digits: int = 2) -> str:
    if x is None:
        return '—'
    return f'{x:.{digits}f}'


def build_index() -> None:
    metrics = (
        json.loads((DATA / 'viz_metrics.json').read_text())
        if (DATA / 'viz_metrics.json').exists()
        else {}
    )
    scorecard = ''
    if metrics:
        scorecard = f"""
<section class="band soft">
  <div class="band-inner">
    <div class="section-head">
      <span class="badge">Supporting OOS</span>
      <h2>Book 2 path vs static Option A</h2>
      <p class="lede">Archived real-BIL sample · {escape(str(metrics.get('n_months', '')))} months · {escape(str(metrics.get('start_date', '')))} → {escape(str(metrics.get('end_date', '')))}. Evidence for the live Book-2 sleeve — not a separate promoted book.</p>
    </div>
    <div class="metric-grid">
      <article class="metric-card">
        <h3>Sharpe (vt)</h3>
        <p class="metric-value">{fmt_num(metrics.get('Sharpe_vt'))}</p>
        <p class="metric-sub">Static A: {fmt_num(metrics.get('Sharpe_a'))}</p>
      </article>
      <article class="metric-card">
        <h3>Max drawdown (vt)</h3>
        <p class="metric-value down">{fmt_pct(metrics.get('MaxDD_vt'))}</p>
        <p class="metric-sub">Static A: {fmt_pct(metrics.get('MaxDD_a'))}</p>
      </article>
      <article class="metric-card">
        <h3>Ann. vol (vt)</h3>
        <p class="metric-value">{fmt_pct(metrics.get('AnnVol_vt'))}</p>
        <p class="metric-sub">Static A: {fmt_pct(metrics.get('AnnVol_a'))}</p>
      </article>
      <article class="metric-card">
        <h3>NW t vs A</h3>
        <p class="metric-value">{fmt_num(metrics.get('NW_t'))}</p>
        <p class="metric-sub">Path/risk improvement, not return alpha</p>
      </article>
    </div>
    <p class="callout">Moreira &amp; Muir (2017) · mean f = {fmt_num(metrics.get('mean_f'))} · months with f&lt;1: {fmt_pct(metrics.get('pct_months_f_lt_1'), 0)}</p>
    <div class="cta-row">
      <a class="btn btn-primary" href="runs.html">Open OOS charts</a>
      <a class="btn btn-secondary" href="books.html">Live shortlist weights</a>
    </div>
  </div>
</section>"""
    content = f"""
<section class="hero">
  <div class="hero-inner">
    <span class="badge">Live shortlist</span>
    <h1>Static core + Book-2 vol-target</h1>
    <p class="lede">The live research shortlist is <strong>Book 1 static Option A</strong> plus <strong>Book 2 unconditional vol-target</strong>. Archive / failed-null methods are not on this door. Static GitHub Pages — no live trading.</p>
    <div class="cta-row">
      <a class="btn btn-primary" href="books.html">Open live shortlist</a>
      <a class="btn btn-secondary" href="runs.html">OOS runs</a>
      <a class="btn btn-secondary" href="explorer/index.html">Explorer</a>
    </div>
  </div>
</section>
<section class="band">
  <div class="band-inner">
    <div class="section-head">
      <span class="badge">Front door</span>
      <h2>What is live right now</h2>
      <p class="lede"><strong>Live shortlist:</strong> two research books only — <strong>Book 1 static core</strong> (VOO / QQQM / IJR) and <strong>Book 2 vol-target</strong> (same core, scale-down into BIL). Justina methods (Spectral RP, Regime-Aware, vol-cond factor corr) failed binding nulls and stay in <strong>Methods → Archive</strong>, not here.</p>
    </div>
    <div class="card-grid shortlist-grid">
      <a class="feature-card shortlist-card" href="books.html">
        <span class="badge">Book 1 · live</span>
        <h3>Static core</h3>
        <p>Fixed weights VOO 70% / QQQM 20% / IJR 10%. Buy-and-hold reference — clean null for timing / risk overlays.</p>
      </a>
      <a class="feature-card shortlist-card" href="books.html">
        <span class="badge">Book 2 · live</span>
        <h3>Vol-target</h3>
        <p>Same Option A core, scale-down into BIL when risk is high. Path/risk book vs Book 1 — not a beat-the-market story.</p>
      </a>
      <div class="feature-card shortlist-card muted-card" role="note">
        <span class="badge badge-quiet">Not live</span>
        <h3>Archive / failed nulls</h3>
        <p>Spectral RP, Regime-Aware, and vol-cond factor corr (#13) failed binding nulls — research record only under Methods → Archive.</p>
        <p class="cta-inline"><a href="methods/index.html#archive">View archive</a></p>
      </div>
    </div>
  </div>
</section>
{scorecard}
<section class="band">
  <div class="band-inner card-grid">
    <a class="feature-card" href="books.html">
      <span class="badge">Books</span>
      <h3>Shortlist weights &amp; comparison</h3>
      <p>Live Books 1–2 with standing-book cards, weights, and comparison. Optional XSD sleeve is not a standing book.</p>
    </a>
    <a class="feature-card" href="runs.html">
      <span class="badge">Runs</span>
      <h3>Out-of-sample charts</h3>
      <p>Equity, drawdown, f<sub>t</sub>, and downloadable CSVs for the live path.</p>
    </a>
    <a class="feature-card" href="explorer/index.html">
      <span class="badge">Explorer</span>
      <h3>Time Series Explorer</h3>
      <p>Growth-panel metrics and charts for research diagnostics.</p>
    </a>
  </div>
</section>
"""
    write_page(
        'index.html',
        page_shell(
            'Live shortlist · USA ETF research lab',
            content,
            active='index.html',
            include_charts=False,
        ),
    )

def build_books() -> None:
    content = '''
<section class="hero hero-compact">
  <div class="hero-inner">
    <span class="badge">Live shortlist</span>
    <h1>Live research shortlist</h1>
    <p class="lede">Two books for comparison on the experimental USA ETF panel. Everything else that failed the leakage / null / DSR gate is archived under Methods — not promoted here.</p>
    <p class="callout">Research only — not investment advice. Panel is an arbitrary experimental USA ETF set for methodology work.</p>
  </div>
</section>
<section class="band">
  <div class="band-inner">
    <div class="section-head">
      <h2>Standing books</h2>
      <p class="lede">Live composition unchanged: static core + Book-2 vol-target. XSD is an optional gated sleeve — not a live book.</p>
    </div>
    <div class="card-grid shortlist-grid" style="grid-template-columns: repeat(2, minmax(0, 1fr));">
      <article class="feature-card shortlist-card">
        <span class="badge">Book 1 · Static core</span>
        <h3>Buy-and-hold reference</h3>
        <p><strong>What it is:</strong> Fixed weights <strong>VOO 70% / QQQM 20% / IJR 10%</strong>. No timing, no vol scale. Strategy id <code>static_option_a</code>.</p>
        <p><strong>Why it&rsquo;s on the shortlist:</strong> Clean null for “did timing or risk management add anything?” Every overlay is judged against this path (and against Book 2 when the claim is risk-managed).</p>
        <p><strong>What it is not:</strong> Not a Justina method. Not a multifactor optimizer showcase.</p>
        <p class="metric-sub">OOS snapshot (panel; rf=0 Sharpe): ~14.7% ann. return · ~15.9% vol · MaxDD ~−25.6% · Sharpe ~0.92 · ~68 months (2021-02 → 2026-09). Turnover ≈ 0.</p>
      </article>
      <article class="feature-card shortlist-card">
        <span class="badge">Book 2 · Vol-target</span>
        <h3>Default research path</h3>
        <p><strong>What it is:</strong> Same Option A core, scaled by estimated volatility (scale-down only in v1); cash residual in <strong>BIL</strong> when risk is high. Strategy id <code>vol_target_option_a</code>.</p>
        <p><strong>Why it&rsquo;s on the shortlist:</strong> On this panel it improves the risk path vs Book 1 (higher Sharpe_rf0, milder MaxDD) without a strong return-alpha claim vs static (NW t vs Book 1 ≈ 0). That is a <strong>path/risk</strong> book, not a “beat the market” story.</p>
        <p><strong>What it is not:</strong> Not the archived conditional factor-corr overlay (#13), which <strong>failed</strong> vs this unconditional Book 2 on Sharpe.</p>
        <p class="metric-sub">OOS snapshot (panel; rf=0 Sharpe): ~14.7% ann. return · ~13.9% vol · MaxDD ~−20.1% · Sharpe ~1.06 · same window. Modest turnover from scaling.</p>
      </article>
    </div>
    <div class="callout" style="margin-top:1.5rem">
      <strong>Not on the shortlist:</strong> Spectral risk parity (null: Ledoit–Wolf MinVar), Regime-aware dual-regime (null: Unconditional ERC), Vol-cond factor corr #13 (null: Unconditional Book-2 VT) — all <strong>FAIL — archive</strong>.
      Full table: <a href="methods/justina_round1_scoreboard.html">Methods → Archive / Justina round-1 scoreboard</a>.
    </div>
  </div>
</section>
<section class="band soft">
  <div class="band-inner">
    <div class="section-head">
      <h2>Comparison</h2>
      <p class="lede">From <code>strategy_comparison.csv</code> (live Books 1–2; optional XSD sleeve may appear). Mobile-friendly table.</p>
    </div>
    <div id="comparison-table" class="comparison-host" data-viz="comparison"></div>
  </div>
</section>
<section class="band">
  <div class="band-inner">
    <div class="section-head">
      <h2>Current weights</h2>
      <p class="lede">Latest as-of bars from monthly weights / suggested_weights. Not a live broker allocation.</p>
    </div>
    <div class="chart-grid">
      <div class="chart-card">
        <h3>Book 1 — Static core</h3>
        <div class="chart" data-chart="weights" data-book="static_option_a" style="min-height:280px"></div>
      </div>
      <div class="chart-card">
        <h3>Book 2 — Vol-target</h3>
        <div class="chart" data-chart="weights" data-book="vol_target_option_a" style="min-height:280px"></div>
      </div>
      <div class="chart-card">
        <h3>Optional sleeve — XSD</h3>
        <div class="chart" data-chart="weights" data-book="score_rotate_xsd" style="min-height:280px"></div>
      </div>
    </div>
    <p class="lede" style="margin-top:1rem"><code>score_rotate_xsd</code> may appear in runs as a gated thematic sleeve — default <strong>OFF</strong> unless ScoreSimple is ON. Optional gated sleeve only.</p>
  </div>
</section>
<section class="band soft">
  <div class="band-inner">
    <div class="section-head">
      <h2>XSD ON / OFF</h2>
      <p class="lede">ScoreSimple gate from <code>strategy_diagnostics.csv</code> (<code>on</code> / <code>rotate_on</code>). Optional sleeve only.</p>
    </div>
    <div class="chart-card">
      <div class="chart" data-chart="xsd-timeline" style="min-height:200px"></div>
    </div>
  </div>
</section>
<section class="band">
  <div class="band-inner">
    <div class="section-head"><h2>Weight snapshot CSV</h2></div>
'''
    snapshot = DATA / 'latest_weights_snapshot.csv'
    if snapshot.exists():
        content += csv_table(snapshot)
    content += '</div></section>'
    write_page('books.html', page_shell(
        'Books / strategies', content, active='books.html', include_charts=True,
    ))


def build_runs() -> None:
    content = '''
<section class="hero hero-compact">
  <div class="hero-inner">
    <span class="badge">OOS archive</span>
    <h1>Out-of-sample runs</h1>
    <p class="lede">Weights use data through the decision date; returns evaluate the following period. Final September 2026 observation ends September 16 (partial month).</p>
    <p class="callout">Book 2 · Moreira &amp; Muir (2017) · path/risk improvement, not return alpha (NW t ≈ 0). <a href="data/README_OOS_note.md">Read the OOS note</a>.</p>
  </div>
</section>
<section class="band">
  <div class="band-inner">
    <div class="section-head">
      <h2>Equity curves</h2>
      <p class="lede">Cumulative wealth from <code>r_vt</code> vs <code>r_option_a</code> in <code>vol_target_oos_returns.csv</code> (cumprod).</p>
    </div>
    <div class="chart-card">
      <div class="chart" data-chart="equity" style="min-height:360px"></div>
    </div>
  </div>
</section>
<section class="band soft">
  <div class="band-inner">
    <div class="section-head">
      <h2>Drawdowns</h2>
      <p class="lede">Peak-to-trough from the same wealth paths.</p>
    </div>
    <div class="chart-card">
      <div class="chart" data-chart="drawdown" style="min-height:320px"></div>
    </div>
  </div>
</section>
<section class="band">
  <div class="band-inner">
    <div class="section-head">
      <h2>Vol-target f<sub>t</sub></h2>
      <p class="lede">Scale factor and BIL residual share from <code>vol_target_monthly_weights.csv</code>.</p>
    </div>
    <div class="chart-card">
      <div class="chart" data-chart="ft" style="min-height:320px"></div>
    </div>
  </div>
</section>
<section class="band soft">
  <div class="band-inner">
    <div class="section-head">
      <h2>XSD gate snapshot</h2>
    </div>
    <div class="chart-card">
      <div class="chart" data-chart="xsd-timeline" style="min-height:200px"></div>
    </div>
  </div>
</section>
<section class="band">
  <div class="band-inner">
    <div class="section-head"><h2>Archived tables</h2></div>
'''
    skip = {
        'growth_alpha_adj_close.csv',
        'growth_panel_history_coverage.csv',
        'latest_weights_snapshot.csv',
        'suggested_weights.csv',
        'book1_static_option_a_weights.csv',
        'book2_vol_target_option_a_weights.csv',
    }
    for p in sorted(DATA.glob('*.csv')):
        if p.name in skip or p.name.startswith('viz_'):
            continue
        content += (
            '<section class="table-block"><h3>'
            + escape(p.stem.replace('_', ' ').title())
            + '</h3>'
            + csv_table(p)
            + '</section>'
        )
    content += '</div></section>'
    write_page('runs.html', page_shell(
        'Out-of-sample runs', content, active='runs.html', include_charts=True,
    ))


def load_archive_cards() -> dict:
    return json.loads(ARCHIVE_JSON.read_text(encoding='utf-8'))


def verdict_card_html(card, prefix) -> str:
    method_page = card['method_page']
    if not prefix:
        method_page = method_page.removeprefix('methods/')
    badge_class = 'badge badge-fail' if card['badge'] == 'FAIL' else 'badge'
    rows = [[row['label'], row['sharpe'], row['maxdd']] for row in card['rows']]

    def href_for(href: str) -> str:
        if href.startswith('http'):
            return href
        return prefix + (href.removeprefix('methods/') if not prefix else href)

    def link(item: dict) -> str:
        ext = ' target="_blank" rel="noreferrer"' if item['href'].startswith('http') else ''
        return f'<a href="{escape(href_for(item["href"]))}"{ext}>{escape(item["label"])}</a>'

    nw_links = ''.join(' · ' + link(item) for item in card.get('nw_t_links', []))
    measured = card.get('measured')
    measured_html = (
        f'<p><strong>{escape(measured["label"])}:</strong> {escape(measured["text"])}</p>' if measured else ''
    )
    return (
        f'<article class="feature-card archive-card" id="card-{escape(card["id"])}">'
        f'<span class="{badge_class}">{escape(card["badge"])}</span>'
        f'<p><strong>{escape(card["name"])}</strong></p>'
        f'<p class="metric-sub">{escape(card["detail"])}</p>'
        f'<p><em>{escape(card["verdict"])}</em></p>'
        f'<p><strong>Binding null:</strong> {escape(card["null"])}</p>'
        + table_html(['', 'Sharpe', 'MaxDD'], rows, f'{card["name"]} OOS vs null')
        + measured_html
        + f'<p><strong>NW t:</strong> {escape(card["nw_t"])}{nw_links} · <strong>DSR (vs zero Sharpe):</strong> {escape(card["dsr"])}</p>'
        '<p class="muted">Gate memo / PR: '
        f'<a href="{escape(card["gate"]["href"])}" target="_blank" rel="noreferrer">{escape(card["gate"]["label"])}</a> · '
        f'<a href="{escape(prefix + method_page)}">Method page</a> · OOS artifact: '
        f'<a href="{escape(card["artifact"]["href"])}" target="_blank" rel="noreferrer">{escape(card["artifact"]["label"])}</a> · '
        f'Archived {escape(card["archived"])} ({escape(card["archived_via"])})</p></article>'
    )


def build_archive_scoreboard() -> None:
    archive = load_archive_cards()
    subtitle = (
        'Archived methods: Justina round-1 (Spectral RP, Regime-Aware), #13 VCFC, #4 FT-MED, #3 RR-ERC · '
        'plus the unconditional Book-2 VT audit null · USA ETF experimental panel · '
        f'updated {archive["updated"]} (ET)'
    )
    content = (
        '<section class="band"><div class="band-inner">'
        '<p><span class="badge">Research archive · not a showcase · not live books</span></p>'
        '<h1>Methods Archive scoreboard</h1>'
        f'<p class="muted">{escape(subtitle)}</p>'
        '<div class="callout"><strong>Research only — not investment advice.</strong> '
        'Negative / null results documented on purpose. The five failed methods are '
        '<strong>FAIL / ARCHIVE</strong> — not promoted to Books, not a showcase, not part of the live shortlist. '
        'Unconditional Book-2 VT is an AUDIT NULL (not live, not a FAIL).</div>'
        '<div class="callout"><strong>CIO frame:</strong> '
        '<p><em>None of the five archived methods cleared its binding null.</em> <strong>No book cut.</strong></p>'
        '<p>Live shortlist: <strong>static core + VT × gate-first skew overlay</strong> (Justina #6, PR #29). '
        'Unconditional Book-2 VT is the audit null that overlay was measured against — not live, not a FAIL.</p>'
        '<p>Further candidates must clear the same leakage · null · DSR · empirical gate. '
        '<a href="../index.html#/">Back to live shortlist →</a></p></div>'
        '<h2>Verdict cards</h2>'
        + ''.join(verdict_card_html(card, '') for card in archive['cards'])
        + '<h2>What cleared the process (not the nulls)</h2><ul>'
        '<li>Walk-forward leakage gates + unit tests (decision / feature_end ≤ t; labels next month).</li>'
        '<li>Predeclared nulls and DSR / trial counts reported (normal-approx DSR where applicable).</li>'
        '<li>Brand-scrub / experimental-panel language only.</li></ul>'
        '<p class="muted">Sources: card numbers are copied from repo artifacts (data/processed/*/…summary.csv) '
        'and gate PR bodies (#10, #11, #13, #24, #26, #27, #29); single source: apps/pages/src/data/archive_verdicts.json.</p>'
        '</div></section>'
    )
    write_page('methods/justina_round1_scoreboard.html', page_shell(
        'Methods Archive scoreboard', content, prefix='../', active='methods/index.html', include_charts=False,
    ))


def build_methods_index() -> None:
    methods = [
        ('allocation_alpha_vol_target.html', 'Allocation alpha: volatility-managed Option A'),
        ('skewness_managed_stub.html', 'Skewness-Managed Book-2 Overlay (Justina #6 · gate-first PASS)'),
        ('ot_short_term_forecasting.html', 'Optimal transport: short-term forecasting'),
        ('ts_explorer_metric_menu.html', 'Time Series Explorer: quant metric menu'),
    ]
    archive = load_archive_cards()
    content = (
        '<section class="hero hero-compact"><div class="hero-inner">'
        '<span class="badge">Teaching notes</span><h1>Methods</h1>'
        '<p class="lede">Citation-backed method pages. Open viz deep-links to the Runs lab.</p>'
        '<div class="cta-row"><a class="btn btn-primary" href="../index.html#/runs">Open OOS viz</a></div>'
        '</div></section>'
        '<section class="band"><div class="band-inner"><ul class="method-list">'
        + ''.join(
            f'<li><a href="{name}">{escape(title)}</a></li>' for name, title in methods
        )
        + '</ul>'
        '<h2 id="archive">Archive / failed nulls</h2>'
        '<p class="lede archive-lede">5 FAIL / ARCHIVE methods + 1 AUDIT NULL — research record only; <strong>not live books</strong>. '
        'Live shortlist: static core + VT × gate-first skew overlay (Justina #6). '
        'Unconditional Book-2 VT is the audit null, not a FAIL.</p>'
        + ''.join(verdict_card_html(card, '') for card in archive['cards'])
        + '<p class="cta-inline"><a href="justina_round1_scoreboard.html">Archive scoreboard page →</a></p>'
        '</div></section>'
    )
    write_page('methods/index.html', page_shell(
        'Methods', content, prefix='../', active='methods/index.html', include_charts=False,
    ))


def restyle_methods_shell() -> None:
    methods = sorted(
        p.name for p in (DOCS / 'methods').glob('*.html') if p.name not in {'index.html', 'justina_round1_scoreboard.html'}
    )
    for name in methods:
        p = DOCS / 'methods' / name
        if not p.exists():
            continue
        s = p.read_text(encoding='utf-8')
        s = re.sub(r'<!-- lab:start -->.*?<!-- lab:end -->', '', s, flags=re.S)
        s = re.sub(r'<header class="site-header">.*?</header>', '', s, count=1, flags=re.S)
        # Inject shared stylesheet + fonts link marker
        inject_head = (
            '<!-- lab:start -->'
            '<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,wght@0,400;0,500;0,600;1,400;1,600&family=Playfair+Display:wght@700;900&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
            '<link rel="stylesheet" href="../assets/style.css">'
            '<!-- lab:end -->'
        )
        s = s.replace('</head>', inject_head + '</head>')
        s = s.replace(
            '<body>',
            '<body><!-- lab:start -->' + nav_html('../', 'methods/index.html') + '<!-- lab:end -->',
        )
        s = s.replace(
            '</body>',
            '<!-- lab:start --><footer class="site-footer"><p>'
            + DISCLAIMER
            + '</p></footer><!-- lab:end --></body>',
        )
        p.write_text(s, encoding='utf-8')


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    copy_cio_inputs()
    refresh_weights_snapshot()
    build_viz()
    # Pages v2 React SPA owns Home/Books/Runs via HashRouter on docs/index.html.
    # Do not emit leftover books.html / runs.html (or overwrite SPA index.html).
    for leftover in ('books.html', 'runs.html'):
        path = DOCS / leftover
        if path.exists():
            path.unlink()
            print('Removed leftover', leftover)
    build_methods_index()
    build_archive_scoreboard()
    restyle_methods_shell()
    print('Built docs viz JSON + methods under', DOCS)


if __name__ == '__main__':
    main()
