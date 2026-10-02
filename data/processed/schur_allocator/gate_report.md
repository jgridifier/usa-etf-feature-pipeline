# Schur complementary allocator (trial 12)

**Label (mechanical + composition): FAIL**
book_eligible: no (gate label is FAIL, not PASS; comparison reported only; Sharpe_exBIL not > Backbone)

## Composition tripwire (cash_like + short_duration + near_cash, default-on)

Status: **PASS** (VOID if the method or the primary null averages > 50% over the OOS window).
- Method `schur_g050`: 0.00%
- Primary null `lw_minvar_156w`: 0.00%

Strategies: `schur_g050` = Schur (γ = 0.5·γ_max); `hrp_g000` = HRP (Schur γ=0); `lw_minvar_156w` = LW MinVar (capped QP); `equal_weight` = Equal weight (capped); `book1_static_option_a` = Book 1 (net rebuild)

Weekly cutoff: covariance windows end at the last weekly row dated on or before CALENDAR month-end t-1. EPO (#43) sliced at the decision date, so for 2018-03 and 2024-03 (month ending on the Thursday before Good Friday) EPO dropped the complete weeks labelled 2018-03-30 and 2024-03-29; this gate includes them. Those weeks close on the Thursday decision date, so this is not look-ahead.

## Tripwires (checked first)

- Effective N (method, post-cap targets): mean 22.875, min 13.515, share of months < 5: 0.00% (VOID if mean < 5).
- Low-vol target share max by strategy: {'equal_weight': 0.041666666666666664, 'hrp_g000': 0.2585233653712902, 'lw_minvar_156w': 0.30000000000000004, 'schur_g050': 0.3} (limit 30%); drifted month-end diagnostic: {'equal_weight': 0.0421991302727994, 'hrp_g000': 0.2561058974622133, 'lw_minvar_156w': 0.3253255046380826, 'schur_g050': 0.30744543018286324}.
- Tripwire status: PASS 

Gamma fallback share of splits: 34.78%; HRP fallback share: 0.04%.
Eligible N per rebalance (min/mean/max): 69 / 81.67 / 93
Skipped months: none
- Caps binding Schur (γ = 0.5·γ_max) (post-hoc pro rata): low-vol 4 months, single-name 0 months.
- Caps binding LW MinVar (capped QP) (QP constraints): low-vol 85 months, single-name 119 months.
- Caps binding HRP (Schur γ=0) (post-hoc pro rata): low-vol 0 months, single-name 0 months.
- Caps binding Equal weight (capped) (post-hoc pro rata): low-vol 0 months, single-name 0 months.
- LW MinVar (capped QP) QP: max KKT gap 1.11e-16, max constraint violation 2.66e-15, 119 solves, all certified.
- Average target share, low-vol (USMV/EFAV/SPHD) | dividend/income equity (DVY/SDY/VYM/DGRO/TMDV/SDIV/PID; reported only, no cap, no tripwire): Equal weight (capped) 3.56% | 7.23%; HRP (Schur γ=0) 15.06% | 12.62%; LW MinVar (capped QP) 28.56% | 21.27%; Schur (γ = 0.5·γ_max) 18.68% | 11.42%

## summary

| strategy_id | period_role | n_months | start | end | CAGR | AnnReturn | AnnVol | Sharpe_exBIL | Sharpe_rf0_legacy | MaxDD | turnover_per_year | turnover_target_per_year_diagnostic | HHI_mean | eff_N_mean | names_held_mean | eff_N_category_mean | largest_single_name | largest_single_name_share | largest_category | largest_category_share | trial_count | DSR_exBIL | sr_var_cross_trial_monthly |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| book1_static_option_a | full window | 71 | 2020-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.17283134744247453 | 0.17283134744247453 | 0.16147511197186876 | 0.8865806870299144 | 1.0703280854363748 | -0.25564187805103256 | 0.1353543261999646 | 0.08450704225352113 | 0.5399999999999998 | 1.8518518518518512 | 3.0 | 1.8518518518518512 | VOO | 0.7 | US Large / Broad Blend | 0.7000000000000007 | 12 | 0.6805670955415313 | 0.014061082169479702 |
| equal_weight | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.11797427845300268 | 0.11797427845300268 | 0.15706281148588047 | 0.6450216454400344 | 0.7511280190193733 | -0.2554818802209785 | 0.17807298034072822 | 0.08028341461610114 | 0.012335332254303064 | 81.67226890756302 | 81.67226890756302 | 6.715941909731479 | ACWI | 0.012335332254303066 | Specialty / Other | 0.2595560333216623 | 12 | 0.45460532685514826 | 0.014061082169479702 |
| hrp_g000 | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.10279915738795808 | 0.10279915738795808 | 0.13699474084499103 | 0.617887027909714 | 0.7503876189252762 | -0.24221848152010517 | 2.3515031410024214 | 2.3439867317702863 | 0.037505877948650033 | 27.32102064947718 | 51.99159663865546 | 4.880543254658325 | EFAV | 0.07893032103775174 | International Developed Equity | 0.3406151006446146 | 12 | 0.42452955902268713 | 0.014061082169479702 |
| lw_minvar_156w | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.08017369943055952 | 0.08017369943055952 | 0.12114837805012113 | 0.5108896508965965 | 0.661781038433633 | -0.2511269192319996 | 0.6272888062632839 | 0.5665473762373341 | 0.16418700590028112 | 6.115688681249325 | 7.420168067226891 | 2.2482316395268995 | EFAV | 0.17223673201116943 | Specialty / Other | 0.500456598217374 | 12 | 0.3133498994322002 | 0.014061082169479702 |
| schur_g050 | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.10235468440523876 | 0.10235468440523876 | 0.13394943150874403 | 0.625669496377814 | 0.7641292930650265 | -0.2354739542146459 | 2.178784028203 | 2.173626297363173 | 0.04527543232792997 | 22.875366297408984 | 53.3109243697479 | 4.238123580780972 | EFAV | 0.1071103714212363 | International Developed Equity | 0.3864805191332721 | 12 | 0.43332745299130904 | 0.014061082169479702 |

## tests

| strategy_id | primary_null | p_one_sided_hac | p_two_sided_hac | p_one_sided_boot | p_two_sided_boot | z_hac | z_boot | se_nat | reps | block_size | seed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| schur_g050 | lw_minvar_156w | 0.13181752205800817 | 0.26363504411601635 | 0.08398320335932813 | 0.1929614077184563 | 1.1178406794769884 | 1.4631337043718882 | 0.022741728741375734 | 5000 | 4 | 20261002 |

## trial_registry

| trial_id | line | window_weeks | status | Sharpe_exBIL_annual | Sharpe_rf0_legacy_recorded | source | preregistered | trial_count | w |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1_invalid_w156 | v1 | 156 | invalid (numerical bug), counted | nan | 0.796 | invalidated v1 legacy record | True | 12 | nan |
| v1_invalid_w260 | v1 | 260 | invalid (numerical bug), counted | nan | 0.733 | invalidated v1 legacy record | True | 12 | nan |
| v1_w156 | v1 | 156 | valid | 0.093356557561721 | nan | data/processed/nonlinear_shrinkage_gmv/oos_returns.csv | True | 12 | nan |
| v1_w260 | v1 | 260 | valid | 0.0383641135374596 | nan | data/processed/nonlinear_shrinkage_gmv/oos_returns.csv | True | 12 | nan |
| v2_w156 | v2 | 156 | valid | -0.4893806276166144 | nan | data/processed/nonlinear_shrinkage_gmv_v2/summary.csv | True | 12 | nan |
| v2_w260 | v2 | 260 | valid | -0.5267547832148654 | nan | data/processed/nonlinear_shrinkage_gmv_v2/summary.csv | True | 12 | nan |
| v3_w156 | v3 | 156 | valid | 0.5282293945809092 | nan | HEAD:data/processed/nonlinear_shrinkage_gmv_v3/summary.csv | True | 12 | nan |
| v3_w260 | v3 | 260 | valid | 0.6115398362811979 | nan | HEAD:data/processed/nonlinear_shrinkage_gmv_v3/summary.csv | True | 12 | nan |
| epo_a_w075 | epo | 156 | valid | 0.2683587476472725 | nan | current EPO full-window method | True | 12 | 0.75 |
| epo_a_w050 | epo | 156 | valid | 0.3539456714511925 | nan | current EPO full-window method | True | 12 | 0.5 |
| epo_a_w090 | epo | 156 | valid | 0.196715936056583 | nan | current EPO full-window method | True | 12 | 0.9 |
| schur_g050 | schur | 156 | valid | 0.625669496377814 | nan | current Schur full-window method | True | 12 | nan |

## name_counts

| decision_date | date | n_eligible | below_floor | skipped |
| --- | --- | --- | --- | --- |
| 2016-10-31 00:00:00 | 2016-11-30 00:00:00 | 69 | False | False |
| 2016-11-30 00:00:00 | 2016-12-30 00:00:00 | 69 | False | False |
| 2016-12-30 00:00:00 | 2017-01-31 00:00:00 | 69 | False | False |
| 2017-01-31 00:00:00 | 2017-02-28 00:00:00 | 69 | False | False |
| 2017-02-28 00:00:00 | 2017-03-31 00:00:00 | 70 | False | False |
| 2017-03-31 00:00:00 | 2017-04-28 00:00:00 | 70 | False | False |
| 2017-04-28 00:00:00 | 2017-05-31 00:00:00 | 70 | False | False |
| 2017-05-31 00:00:00 | 2017-06-30 00:00:00 | 70 | False | False |
| 2017-06-30 00:00:00 | 2017-07-31 00:00:00 | 70 | False | False |
| 2017-07-31 00:00:00 | 2017-08-31 00:00:00 | 70 | False | False |
| 2017-08-31 00:00:00 | 2017-09-29 00:00:00 | 70 | False | False |
| 2017-09-29 00:00:00 | 2017-10-31 00:00:00 | 70 | False | False |
| 2017-10-31 00:00:00 | 2017-11-30 00:00:00 | 72 | False | False |
| 2017-11-30 00:00:00 | 2017-12-29 00:00:00 | 72 | False | False |
| 2017-12-29 00:00:00 | 2018-01-31 00:00:00 | 72 | False | False |
| 2018-01-31 00:00:00 | 2018-02-28 00:00:00 | 72 | False | False |
| 2018-02-28 00:00:00 | 2018-03-29 00:00:00 | 72 | False | False |
| 2018-03-29 00:00:00 | 2018-04-30 00:00:00 | 72 | False | False |
| 2018-04-30 00:00:00 | 2018-05-31 00:00:00 | 73 | False | False |
| 2018-05-31 00:00:00 | 2018-06-29 00:00:00 | 73 | False | False |
| 2018-06-29 00:00:00 | 2018-07-31 00:00:00 | 73 | False | False |
| 2018-07-31 00:00:00 | 2018-08-31 00:00:00 | 74 | False | False |
| 2018-08-31 00:00:00 | 2018-09-28 00:00:00 | 74 | False | False |
| 2018-09-28 00:00:00 | 2018-10-31 00:00:00 | 74 | False | False |
| 2018-10-31 00:00:00 | 2018-11-30 00:00:00 | 74 | False | False |
| 2018-11-30 00:00:00 | 2018-12-31 00:00:00 | 74 | False | False |
| 2018-12-31 00:00:00 | 2019-01-31 00:00:00 | 74 | False | False |
| 2019-01-31 00:00:00 | 2019-02-28 00:00:00 | 74 | False | False |
| 2019-02-28 00:00:00 | 2019-03-29 00:00:00 | 75 | False | False |
| 2019-03-29 00:00:00 | 2019-04-30 00:00:00 | 75 | False | False |
| 2019-04-30 00:00:00 | 2019-05-31 00:00:00 | 75 | False | False |
| 2019-05-31 00:00:00 | 2019-06-28 00:00:00 | 76 | False | False |
| 2019-06-28 00:00:00 | 2019-07-31 00:00:00 | 78 | False | False |
| 2019-07-31 00:00:00 | 2019-08-30 00:00:00 | 78 | False | False |
| 2019-08-30 00:00:00 | 2019-09-30 00:00:00 | 78 | False | False |
| 2019-09-30 00:00:00 | 2019-10-31 00:00:00 | 78 | False | False |
| 2019-10-31 00:00:00 | 2019-11-29 00:00:00 | 78 | False | False |
| 2019-11-29 00:00:00 | 2019-12-31 00:00:00 | 78 | False | False |
| 2019-12-31 00:00:00 | 2020-01-31 00:00:00 | 79 | False | False |
| 2020-01-31 00:00:00 | 2020-02-28 00:00:00 | 80 | False | False |
| 2020-02-28 00:00:00 | 2020-03-31 00:00:00 | 80 | False | False |
| 2020-03-31 00:00:00 | 2020-04-30 00:00:00 | 80 | False | False |
| 2020-04-30 00:00:00 | 2020-05-29 00:00:00 | 80 | False | False |
| 2020-05-29 00:00:00 | 2020-06-30 00:00:00 | 80 | False | False |
| 2020-06-30 00:00:00 | 2020-07-31 00:00:00 | 80 | False | False |
| 2020-07-31 00:00:00 | 2020-08-31 00:00:00 | 80 | False | False |
| 2020-08-31 00:00:00 | 2020-09-30 00:00:00 | 80 | False | False |
| 2020-09-30 00:00:00 | 2020-10-30 00:00:00 | 81 | False | False |
| 2020-10-30 00:00:00 | 2020-11-30 00:00:00 | 81 | False | False |
| 2020-11-30 00:00:00 | 2020-12-31 00:00:00 | 82 | False | False |
| 2020-12-31 00:00:00 | 2021-01-29 00:00:00 | 82 | False | False |
| 2021-01-29 00:00:00 | 2021-02-26 00:00:00 | 82 | False | False |
| 2021-02-26 00:00:00 | 2021-03-31 00:00:00 | 82 | False | False |
| 2021-03-31 00:00:00 | 2021-04-30 00:00:00 | 82 | False | False |
| 2021-04-30 00:00:00 | 2021-05-28 00:00:00 | 82 | False | False |
| 2021-05-28 00:00:00 | 2021-06-30 00:00:00 | 82 | False | False |
| 2021-06-30 00:00:00 | 2021-07-30 00:00:00 | 82 | False | False |
| 2021-07-30 00:00:00 | 2021-08-31 00:00:00 | 82 | False | False |
| 2021-08-31 00:00:00 | 2021-09-30 00:00:00 | 83 | False | False |
| 2021-09-30 00:00:00 | 2021-10-29 00:00:00 | 83 | False | False |
| 2021-10-29 00:00:00 | 2021-11-30 00:00:00 | 83 | False | False |
| 2021-11-30 00:00:00 | 2021-12-31 00:00:00 | 83 | False | False |
| 2021-12-31 00:00:00 | 2022-01-31 00:00:00 | 84 | False | False |
| 2022-01-31 00:00:00 | 2022-02-28 00:00:00 | 84 | False | False |
| 2022-02-28 00:00:00 | 2022-03-31 00:00:00 | 84 | False | False |
| 2022-03-31 00:00:00 | 2022-04-29 00:00:00 | 84 | False | False |
| 2022-04-29 00:00:00 | 2022-05-31 00:00:00 | 84 | False | False |
| 2022-05-31 00:00:00 | 2022-06-30 00:00:00 | 84 | False | False |
| 2022-06-30 00:00:00 | 2022-07-29 00:00:00 | 84 | False | False |
| 2022-07-29 00:00:00 | 2022-08-31 00:00:00 | 85 | False | False |
| 2022-08-31 00:00:00 | 2022-09-30 00:00:00 | 85 | False | False |
| 2022-09-30 00:00:00 | 2022-10-31 00:00:00 | 85 | False | False |
| 2022-10-31 00:00:00 | 2022-11-30 00:00:00 | 85 | False | False |
| 2022-11-30 00:00:00 | 2022-12-30 00:00:00 | 85 | False | False |
| 2022-12-30 00:00:00 | 2023-01-31 00:00:00 | 85 | False | False |
| 2023-01-31 00:00:00 | 2023-02-28 00:00:00 | 85 | False | False |
| 2023-02-28 00:00:00 | 2023-03-31 00:00:00 | 85 | False | False |
| 2023-03-31 00:00:00 | 2023-04-28 00:00:00 | 85 | False | False |
| 2023-04-28 00:00:00 | 2023-05-31 00:00:00 | 85 | False | False |
| 2023-05-31 00:00:00 | 2023-06-30 00:00:00 | 85 | False | False |
| 2023-06-30 00:00:00 | 2023-07-31 00:00:00 | 86 | False | False |
| 2023-07-31 00:00:00 | 2023-08-31 00:00:00 | 86 | False | False |
| 2023-08-31 00:00:00 | 2023-09-29 00:00:00 | 87 | False | False |
| 2023-09-29 00:00:00 | 2023-10-31 00:00:00 | 87 | False | False |
| 2023-10-31 00:00:00 | 2023-11-30 00:00:00 | 87 | False | False |
| 2023-11-30 00:00:00 | 2023-12-29 00:00:00 | 87 | False | False |
| 2023-12-29 00:00:00 | 2024-01-31 00:00:00 | 87 | False | False |
| 2024-01-31 00:00:00 | 2024-02-29 00:00:00 | 87 | False | False |
| 2024-02-29 00:00:00 | 2024-03-28 00:00:00 | 87 | False | False |
| 2024-03-28 00:00:00 | 2024-04-30 00:00:00 | 87 | False | False |
| 2024-04-30 00:00:00 | 2024-05-31 00:00:00 | 87 | False | False |
| 2024-05-31 00:00:00 | 2024-06-28 00:00:00 | 87 | False | False |
| 2024-06-28 00:00:00 | 2024-07-31 00:00:00 | 87 | False | False |
| 2024-07-31 00:00:00 | 2024-08-30 00:00:00 | 87 | False | False |
| 2024-08-30 00:00:00 | 2024-09-30 00:00:00 | 87 | False | False |
| 2024-09-30 00:00:00 | 2024-10-31 00:00:00 | 87 | False | False |
| 2024-10-31 00:00:00 | 2024-11-29 00:00:00 | 87 | False | False |
| 2024-11-29 00:00:00 | 2024-12-31 00:00:00 | 88 | False | False |
| 2024-12-31 00:00:00 | 2025-01-31 00:00:00 | 88 | False | False |
| 2025-01-31 00:00:00 | 2025-02-28 00:00:00 | 88 | False | False |
| 2025-02-28 00:00:00 | 2025-03-31 00:00:00 | 88 | False | False |
| 2025-03-31 00:00:00 | 2025-04-30 00:00:00 | 88 | False | False |
| 2025-04-30 00:00:00 | 2025-05-30 00:00:00 | 88 | False | False |
| 2025-05-30 00:00:00 | 2025-06-30 00:00:00 | 90 | False | False |
| 2025-06-30 00:00:00 | 2025-07-31 00:00:00 | 90 | False | False |
| 2025-07-31 00:00:00 | 2025-08-29 00:00:00 | 90 | False | False |
| 2025-08-29 00:00:00 | 2025-09-30 00:00:00 | 90 | False | False |
| 2025-09-30 00:00:00 | 2025-10-31 00:00:00 | 91 | False | False |
| 2025-10-31 00:00:00 | 2025-11-28 00:00:00 | 92 | False | False |
| 2025-11-28 00:00:00 | 2025-12-31 00:00:00 | 92 | False | False |
| 2025-12-31 00:00:00 | 2026-01-30 00:00:00 | 92 | False | False |
| 2026-01-30 00:00:00 | 2026-02-27 00:00:00 | 92 | False | False |
| 2026-02-27 00:00:00 | 2026-03-31 00:00:00 | 92 | False | False |
| 2026-03-31 00:00:00 | 2026-04-30 00:00:00 | 92 | False | False |
| 2026-04-30 00:00:00 | 2026-05-29 00:00:00 | 92 | False | False |
| 2026-05-29 00:00:00 | 2026-06-30 00:00:00 | 92 | False | False |
| 2026-06-30 00:00:00 | 2026-07-31 00:00:00 | 93 | False | False |
| 2026-07-31 00:00:00 | 2026-08-31 00:00:00 | 93 | False | False |
| 2026-08-31 00:00:00 | 2026-09-30 00:00:00 | 93 | False | False |

## Book comparison (reported only; 2021-02..2026-09, 68 months, net vs net)

| series | n_months | start | end | Sharpe_exBIL | MaxDD | CAGR |
| --- | --- | --- | --- | --- | --- | --- |
| Schur (γ = 0.5·γ_max) | 68 | 2021-02-28 | 2026-09-30 | 0.5687006311798865 | -0.21967994703165317 | 0.09771423768023157 |
| Book 1 (net rebuild) | 68 | 2021-02-28 | 2026-09-30 | 0.7655730238954345 | -0.25564187805103267 | 0.1495717307043365 |
| backbone | 68 | 2021-02-28 | 2026-09-30 | 0.861515938631069 | -0.201285918526651 | 0.15073070287175083 |
| book2 | 68 | 2021-02-28 | 2026-09-30 | 0.9966514803641031 | -0.10116624654920847 | 0.13924407813595652 |

Criteria: {'criteria': {'c1': False, 'c2': True, 'c3': False, 'c4': False}, 'mechanical': 'FAIL', 'failing_criteria': ['c1', 'c3', 'c4']}
DSR: Bailey–López de Prado (2014), N=12, registry cross-trial variance. One run; no sensitivities.

## Monthly panel provenance

- source: usa_universe_panel_monthly_returns.csv
- complete_months_only: True
- dropped_partial_month: none
- source_asof: 2026-09-30
