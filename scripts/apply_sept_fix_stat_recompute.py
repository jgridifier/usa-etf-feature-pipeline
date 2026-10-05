"""Apply Quant's September stats recompute (data/processed/hub/sept_fix_stat_recompute.csv, sha256 pinned).

Scope (CIO/PM ruling 2026-10-04):
- live + docs vol_target_oos_summary.csv: Sharpe_CI_L, Sharpe_CI_U.
- live skew_managed_gatefirst_summary.csv: Sharpe_CI_L/U, OOS_skewness, OOS_pct_neg_months; NW_t_vs_EW/MinVar/ERC
  take the 67-month value (2021-02..2026-08) and are labelled so in NW_t_vs_nulls_window, because those nulls'
  2026-09 still needs a re-run.
- hub/dsr_exbil_recompute.csv: the 86 archived rows ending 2026-09-16 become complete-months-only rows.
Nothing else is touched (comparisons, viz JSON, hub NW/HAC fields, pinned archive summaries). Idempotent.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'data/processed/hub/sept_fix_stat_recompute.csv'
SRC_SHA256 = 'fe8954415fa028f954cc662d79d52689e1c3e6a93caf5233f1ba539a460f1f3c'
SUMMARY_FIELDS = {
    'data/processed/live/vol_target_oos_summary.csv': ['Sharpe_CI_L', 'Sharpe_CI_U'],
    'docs/data/vol_target_oos_summary.csv': ['Sharpe_CI_L', 'Sharpe_CI_U'],
    'data/processed/live/skew_managed_gatefirst_summary.csv': ['Sharpe_CI_L', 'Sharpe_CI_U', 'OOS_skewness', 'OOS_pct_neg_months',
                                                               'NW_t_vs_EW', 'NW_t_vs_MinVar', 'NW_t_vs_ERC'],
}
NULLS_WINDOW = ('2021-02..2026-08 (67 months, to 2026-08): EW / MinVar / ERC null 2026-09 awaits a re-run; '
                "Quant's Sept recompute, sha fe895441")
DSR = ROOT / 'data/processed/hub/dsr_exbil_recompute.csv'
PANEL_BIL = 'data/raw/usa_universe_panel_monthly_returns.csv (BIL, complete months)'
NOT_RECOMPUTED = ['dsr_exbil_blp_ownvar', 'own_registry_var_monthly', 'skew', 'kurt', 'bil_share']


def main() -> None:
    if hashlib.sha256(SRC.read_bytes()).hexdigest() != SRC_SHA256:
        raise SystemExit('sept_fix_stat_recompute.csv does not match its pinned sha256')
    q = pd.read_csv(SRC, dtype=str, keep_default_na=False)
    for rel, fields in SUMMARY_FIELDS.items():
        path = ROOT / rel
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        assert len(df) == 1
        for f in fields:
            row = q[(q.file == rel) & (q.field == f)]
            if rel.startswith('docs/') and row.empty:
                row = q[(q.file == 'data/processed/live/' + Path(rel).name) & (q.field == f)]
            assert len(row) == 1, (rel, f)
            df.at[0, f] = repr(float(row.iloc[0].new_value))
        if 'NW_t_vs_EW' in fields:
            df['NW_t_vs_nulls_window'] = NULLS_WINDOW
        df.to_csv(path, index=False)
    d = pd.read_csv(DSR, dtype=str, keep_default_na=False)
    rows = q[q.field == 'dsr_exbil [complete months only]'].set_index('subject')
    n = 0
    for i in d.index:
        t = d.at[i, 'trial']
        if t not in rows.index:
            continue
        r = rows.loc[t]
        if d.at[i, 'window_end'] == '2026-09-16':
            assert int(d.at[i, 'T']) - 1 == int(r['T']), t
        elif d.at[i, 'window_end'] != '2026-08-31':
            raise SystemExit(f'{t}: unexpected window_end {d.at[i, "window_end"]}')
        m = re.search(r'sharpe_exbil\s+(-?\d+(?:\.\d+)?)\s*->\s*(-?\d+(?:\.\d+)?)', r['method_note'])
        assert m, t
        d.at[i, 'window_end'], d.at[i, 'T'] = '2026-08-31', str(int(r['T']))
        d.at[i, 'dsr_exbil'], d.at[i, 'sharpe_exbil'] = r['new_value'], m.group(2)
        d.at[i, 'rf_file'] = PANEL_BIL
        for c in NOT_RECOMPUTED:
            d.at[i, c] = ''
        n += 1
    assert n == 86, n
    d.to_csv(DSR, index=False, lineterminator='\r\n')  # Quant's file uses CRLF
    print(f'summaries updated; {n} DSR rows rewritten (complete months only)')


if __name__ == '__main__':
    main()
