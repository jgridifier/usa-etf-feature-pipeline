"""Rebuild growth_alpha_adj_close.csv from the full adjusted-close history (removes the 2026-09-16 partial-day splice).

The September refresh spliced growth_alpha_adj_close.csv: its 2026-09-16 row is a partial-day snapshot and the rows
after it were chained onto it, so 2026-09-16 daily returns are off by 0.1 to 1.1 points. The full history,
/workspace/investments/usa_universe_adj_close.csv (sha256 631022f3…, the file the committed monthly / weekly panels
were built from), has every one of the 29 tickers on the same dates. This script rebuilds the 29 columns from it,
using the full file's own cell text, so the two files' daily returns are identical by construction. It checks the
result (same dates, same missing cells, every daily return within 1e-6 of the full file, no duplicate or
out-of-order rows), keeps a .bak of the old file next to it, and writes
data/processed/prices_fix_2026-10/growth_alpha_fix_record.json. docs/data/growth_alpha_adj_close.csv is then copied
from the fixed file by scripts/build_pages.py (one canonical source). Refuses to run twice over a fixed file unless
the result is unchanged (idempotent).

    python scripts/fix_growth_alpha_prices.py
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TARGET = Path('/workspace/investments/growth_alpha_adj_close.csv')
FULL = Path('/workspace/investments/usa_universe_adj_close.csv')
BAK = TARGET.with_name(TARGET.name + '.bak')
DOCS_OLD_SHA = '6af174a5a0f9096e68e22a9a25695ba770c9877e1c761abe121432835b7c6d5c'   # docs copy at main e0ff4e3 (= the spliced file)
SAMPLE = ROOT / 'data/raw/growth_alpha_adj_close_sample.csv'   # committed CI/demo slice of the same file
SAMPLE_OLD_SHA = 'ee4302a18eb6ad18e3baef133c91b486e096b232b2e9b466c29b238b60d6530e'
RECORD = ROOT / 'data/processed/prices_fix_2026-10/growth_alpha_fix_record.json'
SPLICED_SHA = '6af174a5a0f9096e68e22a9a25695ba770c9877e1c761abe121432835b7c6d5c'
TOL = 1e-6


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def daily_return_diff(a: pd.DataFrame, b: pd.DataFrame):
    ra, rb = a.pct_change(fill_method=None), b.pct_change(fill_method=None)
    d = (ra - rb).abs()
    stacked = d.stack()
    if stacked.empty or float(stacked.max()) == 0.0:
        return 0.0, None, None
    (date, ticker) = stacked.idxmax()
    return float(stacked.max()), str(ticker), str(date)


def structure(df: pd.DataFrame) -> dict:
    idx = list(df.index)
    return dict(rows=len(idx), duplicates=int(pd.Index(idx).duplicated().sum()), sorted=idx == sorted(idx),
                first=idx[0], last=idx[-1], weekend_rows=int(sum(pd.Timestamp(d).weekday() >= 5 for d in idx)))


def main() -> None:
    source = BAK if BAK.exists() else TARGET          # always rebuild from the original spliced file's shape
    if sha(source) != SPLICED_SHA:
        raise SystemExit(f'{source} is not the recorded spliced file (sha {sha(source)})')
    old_text = source.read_text()
    header = old_text.splitlines()[0].split(',')
    tickers = header[1:]
    old = pd.read_csv(io.StringIO(old_text), index_col=0, float_precision='round_trip')
    rows = {}
    with FULL.open(newline='') as fh:
        rd = csv.reader(fh)
        fh_header = next(rd)
        pos = [fh_header.index(t) for t in tickers]
        for r in rd:
            rows[r[0]] = [r[i] for i in pos]
    missing = [d for d in old.index if d not in rows]
    if missing:
        raise SystemExit(f'full file lacks {len(missing)} growth dates, e.g. {missing[:3]}')
    out = io.StringIO()
    out.write(','.join(header) + '\n')
    for d in old.index:
        out.write(','.join([d] + rows[d]) + '\n')
    new_text = out.getvalue()
    new = pd.read_csv(io.StringIO(new_text), index_col=0, float_precision='round_trip')
    full = pd.read_csv(FULL, index_col=0, usecols=['Date'] + tickers, float_precision='round_trip').loc[new.index, tickers]
    nan_mismatch = int((old.isna() != new.isna()).sum().sum())
    worst_new = daily_return_diff(new, full)
    worst_old = daily_return_diff(old, full)
    st = structure(new)
    assert st['duplicates'] == 0 and st['sorted'] and st['weekend_rows'] == 0 and nan_mismatch == 0, st
    assert worst_new[0] <= TOL, worst_new
    if not BAK.exists():
        shutil.copy2(TARGET, BAK)
    TARGET.write_text(new_text)
    # The committed sample is a verbatim slice (2020-01-02..2026-09-16, same columns) of the old spliced file, so its
    # last row was the partial-day 2026-09-16 snapshot. Re-slice it from the fixed file on the same dates.
    if sha(SAMPLE) not in (SAMPLE_OLD_SHA,):
        sample_dates = pd.read_csv(io.StringIO(subprocess.run(
            ['git', 'show', 'e0ff4e3:data/raw/growth_alpha_adj_close_sample.csv'], cwd=ROOT, check=True,
            capture_output=True, text=True).stdout), usecols=[0]).iloc[:, 0].tolist()
    else:
        sample_dates = pd.read_csv(SAMPLE, usecols=[0]).iloc[:, 0].tolist()
    lines = {ln.split(',', 1)[0]: ln for ln in new_text.splitlines()[1:]}
    SAMPLE.write_text('\n'.join([new_text.splitlines()[0]] + [lines[d] for d in sample_dates]) + '\n')
    # Per-day view of what changed: days where the old file's daily return was off by more than 1e-6.
    ro, rf = old.pct_change(fill_method=None), full.pct_change(fill_method=None)
    bad = (ro - rf).abs().max(axis=1)
    record = dict(
        target=str(TARGET), backup=str(BAK), full_history=str(FULL), full_history_sha256=sha(FULL),
        old_sha256=SPLICED_SHA, new_sha256=sha(TARGET), old_rows=len(old), new_rows=len(new), columns=len(tickers),
        tickers=tickers, structure=st, missing_cell_pattern_changed=nan_mismatch,
        tolerance=TOL,
        worst_daily_return_diff_after=dict(diff=worst_new[0], ticker=worst_new[1], date=worst_new[2]),
        worst_daily_return_diff_before=dict(diff=worst_old[0], ticker=worst_old[1], date=worst_old[2]),
        days_off_by_more_than_tol_before=int((bad > TOL).sum()),
        days_off_by_more_than_1e_4_before=[str(d) for d in bad.index[bad > 1e-4]],
        docs_copy='docs/data/growth_alpha_adj_close.csv (copied byte-for-byte by scripts/build_pages.py)',
        docs_copy_old_sha256=DOCS_OLD_SHA, docs_copy_new_sha256=sha(TARGET),
        docs_copy_old_rows=len(old), docs_copy_new_rows=len(new),
        sample='data/raw/growth_alpha_adj_close_sample.csv (same dates re-sliced from the fixed file)',
        sample_old_sha256=SAMPLE_OLD_SHA, sample_new_sha256=sha(SAMPLE), sample_rows=len(sample_dates),
        method=('29 columns rebuilt on the same dates from the full history file, cell text copied verbatim; '
                'no other change.'),
    )
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, indent=1) + '\n')
    print(json.dumps({k: record[k] for k in ('old_sha256', 'new_sha256', 'worst_daily_return_diff_before',
                                              'worst_daily_return_diff_after', 'days_off_by_more_than_tol_before',
                                              'days_off_by_more_than_1e_4_before')}, indent=1))


if __name__ == '__main__':
    main()
