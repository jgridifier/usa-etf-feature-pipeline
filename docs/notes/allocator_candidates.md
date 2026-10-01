# CIO note: candidates for the 100+ ETF allocator (2026-09-30)

Research on an experimental ETF panel for Jared's own decisions. Not investment advice.

## Requirements (from Jared)
- Every method must come from a peer-reviewed or working paper published in 2020 or later.
- Statistical or classical ML methods only. No large pretrained models.
- Gate (unchanged): beat LW min-variance on Sharpe above BIL, using complete-month panels, with the composition tripwire on.

## Why risk-only allocators keep failing here
Nonlinear-shrinkage GMV failed three times (v1–v3). Long-only, risk-only allocators collapse into the lowest-volatility funds: first cash, then short bonds, then USMV/EFAV. The no-short constraint already does most of the shrinking (Jagannathan & Ma 2003). To beat min-variance on Sharpe, a method probably needs return information.

## Candidates (CIO ranking; citations checked by Quant)
1. **Anchored EPO.** Pedersen, Babu & Levine (2021), *Financial Analysts Journal* 77(2), 124–151, doi:10.1080/0015198X.2020.1854543.
   - Mechanism: shrinks correlations toward the identity by w, around an anchor portfolio. At w=1 it returns the anchor itself.
   - Uses a return signal: 12-1 excess-of-BIL trend (Baltussen, Swinkels & van Vliet 2021, *JFE* 142(3)).
   - Failure modes: a weak signal falls back toward min-var, and a strong one concentrates in recent winners.
   - Quant's caveat: the paper's gains are gross of costs and come from long-short books. Long-only runs are its weakest.
   - **Selected by Quant.**
2. **Schur complementary allocation.** Cotton (2024), arXiv 2411.05807. This is a working paper with no journal publication.
   - Mechanism: interpolates between HRP and min-variance via γ. It uses risk only.
   - Failure modes: at low γ it is HRP, which on a mixed universe drifts into cash and short bonds. At high γ it is just min-var.
3. **GMV plus a scaled tilt under estimation risk.** Kan, Wang & Zhou (2022), *Management Science* 68(3).
   - Mechanism: 100% sample GMV plus a scaled zero-investment tilt.
   - At our size (about 100+ assets over about 119 months) the scale is roughly 0–0.05, so it is effectively GMV. Diagnostic only.

## Pre-registered EPO conditions
| Setting | Value |
|---|---|
| Primary w | 0.75 |
| Sensitivities | w = 0.50, 0.90 |
| trial_count | 11 |
| Anchor | 1/σ |
| Signal | 12-1 is final |

**Universe:** the EPO universe has 135 names: 98 equity, 20 bond and 17 commodity. Cash-like, short-duration and near-cash funds are excluded.

**Gate:**
- Null: LW min-variance on the same names. Test: LW2008 Sharpe-difference test on Sharpe above BIL.
- Composition tripwire: limit ≤50%.
- Effective N ≥ 5 applies to the method only. The null's effective N is a diagnostic.

**Book eligibility (CIO):** a PASS counts toward a book only if all three of these hold:
1. The w=0.75 point estimate of Sharpe above BIL is higher than the 1/σ anchor's, on the full OOS window.
2. EPO beats Book 1 on Sharpe above BIL or MaxDD. Both are net of costs and measured on the overlapping months from 2020-11. The published gross series is printed as a reference.
3. The average OOS equity share is at least 50%. Asset class comes from the EPO universe's asset-class tags.

If any of these fails, the result is research-only.

**Power caveat:** with about 119 months, a Sharpe gap of about 0.5 is needed for p≤0.05. A modest real edge may read "not significant", and it will be recorded that way, with no reruns.
