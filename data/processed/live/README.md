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
