"""Presentation-only power note for the Schur results page's Book comparisons (CIO copy, 2026-10-02).

For each Book comparison (Schur vs the Backbone, Book 1 and Book 2) on the same common window the
gate used (from 2021-02, months common to all four series), compute the month count, the LW2008
HAC standard error of the Sharpe difference (monthly, x sqrt(12) annualized) and the minimum
detectable annualized Sharpe gap at one-sided 5% size and 80% power: (z_0.95 + z_0.80) * SE_ann.

Reads the committed gate output (oos_returns.csv) and the live reference series; it does not
rerun or modify the gate, its label, criteria or trial count. Writes book_power.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from usa_etf_features import gate_metrics as gm
from usa_etf_features import schur_allocator as sa

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'data/processed/schur_allocator'
ALPHA, POWER = 0.05, 0.80
COMPARATORS = (('backbone', 'Backbone'), (sa.BOOK1, 'Book 1'), ('book2', 'Book 2'))


def common_series(oos: pd.DataFrame) -> tuple[dict[str, pd.Series], list[pd.Period]]:
    series = {sid: oos.loc[oos.strategy_id.eq(sid)].set_index('date')['return'] for sid in (sa.METHOD, sa.BOOK1)}
    series['backbone'] = sa._load_reference(ROOT / sa.BACKBONE_PATH, 'r_vt')
    series['book2'] = sa._load_reference(ROOT / sa.BOOK2_PATH, 'r_method')
    by_month = {k: s.set_axis(pd.DatetimeIndex(s.index).to_period('M')) for k, s in series.items()}
    common = sorted(set.intersection(*(set(s.index) for s in by_month.values())))
    common = [p for p in common if p >= pd.Period(sa.BOOK_WINDOW_START, 'M')]
    out = {}
    for k, s in by_month.items():
        r = s.loc[common]
        r.index = r.index.to_timestamp('M')
        out[k] = r
    return out, common


def compute(rf: pd.DataFrame | None = None) -> dict:
    oos = pd.read_csv(OUT_DIR / 'oos_returns.csv', parse_dates=['date'])
    series, common = common_series(oos)
    gate = json.loads((OUT_DIR / 'gate_result.json').read_text())
    gate_n = gate['fields']['book_eligible'].get('n_months')
    if gate_n is not None and gate_n != len(common):
        raise SystemExit(f'common window {len(common)} months != gate book window {gate_n}')
    rf = gm.risk_free_monthly() if rf is None else rf
    z = float(norm.ppf(1 - ALPHA) + norm.ppf(POWER))
    rows = {}
    for key, label in COMPARATORS:
        t = sa.lw2008_sharpe_test(series[sa.METHOD], series[key], rf)
        se_ann = t['se_hac'] * np.sqrt(12)
        rows[key] = dict(label=label, n_months=int(t['n']), se_hac_monthly=t['se_hac'], se_hac_annual=float(se_ann),
                         sharpe_gap_annual=float(t['diff_monthly'] * np.sqrt(12)),
                         detectable_gap_annual=float(z * se_ann), z=t['z'], p_one_sided=t['p_one_sided_a_gt_b'])
    gaps = [r['detectable_gap_annual'] for r in rows.values()]
    payload = dict(
        note=('Presentation only (CIO copy 2026-10-02). Not a gate output: does not change the label, criteria, '
              'book_eligible or trial count. Derived from the committed oos_returns.csv and the live reference series.'),
        method=('LW2008 HAC (QS kernel, prewhitened) SE of the monthly Sharpe difference, Schur minus comparator, '
                'on excess-of-BIL returns; annualized x sqrt(12); detectable gap = (z_0.95 + z_0.80) x SE_ann.'),
        alpha_one_sided=ALPHA, power=POWER, z_sum=z, method_id=sa.METHOD,
        window=f'{common[0]}..{common[-1]}', n_months=len(common),
        detectable_gap_min=float(min(gaps)), detectable_gap_max=float(max(gaps)),
        comparisons=rows,
    )
    return payload


def main() -> None:
    payload = compute()
    (OUT_DIR / 'book_power.json').write_text(json.dumps(payload, indent=2) + '\n')
    print(json.dumps(payload, indent=2))


if __name__ == '__main__':
    main()
