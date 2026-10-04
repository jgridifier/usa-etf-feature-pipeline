# Notes for QUANT_sept_fix_stat_recompute.csv (204 data rows)

This is research only, not investment advice. Produced 2026-10-04 (ET) by `stage2_code/sept_fix_stat_recompute.py` (sha256 `3de21302…db7361`).

- **Source commit:** main `0797179`, the merge of #56. Its tree is identical to `pr56` / `0d5c351` (tree `7b86ca09…`; `git diff pr56 origin/main` is empty).
- **Original inputs for the reproduction check:** commit `111fbc7`, the live refresh with the partial September. #53's main is `85002a8`; it was used for the 67-month strategy comparison.
- **Python:** pandas 3.0.6, scipy 1.18.1 and numpy 2.5.3, with the repo's own `src/` functions imported unchanged.

## Method
- **NW t:** `vol_target.newey_west_tstat`, lags = 3 (Bartlett), on the repo's active-return columns. The strategy comparison uses `strategy_registry.comparison_frame` with `static_option_a` as the benchmark.
- **Bootstrap Sharpe CI:** `vol_target.block_bootstrap_sharpe_ci` on the rf = 0 Sharpe. It uses circular-wrap 3-month blocks, seed = 7, and the 2.5 / 97.5 percentiles.
  - B = 1000 for the vol-target backbone (the `summarize_trial` default).
  - B = 500 for the skew-managed Book 2 (the `summarize_skew_managed` default).
- **Distribution stats (Book 2):** `scipy.stats.skew`, the repo's `cvar_at_level`, and the share of months below zero.
- **DSR:** the repo's `deflated_sharpe_approx`, with SR0 = z(1−1/N)/√(T−1), on the monthly ex-BIL Sharpe. Each row's recorded `N_used` is kept, and the convention matches `QUANT_dsr_exbil_recompute.csv`.
  - Recorded values used `bil_monthly_asof_20260916.csv`. New values use the complete-month panel BIL (2026-09 = 0.2845%).
  - **`[complete months only]`:** drops the partial 2026-09-16 row, the hub's own load rule. This is computable for all 86 rows. **This is the value I recommend publishing.**
  - **`[2026-09 rebuilt]`:** sensitivity only. It applies only where the archived September row is mechanically the core (f̃ = 1 and gross = the partial core). In those rows, r = complete-month core (−0.11123%) minus the recorded cost; the cost was set at the 2026-08-31 decision, so it doesn't depend on September prices.
    - This applies to 64 of the 86 rows.
    - The other 22 (f̃ < 1, or RR-ERC's non-core construction) would need a re-run, so their new value is left blank.
- **Labels:** derived for reference only, not as gates:
  - NW t: |t| ≥ 1.96.
  - CI: whether the lower bound is above 0.
  - DSR: ≥ 0.95.

## Reproduction check: 204 of 204 reproduced
Full results are in `stage2_code/results/sept_fix_repro_check.csv`.
- **Live vol-target and Book 2 summaries:** every NW t, CI, skew, CVaR and pct-negative value on the `111fbc7` inputs reproduces the recorded value to within 5e-15. The values on main are byte-identical to the as-run values, which confirms they still embed the partial September.
- **Strategy comparison NW t:** reproduced exactly on both the `111fbc7` inputs (68 months, partial) and the `85002a8` inputs (67 months).
- **DSR ex-BIL (86 rows ending 2026-09-16):** `dsr_exbil` and `sharpe_exbil` reproduce to within 5e-6, the 6-significant-figure rounding of the stored CSV.
- **Hub JSON:** rebuilt with `scripts/build_hub_data.py` on `0797179`. The result is byte-identical to the committed `data/processed/hub/`. The hub repairs the live core and drops partial months when it loads data, so its NW t, HAC Sharpe tests and p-values are already correct. The only exception is the DSRs it reads from `dsr_exbil_recompute.csv`.

## Results
- **No label or verdict flips** in any of the 204 rows.
- **NW t vs the core or Book 2:** unchanged to 1e-14. In September 2026 the method and the core are the same series, so the active return is 0 both before and after the fix.
- **NW t vs EW / MinVar / ERC (Book 2), the largest change:** 2.103 → 1.990.
  - **This is blocked for 68 months.** The 2026-09 values of the nulls `r_null_c..e` are blank on main because they need a re-run.
  - The new value is the 67-month figure (2021-02 to 2026-08), which matches `book2.json vs_nulls`. All three stay above 1.96.
- **Bootstrap Sharpe CI:** the largest change is 0.014 (Book 2 upper bound, 2.235 → 2.221). Both lower bounds stay above 0.
- **Distribution stats (Book 2):**
  - Skew moves 0.158 → 0.162.
  - The share of negative months moves 0.338 → 0.353 (23 → 24 of 68).
  - CVaR5 is unchanged.
- **DSR ex-BIL, complete months only:** the largest change is +0.034 (VCFC C6 g0.25), and every change is between +0.0001 and +0.034.
  - **Hub-displayed:** the #6 grid row (Backbone, Book 2 and the skew-overlay reference) goes 0.533 → 0.563 (T = 67; the rebuilt sensitivity, T = 68, gives 0.555), so the display changes from **0.53 to 0.56**.
  - VCFC (chosen) goes 0.663 → 0.690, displayed **0.66 → 0.69**.
  - RR-ERC pathB goes 0.99933 → 0.99944.
  - All are still below 0.95 except RR-ERC, which still passes.

## Not reproducible or not computable (no guesses made)
- **Book 2 NW t vs EW / MinVar / ERC over 68 months:** needs a re-run of the null for September.
- **DSR `[2026-09 rebuilt]` for 22 rows:** needs a re-run of each trial.
- **PSR:** no numeric PSR field exists in any live, hub or docs file. It appears only as text ("PSR only").
- **DSR with N = 1:** the vol-target and Book 2 gate-first specs are blank by design.

## Files Developer must update
1. `data/processed/live/vol_target_oos_summary.csv` and its copy `docs/data/vol_target_oos_summary.csv`: `Sharpe_CI_L` and `Sharpe_CI_U`. `NW_t_vs_OptionA` is unchanged.
2. `data/processed/live/skew_managed_gatefirst_summary.csv`:
   - Update `Sharpe_CI_L`, `Sharpe_CI_U`, `OOS_skewness` and `OOS_pct_neg_months`.
   - For `NW_t_vs_EW/MinVar/ERC`, use the 67-month value labelled "to 2026-08", or re-run the nulls. If the nulls are re-run, `EW/MinVar/ERC_AnnReturn` and `EW/MinVar/ERC_Sharpe_rf0` also need re-deriving; they likewise still use the partial month and are outside this stat scope.
3. `data/processed/hub/dsr_exbil_recompute.csv`:
   - Rewrite the 86 rows ending 2026-09-16 with the complete-months-only values: `window_end` 2026-08-31, T−1, and `rf_file` set to panel BIL.
   - Update the sha pin `RECOMPUTE_SHA256` in `tests/test_hub_data.py`, plus `dsr_exbil_recompute.PROVENANCE.md`.
   - Then re-run `build_hub_data.py`. That changes `dsr` and `gates` in `backbone`, `book2`, `skew_overlay`, `vcfc` and `rr_erc.json`; the grid-reference window becomes 2021-02 to 2026-08, 67 months.
4. **No change needed:** `docs/data/strategy_comparison.csv`, `docs/data/cio_book_shortlist/run_latest/strategy_comparison.csv`, both `shortlist_comparison.csv` copies, `viz_comparison.json`, `viz_metrics.json` and hub NW / HAC fields are already current, with delta 0.
5. **Leave as they are:** the frozen archives with a 2026-09-16 row are pinned by `tests/data/archived_csv_sha256.json`. They are `ft_med`, `nls_v3`, `rr_erc`, `skewness_managed` (both summaries), `vol_cond_factor_corr` (and its docs copy), and `data/processed/vol_target_oos_summary.csv`. The hub drops their partial month.
6. **Pinned documents:** Addendum 3 E6 and the recheck note cite 0.533. Add a build-time lab note, as for A6; don't edit or re-hash them.

## sha256
| File | sha256 |
|---|---|
| QUANT_sept_fix_stat_recompute.csv | `fe8954415fa028f954cc662d79d52689e1c3e6a93caf5233f1ba539a460f1f3c` |
| results/sept_fix_repro_check.csv | `75ff455f5d270ebd184da806822804caaede3d22656a32e8598abc947463d46e` |
| live/vol_target_oos_returns.csv @0797179 | `a0e76aa34212821d4cad5b5dd6d473696af4997139129078afa0279cceb452c6` |
| live/vol_target_oos_summary.csv @0797179 | `dee50a537e650f15ee680e6aa60279ab98d1127aa30188b4ae4bf1bd36cda09d` |
| live/skew_managed_gatefirst_returns.csv @0797179 | `dfee6ca05ef24a847c13d9b9cecd2275846d5ad31a8e056e444f40f323703f02` |
| live/skew_managed_gatefirst_summary.csv @0797179 | `0e95eab5d021042331a0aa1a131e6e879a76711530c2ea230219d6d489d35ad2` |
| live/strategy_returns.csv @0797179 | `6894c538852f3e329e4c68aca6a79c0354b085ff02480e0f28df0fed7ba2f628` |
| raw/usa_universe_panel_monthly_returns.csv | `8107825beeb01c0239eefe236a329813b1e218b57e9a5ca7618c73c6f10d1642` |
| raw/fred_tb3ms.csv | `ebf04b1ae5bc5729ba3bb2b35dbb0e0c5e22dace36bea0c02632782d625ae6ab` |
| cash_null_audit/bil_monthly_asof_20260916.csv | `34ac9046fc7465e96b114a4f4e5d0a59cf1efb7934ea06178b248ff02ea1723b` |
| hub/dsr_exbil_recompute.csv | `94c122bb05d9c25ef3db113f7cdcc64e63fc2794edc012f9579c00d440c8b8f6` |
| skewness_managed/skew_managed_oos_returns.csv | `5aea8a83995a5c70731f57b6efcde9604bf4aedb50a8e47f666775d9d64c6f27` |
| vol_cond_factor_corr/vol_cfc_oos_returns.csv | `78e73102fce453ab653614708042304f520b933db1f2c6f6794d8c2c4f391936` |
| rr_erc/rr_erc_oos_returns.csv | `b51274109da1d570066c670ca9adeb201d79e79b81927562b621bf7b1f580e4f` |
| 111fbc7 live vol_target_oos_returns.csv | `4ce54896def952eb352ea97d1041684a47f4ad91d6393aa0f7de0e4ffe78028f` |
| 111fbc7 live skew_managed_gatefirst_returns.csv | `ecf474471bf45d87d9bf9f88d8907c93bbfef57ed7ca66e90dd9351812ff089d` |
| 111fbc7 live strategy_returns.csv | `1894fa3a0c1b419cbe85c05c6d4ec76ac7e4a71711f507e8c65e8118969f0d71` |

CSV columns: `subject` holds the strategy or trial id; there is no PSR row (see above).
