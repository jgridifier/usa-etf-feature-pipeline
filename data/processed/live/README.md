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
