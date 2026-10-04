# Addendum 3 to the Quant stage-2 holdout pre-registration: final dispositions and errata

Date: 2026-10-04 (ET). Status: **records rulings and corrects errors; changes no frozen spec**. Research only, not investment advice. Addendum 2 and the robustness appendix (§7) are not edited. Corrections to them are made here.

## 0. Prior hashes (sha256, full file)
| File | sha256 |
|---|---|
| QUANT_PREREG_stage2_holdout.md | 4d07f0a9f4d127a21ae09d7f8a426e05257f1d5115712c1e28c423b38fda0c39 |
| QUANT_PREREG_stage2_holdout_ADDENDUM.md | 74df64b3123a72f0772d77af051146b99774d8f4b0f2c3e8cfa9f3d2bbb2cf9d |
| QUANT_PREREG_stage2_holdout_ADDENDUM2.md | 8288e027b44fdfd7bb6baf0af623545d8bd2224f771c471548bc6b938b56d199 (body f004527e2c41183ef679b7ca5b9de18bc9884ef1c64816201df9963c96496e0c) |
| QUANT_stage2_robustness.md | c1ca949521e3132f9bae592acfcb5fe53fa323fdd48b646d6bc6b14963fbde17 |
| QUANT_stage2_family2_PREDECLARATION.md | d72ad33a74b40648f2700352ef6a6370f07b65206d63017500c8c6b8cd4cbf50 |
| QUANT_stage2_family2_PREDECLARATION_ADDENDUM1.md | 5ae9322b1bfee1fc7b70d00aaef71d4e97ecf0c416c3ce92d44d1fc55c1f25be |
| QUANT_stage2_family2_dev.md | 674fd1f915d7e28d83a3dad9f3c7f9510f77093ce5c2036c36b8dfe904e50dcc |

## 1. Rulings recorded (CIO and CoS, 2026-10-04)
1. **DeMiguel (frozen κ = 5 spec, Addendum 2 §6) is forward-tracked only.** It fails both parts of the CIO Book rule, so a holdout pass could only be a research result. The 2008-01 … 2016-10 holdout is **not run** on it, including on 2026-10-19. This supersedes "N_holdout = 1, DeMiguel only" in Addendum 2 §1 and robustness appendix §7.
2. **The 2008-01 … 2016-10 window stays unspent.** It is reserved for a future candidate that could become a Book. Any future use needs its own pre-registration and N count, and must disclose that the window was used by earlier trials (FT-MED, RR-ERC, Regime-dual, Spectral RP sleeve).
3. **Family 2 goes forward-only, and its qualification is decided early.** Candidate A has used all 6 of its slots and Candidate B's CI is centred on zero, so the 2026-10-18 deadline adds nothing.
   - **A: Deng–Gao–Wang plus the Antulov-Fantulin–Kolm–Šikić TE layer** (one candidate; selected A6). Anchored to the live static core. Dev CI of the Sharpe gap against the live core is [−0.123, +0.058], so it does **not qualify**. The placebo (p = 0.78) and the failed replication both point to no edge.
   - **B: Guo–Wachter core-vs-cash timing** (selected B3). Dev CI against the live core (2020-11 … 2026-09) is [−0.119, +0.269], and [−0.208, +0.197] against the stand-in core (2019-11 … 2026-09). It does **not qualify**. The result is inconclusive. B is 0.95 correlated with Book 2.
4. **Forward tracking** of DeMiguel, A6 and B3 starts with 2026-10, the first complete month. The frozen code must be verified against its hashes. Engineering owns the monthly job. Results are shown against the **live** core, with the month count and a power caveat.
5. **No Book changes.** The static core remains the default.

## 2. Errata
- **E1 (Addendum 2 §4).** Candidate (i), the DGW + AKS tilt layer, is judged against the **static core**, not "capped EW". Family-2 Addendum 1 (5ae9322b…) made this change before any core-anchored run, following the CoS ruling at 08:25 ET. Addendum 2 §4's "against capped EW" is superseded. "Excludes zero" means the CI's lower bound is > 0 (CoS confirmed).
- **E2 (turnover convention, all stage-2 documents).** The CIO Book rule's 100%/yr limit is on **textbook one-way turnover, ½·Σ|Δw|**. On that basis:

  | Candidate | One-way turnover/yr | Turnover test |
  |---|---|---|
  | DeMiguel | 178% (L1 355%) | fails |
  | A6 | **12%** (L1 24%) | passes |
  | B3 | 75% (L1 149%) | passes |

  Family-2 dev §1 applied the 100% limit to L1 turnover, which is superseded. The CIO's figure of "A is 24%" is the L1 figure. All three still fail the Book rule on CAGR at 10 bp.
- **E3 (core version and window labelling).** Every comparison leads with the **live** core (70/20/10 VOO/QQQM/IJR, from 2020-11), with the stand-in core (IVV/QQQ/IJR) in brackets as a sensitivity. Each figure names its window.
  - B3's CAGR gap at 10 bp is **−1.4 pp against the live core** (2020-11 … 2026-09), and [−2.7 pp against the stand-in core] (2019-11 … 2026-09).
  - A6's gap is −0.73 pp against the live core.
  - DeMiguel's dev window (2019-11 …) predates the live core, so its −4.3 pp is against the stand-in core.
  - The core's own Sharpe ex-BIL differs by window: 0.887 over 2020-11 … 2026-09, and the CIO's 0.77 over 2021-02 … 2026-09. These are window effects, not errors.
- **E4 (September 2026 core row).** The live-core file's 2026-09 `static_option_a` reads +0.24%, but the complete-month panel gives −0.11%. Family-2 live-core figures used that file, so they include the bad month. Once Engineering rebuilds the row, Quant will recompute the live-core figures in §1.3 and E3 and post any change. One month is expected to move CAGR gaps by about 0.05 pp and the CIs by about 0.01, with no change to the verdicts.
- **E5 (teaching page).** `methods/stage2_demiguel.html` is revised to reflect §1 (status, new-family outcome, conventions). It is not a pre-registration document. The superseded copy was sha256 8091157e656d740ceae02f2f53ec75ff049c02a8e8c56364d05ce379a9e1625d, and the new hash is recorded in the hand-off message.
- **E6 (archived DSR card).** The Book 2 / #6 skew overlay's recorded "DSR 1.00 (trial_count = 72)" is for the selected spec, `SM_option_a_vt_L63_SL21_g0p5_realizedamaya_cvar5`. Recomputed on an ex-BIL monthly basis, it is 0.533 at N = 72 (Sharpe ex-BIL 0.966). The recorded value came from the annual-Sharpe-in-monthly-formula unit bug. No verdict changes.
