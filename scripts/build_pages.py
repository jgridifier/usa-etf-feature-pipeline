#!/usr/bin/env python3
"""Build the committed research lab using only Python's standard library."""
import csv
from html import escape
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
DATA = DOCS / 'data'
DISCLAIMER = 'Research only; not investment advice; experimental panel; no performance guarantees.'


def nav(prefix=''):
    return '<nav aria-label="Main">' + ' '.join(
        f'<a href="{prefix}{path}">{label}</a>' for path, label in
        [('index.html', 'Home'), ('methods/index.html', 'Methods'),
         ('books.html', 'Books'), ('runs.html', 'Runs')]) + '</nav>'


def table(headers, rows, caption):
    return (f'<div class="table-scroll" tabindex="0" role="region" aria-label="{escape(caption)}">'
            f'<table><caption>{escape(caption)}</caption><thead><tr>'
            + ''.join(f'<th scope="col">{escape(str(h))}</th>' for h in headers)
            + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in row)
                      + '</tr>' for row in rows) + '</tbody></table></div>')


def read_csv(name):
    with (DATA / name).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def csv_table(path, prefix='data/'):
    with path.open(newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    return (table(rows[0], rows[1:], path.stem.replace('_', ' '))
            + f'<p><a href="{prefix}{escape(path.name)}">Download CSV</a></p>')


def page(path, title, content, prefix=''):
    (DOCS / path).write_text(f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} | USA ETF Lab</title>
<link rel="stylesheet" href="{prefix}assets/style.css"></head>
<body>{nav(prefix)}<main><h1>{escape(title)}</h1>{content}</main>
<footer>{DISCLAIMER}</footer></body></html>
''', encoding='utf-8')


def main():
    page('index.html', 'Experimental USA ETF research panel lab',
         '<p>A research lab for transparent ETF features, fixed allocation books, '
         'and volatility-managed portfolio experiments.</p>'
         '<p>Research only; not investment advice. Explore the teaching notes, '
         'three-book CIO shortlist, and archived out-of-sample (OOS) runs.</p>'
         '<p><a href="books.html">Explore the books</a> · '
         '<a href="runs.html">Inspect OOS results</a></p>')
    methods = [('allocation_alpha_vol_target.html', 'Allocation alpha: volatility-managed Option A'),
               ('ot_short_term_forecasting.html', 'Optimal transport: short-term forecasting')]
    page('methods/index.html', 'Methods', '<ul>' + ''.join(
        f'<li><a href="{name}">{title}</a></li>' for name, title in methods) + '</ul>', '../')
    # Replace only the marked shared chrome on rebuild; preserve teaching content and citations.
    for name, _ in methods:
        p = DOCS / 'methods' / name
        s = re.sub(r'<!-- lab:start -->.*?<!-- lab:end -->', '', p.read_text(), flags=re.S)
        s = s.replace('</head>', '<!-- lab:start --><link rel="stylesheet" href="../assets/style.css"><!-- lab:end --></head>')
        s = s.replace('<body>', '<body><!-- lab:start -->' + nav('../') + '<!-- lab:end -->')
        s = s.replace('</body>', '<!-- lab:start --><footer>' + DISCLAIMER + '</footer><!-- lab:end --></body>')
        p.write_text(s, encoding='utf-8')

    weights = read_csv('vol_target_monthly_weights.csv')
    primary = read_csv('vol_target_oos_summary.csv')[0]['trial_id']
    latest = max((r for r in weights if r['trial_id'] == primary), key=lambda r: r['date'])
    snapshot = DATA / 'latest_weights_snapshot.csv'
    with snapshot.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['strategy_id', 'decision_date', 'eval_date', 'ticker', 'weight', 'basis'])
        for ticker, weight in [('VOO', .7), ('QQQM', .2), ('IJR', .1)]:
            writer.writerow(['static_option_a', '', '', ticker, weight, 'static research template'])
        for ticker in ['VOO', 'QQQM', 'IJR', 'BIL']:
            writer.writerow(['vol_target_option_a', latest['date'], latest['eval_date'], ticker,
                             latest['w_' + ticker], 'historical OOS sample: ' + primary])
    books = table(['ID', 'Book', 'Research role'], [
        ['static_option_a', 'Static Option A', 'VOO 70% / QQQM 20% / IJR 10%'],
        ['vol_target_option_a', 'Vol-target Option A', 'Default research recommended path: f_max=1, cash=BIL; Moreira & Muir (2017)'],
        ['score_rotate_xsd', 'ScoreSimple XSD sleeve', 'Optional thematic research sleeve'],
    ], 'CIO shortlist — three research books')
    page('books.html', 'Books / strategies', books +
         '<p><code>m3_p2</code> is held off. The default recommendation above concerns '
         'the research workflow only.</p><p>Weights refresh via <code>run-strategies --asof</code>. '
         'Until refreshed artifacts are published, this snapshot shows the static template and '
         'the latest decision month in the archived primary vol-target trial; it is not a live allocation.</p>'
         + csv_table(snapshot))
    summary = read_csv('vol_target_oos_summary.csv')
    comparison = table(['Trial', 'Metric', 'Vol-target Option A', 'Static Option A'], [
        [r['trial_id'], metric, f"{float(r[metric]):.4f}", f"{float(r['OptionA_' + metric]):.4f}"]
        for r in summary for metric in ['AnnReturn', 'AnnVol', 'MaxDD', 'Sharpe_rf0']
    ], 'OOS comparison (returns, volatility and drawdown in decimal units)')
    content = ('<p>Archived real-BIL run: weights use data through the decision date; '
               'returns evaluate the following period. The final September 2026 observation '
               'ends September 16 and is a partial month.</p>'
               '<p>These results show lower volatility and drawdown, without a statistically '
               'significant return edge in the supplied note. '
               '<a href="data/README_OOS_note.md">Read the OOS note</a>.</p>' + comparison)
    for p in sorted(DATA.glob('*.csv')):
        if p.name == snapshot.name:
            continue
        content += '<section><h2>' + escape(p.stem.replace('_', ' ').title()) + '</h2>' + csv_table(p) + '</section>'
    page('runs.html', 'Out-of-sample runs', content)


if __name__ == '__main__':
    main()
