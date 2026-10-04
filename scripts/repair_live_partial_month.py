"""Rebuild the 2026-09 rows of the live-book files from the complete-month panel (PR A, Sep-core fix).

Cause: the refreshed live books (data/processed/live/) were run with partial months allowed, so the row
labelled 2026-09-30 holds a return built from prices through about 2026-09-16 (+0.2412% for the core),
while the complete-month panel (data/raw/usa_universe_panel_monthly_returns.csv) gives -0.1112%.

Repair (no strategy is re-run):
- In 2026-09 every live book was fully invested (f = 1, f_tilde = 1, zero cost), so each column whose
  2026-09 value equals the partial-month core is mechanically the core; it is set to the complete-month
  panel core, 70/20/10 VOO/QQQM/IJR.
- Active-return columns are re-derived as method minus null.
- Columns that are not the core (EW / MinVar / ERC nulls, m3_p2_core_rotate) cannot be rebuilt without a
  re-run; their 2026-09 value is blanked rather than kept from a partial month.
The log is written to data/processed/live/partial_month_repair.json. Idempotent.

    .venv/bin/python scripts/repair_live_partial_month.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from usa_etf_features import monthly_panel as mp

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / 'data/processed/live'
PANEL = ROOT / 'data/raw/usa_universe_panel_monthly_returns.csv'
MONTH = '2026-09'
BAD_CORE = 0.002411878710272353          # partial-month core in every live file
WEIGHTS = {'VOO': 0.70, 'QQQM': 0.20, 'IJR': 0.10}
LOG = LIVE / 'partial_month_repair.json'


def panel_core() -> float:
    p = mp.load_monthly_panel(PANEL, complete_months_only=True)
    r = p[list(WEIGHTS)].mul(pd.Series(WEIGHTS), axis=1).sum(axis=1, min_count=len(WEIGHTS))
    r.index = p.index.to_period('M').astype(str)
    return float(r.loc[MONTH])


def _fmt(v):
    return '' if v is None or pd.isna(v) else repr(float(v))


def repair_wide(name, core_cols, blank_cols, active, core, log):
    path = LIVE / name
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    rows = df.index[df['date'].str[:7] == MONTH]
    for i in rows:
        for c in core_cols:
            v = df.at[i, c]
            if v and abs(float(v) - BAD_CORE) < 1e-15:
                df.at[i, c] = _fmt(core)
                log.append(dict(file=name, column=c, month=MONTH, was=float(v), now=core, action='rebuilt from panel core'))
            elif v and abs(float(v) - core) > 1e-12:
                raise SystemExit(f'{name}:{c} 2026-09 is neither the partial-month core nor the panel core: {v}')
        for c in blank_cols:
            if df.at[i, c]:
                log.append(dict(file=name, column=c, month=MONTH, was=float(df.at[i, c]), now=None, action='blanked: not the core, needs a re-run'))
                df.at[i, c] = ''
        for c, (a, b) in active.items():
            va, vb = df.at[i, a], df.at[i, b]
            df.at[i, c] = _fmt(float(va) - float(vb)) if va and vb else ''
    df.to_csv(path, index=False)


def repair_long(name, core_ids, blank_ids, core, log):
    path = LIVE / name
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for i in df.index[df['date'].str[:7] == MONTH]:
        sid, v = df.at[i, 'strategy_id'], df.at[i, 'return']
        if sid in core_ids and v and abs(float(v) - BAD_CORE) < 1e-15:
            df.at[i, 'return'] = _fmt(core)
            log.append(dict(file=name, column=f'return[{sid}]', month=MONTH, was=float(v), now=core, action='rebuilt from panel core'))
        elif sid in blank_ids and v:
            df.at[i, 'return'] = ''
            log.append(dict(file=name, column=f'return[{sid}]', month=MONTH, was=float(v), now=None, action='blanked: not the core, needs a re-run'))
    df.to_csv(path, index=False)


def _simple_stats(r: pd.Series) -> dict:
    """Same definitions as the run summaries: CAGR, sample vol x sqrt(12), wealth MaxDD, rf = 0 Sharpe = CAGR / vol."""
    w = (1 + r).cumprod()
    cagr = float(w.iloc[-1] ** (12 / len(r)) - 1)
    vol = float(r.std(ddof=1) * 12 ** 0.5)
    dd = float(min(0.0, (w / w.cummax().clip(lower=1.0) - 1).min()))
    return {'AnnReturn': cagr, 'AnnVol': vol, 'MaxDD': dd, 'Sharpe_rf0': cagr / vol}


def repair_summary(name, returns_name, blocks, log):
    """Refresh the return-derived headline fields (AnnReturn, AnnVol, MaxDD, Sharpe_rf0) of a run summary.
    Test statistics (NW t, CIs, DSR, skew) stay as run."""
    path = LIVE / name
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    ret = pd.read_csv(LIVE / returns_name)
    for prefix, col in blocks.items():
        st = _simple_stats(ret[col].astype(float))
        for k, v in st.items():
            c = prefix + k
            if c in df.columns and abs(float(df.at[0, c]) - v) > 1e-12:
                log.append(dict(file=name, column=c, month=MONTH, was=float(df.at[0, c]), now=v, action='re-derived from the rebuilt returns'))
                df.at[0, c] = repr(v)
    df.to_csv(path, index=False)


def main():
    core = panel_core()
    prior = json.loads(LOG.read_text()) if LOG.exists() else {'changes': []}
    log = []
    repair_wide('vol_target_oos_returns.csv', ['r_vt_gross', 'r_vt', 'r_option_a'], [], {'r_active': ('r_vt', 'r_option_a')}, core, log)
    repair_wide('skew_managed_gatefirst_returns.csv', ['r_method', 'r_method_gross', 'r_null_a', 'r_null_b'],
                ['r_null_c', 'r_null_d', 'r_null_e'],
                {f'r_active_vs_{k}': ('r_method', f'r_null_{k}') for k in 'abcde'}, core, log)
    repair_long('strategy_returns.csv', {'static_option_a', 'vol_target_option_a', 'score_rotate_xsd'}, {'m3_p2_core_rotate'}, core, log)
    repair_summary('vol_target_oos_summary.csv', 'vol_target_oos_returns.csv', {'': 'r_vt', 'OptionA_': 'r_option_a'}, log)
    repair_summary('skew_managed_gatefirst_summary.csv', 'skew_managed_gatefirst_returns.csv',
                   {'': 'r_method', 'Book2_': 'r_null_a', 'OptionA_': 'r_null_b'}, log)
    changes = prior['changes'] + log
    LOG.write_text(json.dumps(dict(
        month=MONTH, cause=('Live books were run with partial months allowed; the 2026-09 row used prices through about '
                            '2026-09-16. Rebuilt from the complete-month panel core where the row is mechanically the core '
                            '(f = 1, f_tilde = 1, zero cost); other columns blanked.'),
        partial_month_core=BAD_CORE, complete_month_panel_core=core, panel=str(PANEL.relative_to(ROOT)),
        changes=changes), indent=1) + '\n')
    print(f'{len(log)} cells changed; log {LOG.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
