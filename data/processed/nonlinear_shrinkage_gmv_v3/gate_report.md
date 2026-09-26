# NLS GMV v3 equity-only research gate

Status: PENDING QUANT — mechanical reading only
**Label (mechanical + composition): VOID**
book_eligible: no (gate label is VOID, not PASS)

Research only; snapshot universe implies survivorship bias. Registry enabled:false.

## Composition tripwire (cash_like + short_duration + near_cash, default-on)

Status: **PASS** (VOID if the method or the primary null averages > 0% over the OOS window).
- Method `nonlinear_shrinkage_gmv`: 0.00%
- Primary null `minvar_lw_weekly`: 0.00%

Any composition share above 0% is VOID.

156w eligible N: min 70, mean 83.40, max 94; skipped months: none.
260w eligible N: min 64, mean 78.66, max 91; skipped months: 2016-01.
Coverage-gap names (>35 days): none
Not investable at the final rebalance (no return in the partial 2026-09 row, method and every null alike): GUSA, TMDV

## 156w — full 2016-01..2026-09

| Strategy | AnnVol | LW2011 p HAC | LW2011 p boot | LW2011 p gate | Sharpe ex-BIL | Sharpe legacy (rf=0) | MaxDD | DSR (8, cross-trial V) | DSR (repo approx) | eff N | eff N category | low-vol share | names held | turnover/yr | NW t | LW2008 p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| method | 0.1066 | 0.1552 | 0.1366 | 0.1552 | 0.5282 | 0.6949 | -0.2310 | 0.2927 | 0.7173 | 2.6284 | 2.1320 | 0.7373 | 3.9457 | 0.6473 | -1.0133 | 0.5094 |
| primary null | 0.1083 | — | — | — | 0.5506 | 0.7155 | -0.2225 | 0.3185 | 0.7415 | 3.1935 | 2.3406 | 0.6402 | 4.7829 | 0.6206 | — | — |
| ERC | 0.1500 | 1.0000 | 1.0000 | 1.0000 | 0.6493 | 0.7519 | -0.2506 | 0.4318 | 0.8340 | 80.2296 | 5.9811 | 0.0373 | 83.3953 | 0.1237 | 1.7907 | 0.5514 |
| EW | 0.1546 | 1.0000 | 1.0000 | 1.0000 | 0.6473 | 0.7439 | -0.2530 | 0.4291 | 0.8324 | 83.3953 | 6.3089 | 0.0256 | 83.3953 | 0.0757 | 1.7476 | 0.5905 |
| buy-and-hold USMV | 0.1203 | 0.9934 | 0.9900 | 0.9934 | 0.6977 | 0.8525 | -0.1906 | 0.4904 | 0.8704 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0465 | 1.3900 | 0.3308 |
| buy-and-hold ACWI | 0.1439 | 1.0000 | 1.0000 | 1.0000 | 0.7278 | 0.8467 | -0.2574 | 0.5272 | 0.8900 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0465 | 2.3899 | 0.2798 |

## 260w — full 2016-01..2026-09

| Strategy | AnnVol | LW2011 p HAC | LW2011 p boot | LW2011 p gate | Sharpe ex-BIL | Sharpe legacy (rf=0) | MaxDD | DSR (8, cross-trial V) | DSR (repo approx) | eff N | eff N category | low-vol share | names held | turnover/yr | NW t | LW2008 p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| method | 0.1077 | 0.5715 | 0.5221 | 0.5715 | 0.6115 | 0.7841 | -0.2462 | 0.3875 | 0.7993 | 2.0792 | 1.7434 | 0.7513 | 3.6250 | 0.4823 | -1.3021 | 0.1725 |
| primary null | 0.1075 | — | — | — | 0.6453 | 0.8216 | -0.2307 | 0.4276 | 0.8287 | 2.5586 | 1.9018 | 0.6712 | 4.8359 | 0.5340 | — | — |
| ERC | 0.1498 | 1.0000 | 1.0000 | 1.0000 | 0.6979 | 0.8075 | -0.2525 | 0.4907 | 0.8686 | 76.3392 | 6.1339 | 0.0338 | 78.7734 | 0.1096 | 1.6118 | 0.7476 |
| EW | 0.1539 | 1.0000 | 1.0000 | 1.0000 | 0.6944 | 0.7985 | -0.2552 | 0.4865 | 0.8662 | 78.7734 | 6.4568 | 0.0235 | 78.7734 | 0.0792 | 1.5856 | 0.7802 |
| buy-and-hold USMV | 0.1206 | 0.9976 | 0.9950 | 0.9976 | 0.7124 | 0.8696 | -0.1906 | 0.5083 | 0.8784 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0469 | 0.9298 | 0.6489 |
| buy-and-hold ACWI | 0.1431 | 1.0000 | 1.0000 | 1.0000 | 0.7720 | 0.8985 | -0.2574 | 0.5799 | 0.9133 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0469 | 2.0945 | 0.4268 |

## 156w — book2 2021-02..2026-09

| Strategy | AnnVol | LW2011 p HAC | LW2011 p boot | LW2011 p gate | Sharpe ex-BIL | Sharpe legacy (rf=0) | MaxDD | DSR (8, cross-trial V) | DSR (repo approx) | eff N | eff N category | low-vol share | names held | turnover/yr | NW t | LW2008 p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| method | 0.1058 | 0.9293 | 0.8944 | 0.9293 | 0.3732 | 0.6322 | -0.2310 | 0.2206 | 0.3942 | 3.1665 | 2.2935 | 0.6005 | 4.1618 | 0.5764 | -0.3247 | 0.6222 |
| primary null | 0.1043 | — | — | — | 0.3888 | 0.6537 | -0.2225 | 0.2315 | 0.4084 | 3.6930 | 2.3710 | 0.5137 | 4.8529 | 0.5457 | — | — |
| ERC | 0.1415 | 1.0000 | 0.9984 | 1.0000 | 0.5849 | 0.7703 | -0.2407 | 0.3910 | 0.5916 | 84.5892 | 5.7219 | 0.0363 | 88.7794 | 0.0694 | 1.3964 | 0.4772 |
| EW | 0.1468 | 1.0000 | 0.9990 | 1.0000 | 0.5796 | 0.7543 | -0.2424 | 0.3858 | 0.5867 | 88.7794 | 6.1519 | 0.0254 | 88.7794 | 0.0256 | 1.3311 | 0.5257 |
| buy-and-hold USMV | 0.1206 | 0.9761 | 0.9166 | 0.9761 | 0.5220 | 0.7516 | -0.1735 | 0.3354 | 0.5331 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.7638 | 0.6081 |
| buy-and-hold ACWI | 0.1427 | 1.0000 | 0.9984 | 1.0000 | 0.6614 | 0.8509 | -0.2574 | 0.4600 | 0.6600 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 | 1.8208 | 0.2980 |

## 260w — book2 2021-02..2026-09

| Strategy | AnnVol | LW2011 p HAC | LW2011 p boot | LW2011 p gate | Sharpe ex-BIL | Sharpe legacy (rf=0) | MaxDD | DSR (8, cross-trial V) | DSR (repo approx) | eff N | eff N category | low-vol share | names held | turnover/yr | NW t | LW2008 p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| method | 0.1094 | 0.9999 | 0.9992 | 0.9999 | 0.3363 | 0.5825 | -0.2462 | 0.1957 | 0.3611 | 2.3391 | 1.7567 | 0.6941 | 4.0588 | 0.3342 | -0.9551 | 0.1686 |
| primary null | 0.1062 | — | — | — | 0.3782 | 0.6368 | -0.2307 | 0.2242 | 0.3987 | 2.9392 | 1.8690 | 0.5926 | 5.3382 | 0.3635 | — | — |
| ERC | 0.1418 | 1.0000 | 1.0000 | 1.0000 | 0.5935 | 0.7790 | -0.2379 | 0.3986 | 0.5995 | 81.4715 | 5.7543 | 0.0330 | 84.7647 | 0.0499 | 1.4775 | 0.4508 |
| EW | 0.1467 | 1.0000 | 1.0000 | 1.0000 | 0.5834 | 0.7588 | -0.2389 | 0.3892 | 0.5903 | 84.7647 | 6.2077 | 0.0236 | 84.7647 | 0.0245 | 1.3869 | 0.5097 |
| buy-and-hold USMV | 0.1206 | 0.9675 | 0.9140 | 0.9675 | 0.5220 | 0.7516 | -0.1735 | 0.3354 | 0.5331 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.7514 | 0.5657 |
| buy-and-hold ACWI | 0.1427 | 1.0000 | 0.9996 | 1.0000 | 0.6614 | 0.8509 | -0.2574 | 0.4600 | 0.6600 | 1.0000 | 1.0000 | 0.0000 | 1.0000 | 0.0000 | 1.8740 | 0.2783 |

## Mechanical reading of the six criteria

- c1: False
- c2: False
- c3: False
- c4: False
- c5: False
- c6: False
w156: c1 vol 0.1066 < 0.1083, p_gate 0.1552 <= 0.05; c2 Sharpe 0.5282 >= 0.5506; c3 MaxDD -0.2310 >= -0.2225; c4 DSR 0.2927 >= 0.95; eff N method 2.6284, primary 3.1935 (floor 5).
w260: c1 vol 0.1077 < 0.1075, p_gate 0.5715 <= 0.05; c2 Sharpe 0.6115 >= 0.6453; c3 MaxDD -0.2462 >= -0.2307; c4 DSR 0.3875 >= 0.95; eff N method 2.0792, primary 2.5586 (floor 5).
c5: 260w volatility and Sharpe direction only; 260w effective-N tripwires are information only.
c6: composition method 0.0000, null 0.0000; both must equal zero, be computable, and both 156w effective N must be >= 5.

## Book eligibility

book_eligible: no (gate label is VOID, not PASS)
LW2008 vs USMV (informational): 0.2511392811394919
Book comparison details: {"beats_on_maxdd": false, "beats_on_sharpe": false, "eligible": false, "lw2008_p_vs_usmv": 0.2511392811394919, "maxdd_method": -0.23095302115908078, "maxdd_usmv": -0.19055940910233926, "reason": "gate label is VOID, not PASS", "sharpe_exbil_method": 0.5282293945809092, "sharpe_exbil_usmv": 0.6977323928207804}

## DSR notes and trial registry

V = 0.01948818, sample variance of monthly Sharpes from the registry. 6 of 8 trials have ex-BIL Sharpe in the preregistered run; the two invalidated trials have only legacy rf=0 records. DSR uses Bailey & López de Prado (2014); repo approximation is informational.

| trial_id | line | window_weeks | status | Sharpe_exBIL_annual | Sharpe_rf0_legacy_recorded | source | preregistered | trial_count |
|---|---|---|---|---|---|---|---|---|
| v1_invalid_w156 | v1 | 156 | invalid (numerical bug), counted | nan | 0.796 | invalidated v1 legacy record | True | 8 |
| v1_invalid_w260 | v1 | 260 | invalid (numerical bug), counted | nan | 0.733 | invalidated v1 legacy record | True | 8 |
| v1_w156 | v1 | 156 | valid | 0.09335655756172109 | nan | data/processed/nonlinear_shrinkage_gmv/oos_returns.csv | True | 8 |
| v1_w260 | v1 | 260 | valid | 0.03836411353745967 | nan | data/processed/nonlinear_shrinkage_gmv/oos_returns.csv | True | 8 |
| v2_w156 | v2 | 156 | valid | -0.4893806276166144 | nan | data/processed/nonlinear_shrinkage_gmv_v2/summary.csv | True | 8 |
| v2_w260 | v2 | 260 | valid | -0.5267547832148654 | nan | data/processed/nonlinear_shrinkage_gmv_v2/summary.csv | True | 8 |
| v3_w156 | v3 | 156 | valid | 0.5282293945809092 | nan | current v3 full-window method | True | 8 |
| v3_w260 | v3 | 260 | valid | 0.6115398362811979 | nan | current v3 full-window method | True | 8 |

2026-09 is a partial month through 2026-09-16. Book 2 (2021-02..2026-09) is a sub-period (not a trial).
Bootstrap settings: {"bootstrap_reps": 5000, "block_size": 4, "seed": 20260926}
LW2008 Sharpe comparisons are informational and never change the label.

