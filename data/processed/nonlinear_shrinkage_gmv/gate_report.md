# Analytical nonlinear shrinkage GMV (Bet 1) — gate report

**Verdict: VOID — cash-dominated, no evidence of estimator edge** (Quant, 2026-09-26). Not PASS, not FAIL.

All criteria passed mechanically, but the test design was broken: the primary null (weekly LW MinVar) was ~68% in the cash-like category and the method ~81%, and Sharpe_rf0 rewards whichever holds more T-bills. NW t vs the null was +0.48 (156w) / +0.76 (260w): no evidence of a return edge. DSR at a low trial_count is effectively PSR vs zero and carries no weight.

**Follow-up:** v2 re-spec (Quant ticket ENGINEERING_TICKET_nonlinear_shrinkage_gmv_v2_excash.md): ex-cash universe (cash_like tag excluded for the method and every null), Sharpe in excess of BIL (priced) with Sharpe_rf0 as legacy, realized-vol primary test; trial_count carries forward from 4.

**Cash-share caveat:** The 'US Treasuries / Govt / Cash-like' category used for the cash shares also contains duration (e.g. GOVT, IEF, TLT, SHY), while USFR sits in 'High Yield Credit'; quoted cash shares therefore mix in some duration and are not a pure T-bill share.

Research only. Registry enabled:false. No live-book wiring.

- Ticket: `/workspace/investments/justina_shortlist/ENGINEERING_TICKET_nonlinear_shrinkage_gmv.md`
- Teaching note: `/workspace/investments/methods/allocation_alpha_nonlinear_shrinkage_gmv.html`
- OOS window: 2021-04-30 → 2026-08-31 (65 monthly evaluations)
- Primary null: LW (2004) linear-shrinkage long-only MinVar re-estimated on the SAME weekly returns and window.
- Monthly LW MinVar (Archive, Spectral RP gate) appears only as a labeled reference row.

## Geometry

Monthly/universe/weekly intersection; excluded categories, static coverage and ADV filters; dynamic monthly history and complete weekly windows. Snapshot filters imply survivorship bias.

Mirrors the committed Spectral RP name gate (data/processed/spectral_rp/name/trial_registry.csv: adv_min 0.0, include_thin false, min_names 100, same excluded categories, 5 bp). An ADV >= $10M snapshot filter is NOT applied: it would leave 98 non-thin names (< 100), and the archived gate did not apply it. Eligible N per rebalance matches the archived gate (101-120).

Monthly decisions, next observed monthly evaluation within inclusive trial OOS bounds; weekly dates <= decision; no warm-up skipping.

Half L1 change from previous target weights, including initial entry; turnover times trial cost_bps / 10000.

Covariance divided by mean diagonal; SLSQP, equal initial weights, bounds (0,1), sum=1, maxiter=1000, ftol=1e-12; shared spectral nulls.

Clean-room Ledoit-Wolf (2020) analytical nonlinear shrinkage, p < n case; demeaned inside each window, effective n = T - 1 (paper Remark 2.1), c = N/n, h = n^(-1/3), h_j = lambda_j h; Hilbert transform far field (|x| >= 10) via exact series for float64 stability.

## 156-week configuration

| Strategy | Sharpe_rf0 | AnnVol | OOS var (ann.) | MaxDD | turnover/yr | HHI | eff N | avg N | NW t vs weekly LW | DSR |
|---|---|---|---|---|---|---|---|---|---|---|
| method | 5.734 | 0.58% | 0.00% | -0.03% | 64.74% | 0.3497 | 3.02 | 110.26 | 0.48 | 1.0000 |
| weekly LW MinVar (primary null) | 2.370 | 1.31% | 0.02% | -2.96% | 30.79% | 0.1071 | 9.52 | 110.26 | — | 1.0000 |
| EW | 0.828 | 10.76% | 1.16% | -18.40% | 12.40% | 0.0091 | 110.26 | 110.26 | 1.89 | 0.8919 |
| ERC | 1.057 | 4.14% | 0.17% | -8.82% | 26.16% | 0.0449 | 22.54 | 110.26 | 1.21 | 0.9614 |
| monthly LW MinVar (reference only) | 1.598 | 1.79% | 0.03% | -4.46% | 31.83% | 0.0818 | 13.32 | 110.26 | -0.70 | 0.9987 |

## 260-week configuration

| Strategy | Sharpe_rf0 | AnnVol | OOS var (ann.) | MaxDD | turnover/yr | HHI | eff N | avg N | NW t vs weekly LW | DSR |
|---|---|---|---|---|---|---|---|---|---|---|
| method | 5.627 | 0.59% | 0.00% | -0.09% | 50.34% | 0.4491 | 2.27 | 110.26 | 0.76 | 1.0000 |
| weekly LW MinVar (primary null) | 2.387 | 1.25% | 0.02% | -2.69% | 24.32% | 0.1087 | 9.24 | 110.26 | — | 1.0000 |
| EW | 0.828 | 10.76% | 1.16% | -18.40% | 12.40% | 0.0091 | 110.26 | 110.26 | 1.91 | 0.8919 |
| ERC | 1.050 | 3.97% | 0.16% | -8.32% | 20.99% | 0.0471 | 21.30 | 110.26 | 1.17 | 0.9599 |
| monthly LW MinVar (reference only) | 1.598 | 1.79% | 0.03% | -4.46% | 31.83% | 0.0818 | 13.32 | 110.26 | -0.32 | 0.9987 |

## Holdings composition (descriptive)

Average over rebalances. Sharpe_rf0 uses rf = 0, so for portfolios dominated by T-bill / cash-like ETFs it largely reflects the cash yield over the OOS window, not excess return.

| Config | Strategy | Cash-like category weight | Top holdings (avg) |
|---|---|---|---|
| 156w | EW | 8.6% | ACWI 0.9%; ACWX 0.9%; AGG 0.9%; BIL 0.9%; BSV 0.9% |
| 156w | ERC | 47.8% | USFR 9.0%; BIL 8.9%; SHV 8.3%; GBIL 7.5%; SPTS 5.0% |
| 156w | monthly LW MinVar (reference only) | 59.9% | USFR 11.1%; BIL 11.0%; SHV 10.7%; GBIL 10.0%; SHY 7.7% |
| 156w | weekly LW MinVar (primary null) | 67.6% | USFR 13.8%; BIL 13.7%; SHV 13.3%; GBIL 12.0%; SHY 8.3% |
| 156w | method | 81.0% | BIL 47.3%; USFR 17.9%; SHV 17.8%; GBIL 7.9%; SGOV 7.7% |
| 260w | EW | 8.6% | ACWI 0.9%; ACWX 0.9%; AGG 0.9%; BIL 0.9%; BSV 0.9% |
| 260w | ERC | 51.2% | BIL 9.0%; USFR 8.9%; SHV 8.5%; GBIL 7.8%; SPTS 5.9% |
| 260w | monthly LW MinVar (reference only) | 59.9% | USFR 11.1%; BIL 11.0%; SHV 10.7%; GBIL 10.0%; SHY 7.7% |
| 260w | weekly LW MinVar (primary null) | 70.0% | BIL 13.7%; USFR 13.7%; SHV 13.3%; GBIL 12.0%; SHY 9.2% |
| 260w | method | 84.5% | BIL 53.9%; USFR 14.0%; SGOV 12.4%; SHV 11.1%; GBIL 6.7% |

Cash-like = universe Category "US Treasuries / Govt / Cash-like" (usa_universe_categorized.csv). That category also contains duration (e.g. GOVT, IEF, TLT, SHY) and misses USFR (labelled High Yield Credit), so these shares mix in some duration and are not a pure T-bill share.

## DSR and trial_count

trial_count = 4 (2 pre-registered configs + 2 configs from the invalidated first run, counted per Quant + 0 extra previews). normal approximation; monthly Sharpe (repo deflated_sharpe_approx, Bailey & Lopez de Prado 2014).

**DSR is non-decisive.** Sharpe_rf0 is the repo convention (compound annual return / annualized vol, as in the Spectral RP gate) and rewards cash carry; DSR input is Sharpe_rf0/sqrt(12). At this low trial_count the expected-max-noise term is small, so DSR is effectively a PSR vs zero without skew/kurtosis adjustment and carries no weight in the verdict.

All extra previews count: none.

Pre-registered trials: 156w, 260w.

### Invalidated first run (same configs; counted in trial_count)

- **2026-09-25 ~23:49 ET: first full walk-forward of the two pre-registered configs (156w, 260w)** — invalid (numerical bug), superseded.
  - Bug: closed-form Epanechnikov Hilbert transform cancelled catastrophically in float64 for |x| >> sqrt(5) (wrong by orders of magnitude at |x| ~ 1e7, wrong sign at 1e8); with sample eigenvalues spanning ~7 decades the largest eigenvalues were shrunk to ~1e-9 of their sample values, so 'GMV' loaded on the highest-variance ETFs.
  - Fix: exact far-field series for |x| >= 10 (same function; quadrature-verified to 1e-9 relative); regression tests added.
  - Invalid method numbers (do not use): 156w Sharpe 0.796 / AnnVol 14.54% / MaxDD -23.02%; 260w Sharpe 0.733 / AnnVol 14.46% / MaxDD -22.88%.
  - Nulls affected: no (EW, weekly LW MinVar, ERC do not use the estimator).

Counted in trial_count per the Quant ruling.

## Weekly versus monthly LW (reference only)

This frequency comparison is separate from the estimator gate checks. The committed monthly allocation is reference only.

156 weeks: 65 common months; NW t (weekly − monthly) 0.70.

| Metric | Weekly LW | Monthly LW (reference only) | Difference |
|---|---|---|---|
| Sharpe_rf0 | 2.370 | 1.598 | 0.772 |
| AnnVol | 1.31% | 1.79% | -0.49% |
| MaxDD | -2.96% | -4.46% | 1.49% |

260 weeks: 65 common months; NW t (weekly − monthly) 0.32.

| Metric | Weekly LW | Monthly LW (reference only) | Difference |
|---|---|---|---|
| Sharpe_rf0 | 2.387 | 1.598 | 0.789 |
| AnnVol | 1.25% | 1.79% | -0.54% |
| MaxDD | -2.69% | -4.46% | 1.77% |

## Mechanical gate checks (superseded by the VOID verdict)

All v1 criteria passed mechanically, but the design was broken (cash-dominated method and null, Sharpe_rf0), so these checks carry no weight.

```json
{
  "w156": {
    "vol_lower_than_primary_null": true,
    "sharpe_ge_primary_null": true,
    "maxdd_no_worse_than_primary_null": true,
    "dsr_ge_0p95": true,
    "sharpe_gt_ew": true,
    "sharpe_gt_erc": true
  },
  "w260": {
    "vol_lower_than_primary_null": true,
    "sharpe_ge_primary_null": true,
    "maxdd_no_worse_than_primary_null": true,
    "dsr_ge_0p95": true,
    "sharpe_gt_ew": true,
    "sharpe_gt_erc": true
  },
  "w260_points_same_way": true
}
```

Verdict: VOID — cash-dominated, no evidence of estimator edge. Follow-up: v2 ex-cash re-spec.
