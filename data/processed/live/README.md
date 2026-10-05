# Refreshed live books

Outputs through the **2026-09-30 close**, with 68 OOS months (2021-02 → 2026-09),
using the same registered specifications; this is **not a new gate**. Frozen
research/gate evidence remains in the parent directories (`../vol_target_*.csv`
and `../skewness_managed/`) and is pinned by `tests/data/archived_csv_sha256.json`.

VT is `VT_option_a_L63_sigexpanding_fmax1p0`: L63, expanding target, f=0.25..1,
priced BIL cash, 5 bps costs. Book 2 is the single
`SM_option_a_vt_L63_SL21_g0p5_realizedamaya_cvar5` spec: skew lookback 21,
realized Amaya / CVaR5 / g_min=0.5, same backbone and costs. No grid was rerun.
The frozen research VT used cash=0; this live VT matches the site's BIL convention.

`cio_registry.yaml` preserves the original four CIO specs (including unconditional
VT); `strategy_returns.csv` is their refreshed run output. The site command
`.venv/bin/python scripts/reconcile_cash_null_audit.py --site-only --live-dir data/processed/live`
refreshes books, VT and comparison Sharpes with current BIL. Archive Sharpes,
historical cash0 VT and auxiliary gate nulls use the verbatim pre-refresh BIL
column in `../cash_null_audit/bil_monthly_asof_20260916.csv`. Archived reconciliation
and verdict tables remain unchanged. Flat site copies are in `docs/data/`.

## 2026-09 row rebuilt from the complete-month panel (2026-10-04)

The refresh above was run with partial months allowed, so the row labelled 2026-09-30 held a return built from
prices through about 2026-09-16 (core +0.2412%). The complete-month panel gives −0.1112%. In 2026-09 every book was
fully invested (f = 1, f̃ = 1, zero cost), so `scripts/repair_live_partial_month.py` set each core-equivalent column
to the complete-month panel core and re-derived the active columns. Columns that are not the core (the EW / MinVar /
ERC nulls `r_null_c..e` and `m3_p2_core_rotate`) cannot be rebuilt without a re-run, so their 2026-09 value is blank.
Every changed cell is in `partial_month_repair.json`. In the `*_summary.csv` files the return-derived headline
fields (AnnReturn, AnnVol, MaxDD, Sharpe_rf0 for the method, Book 2 and Option A blocks) are re-derived from the
rebuilt returns; test statistics (NW t, CIs, DSR, skew/CVaR) stay as run and still include the partial month. `site_sharpe.json` and `docs/data/live_figures.json` were regenerated
(Book 1 0.7699 → 0.7657, Book 2 0.9967 → 0.9901, vol-target backbone 0.8615 → 0.8567, Sharpe ex-BIL, 2021-02..2026-09).

Restated 2026-10-04: the whole `m3_p2_core_rotate` history was restated on the corrected prices (data restatement, not a new trial; code and params frozen); see `data/processed/prices_fix_2026-10/m3_p2_restatement.json`.

### m3_p2_core_rotate 2026-09 restored from a re-run (2026-10-04)

`m3_p2_core_rotate` was re-run unchanged (frozen code at main 85002a8; the M3/P2 path is identical to the original
refresh 111fbc7) on the complete-month prices (`growth_alpha_adj_close.csv` through 2026-09-30), with only that
registry entry enabled. The other 179 months reproduce the committed returns (max |diff| 1.6e-8), so only the
blank 2026-09 cell was written: −0.2340%. Output, registry, command and the code / input / output sha256 values are
in `m3_p2_rerun_2026-09/` (`rerun_record.json`); `scripts/restore_m3_p2_rerun.py` checks and applies it, and the
repair script no longer blanks the restored value. The strategy comparison is back to 68 months (2021-02..2026-09).

### growth_alpha price fix: m3_p2_core_rotate re-run on the rebuilt file (2026-10-04)

`growth_alpha_adj_close.csv` held a partial-day 2026-09-16 splice, so the 2026-09 m3_p2 value above (−0.2340%) came
from spliced prices. The file was rebuilt from the full adjusted-close history
(`data/processed/prices_fix_2026-10/growth_alpha_fix_record.json`) and every live consumer was re-run unchanged on it
(`data/processed/prices_fix_2026-10/downstream_rerun_check.json`). The core books (vol-target backbone, skew gate-first,
static / vol-target / XSD rows here) reproduce every committed month to ≤ 4.3e-7 and are kept. `m3_p2_core_rotate` does
not: its walk-forward returns move on the ~1e-6 daily differences between the two price vintages, so 56 earlier
months move by more than 1e-6 (max 1.02 points, 2020-03). Its whole series is replaced by the re-run
(`m3_p2_rerun_2026-09/`, `scripts/restore_m3_p2_rerun.py`); 2026-09 is now −0.6847%. Over 2021-02..2026-09
(68 months) its Sharpe (rf 0) moves 0.7576 → 0.7405, ex-BIL 0.6032 → 0.5885 and NW t vs Option A −2.13 → −2.34.

