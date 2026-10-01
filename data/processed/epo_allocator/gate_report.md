# Anchored EPO allocator — PENDING QUANT

**Label (mechanical + composition): FAIL**
book_eligible: no (gate label is FAIL, not PASS; full OOS Sharpe_exBIL is not strictly greater than anchor_ivol; growth-mandate fit: equity share under 50% or not computable)

## Composition tripwire (cash_like + short_duration + near_cash, default-on)

Status: **PASS** (VOID if the method or the primary null averages > 50% over the OOS window).
- Method `epo_a_w075`: 0.00%
- Primary null `lw_minvar_156w`: 0.00%

Observed composition share (cash_like + short_duration + near_cash): method 0.00%, primary null 0.00%; limit <= 50%.

Month counts: full OOS 119 (2016-11-30..2026-09-30; anchor comparison window); Book 1 overlap 71 (2020-11-30..2026-09-30; method restricted to the same months, net vs net).
Book 1 published gross series (reference only, not used for eligibility): data/processed/vol_target_oos_returns.csv r_option_a (published, gross), 68 months 2021-02-26..2026-09-16: CAGR 0.1468, Sharpe_exBIL 0.7491, MaxDD -0.2556.
Turnover: drifted-weight turnover is primary and drives costs for every strategy (including the rebuilt Book 1); turnover_target (vs previous target weights) is a diagnostic.

Monthly panel window: {'start': '1993-01-29', 'end': '2026-09-30', 'n_months': 405}
Eligible N per rebalance (min/mean/max): 101 / 117.46 / 130
Skipped months: none
Sharpe_rf0_legacy is legacy (rf = 0). Category has known mislabels.

## name_counts

| decision_date | date | n_eligible | below_floor | skipped |
| --- | --- | --- | --- | --- |
| 2016-10-31 00:00:00 | 2016-11-30 00:00:00 | 101 | False | False |
| 2016-11-30 00:00:00 | 2016-12-30 00:00:00 | 101 | False | False |
| 2016-12-30 00:00:00 | 2017-01-31 00:00:00 | 101 | False | False |
| 2017-01-31 00:00:00 | 2017-02-28 00:00:00 | 101 | False | False |
| 2017-02-28 00:00:00 | 2017-03-31 00:00:00 | 103 | False | False |
| 2017-03-31 00:00:00 | 2017-04-28 00:00:00 | 104 | False | False |
| 2017-04-28 00:00:00 | 2017-05-31 00:00:00 | 105 | False | False |
| 2017-05-31 00:00:00 | 2017-06-30 00:00:00 | 105 | False | False |
| 2017-06-30 00:00:00 | 2017-07-31 00:00:00 | 105 | False | False |
| 2017-07-31 00:00:00 | 2017-08-31 00:00:00 | 105 | False | False |
| 2017-08-31 00:00:00 | 2017-09-29 00:00:00 | 105 | False | False |
| 2017-09-29 00:00:00 | 2017-10-31 00:00:00 | 105 | False | False |
| 2017-10-31 00:00:00 | 2017-11-30 00:00:00 | 108 | False | False |
| 2017-11-30 00:00:00 | 2017-12-29 00:00:00 | 108 | False | False |
| 2017-12-29 00:00:00 | 2018-01-31 00:00:00 | 108 | False | False |
| 2018-01-31 00:00:00 | 2018-02-28 00:00:00 | 108 | False | False |
| 2018-02-28 00:00:00 | 2018-03-29 00:00:00 | 108 | False | False |
| 2018-03-29 00:00:00 | 2018-04-30 00:00:00 | 108 | False | False |
| 2018-04-30 00:00:00 | 2018-05-31 00:00:00 | 109 | False | False |
| 2018-05-31 00:00:00 | 2018-06-29 00:00:00 | 109 | False | False |
| 2018-06-29 00:00:00 | 2018-07-31 00:00:00 | 109 | False | False |
| 2018-07-31 00:00:00 | 2018-08-31 00:00:00 | 110 | False | False |
| 2018-08-31 00:00:00 | 2018-09-28 00:00:00 | 110 | False | False |
| 2018-09-28 00:00:00 | 2018-10-31 00:00:00 | 110 | False | False |
| 2018-10-31 00:00:00 | 2018-11-30 00:00:00 | 110 | False | False |
| 2018-11-30 00:00:00 | 2018-12-31 00:00:00 | 110 | False | False |
| 2018-12-31 00:00:00 | 2019-01-31 00:00:00 | 110 | False | False |
| 2019-01-31 00:00:00 | 2019-02-28 00:00:00 | 110 | False | False |
| 2019-02-28 00:00:00 | 2019-03-29 00:00:00 | 111 | False | False |
| 2019-03-29 00:00:00 | 2019-04-30 00:00:00 | 111 | False | False |
| 2019-04-30 00:00:00 | 2019-05-31 00:00:00 | 111 | False | False |
| 2019-05-31 00:00:00 | 2019-06-28 00:00:00 | 112 | False | False |
| 2019-06-28 00:00:00 | 2019-07-31 00:00:00 | 114 | False | False |
| 2019-07-31 00:00:00 | 2019-08-30 00:00:00 | 114 | False | False |
| 2019-08-30 00:00:00 | 2019-09-30 00:00:00 | 114 | False | False |
| 2019-09-30 00:00:00 | 2019-10-31 00:00:00 | 114 | False | False |
| 2019-10-31 00:00:00 | 2019-11-29 00:00:00 | 114 | False | False |
| 2019-11-29 00:00:00 | 2019-12-31 00:00:00 | 114 | False | False |
| 2019-12-31 00:00:00 | 2020-01-31 00:00:00 | 115 | False | False |
| 2020-01-31 00:00:00 | 2020-02-28 00:00:00 | 116 | False | False |
| 2020-02-28 00:00:00 | 2020-03-31 00:00:00 | 116 | False | False |
| 2020-03-31 00:00:00 | 2020-04-30 00:00:00 | 116 | False | False |
| 2020-04-30 00:00:00 | 2020-05-29 00:00:00 | 116 | False | False |
| 2020-05-29 00:00:00 | 2020-06-30 00:00:00 | 116 | False | False |
| 2020-06-30 00:00:00 | 2020-07-31 00:00:00 | 116 | False | False |
| 2020-07-31 00:00:00 | 2020-08-31 00:00:00 | 116 | False | False |
| 2020-08-31 00:00:00 | 2020-09-30 00:00:00 | 116 | False | False |
| 2020-09-30 00:00:00 | 2020-10-30 00:00:00 | 117 | False | False |
| 2020-10-30 00:00:00 | 2020-11-30 00:00:00 | 117 | False | False |
| 2020-11-30 00:00:00 | 2020-12-31 00:00:00 | 118 | False | False |
| 2020-12-31 00:00:00 | 2021-01-29 00:00:00 | 118 | False | False |
| 2021-01-29 00:00:00 | 2021-02-26 00:00:00 | 118 | False | False |
| 2021-02-26 00:00:00 | 2021-03-31 00:00:00 | 118 | False | False |
| 2021-03-31 00:00:00 | 2021-04-30 00:00:00 | 118 | False | False |
| 2021-04-30 00:00:00 | 2021-05-28 00:00:00 | 118 | False | False |
| 2021-05-28 00:00:00 | 2021-06-30 00:00:00 | 118 | False | False |
| 2021-06-30 00:00:00 | 2021-07-30 00:00:00 | 118 | False | False |
| 2021-07-30 00:00:00 | 2021-08-31 00:00:00 | 118 | False | False |
| 2021-08-31 00:00:00 | 2021-09-30 00:00:00 | 119 | False | False |
| 2021-09-30 00:00:00 | 2021-10-29 00:00:00 | 119 | False | False |
| 2021-10-29 00:00:00 | 2021-11-30 00:00:00 | 119 | False | False |
| 2021-11-30 00:00:00 | 2021-12-31 00:00:00 | 119 | False | False |
| 2021-12-31 00:00:00 | 2022-01-31 00:00:00 | 120 | False | False |
| 2022-01-31 00:00:00 | 2022-02-28 00:00:00 | 120 | False | False |
| 2022-02-28 00:00:00 | 2022-03-31 00:00:00 | 120 | False | False |
| 2022-03-31 00:00:00 | 2022-04-29 00:00:00 | 120 | False | False |
| 2022-04-29 00:00:00 | 2022-05-31 00:00:00 | 120 | False | False |
| 2022-05-31 00:00:00 | 2022-06-30 00:00:00 | 120 | False | False |
| 2022-06-30 00:00:00 | 2022-07-29 00:00:00 | 120 | False | False |
| 2022-07-29 00:00:00 | 2022-08-31 00:00:00 | 121 | False | False |
| 2022-08-31 00:00:00 | 2022-09-30 00:00:00 | 121 | False | False |
| 2022-09-30 00:00:00 | 2022-10-31 00:00:00 | 121 | False | False |
| 2022-10-31 00:00:00 | 2022-11-30 00:00:00 | 121 | False | False |
| 2022-11-30 00:00:00 | 2022-12-30 00:00:00 | 121 | False | False |
| 2022-12-30 00:00:00 | 2023-01-31 00:00:00 | 121 | False | False |
| 2023-01-31 00:00:00 | 2023-02-28 00:00:00 | 121 | False | False |
| 2023-02-28 00:00:00 | 2023-03-31 00:00:00 | 121 | False | False |
| 2023-03-31 00:00:00 | 2023-04-28 00:00:00 | 121 | False | False |
| 2023-04-28 00:00:00 | 2023-05-31 00:00:00 | 121 | False | False |
| 2023-05-31 00:00:00 | 2023-06-30 00:00:00 | 121 | False | False |
| 2023-06-30 00:00:00 | 2023-07-31 00:00:00 | 122 | False | False |
| 2023-07-31 00:00:00 | 2023-08-31 00:00:00 | 122 | False | False |
| 2023-08-31 00:00:00 | 2023-09-29 00:00:00 | 123 | False | False |
| 2023-09-29 00:00:00 | 2023-10-31 00:00:00 | 123 | False | False |
| 2023-10-31 00:00:00 | 2023-11-30 00:00:00 | 123 | False | False |
| 2023-11-30 00:00:00 | 2023-12-29 00:00:00 | 123 | False | False |
| 2023-12-29 00:00:00 | 2024-01-31 00:00:00 | 123 | False | False |
| 2024-01-31 00:00:00 | 2024-02-29 00:00:00 | 123 | False | False |
| 2024-02-29 00:00:00 | 2024-03-28 00:00:00 | 123 | False | False |
| 2024-03-28 00:00:00 | 2024-04-30 00:00:00 | 123 | False | False |
| 2024-04-30 00:00:00 | 2024-05-31 00:00:00 | 123 | False | False |
| 2024-05-31 00:00:00 | 2024-06-28 00:00:00 | 123 | False | False |
| 2024-06-28 00:00:00 | 2024-07-31 00:00:00 | 123 | False | False |
| 2024-07-31 00:00:00 | 2024-08-30 00:00:00 | 123 | False | False |
| 2024-08-30 00:00:00 | 2024-09-30 00:00:00 | 123 | False | False |
| 2024-09-30 00:00:00 | 2024-10-31 00:00:00 | 123 | False | False |
| 2024-10-31 00:00:00 | 2024-11-29 00:00:00 | 123 | False | False |
| 2024-11-29 00:00:00 | 2024-12-31 00:00:00 | 124 | False | False |
| 2024-12-31 00:00:00 | 2025-01-31 00:00:00 | 124 | False | False |
| 2025-01-31 00:00:00 | 2025-02-28 00:00:00 | 124 | False | False |
| 2025-02-28 00:00:00 | 2025-03-31 00:00:00 | 124 | False | False |
| 2025-03-31 00:00:00 | 2025-04-30 00:00:00 | 124 | False | False |
| 2025-04-30 00:00:00 | 2025-05-30 00:00:00 | 124 | False | False |
| 2025-05-30 00:00:00 | 2025-06-30 00:00:00 | 126 | False | False |
| 2025-06-30 00:00:00 | 2025-07-31 00:00:00 | 126 | False | False |
| 2025-07-31 00:00:00 | 2025-08-29 00:00:00 | 126 | False | False |
| 2025-08-29 00:00:00 | 2025-09-30 00:00:00 | 126 | False | False |
| 2025-09-30 00:00:00 | 2025-10-31 00:00:00 | 127 | False | False |
| 2025-10-31 00:00:00 | 2025-11-28 00:00:00 | 128 | False | False |
| 2025-11-28 00:00:00 | 2025-12-31 00:00:00 | 128 | False | False |
| 2025-12-31 00:00:00 | 2026-01-30 00:00:00 | 128 | False | False |
| 2026-01-30 00:00:00 | 2026-02-27 00:00:00 | 128 | False | False |
| 2026-02-27 00:00:00 | 2026-03-31 00:00:00 | 128 | False | False |
| 2026-03-31 00:00:00 | 2026-04-30 00:00:00 | 128 | False | False |
| 2026-04-30 00:00:00 | 2026-05-29 00:00:00 | 128 | False | False |
| 2026-05-29 00:00:00 | 2026-06-30 00:00:00 | 128 | False | False |
| 2026-06-30 00:00:00 | 2026-07-31 00:00:00 | 129 | False | False |
| 2026-07-31 00:00:00 | 2026-08-31 00:00:00 | 130 | False | False |
| 2026-08-31 00:00:00 | 2026-09-30 00:00:00 | 130 | False | False |

## summary

| strategy_id | period_role | n_months | start | end | CAGR | AnnReturn | AnnVol | Sharpe_exBIL | Sharpe_rf0_legacy | MaxDD | turnover_per_year | turnover_target_per_year_diagnostic | HHI_mean | eff_N_mean | names_held_mean | eff_N_category_mean | largest_single_name | largest_single_name_share | largest_category | largest_category_share | trial_count | DSR_exBIL | sr_var_cross_trial_monthly |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| anchor_ivol | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.07717210490637871 | 0.07717210490637871 | 0.09163318132936525 | 0.6083100944273679 | 0.84218515374897 | -0.16863176770207078 | 0.23438280097537734 | 0.15675477268285334 | 0.015417299925820105 | 66.97761447752433 | 117.46218487394958 | 10.800564615393672 | ISTB | 0.04137326190691522 | Specialty / Other | 0.2098403183911514 | 11 | 0.4501207175774183 | 0.013415584931068366 |
| book1_static_option_a | full window | 71 | 2020-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.17283134744247453 | 0.17283134744247453 | 0.16147511197186876 | 0.8865806870299144 | 1.0703280854363748 | -0.25564187805103256 | 0.1353543261999646 | 0.08450704225352113 | 0.5399999999999998 | 1.8518518518518512 | 3.0 | 1.8518518518518512 | VOO | 0.7 | US Large / Broad Blend | 0.7000000000000007 | 11 | 0.7073384870168552 | 0.013415584931068366 |
| epo_a_w050 | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.037208497421636455 | 0.037208497421636455 | 0.041135403509230124 | 0.35394567145119255 | 0.9045370714131311 | -0.0859425025743491 | 3.0219626003754536 | 3.01161304085029 | 0.2016123909074388 | 5.948284751009158 | 24.394957983193276 | 3.506772608697978 | VCSH | 0.18461903054943893 | Specialty / Other | 0.3012214220972387 | 11 | 0.18778977359471694 | 0.013415584931068366 |
| epo_a_w075 | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.03292767555824505 | 0.03292767555824505 | 0.03854636813662623 | 0.2683587476472725 | 0.8542354870252388 | -0.09413108335733011 | 2.0589298675041414 | 2.0470702097485542 | 0.1628815359219167 | 6.64880442838787 | 38.76470588235294 | 4.118074260688789 | ISTB | 0.19889128838337136 | Specialty / Other | 0.3287658462771309 | 11 | 0.12492404978379312 | 0.013415584931068366 |
| epo_a_w090 | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.030588131733723545 | 0.030588131733723545 | 0.04154609369551225 | 0.196715936056583 | 0.7362456734898191 | -0.11018828792670321 | 1.0975881111437953 | 1.0859706754754483 | 0.10341352544658412 | 9.823244098792374 | 66.81512605042016 | 5.4714981563453975 | ISTB | 0.16291153127385585 | Specialty / Other | 0.29896805427188555 | 11 | 0.08273762955324226 | 0.013415584931068366 |
| equal_weight | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.09834202653470658 | 0.09834202653470658 | 0.12436417923707513 | 0.633630054636155 | 0.7907584574432596 | -0.2172657079363698 | 0.21966883782095697 | 0.07571246610994142 | 0.008548265333917133 | 117.46218487394958 | 117.46218487394958 | 9.14263592367189 | ACWI | 0.008548265333917133 | Specialty / Other | 0.23921076098635083 | 11 | 0.480165931341065 | 0.013415584931068366 |
| erc_lw | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.05743300849902333 | 0.05743300849902333 | 0.0704069367682071 | 0.5042469637769935 | 0.8157294030289035 | -0.1453484994194819 | 0.2919401473324598 | 0.23244087017315695 | 0.025375118817465275 | 44.65791684933989 | 117.46218487394958 | 8.818873160328094 | IEI | 0.0651753273274524 | Specialty / Other | 0.18796604742863376 | 11 | 0.32970355407630275 | 0.013415584931068366 |
| lw_minvar_156w | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.023953527827753396 | 0.023953527827753396 | 0.03485452875564151 | 0.040533523206714536 | 0.6872429116941169 | -0.09995866796892428 | 0.46771844541316415 | 0.45901093847284735 | 0.1557727956350158 | 6.972376305795735 | 15.739495798319327 | 4.2649691911515 | ISTB | 0.20541303099800784 | Specialty / Other | 0.3201203386051852 | 11 | 0.028443820894338973 | 0.013415584931068366 |
| trend_ivol | full window | 119 | 2016-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.06112963381585956 | 0.06112963381585956 | 0.09672824251376907 | 0.42634856941440585 | 0.6319729608150162 | -0.170062767070835 | 2.427409246849698 | 2.4104476850652024 | 0.02710796515897241 | 51.9297926431854 | 77.17647058823529 | 8.659471485223161 | VCSH | 0.0354809818490817 | Specialty / Other | 0.21294748051846513 | 11 | 0.25126495806990984 | 0.013415584931068366 |
| anchor_ivol | sub-period (not a trial) | 68 | 2021-02-26 00:00:00 | 2026-09-30 00:00:00 | 0.07047080919917237 | 0.07047080919917237 | 0.09438344790783734 | 0.438051061594114 | 0.7466437257937963 | -0.1686317677020709 | 0.16454380406691285 | 0.07931186397542381 | 0.013512068626867949 | 75.21876807857434 | 122.79411764705883 | 10.564358555591282 | ISTB | 0.040173842545596104 | Specialty / Other | 0.21245825014235545 | 11 | 0.31202023214470137 | 0.013415584931068366 |
| book1_static_option_a | sub-period (not a trial) | 68 | 2021-02-26 00:00:00 | 2026-09-30 00:00:00 | 0.1495717307043365 | 0.1495717307043365 | 0.15855638724572635 | 0.7655730238954345 | 0.9433346287875134 | -0.25564187805103267 | 0.051236206374884824 | 0.0 | 0.5399999999999999 | 1.8518518518518514 | 3.0 | 1.8518518518518514 | VOO | 0.7 | US Large / Broad Blend | 0.7000000000000006 | 11 | 0.6023315917115333 | 0.013415584931068366 |
| epo_a_w050 | sub-period (not a trial) | 68 | 2021-02-26 00:00:00 | 2026-09-30 00:00:00 | 0.039533900836907776 | 0.039533900836907776 | 0.04707873700018792 | 0.17836572146655807 | 0.8397400473328325 | -0.08594250257434921 | 2.8673987309484454 | 2.8519587686346988 | 0.21405304219205343 | 5.349302324197381 | 21.61764705882353 | 3.433224104127379 | ISTB | 0.2229204190957775 | Specialty / Other | 0.3178615414114976 | 11 | 0.1358686380030693 | 0.013415584931068366 |
| epo_a_w075 | sub-period (not a trial) | 68 | 2021-02-26 00:00:00 | 2026-09-30 00:00:00 | 0.031662611900216575 | 0.031662611900216575 | 0.04416418041942386 | 0.013306608722972615 | 0.7169296837282875 | -0.09413108335733034 | 2.004754817642564 | 1.9874427402477586 | 0.16718721264128833 | 6.39596930942824 | 32.8235294117647 | 4.162684352155766 | ISTB | 0.2299311198138845 | Specialty / Other | 0.3434600891112291 | 11 | 0.06621248647178522 | 0.013415584931068366 |
| epo_a_w090 | sub-period (not a trial) | 68 | 2021-02-26 00:00:00 | 2026-09-30 00:00:00 | 0.02468994045489592 | 0.02468994045489592 | 0.04775726552371666 | -0.12932974783509577 | 0.5169881521511044 | -0.11018828792670288 | 1.0660908721764906 | 1.0522624089642534 | 0.10412332170635052 | 9.75428706478159 | 62.3235294117647 | 5.529138979968777 | ISTB | 0.17910719661660676 | Specialty / Other | 0.3056294971730152 | 11 | 0.03146256542569283 | 0.013415584931068366 |
| equal_weight | sub-period (not a trial) | 68 | 2021-02-26 00:00:00 | 2026-09-30 00:00:00 | 0.09699106907964117 | 0.09699106907964117 | 0.11534398332989539 | 0.5901958907191167 | 0.8408853784963968 | -0.1761436638275362 | 0.16858877002968703 | 0.017011103563581237 | 0.008149503871932275 | 122.79411764705883 | 122.79411764705883 | 8.832098905826227 | ACWI | 0.008149503871932277 | Specialty / Other | 0.2440517341940178 | 11 | 0.4449112532110354 | 0.013415584931068366 |
| erc_lw | sub-period (not a trial) | 68 | 2021-02-26 00:00:00 | 2026-09-30 00:00:00 | 0.0525887069765163 | 0.0525887069765163 | 0.07922638209134508 | 0.2905564456768478 | 0.6637777163152985 | -0.1453484994194819 | 0.21978219002999028 | 0.151299660535008 | 0.021762690012970796 | 53.05592461986903 | 122.79411764705883 | 8.803846327708506 | IEI | 0.057856575937504956 | Specialty / Other | 0.19579508706671275 | 11 | 0.20127806247844693 | 0.013415584931068366 |
| lw_minvar_156w | sub-period (not a trial) | 68 | 2021-02-26 00:00:00 | 2026-09-30 00:00:00 | 0.020818568593828912 | 0.020818568593828912 | 0.04126762366257532 | -0.25075379855409086 | 0.5044770390476543 | -0.09995866796892483 | 0.3935733161527558 | 0.3861449351546258 | 0.18281053853242776 | 5.899457377903921 | 14.529411764705882 | 3.915165676897335 | ISTB | 0.2590922084423221 | Specialty / Other | 0.33591025048046363 | 11 | 0.015553733149667473 | 0.013415584931068366 |
| trend_ivol | sub-period (not a trial) | 68 | 2021-02-26 00:00:00 | 2026-09-30 00:00:00 | 0.05896688870500277 | 0.05896688870500277 | 0.10161091301727533 | 0.30605862270889383 | 0.5803204297059859 | -0.17006276707083468 | 2.659874399697797 | 2.646455066604349 | 0.02514100943660897 | 59.10673265154775 | 80.97058823529412 | 7.892680118356957 | DXJ | 0.024258987796051363 | Specialty / Other | 0.21916135801971515 | 11 | 0.212736059466751 | 0.013415584931068366 |

## tests

| period_role | strategy_id | primary_null | p_one_sided_hac | p_two_sided_hac | p_one_sided_boot | p_two_sided_boot | z_hac | z_boot | se_nat | reps | block_size | seed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full window | epo_a_w075 | lw_minvar_156w | 0.015885294095845152 | 0.031770588191690305 | 0.007998400319936013 | 0.022795440911817635 | 2.1472851390981087 | 2.450151947622024 | 0.026955701755078755 | 5000 | 4 | 20260930 |
| full window | epo_a_w075 | anchor_ivol | 0.9703079237148852 | 0.05938415257022965 | 0.9732053589282144 | 0.046590681863627276 | -1.8853384912668627 | -2.201368575611031 | 0.04476781080344477 | 5000 | 4 | 20260930 |
| full window | epo_a_w075 | trend_ivol | 0.7710908354172847 | 0.4578183291654304 | 0.7894421115776845 | 0.4189162167566487 | -0.74244406608872 | -0.8708635127882803 | 0.05259214307188788 | 5000 | 4 | 20260930 |
| full window | epo_a_w075 | equal_weight | 0.9382626619402648 | 0.1234746761194705 | 0.935612877424515 | 0.11277744451109778 | -1.5403515844866202 | -1.8303074822339043 | 0.05785399550525237 | 5000 | 4 | 20260930 |
| full window | epo_a_w075 | book1_static_option_a | 0.9795418222730002 | 0.04091635545399954 | 0.9934013197360528 | 0.007798440311937612 | -2.044376617367462 | -3.222419735642478 | 0.06888250043847319 | 5000 | 4 | 20260930 |
| full window | epo_a_w050 | lw_minvar_156w | 0.028867709846362055 | 0.05773541969272411 | 0.01779644071185763 | 0.04579084183163367 | 1.897701463414246 | 2.16875272368106 | 0.041893596234838446 | 5000 | 4 | 20260930 |
| full window | epo_a_w050 | anchor_ivol | 0.8925269742649062 | 0.21494605147018764 | 0.903619276144771 | 0.18316336732653468 | -1.2400793353351813 | -1.4168480213886137 | 0.05204451359924819 | 5000 | 4 | 20260930 |
| full window | epo_a_w050 | trend_ivol | 0.6300491873671868 | 0.7399016252656263 | 0.6432713457308539 | 0.713257348530294 | -0.33198362309123314 | -0.3988382122771639 | 0.052626082532147865 | 5000 | 4 | 20260930 |
| full window | epo_a_w050 | equal_weight | 0.8719088547579643 | 0.25618229048407126 | 0.875624875024995 | 0.22795440911817635 | -1.1354608165817794 | -1.3259249803307451 | 0.061149247709164946 | 5000 | 4 | 20260930 |
| full window | epo_a_w050 | book1_static_option_a | 0.9277599160032083 | 0.14448016799358346 | 0.9602079584083183 | 0.05018996200759848 | -1.4593086779792648 | -2.2226147615624456 | 0.07745189267671793 | 5000 | 4 | 20260930 |
| full window | epo_a_w090 | lw_minvar_156w | 0.02582068599917264 | 0.05164137199834528 | 0.005598880223955209 | 0.02459508098380324 | 1.9461112959093925 | 2.4200786845664624 | 0.018708738099734723 | 5000 | 4 | 20260930 |
| full window | epo_a_w090 | anchor_ivol | 0.9938170574626285 | 0.012365885074743056 | 0.9946010797840432 | 0.008598280343931213 | -2.5015274643381202 | -3.021837189613267 | 0.03948571391475063 | 5000 | 4 | 20260930 |
| full window | epo_a_w090 | trend_ivol | 0.861673224891281 | 0.2766535502174381 | 0.8732253549290142 | 0.24755048990201958 | -1.0878676251268458 | -1.250574999394465 | 0.05323113396421778 | 5000 | 4 | 20260930 |
| full window | epo_a_w090 | equal_weight | 0.9705019288109897 | 0.058996142378020575 | 0.9708058388322336 | 0.04899020195960808 | -1.888222083213582 | -2.2964917925708157 | 0.05515349461494083 | 5000 | 4 | 20260930 |
| full window | epo_a_w090 | book1_static_option_a | 0.9964601823607414 | 0.007079635278517248 | 0.9992001599680064 | 0.0009998000399920016 | -2.6930749462424344 | -4.157671044157614 | 0.0638233773214966 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w075 | lw_minvar_156w | 0.036993617820003044 | 0.07398723564000609 | 0.057388522295540895 | 0.10757848430313938 | 1.7866922916295562 | 1.7943103709480974 | 0.042798855293593153 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w075 | anchor_ivol | 0.971746412876746 | 0.05650717424650791 | 0.9870025994801039 | 0.025994801039792043 | -1.9071035917141042 | -2.5641271953358156 | 0.04817420793346815 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w075 | trend_ivol | 0.8374969049103163 | 0.3250061901793674 | 0.9290141971605679 | 0.14377124575084982 | -0.984222367857561 | -1.603376467102695 | 0.05309954727665566 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w075 | equal_weight | 0.9886562780757397 | 0.02268744384852057 | 0.9928014397120576 | 0.016396720655868825 | -2.2786573175806866 | -2.8257624290820322 | 0.0593722155874544 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w075 | book1_static_option_a | 0.975530912670441 | 0.048938174659117956 | 0.9982003599280144 | 0.0027994401119776045 | -1.969129912682297 | -3.328777193612058 | 0.06572239449298967 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w050 | lw_minvar_156w | 0.03365457383467832 | 0.06730914766935664 | 0.03679264147170566 | 0.05838832233553289 | 1.8296041838352761 | 2.1619025217558305 | 0.057725618422752645 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w050 | anchor_ivol | 0.8249753640883547 | 0.3500492718232906 | 0.8680263947210558 | 0.2525494901019796 | -0.9344937240661054 | -1.2392555161561425 | 0.060941481051587976 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w050 | trend_ivol | 0.6637086450701335 | 0.6725827098597329 | 0.7580483903219356 | 0.4927014597080584 | -0.4226060526305935 | -0.7279687589650902 | 0.05101295067926786 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w050 | equal_weight | 0.9232377801970747 | 0.15352443960585055 | 0.9510097980403919 | 0.09678064387122576 | -1.4271924171044155 | -1.83596689593023 | 0.06523486141488466 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w050 | book1_static_option_a | 0.9211270044056721 | 0.15774599118865584 | 0.9774045190961808 | 0.03119376124775045 | -1.4126930662483514 | -2.4346138907772286 | 0.07014355681806217 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w090 | lw_minvar_156w | 0.11340336489309488 | 0.22680672978618976 | 0.1349730053989202 | 0.30093981203759246 | 1.2086255659149308 | 1.1031976587950292 | 0.032009420914877115 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w090 | anchor_ivol | 0.9992636101695266 | 0.0014727796609467362 | 0.9988002399520096 | 0.004199160167966407 | -3.1799942668530123 | -3.680166494106384 | 0.044836696558577555 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w090 | trend_ivol | 0.9354430622185713 | 0.12911387556285742 | 0.9644071185762847 | 0.0611877624475105 | -1.5176055156830481 | -2.1537194210805937 | 0.058791444690131006 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w090 | equal_weight | 0.9992417439634309 | 0.001516512073138224 | 0.9984003199360127 | 0.0061987602479504095 | -3.1715050959725604 | -3.4698327833017317 | 0.0603065049274782 | 5000 | 4 | 20260930 |
| sub-period (not a trial) | epo_a_w090 | book1_static_option_a | 0.9949139456501539 | 0.010172108699692215 | 0.9996000799840032 | 0.0013997200559888023 | -2.569923118257952 | -4.012779663998394 | 0.06485701717891948 | 5000 | 4 | 20260930 |

## asset_class_mix

| strategy_id | computable | equity | bond | commodity |
| --- | --- | --- | --- | --- |
| anchor_ivol | True | 0.5007114908796604 | 0.42364599299687306 | 0.07564251612346652 |
| book1_static_option_a | True | 1.0000000000000004 | 0.0 | 0.0 |
| epo_a_w050 | True | 0.10010279942336173 | 0.7936706492104735 | 0.10622655136616485 |
| epo_a_w075 | True | 0.08987634724722368 | 0.8379508838656331 | 0.07217276888714332 |
| epo_a_w090 | True | 0.10757143596357774 | 0.8329970270993221 | 0.059431536937100155 |
| equal_weight | True | 0.6943509443333145 | 0.16916192026414179 | 0.13648713540254387 |
| erc_lw | True | 0.32861968010042053 | 0.53514933812146 | 0.13623098177811938 |
| lw_minvar_156w | True | 0.04187504216192978 | 0.9009223287199228 | 0.05720262911814749 |
| trend_ivol | True | 0.5799533771246123 | 0.316738390109816 | 0.10330823276557176 |

## category_spread

| strategy_id | grouping | group | average_weight |
| --- | --- | --- | --- |
| anchor_ivol | Category (known mislabels) | Commodities / Metals | 0.060586731062565326 |
| anchor_ivol | Category (known mislabels) | Core / Aggregate Bonds | 0.04714934339833032 |
| anchor_ivol | Category (known mislabels) | EM Debt | 0.02191908766634579 |
| anchor_ivol | Category (known mislabels) | Global Equity (incl US) | 0.006944531390476447 |
| anchor_ivol | Category (known mislabels) | High Yield Credit | 0.0353703416503131 |
| anchor_ivol | Category (known mislabels) | International Developed Equity | 0.1214506874112461 |
| anchor_ivol | Category (known mislabels) | International EM Equity | 0.00583488540400557 |
| anchor_ivol | Category (known mislabels) | Investment Grade Credit | 0.057423967508742936 |
| anchor_ivol | Category (known mislabels) | Municipal Bonds | 0.06742832374343105 |
| anchor_ivol | Category (known mislabels) | Other Fixed Income | 0.009713507325899151 |
| anchor_ivol | Category (known mislabels) | REITs / Real Estate | 0.0006837853338788816 |
| anchor_ivol | Category (known mislabels) | Sector / Factor / Thematic | 0.013500867303049655 |
| anchor_ivol | Category (known mislabels) | Specialty / Other | 0.20984031839115133 |
| anchor_ivol | Category (known mislabels) | TIPS / Inflation-Linked | 0.040899839711626466 |
| anchor_ivol | Category (known mislabels) | US Large / Broad Blend | 0.061048448286429864 |
| anchor_ivol | Category (known mislabels) | US Large Growth / Tech-tilt | 0.006084471365941168 |
| anchor_ivol | Category (known mislabels) | US Large Value | 0.04655018645188274 |
| anchor_ivol | Category (known mislabels) | US Mid Blend | 0.03514310603475095 |
| anchor_ivol | Category (known mislabels) | US Mid Growth | 0.011485431101294597 |
| anchor_ivol | Category (known mislabels) | US Mid Value | 0.011653459363140148 |
| anchor_ivol | Category (known mislabels) | US Small Blend | 0.022781153207610674 |
| anchor_ivol | Category (known mislabels) | US Small Growth | 0.015288394965281947 |
| anchor_ivol | Category (known mislabels) | US Small Value | 0.01003836162677762 |
| anchor_ivol | Category (known mislabels) | US Treasuries / Govt / Cash-like | 0.08118077029582817 |
| anchor_ivol | exposure diagnostic | equity_only | 0.48769042636608295 |
| anchor_ivol | exposure diagnostic | rest | 0.512309573633917 |
| anchor_ivol | exposure diagnostic | commodity | 0.07564251612346652 |
| anchor_ivol | exposure diagnostic | ISTB/VCSH/SJNK | 0.09751390570706907 |
| book1_static_option_a | Category (known mislabels) | US Large / Broad Blend | 0.7 |
| book1_static_option_a | Category (known mislabels) | US Large Growth / Tech-tilt | 0.2 |
| book1_static_option_a | Category (known mislabels) | US Small Blend | 0.1 |
| book1_static_option_a | exposure diagnostic | equity_only | 1.0000000000000004 |
| book1_static_option_a | exposure diagnostic | rest | 0.0 |
| book1_static_option_a | exposure diagnostic | commodity | 0.0 |
| book1_static_option_a | exposure diagnostic | ISTB/VCSH/SJNK | 0.0 |
| epo_a_w050 | Category (known mislabels) | Commodities / Metals | 0.08436779638977174 |
| epo_a_w050 | Category (known mislabels) | Core / Aggregate Bonds | 0.024940038713469337 |
| epo_a_w050 | Category (known mislabels) | EM Debt | 0.005430757913529294 |
| epo_a_w050 | Category (known mislabels) | Global Equity (incl US) | 1.9498241131466483e-17 |
| epo_a_w050 | Category (known mislabels) | High Yield Credit | 0.02975193073213092 |
| epo_a_w050 | Category (known mislabels) | International Developed Equity | 0.034226961843176994 |
| epo_a_w050 | Category (known mislabels) | International EM Equity | 0.00019262442520867452 |
| epo_a_w050 | Category (known mislabels) | Investment Grade Credit | 0.19112654473342952 |
| epo_a_w050 | Category (known mislabels) | Municipal Bonds | 0.09789355698202781 |
| epo_a_w050 | Category (known mislabels) | Other Fixed Income | 0.00233263756955356 |
| epo_a_w050 | Category (known mislabels) | REITs / Real Estate | 1.409031352076292e-18 |
| epo_a_w050 | Category (known mislabels) | Sector / Factor / Thematic | 0.001359500418932095 |
| epo_a_w050 | Category (known mislabels) | Specialty / Other | 0.3012214220972388 |
| epo_a_w050 | Category (known mislabels) | TIPS / Inflation-Linked | 0.04417994202700482 |
| epo_a_w050 | Category (known mislabels) | US Large / Broad Blend | 0.002187124793123801 |
| epo_a_w050 | Category (known mislabels) | US Large Growth / Tech-tilt | 0.0024180856353807384 |
| epo_a_w050 | Category (known mislabels) | US Large Value | 0.004075196322635468 |
| epo_a_w050 | Category (known mislabels) | US Mid Blend | 0.00013968575331346948 |
| epo_a_w050 | Category (known mislabels) | US Mid Growth | 3.270836677285071e-05 |
| epo_a_w050 | Category (known mislabels) | US Mid Value | 0.0002483589136198453 |
| epo_a_w050 | Category (known mislabels) | US Small Blend | 0.0009055620771362179 |
| epo_a_w050 | Category (known mislabels) | US Small Growth | 0.001500012571733134 |
| epo_a_w050 | Category (known mislabels) | US Small Value | 0.0004440482121634722 |
| epo_a_w050 | Category (known mislabels) | US Treasuries / Govt / Cash-like | 0.17102550350864745 |
| epo_a_w050 | exposure diagnostic | equity_only | 0.09971087310958776 |
| epo_a_w050 | exposure diagnostic | rest | 0.9002891268904122 |
| epo_a_w050 | exposure diagnostic | commodity | 0.10622655136616485 |
| epo_a_w050 | exposure diagnostic | ISTB/VCSH/SJNK | 0.3918167234853726 |
| epo_a_w075 | Category (known mislabels) | Commodities / Metals | 0.05837880147133484 |
| epo_a_w075 | Category (known mislabels) | Core / Aggregate Bonds | 0.03244467316779666 |
| epo_a_w075 | Category (known mislabels) | EM Debt | 0.009166756660344517 |
| epo_a_w075 | Category (known mislabels) | Global Equity (incl US) | 6.45415006495562e-05 |
| epo_a_w075 | Category (known mislabels) | High Yield Credit | 0.03804814745364051 |
| epo_a_w075 | Category (known mislabels) | International Developed Equity | 0.024227904780312018 |
| epo_a_w075 | Category (known mislabels) | International EM Equity | 0.00045344913571959965 |
| epo_a_w075 | Category (known mislabels) | Investment Grade Credit | 0.20075951999664676 |
| epo_a_w075 | Category (known mislabels) | Municipal Bonds | 0.08578903072737629 |
| epo_a_w075 | Category (known mislabels) | Other Fixed Income | 0.001461835082977968 |
| epo_a_w075 | Category (known mislabels) | REITs / Real Estate | 3.747463313146714e-19 |
| epo_a_w075 | Category (known mislabels) | Sector / Factor / Thematic | 0.002905266828170402 |
| epo_a_w075 | Category (known mislabels) | Specialty / Other | 0.32876584627713107 |
| epo_a_w075 | Category (known mislabels) | TIPS / Inflation-Linked | 0.042540471736076016 |
| epo_a_w075 | Category (known mislabels) | US Large / Broad Blend | 0.006725137663789734 |
| epo_a_w075 | Category (known mislabels) | US Large Growth / Tech-tilt | 0.0024599465410251324 |
| epo_a_w075 | Category (known mislabels) | US Large Value | 0.008358406001540013 |
| epo_a_w075 | Category (known mislabels) | US Mid Blend | 0.0005545499500115348 |
| epo_a_w075 | Category (known mislabels) | US Mid Growth | 0.00027827503972897724 |
| epo_a_w075 | Category (known mislabels) | US Mid Value | 0.0003933766566786824 |
| epo_a_w075 | Category (known mislabels) | US Small Blend | 0.0019496165573749124 |
| epo_a_w075 | Category (known mislabels) | US Small Growth | 0.0023248640535884885 |
| epo_a_w075 | Category (known mislabels) | US Small Value | 0.0012520077245878971 |
| epo_a_w075 | Category (known mislabels) | US Treasuries / Govt / Cash-like | 0.1506975749934985 |
| epo_a_w075 | exposure diagnostic | equity_only | 0.08885909929303906 |
| epo_a_w075 | exposure diagnostic | rest | 0.9111409007069609 |
| epo_a_w075 | exposure diagnostic | commodity | 0.07217276888714332 |
| epo_a_w075 | exposure diagnostic | ISTB/VCSH/SJNK | 0.4214934162903144 |
| epo_a_w090 | Category (known mislabels) | Commodities / Metals | 0.04993168597238338 |
| epo_a_w090 | Category (known mislabels) | Core / Aggregate Bonds | 0.059174769309537696 |
| epo_a_w090 | Category (known mislabels) | EM Debt | 0.011104839009021518 |
| epo_a_w090 | Category (known mislabels) | Global Equity (incl US) | 0.0006740962135814555 |
| epo_a_w090 | Category (known mislabels) | High Yield Credit | 0.034838182054774104 |
| epo_a_w090 | Category (known mislabels) | International Developed Equity | 0.024486274091931375 |
| epo_a_w090 | Category (known mislabels) | International EM Equity | 0.0010895576100080455 |
| epo_a_w090 | Category (known mislabels) | Investment Grade Credit | 0.15899042106202824 |
| epo_a_w090 | Category (known mislabels) | Municipal Bonds | 0.09555197187235379 |
| epo_a_w090 | Category (known mislabels) | Other Fixed Income | 0.0016940202883987795 |
| epo_a_w090 | Category (known mislabels) | REITs / Real Estate | 1.59044914490862e-05 |
| epo_a_w090 | Category (known mislabels) | Sector / Factor / Thematic | 0.003719126983481519 |
| epo_a_w090 | Category (known mislabels) | Specialty / Other | 0.2989680542718856 |
| epo_a_w090 | Category (known mislabels) | TIPS / Inflation-Linked | 0.052932210823879874 |
| epo_a_w090 | Category (known mislabels) | US Large / Broad Blend | 0.01473232240091432 |
| epo_a_w090 | Category (known mislabels) | US Large Growth / Tech-tilt | 0.002066001045730321 |
| epo_a_w090 | Category (known mislabels) | US Large Value | 0.012934369641078237 |
| epo_a_w090 | Category (known mislabels) | US Mid Blend | 0.003145546616185781 |
| epo_a_w090 | Category (known mislabels) | US Mid Growth | 0.001450144034278905 |
| epo_a_w090 | Category (known mislabels) | US Mid Value | 0.0011845654115180916 |
| epo_a_w090 | Category (known mislabels) | US Small Blend | 0.002737033101698979 |
| epo_a_w090 | Category (known mislabels) | US Small Growth | 0.002418586509325181 |
| epo_a_w090 | Category (known mislabels) | US Small Value | 0.00153531306092334 |
| epo_a_w090 | Category (known mislabels) | US Treasuries / Govt / Cash-like | 0.1646250041236324 |
| epo_a_w090 | exposure diagnostic | equity_only | 0.10563327017403176 |
| epo_a_w090 | exposure diagnostic | rest | 0.8943667298259682 |
| epo_a_w090 | exposure diagnostic | commodity | 0.059431536937100155 |
| epo_a_w090 | exposure diagnostic | ISTB/VCSH/SJNK | 0.3329093160943633 |
| equal_weight | Category (known mislabels) | Commodities / Metals | 0.09374580873295818 |
| equal_weight | Category (known mislabels) | Core / Aggregate Bonds | 0.017096530667834266 |
| equal_weight | Category (known mislabels) | EM Debt | 0.017096530667834266 |
| equal_weight | Category (known mislabels) | Global Equity (incl US) | 0.008548265333917133 |
| equal_weight | Category (known mislabels) | High Yield Credit | 0.024174215977433237 |
| equal_weight | Category (known mislabels) | International Developed Equity | 0.15410653140719524 |
| equal_weight | Category (known mislabels) | International EM Equity | 0.008548265333917133 |
| equal_weight | Category (known mislabels) | Investment Grade Credit | 0.017096530667834266 |
| equal_weight | Category (known mislabels) | Municipal Bonds | 0.03419306133566853 |
| equal_weight | Category (known mislabels) | Other Fixed Income | 0.008548265333917133 |
| equal_weight | Category (known mislabels) | REITs / Real Estate | 0.0007858031018247311 |
| equal_weight | Category (known mislabels) | Sector / Factor / Thematic | 0.015423006034609634 |
| equal_weight | Category (known mislabels) | Specialty / Other | 0.239210760986351 |
| equal_weight | Category (known mislabels) | TIPS / Inflation-Linked | 0.017096530667834266 |
| equal_weight | Category (known mislabels) | US Large / Broad Blend | 0.07700338648279483 |
| equal_weight | Category (known mislabels) | US Large Growth / Tech-tilt | 0.009267900236178574 |
| equal_weight | Category (known mislabels) | US Large Value | 0.05839561787881561 |
| equal_weight | Category (known mislabels) | US Mid Blend | 0.0512895920035028 |
| equal_weight | Category (known mislabels) | US Mid Growth | 0.017096530667834266 |
| equal_weight | Category (known mislabels) | US Mid Value | 0.017096530667834266 |
| equal_weight | Category (known mislabels) | US Small Blend | 0.03757875419853916 |
| equal_weight | Category (known mislabels) | US Small Growth | 0.0256447960017514 |
| equal_weight | Category (known mislabels) | US Small Value | 0.017096530667834266 |
| equal_weight | Category (known mislabels) | US Treasuries / Govt / Cash-like | 0.033860254945785845 |
| equal_weight | exposure diagnostic | equity_only | 0.6782297997160545 |
| equal_weight | exposure diagnostic | rest | 0.3217702002839455 |
| equal_weight | exposure diagnostic | commodity | 0.13648713540254387 |
| equal_weight | exposure diagnostic | ISTB/VCSH/SJNK | 0.024174215977433237 |
| erc_lw | Category (known mislabels) | Commodities / Metals | 0.10982185443624104 |
| erc_lw | Category (known mislabels) | Core / Aggregate Bonds | 0.05235672599199883 |
| erc_lw | Category (known mislabels) | EM Debt | 0.01707333194715021 |
| erc_lw | Category (known mislabels) | Global Equity (incl US) | 0.004049630318885834 |
| erc_lw | Category (known mislabels) | High Yield Credit | 0.02337396380333561 |
| erc_lw | Category (known mislabels) | International Developed Equity | 0.0788680981420516 |
| erc_lw | Category (known mislabels) | International EM Equity | 0.0040889322800852085 |
| erc_lw | Category (known mislabels) | Investment Grade Credit | 0.05252339334981778 |
| erc_lw | Category (known mislabels) | Municipal Bonds | 0.08177581136996294 |
| erc_lw | Category (known mislabels) | Other Fixed Income | 0.010345608103950455 |
| erc_lw | Category (known mislabels) | REITs / Real Estate | 0.0004945680054212947 |
| erc_lw | Category (known mislabels) | Sector / Factor / Thematic | 0.008581405575842638 |
| erc_lw | Category (known mislabels) | Specialty / Other | 0.18796604742863376 |
| erc_lw | Category (known mislabels) | TIPS / Inflation-Linked | 0.04368086176747946 |
| erc_lw | Category (known mislabels) | US Large / Broad Blend | 0.03774483350485369 |
| erc_lw | Category (known mislabels) | US Large Growth / Tech-tilt | 0.004269335598688937 |
| erc_lw | Category (known mislabels) | US Large Value | 0.028999989132676443 |
| erc_lw | Category (known mislabels) | US Mid Blend | 0.02110214315405523 |
| erc_lw | Category (known mislabels) | US Mid Growth | 0.0071161987759730955 |
| erc_lw | Category (known mislabels) | US Mid Value | 0.007070508384888951 |
| erc_lw | Category (known mislabels) | US Small Blend | 0.014739649244897799 |
| erc_lw | Category (known mislabels) | US Small Growth | 0.01004775730987444 |
| erc_lw | Category (known mislabels) | US Small Value | 0.006679798241568939 |
| erc_lw | Category (known mislabels) | US Treasuries / Govt / Cash-like | 0.1872295541316658 |
| erc_lw | exposure diagnostic | equity_only | 0.32052115763457095 |
| erc_lw | exposure diagnostic | rest | 0.679478842365429 |
| erc_lw | exposure diagnostic | commodity | 0.13623098177811938 |
| erc_lw | exposure diagnostic | ISTB/VCSH/SJNK | 0.08463625547019056 |
| lw_minvar_156w | Category (known mislabels) | Commodities / Metals | 0.04991219113268413 |
| lw_minvar_156w | Category (known mislabels) | Core / Aggregate Bonds | 0.03749494367194153 |
| lw_minvar_156w | Category (known mislabels) | EM Debt | 0.00048188295048353486 |
| lw_minvar_156w | Category (known mislabels) | Global Equity (incl US) | 8.967868479552814e-18 |
| lw_minvar_156w | Category (known mislabels) | High Yield Credit | 0.036464814600935765 |
| lw_minvar_156w | Category (known mislabels) | International Developed Equity | 0.029080441724790795 |
| lw_minvar_156w | Category (known mislabels) | International EM Equity | 6.9251901724065086e-18 |
| lw_minvar_156w | Category (known mislabels) | Investment Grade Credit | 0.18044757690396998 |
| lw_minvar_156w | Category (known mislabels) | Municipal Bonds | 0.12139473215735538 |
| lw_minvar_156w | Category (known mislabels) | Other Fixed Income | 6.960301295170972e-18 |
| lw_minvar_156w | Category (known mislabels) | REITs / Real Estate | 6.287509111061265e-19 |
| lw_minvar_156w | Category (known mislabels) | Sector / Factor / Thematic | 8.713689031143773e-18 |
| lw_minvar_156w | Category (known mislabels) | Specialty / Other | 0.32012033860518513 |
| lw_minvar_156w | Category (known mislabels) | TIPS / Inflation-Linked | 0.018745441217587176 |
| lw_minvar_156w | Category (known mislabels) | US Large / Broad Blend | 4.467580471608508e-17 |
| lw_minvar_156w | Category (known mislabels) | US Large Growth / Tech-tilt | 5.654180049171832e-18 |
| lw_minvar_156w | Category (known mislabels) | US Large Value | 3.0557172357522675e-17 |
| lw_minvar_156w | Category (known mislabels) | US Mid Blend | 3.3276840192717367e-17 |
| lw_minvar_156w | Category (known mislabels) | US Mid Growth | 1.2492201058925595e-17 |
| lw_minvar_156w | Category (known mislabels) | US Mid Value | 1.0648348304406107e-17 |
| lw_minvar_156w | Category (known mislabels) | US Small Blend | 2.718300338017454e-17 |
| lw_minvar_156w | Category (known mislabels) | US Small Growth | 1.6641740113580053e-17 |
| lw_minvar_156w | Category (known mislabels) | US Small Value | 1.1642763448665412e-17 |
| lw_minvar_156w | Category (known mislabels) | US Treasuries / Govt / Cash-like | 0.2058576370350664 |
| lw_minvar_156w | exposure diagnostic | equity_only | 0.04187504216192977 |
| lw_minvar_156w | exposure diagnostic | rest | 0.9581249578380702 |
| lw_minvar_156w | exposure diagnostic | commodity | 0.05720262911814749 |
| lw_minvar_156w | exposure diagnostic | ISTB/VCSH/SJNK | 0.42204924804318156 |
| trend_ivol | Category (known mislabels) | Commodities / Metals | 0.07918027092658018 |
| trend_ivol | Category (known mislabels) | Core / Aggregate Bonds | 0.031522898096784616 |
| trend_ivol | Category (known mislabels) | EM Debt | 0.01774313491255358 |
| trend_ivol | Category (known mislabels) | Global Equity (incl US) | 0.008000923608535668 |
| trend_ivol | Category (known mislabels) | High Yield Credit | 0.04521308234146496 |
| trend_ivol | Category (known mislabels) | International Developed Equity | 0.14208555668283737 |
| trend_ivol | Category (known mislabels) | International EM Equity | 0.0048930920881631165 |
| trend_ivol | Category (known mislabels) | Investment Grade Credit | 0.051116370417563485 |
| trend_ivol | Category (known mislabels) | Municipal Bonds | 0.052516924934311246 |
| trend_ivol | Category (known mislabels) | Other Fixed Income | 0.0067536943775556866 |
| trend_ivol | Category (known mislabels) | REITs / Real Estate | 0.0006678347913540205 |
| trend_ivol | Category (known mislabels) | Sector / Factor / Thematic | 0.01824735881518241 |
| trend_ivol | Category (known mislabels) | Specialty / Other | 0.21294748051846504 |
| trend_ivol | Category (known mislabels) | TIPS / Inflation-Linked | 0.03348855148552111 |
| trend_ivol | Category (known mislabels) | US Large / Broad Blend | 0.08020349772861106 |
| trend_ivol | Category (known mislabels) | US Large Growth / Tech-tilt | 0.008553940910386191 |
| trend_ivol | Category (known mislabels) | US Large Value | 0.05873883886410102 |
| trend_ivol | Category (known mislabels) | US Mid Blend | 0.03725845797879256 |
| trend_ivol | Category (known mislabels) | US Mid Growth | 0.012909715904770188 |
| trend_ivol | Category (known mislabels) | US Mid Value | 0.012147527145690038 |
| trend_ivol | Category (known mislabels) | US Small Blend | 0.019738465958458462 |
| trend_ivol | Category (known mislabels) | US Small Growth | 0.01464373714746505 |
| trend_ivol | Category (known mislabels) | US Small Value | 0.008179136677871289 |
| trend_ivol | Category (known mislabels) | US Treasuries / Govt / Cash-like | 0.04324950768698164 |
| trend_ivol | exposure diagnostic | equity_only | 0.5634487555516421 |
| trend_ivol | exposure diagnostic | rest | 0.436551244448358 |
| trend_ivol | exposure diagnostic | commodity | 0.10330823276557176 |
| trend_ivol | exposure diagnostic | ISTB/VCSH/SJNK | 0.08729337338176003 |

## book1_window_summary

| strategy_id | period_role | n_months | start | end | CAGR | AnnReturn | AnnVol | Sharpe_exBIL | Sharpe_rf0_legacy | MaxDD | turnover_per_year | turnover_target_per_year_diagnostic | HHI_mean | eff_N_mean | names_held_mean | eff_N_category_mean | largest_single_name | largest_single_name_share | largest_category | largest_category_share | trial_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| book1_static_option_a | Book 1 overlap | 71 | 2020-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.17283134744247453 | 0.17283134744247453 | 0.16147511197186876 | 0.8865806870299144 | 1.0703280854363748 | -0.25564187805103256 | 0.1353543261999646 | 0.08450704225352113 | 0.5399999999999998 | 1.8518518518518512 | 3.0 | 1.8518518518518512 | VOO | 0.7 | US Large / Broad Blend | 0.7000000000000007 | 11 |
| epo_a_w075 | Book 1 overlap | 71 | 2020-11-30 00:00:00 | 2026-09-30 00:00:00 | 0.03517440001336336 | 0.03517440001336336 | 0.0436294819999246 | 0.1230939782188429 | 0.8062071425332107 | -0.09413108335733 | 1.9446308472098712 | 1.9277275501371804 | 0.16658170155360477 | 6.402147776174646 | 33.32394366197183 | 4.112710811190799 | ISTB | 0.22411870087981897 | Specialty / Other | 0.3447846440924564 | 11 |

## cost_stress

| strategy_id | cost_bps | Sharpe_exBIL | CAGR |
| --- | --- | --- | --- |
| anchor_ivol | 10 | 0.6070840323990685 | 0.07704726771022519 |
| anchor_ivol | 25 | 0.6034017552054979 | 0.07667279349582579 |
| book1_static_option_a | 10 | 0.8863143797034745 | 0.1727575389773599 |
| book1_static_option_a | 25 | 0.8855129377185306 | 0.17253608129306186 |
| epo_a_w050 | 10 | 0.3172339949760586 | 0.03564749531312117 |
| epo_a_w050 | 25 | 0.2068956282531672 | 0.030976695323575054 |
| epo_a_w075 | 10 | 0.24159616835996287 | 0.03186825473075228 |
| epo_a_w075 | 25 | 0.16114035137580876 | 0.02869565507272842 |
| epo_a_w090 | 10 | 0.18344691988969178 | 0.030024189327771955 |
| epo_a_w090 | 25 | 0.14362308113607752 | 0.028333961310714306 |
| equal_weight | 10 | 0.632779087775985 | 0.09822297468958885 |
| equal_weight | 25 | 0.6302242487772445 | 0.09786585256537994 |
| erc_lw | 10 | 0.5021852431213363 | 0.05727936539691458 |
| erc_lw | 25 | 0.4959953080918184 | 0.05681851320867648 |
| lw_minvar_156w | 10 | 0.033757558870531376 | 0.02371398800179958 |
| lw_minvar_156w | 25 | 0.013462487832807494 | 0.022995588931159716 |
| trend_ivol | 10 | 0.4137061955207291 | 0.05984628323523644 |
| trend_ivol | 25 | 0.37578937812590135 | 0.0560040455098767 |

## trial_registry

| trial_id | line | window_weeks | status | Sharpe_exBIL_annual | Sharpe_rf0_legacy_recorded | source | preregistered | trial_count | w |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v1_invalid_w156 | v1 | 156 | invalid (numerical bug), counted | nan | 0.796 | invalidated v1 legacy record | True | 11 | nan |
| v1_invalid_w260 | v1 | 260 | invalid (numerical bug), counted | nan | 0.733 | invalidated v1 legacy record | True | 11 | nan |
| v1_w156 | v1 | 156 | valid | 0.09335655756172109 | nan | data/processed/nonlinear_shrinkage_gmv/oos_returns.csv | True | 11 | nan |
| v1_w260 | v1 | 260 | valid | 0.03836411353745967 | nan | data/processed/nonlinear_shrinkage_gmv/oos_returns.csv | True | 11 | nan |
| v2_w156 | v2 | 156 | valid | -0.4893806276166144 | nan | data/processed/nonlinear_shrinkage_gmv_v2/summary.csv | True | 11 | nan |
| v2_w260 | v2 | 260 | valid | -0.5267547832148654 | nan | data/processed/nonlinear_shrinkage_gmv_v2/summary.csv | True | 11 | nan |
| v3_w156 | v3 | 156 | valid | 0.5282293945809092 | nan | HEAD:data/processed/nonlinear_shrinkage_gmv_v3/summary.csv | True | 11 | nan |
| v3_w260 | v3 | 260 | valid | 0.6115398362811979 | nan | HEAD:data/processed/nonlinear_shrinkage_gmv_v3/summary.csv | True | 11 | nan |
| epo_a_w075 | epo | 156 | valid | 0.2683587476472725 | nan | current EPO full-window method | True | 11 | 0.75 |
| epo_a_w050 | epo | 156 | valid | 0.35394567145119255 | nan | current EPO full-window method | True | 11 | 0.5 |
| epo_a_w090 | epo | 156 | valid | 0.196715936056583 | nan | current EPO full-window method | True | 11 | 0.9 |

Criteria: {'criteria': {'c1': True, 'c2': False, 'c3': False, 'c4': False, 'c5': True, 'c6': True}, 'mechanical': 'FAIL', 'failing_criteria': ['c2', 'c3', 'c4'], 'effN_method': 6.64880442838787, 'effN_primary_diagnostic': 6.972376305795735}

## Projection diagnostics

| strategy_id | distance_mean | distance_max | zero_mean | kkt_max | solver_success | anchor_months |
| --- | --- | --- | --- | --- | --- | --- |
| epo_a_w050 | 0.5369538942628692 | 0.8237704766730928 | 91.16806722689076 | 1.1438109388372392e-06 | True | 0 |
| epo_a_w075 | 0.5040931450904776 | 0.8547557924085257 | 71.02521008403362 | 8.584833730319874e-07 | True | 0 |
| epo_a_w090 | 0.4427655168764174 | 0.8258757405026601 | 31.95798319327731 | 5.27865390601576e-07 | True | 0 |
All-zero-signal months: 0.
DSR: Bailey–López de Prado (2014), N=11; cross-trial monthly Sharpe variance excludes the two invalid runs with no ex-BIL Sharpe. Sub-period is not a trial.
No reruns or retuning to chase significance. A not-significant edge is recorded as not significant. Any preview or rerun adds a trial and needs a new ticket.
Jared's method rule: statistical or classical methods only; no large pretrained models or model downloads.
Signal is 12-1 (final); 12-0 is not a sensitivity and is not run.

## Monthly panel provenance

- source: usa_universe_panel_monthly_returns.csv
- complete_months_only: True
- dropped_partial_month: none
- source_asof: 2026-09-30
