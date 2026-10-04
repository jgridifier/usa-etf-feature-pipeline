# Quant stage-2 robustness appendix: KWZ, DeMiguel, replications, holdout power

Date: 2026-10-04 (ET). Role: Quant (research only; not investment advice). This file goes with `QUANT_PREREG_stage2_holdout.md` (body sha256 `42f01906…`) and `QUANT_PREREG_stage2_holdout_ADDENDUM.md` (body sha256 `46010264…`). All code is in `stage2_code/` and all outputs are in `stage2_code/results/`. Run with `stage2/venv/bin/python` (numpy 2.5.3, scipy 1.18.1) and `OMP_NUM_THREADS=1`.

**Firewall.** No candidate return dated 2008-01 … 2016-10 was loaded in any step. `common.py::firewall` raises an error on any row dated ≤ 2016-10. The development window is the spent one: lookbacks from 2016-11, OOS decisions 2019-11 … 2026-09, T = 83. The replications use public Ken French data (`stage2_code/public_data/`) and synthetic data only. The 2009 momentum-crash figures below come from Ken French factor and decile files, not from candidate ETFs.

## 0. Summary for the committee
1. **KWZ (2022) does not fall back to EW. It falls back to GMV.** Derived in §1.1 and checked by Monte Carlo in §1.3. At our dimensions (N = 45–96), a monthly lookback of 36 is infeasible for every N, and 60 is infeasible for N ≥ 60. Where the rule is feasible, the estimated ĉ is 0.01–0.19, so KWZ sits close to GMV. The EW-anchored blend that the plan described is the Tu–Zhou-style rule 2-B (§1.2). It falls back to EW as h → N+2, but at weekly h = 156 its δ̂ ≈ 0.75–0.84, so it is mostly GMV, not "EW plus a little".
2. **DeMiguel tilt on dev:** κ = 5 was selected (0.633 vs EW 0.600). That edge sits inside noise:
   - Bootstrap 95% CI [−0.10, +0.16].
   - Placebo p = 0.08. The in-sample gain is real (placebo p = 0.01), but it barely survives out of sample.
   - The γ×κ surface spans 0.48–0.64.
   - Turnover is about 355% a year, and θ̂ sits on the grid bound in 88% of months.
   - Smoothing does not help.
3. **Replications:**
   - KWZ Tables 1–2 (10 momentum portfolios 1927–2018; 49 industry portfolios 1969-07…2018-12) reproduce within about 0.01 of Sharpe.
   - DeMiguel's "costs increase the number of significant characteristics" shows up in a 49-industry, two-characteristic version: 1 significant characteristic at 0 bp, 2 at 50 bp.
4. **Holdout power, T = 106:** with EW's true Sharpe at 0.55, a no-skill candidate passes C1 and C4 14% of the time at N = 2 (any of 2: 23%) and 5% at N = 4 (any of 4: 12%). A true +0.3 Sharpe edge passes only 58% (N = 2) or 34% (N = 4). **C4 is effectively a test of absolute Sharpe, so it depends on the regime.** If the holdout's true EW Sharpe is 0.35 (the window includes 2008), a +0.3 edge passes only 36% (N = 2) or 16% (N = 4). Changing C1 to "Memmel p ≤ 0.20" cuts the no-skill pass rate from 14% to 6% at N = 2, while power at Δ ≥ +0.2 stays essentially unchanged. **Recommendation: a CoS-approved pre-holdout amendment to C1.**

## 1. KWZ (2022): explicit derivation and Monte Carlo
### 1.1 The combining rule (no risk-free asset)
**Setup.** N risky assets with returns r_t ~ iid N(μ, Σ). The investor maximises U(w) = w′μ − (γ/2) w′Σw subject to 1′w = 1. Define:
- w_g = Σ⁻¹1/(1′Σ⁻¹1) (GMV), with σ_g² = 1/(1′Σ⁻¹1) and μ_g = w_g′μ;
- w_z = Σ⁻¹(μ − μ_g 1), a zero-investment portfolio (1′w_z = 0);
- ψ² = (μ − μ_g1)′Σ⁻¹(μ − μ_g1), the squared slope of the frontier asymptote.

Then w* = w_g + w_z/γ and U(w*) = μ_g − γσ_g²/2 + ψ²/(2γ).

**Estimation.** Use the MLEs μ̂ and Σ̂ (divisor h) from h observations. Then μ̂ is independent of Σ̂, and hΣ̂ ~ W_N(h−1, Σ). KWZ consider ŵ_c = ŵ_g + (c/γ)ŵ_z. Since 1′ŵ_z = 0 and Σw_g = σ_g²1, the cross term w_g′Σŵ_z vanishes, so out-of-sample utility separates:

  E[U(ŵ_c)] = E[U(ŵ_g)] + (c/γ)·A − (c²/(2γ))·B,

where:
- A = E[ŵ_z′μ] = h/(h−N−1)·ψ², which uses E[Σ̂⁻¹] restricted to the (N−1)-dimensional zero-investment space;
- B = E[ŵ_z′Σŵ_z] = h²(h−2)/[(h−N)(h−N−1)(h−N−3)]·(ψ² + (N−1)/h), from the second inverse-Wishart moment plus the μ̂ noise term (N−1)/h;
- E[U(ŵ_g)] = μ_g − (γ/2)σ_g²·(h−2)/(h−N−1).

**Optimal c.** Maximising over c gives

  c* = A/B = k·ψ²/(ψ² + (N−1)/h),  k = (h−N)(h−N−3)/(h(h−2))   (KWZ eqs 20–22),

which exists only for **h > N+3**. The feasible rule replaces ψ² with the Kan–Zhou (2007) adjusted estimator ψ̂²_a (KWZ eq 23, incomplete beta), implemented in `kwz_rules.py::psi2_adjusted`.

**What happens under noise:**
- When ψ² → 0, or h ↓ N+3, k → 0 and c* → 0, so **ŵ_q → ŵ_g, the sample GMV.**
- When ψ² is large and h → ∞, c* → 1, giving the plug-in mean-variance rule.

EW does not appear anywhere in this rule. In the paper 1/N is only a comparator.

**Verification of the closed form (`kwz_mc.py`, "lemma1").** At N = 45, h = 120, c = 0.5, with the dev-calibrated Σ and μ, the analytic E[U] is −0.03131 and the Monte Carlo value is −0.03158 (s.e. 0.00057, 1000 reps), a 0.5 s.e. difference. The mean of ĉ also tracks c* in every feasible cell (tables below).

### 1.2 The EW-anchored alternative (2-B, Quant derivation, Tu–Zhou 2011 family)
Take w_δ = (1−δ)w_e + δŵ_g with w_e = 1/N. KWZ (A11) gives two exact results: E[ŵ_g] = w_g and E[ŵ_g′Σŵ_g] = σ_g²(h−2)/(h−N−1). Also w_e′Σw_g = σ_g², because Σw_g = σ_g²1. So expected out-of-sample variance is

  V(δ) = (1−δ)²σ_e² + 2δ(1−δ)σ_g² + δ²σ_g²(h−2)/(h−N−1).

Setting the derivative to zero and using (h−2)/(h−N−1) = 1 + (N−1)/(h−N−1):

  **δ* = ψ_e²/(ψ_e² + (N−1)/(h−N−1)),  ψ_e² = σ_e²/σ_g² − 1 ≥ 0.**

So δ* → 0 (pure EW) as h ↓ N+1, or as EW approaches efficiency (ψ_e² → 0).

**Feasible estimator.** Let n = h−1 and ratio = (w_e′Σ̂w_e)(1′Σ̂⁻¹1). Then E[ratio] = (n−2)/(n−N−1) + ψ_e²·n/(n−N−1), which gives the unbiased estimator ψ̂²_e,a = max{0, [ratio·(n−N−1) − (n−2)]/n}. The bias formula was checked by Monte Carlo in `kwz_mc.py`. Two caveats: the rule ignores means (it minimises variance), and it is outside the 2020+ rule, so it needs Jared's waiver.

### 1.3 Monte Carlo on panel-like dimensions
`kwz_mc.py` and `summarize_kwz_mc.py` produce `results/kwz_mc.csv`, `kwz_mc_checks.json` and `kwz_mc_tables.md`.

**Truth.** Σ is the LW-shrunk covariance of the 81 full-history dev-window equity ETFs, using weekly data inside the dev window and subsetting N names. μ comes in three versions:
- "raw": dev sample means, ψ² ≈ 0.37 monthly, which flatters mean-based rules;
- "shrunk";
- "flat": all means equal, ψ² = 0, so no rule should use means.

**Simulation.** For each (frequency, N, h) cell, draw iid normal samples (1000 reps), form each rule, and score expected out-of-sample CE = w′μ − (3/2)w′Σw with the true moments.

Monthly CE ×1e4 ("–" = infeasible). Values in brackets are the mean of the estimate (truth):

| freq | N | h | EW | GMV-LW | KWZ q | KWZ plug-in | KWZ q-LW | q-LW capped | 2-B blend | blend capped | ĉ (c*) raw μ | δ̂ (δ*) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| monthly | 45 | 36 | 44 | 48 | – | – | – | – | 44 (=EW) | – | – | 0 (0) |
| monthly | 45 | 60 | 44 | 47 | 2 | −146604 | 58 | 49 | 40 | 43 | 0.019 (0.017) | 0.38 (0.40) |
| monthly | 45 | 120 | 44 | 45 | 198 | −3209 | 139 | 58 | 38 | 43 | 0.184 (0.192) | 0.77 (0.78) |
| monthly | 60 | 36/60 | 45 | 39 | – | – | – | – | 45 (=EW) | – | – | 0 (0) |
| monthly | 60 | 120 | 45 | 39 | 139 | −10124 | 92 | 52 | 41 | 52 | 0.104 (0.107) | 0.75 (0.76) |
| monthly | 96 | 36/60 | 44 | 38–40 | – | – | – | – | 44 (=EW) | – | – | 0 (0) |
| monthly | 96 | 120 | 44 | 41 | 130 | −388531 | 64 | 45 | 47 | 50 | 0.017 (0.018) | 0.54 (0.56) |
| weekly | 45 | 156 | 10 | 10 | 21 | −1314 | 23 | 12 | 8 | 10 | 0.133 (0.116) | 0.83 (0.84) |
| weekly | 60 | 156 | 10 | 9 | 13 | −2993 | 18 | 11 | 9 | 12 | 0.090 (0.071) | 0.83 (0.84) |
| weekly | 96 | 156 | 10 | 10 | 24 | −23135 | 20 | 11 | 11 | 11 | 0.038 (0.035) | 0.75 (0.76) |

With flat μ (ψ² = 0, no mean information; full table in `kwz_mc_tables.md`), KWZ-q earns −13 to +44 against GMV-LW at 65–71. ĉ averages 0.01–0.08 because ψ̂²_a is clipped at a small positive value. The q rule still pays a small price for estimating means when none exist.

**Reversion curve** at N = 45 (dev Σ, raw μ, true ψ_e² = 2.11):

| h | 48 | 50 | 55 | 65 | 85 | 120 | 240 | 480 |
|---|---|---|---|---|---|---|---|---|
| δ̂ (2-B), 0 = EW | 0.06 | 0.14 | 0.28 | 0.45 | 0.63 | 0.77 | 0.90 | 0.95 |
| ĉ (KWZ), 0 = GMV | – | 0.001 | 0.009 | 0.030 | 0.082 | 0.18 | 0.43 | 0.65 |

**Conclusions:**
- (i) The KWZ plug-in rule is catastrophic at these dimensions, and the q correction rescues it. That is the paper's main qualitative claim, and it is confirmed here.
- (ii) Under noise KWZ reverts to **GMV**, not EW.
- (iii) The rule that reverts to EW is 2-B, and only as h approaches N+2. At the feasible weekly h = 156 it is about 80% GMV.
- (iv) The long-only cap projection removes most of the difference between rules. The capped versions sit at 43–58 vs EW 44 (monthly units). In the dev backtest, the raw KWZ-LW weights carried an average of 291% short mass before projection (sample-Σ version: 6,348%). **The long-only, capped "KWZ" in our gate is therefore a projection of a long-short rule. The paper's optimality result does not carry over to it.** This caveat must be printed next to any 2-A result.

### 1.4 Dev-window behaviour (diagnostic, non-selectable; 2019-11 … 2026-09)
| rule | Sharpe ex-BIL | Δ vs EW | Turnover/yr | Mean coefficient |
|---|---|---|---|---|
| capped EW | 0.600 | – | 40% | – |
| LW MinVar (QP, capped) | 0.373 | −0.227 | 132% | – |
| 2-A KWZ q-LW (h = 156 wk), capped | 0.560 | −0.040 | 209% | ĉ = 0.015 (p10–p90 0.008–0.024) |
| KWZ q-sample, capped | 0.616 | +0.016 | 465% | ĉ = 0.015 |
| 2-B EW/GMV blend, capped | 0.625 | +0.025 | 455% | δ̂ = 0.82 (0.74–0.87) |

## 2. DeMiguel et al. (2020) tilt: dev-window study
Code: `dev_engine.py`, `dev_study.py` and `dev_diag_smoothing.py`. Logs: `results/dev_variant_log.csv` (selection plus first diagnostics) and `results/dev_diag_variant_log.csv` (surface, costs, smoothing). Every run is published. Diagnostics are `selectable = N` and run after the spec hash.

### 2.1 Selection (prereg §3.6)
| κ | Sharpe ex-BIL | Turnover/yr | θ̄ (MOM, VOL) | θ̂ on bound |
|---|---|---|---|---|
| 1 | 0.636 | 373% | (+1.12, −0.89) | 89% |
| **5 (selected)** | **0.633** | 355% | (+1.04, −0.89) | 88% |
| 25 | 0.476 | 354% | (+0.96, −0.37) | 47% |
| EW | 0.600 | 40% | – | – |

The selected spec beats EW by **+0.033**:
- Block-bootstrap 95% CI: [−0.10, +0.16]; P(≤ 0) = 0.31.
- Correlation with EW: 0.977.
- MaxDD −24.8% vs EW −25.3%.

### 2.2 Sensitivity to λ (γ, κ), caps, H, characteristics and costs (one at a time around κ = 5)
**γ × κ surface** (Sharpe ex-BIL; EW = 0.600):

| γ \ κ | 0 | 1 | 5 | 25 | 100 |
|---|---|---|---|---|---|
| 2 | 0.560 | 0.569 | 0.572 | 0.547 | 0.600 (=EW) |
| 5 | 0.638 | 0.636 | **0.633** | 0.476 | 0.600 (=EW) |
| 10 | 0.616 | 0.609 | 0.613 | 0.582 | 0.592 |

At κ = 100 the turnover penalty forces θ̂ = 0, so the rule collapses exactly to EW. This sanity check confirms the tilt nests EW.

**Other single-parameter sensitivities:**

| Change | Sharpe | Δ vs EW (same settings) | Turnover/yr |
|---|---|---|---|
| cap 10% | 0.630 | +0.029 | 354% |
| no cap / no low-vol cap | 0.633 | +0.033 | 355% |
| H = 12 | 0.692 | +0.091 | 514% |
| MOM only | 0.554 | −0.047 | 441% |
| VOL only | 0.483 | −0.117 | 304% |

The two characteristics hedge each other's turnover: TO(both)/[TO(MOM) + TO(VOL)] = 0.48 (netting). Each one alone loses to EW.

**Costs, two channels:**

| Cost (bp) | 0 | 2 | 5 | 7.5 | 10 | 15 | 25 | 50 |
|---|---|---|---|---|---|---|---|---|
| Δ vs EW, re-estimating θ at that cost | +0.047 | +0.040 | +0.033 | +0.007 | −0.044 | −0.086 | −0.161 | −0.105 |
| Δ vs EW, θ path fixed at 5 bp, charge only | – | – | +0.033 | +0.028 | +0.023 | +0.018 (12.5) | +0.013 (15) | – |

The charged-cost drag is small: about 0.01 Sharpe per extra 5 bp at 355% turnover. The large swing comes from **θ̂ choosing a different bound-to-bound path** when the cost in the objective changes. This is path dependence, i.e. estimation noise, not a cost effect.

### 2.3 Placebo: shuffled characteristics (B = 100)
**Design.** For each placebo, draw a fixed random order of the ETFs. Each ETF then receives the MOM and VOL of its neighbour in that order (a fixed cyclic shift). This keeps the cross-sectional distribution and the time persistence of the characteristics, so turnover is comparable. It breaks the link between an ETF's own characteristic and its own future return. Everything else, including the κ = 5 objective and the caps, is unchanged.

| | Real | Placebo mean | Placebo 5–95% | p (one-sided) |
|---|---|---|---|---|
| OOS Sharpe ex-BIL | 0.633 | 0.586 | 0.540–0.636 | **0.08** |
| Mean in-sample J gain (monthly) | 0.00275 | 0.00059 | p95 0.00113 | **0.01** |

**Reading:**
- About 21% of the in-sample gain is what noise alone delivers.
- The real characteristics do carry in-sample signal. Out of sample, though, the real rule sits at the edge of the placebo band.
- The placebo mean is *below* EW (0.586 vs 0.600). A noise tilt costs about −0.014 Sharpe through turnover and concentration, so the real rule's "skill" relative to a noise tilt (+0.047) is larger than its edge over EW (+0.033).
- Either way, at 83 months the dev evidence is suggestive, not conclusive.

### 2.4 Bootstrap
Circular block bootstrap, fixed 6-month blocks, B = 5000, resampling the paired monthly returns (tilt and EW together). Δ Sharpe median +0.034, 95% CI [−0.10, +0.16].

### 2.5 θ smoothing / partial adjustment (diagnostic for a possible amendment)
| Variant | Sharpe | Δ vs EW | Turnover/yr |
|---|---|---|---|
| θ̂ trailing mean, 3 m | 0.594 | −0.007 | 321% |
| θ̂ trailing mean, 6 m | 0.561 | −0.039 | 298% |
| θ̂ trailing mean, 12 m | 0.519 | −0.081 | 297% |
| partial adjustment a = 0.5 | 0.593 | −0.007 | 221% |
| partial adjustment a = 0.25 | 0.560 | −0.040 | 151% |
| no-trade band 0.10 (L1) | 0.635 | +0.035 | 351% |
| no-trade band 0.20 (L1) | 0.641 | +0.041 | 322% |
| θ fixed at dev mean (**look-ahead**, upper bound) | 0.638 | +0.038 | 244% |

Even an oracle-stable θ adds only +0.005 over the selected rule. **No amendment is recommended.** Smoothing lowers turnover but also lowers Sharpe, and the bands differ from the frozen rule by less than the noise.

### 2.6 Holdout-specific risk: the 2009 momentum crash
The holdout spans 2008-01 … 2016-10. From public Ken French data (not candidate data), UMD returned −39% in Mar 2009, −45% in Apr and −21% in May. Over Mar–May 2009 the loser decile returned +158% and the winner decile +7%.

The tilt loads positively on MOM (θ̄ ≈ +1). In spring 2009 it would have held 2008's relative winners (defensive and low-beta equity ETFs) and avoided the losers (financials, small caps, EM). At ETF level the spread is much smaller than for single stocks. Still, a 2009 drawdown in relative terms is the most likely way #1 fails C1 or C3. That is a pre-stated risk, not a reason to re-spec. The 2008-09 MaxDD of #1, EW and the core is reported next to the gate.

## 3. Replications of each paper's key qualitative result
`replicate.py` → `results/replications.json`, using public Ken French data.

### 3.1 KWZ (2022) Tables 1–2: monthly CER and Sharpe, γ = 3, h = 120, rolling
| Dataset | Rule | Reproduced CER / SR | Paper CER / SR |
|---|---|---|---|
| Momentum-10 (T_oos = 984) | q | .0091 / .245 | .0098 / .252 |
| | plug-in p | −.0073 / .228 | −.0063 / .238 |
| | g (GMV) | .0052 / .185 | .0051 / .182 |
| | LW2004_q | .0117 / .267 | .0120 / .269 |
| | 1/N | .0026 / .127 | .0026 / .128 |
| Industry-49 (T_oos = 474) | q | .0020 / .115 | .0022 / .119 |
| | p | −.380 / .072 | −.400 / .061 |
| | g | .0021 / .113 | .0025 / .123 |
| | LW2004_q | .0039 / .159 | .0042 / .166 |
| | 1/N | .0038 / .152 | .0039 / .153 |

Mean ĉ is 0.40 (Momentum) and 0.04 (Industry). The qualitative results reproduce:
- q ≫ plug-in;
- LW2004_q is best;
- q falls back to about GMV when ψ² is small (Industry: q ≈ g);
- 1/N is hard to beat on Industry.

Remaining differences (≤ 0.01 SR) are consistent with later Ken French data revisions. Extending Industry-49 to 2026-08 gives 1/N 0.163 vs LW2004_q 0.183 vs q 0.141.

### 3.2 DeMiguel et al. (2020): costs increase the number of significant characteristics
Setting: 49 industry portfolios, 1969-07…2018-12. Characteristics MOM 12-1 and VOL 12m, z-scored. The rule is the paper's unconstrained w = 1/N + Xθ/N with γ = 5, fitted in-sample over the full sample as in the paper's main analysis, on a θ grid of ±6 in steps of 0.25. θ CIs come from a 12-month circular block bootstrap (300 reps).
- At 0 bp, θ̂ = (+1.75, −1.25); only MOM is significant (VOL CI [−2.38, 0.00]).
- At 50 bp, θ̂ = (+1.00, −1.00), and **both** are significant (VOL CI [−2.00, −0.25]).
- Turnover netting: TO(both) = 0.35 vs TO(MOM) + TO(VOL) = 0.47, a ratio of 0.74.

This mirrors the paper's mechanism: with costs, characteristics are valued for their turnover-netting as well as their return signal. Our K = 2 version gives a 1 → 2 change, against the paper's 6 → 15. The paper's long-short single-stock setting with many characteristics is not reproducible with public data here.

## 4. Holdout power (T = 106) under N = 2 and N = 4
`hurdles.py`, `power.py` and `power2.py` → `results/hurdles.json`, `power.json` and `power2.json`.

**Assumptions.** Synthetic iid monthly returns, 15% vol, normal or Student-t with 5 df, 6000–20000 reps. ρ(candidate, EW) uses the dev values: 0.977 for DeMiguel, 0.989 for KWZ-LW and 0.995 for the blend. C3 and the tripwires are not modelled.

**C4 hurdles** (DSR ≥ 0.95, V = 0.014061, BLP):

| N | 1 (PSR) | 2 | 3 | 4 | 13 | 117 |
|---|---|---|---|---|---|---|
| Annual Sharpe hurdle, normal | 0.56 | 0.78 | 0.92 | 1.00 | 1.27 | 1.65 |
| Skew −0.5, kurt 5 | 0.59 | 0.82 | 0.96 | 1.05 | 1.34 | 1.74 |
| True Sharpe for 80% C4 power | 0.85 | 1.06 | – | 1.29 | 1.57 | – |

**Pass probability for C1 and C4** (ρ = 0.977, normal; Δ = candidate true Sharpe − EW true Sharpe). Columns: C1 as point estimate (spec) / C1 as Memmel p ≤ 0.20:

| EW true Sharpe | Δ | N = 2 | N = 4 |
|---|---|---|---|
| 0.55 | 0 (no skill) | **0.14 / 0.06** | 0.05 / 0.02 |
| 0.55 | 0, any of N candidates | 0.23 / 0.12 | 0.12 / 0.08 |
| 0.55 | +0.1 | 0.34 / 0.26 | 0.15 / 0.12 |
| 0.55 | +0.2 | 0.48 / 0.46 | 0.24 / 0.23 |
| 0.55 | +0.3 | 0.58 / 0.58 | 0.34 / 0.34 |
| 0.55 | +0.5 | 0.80 / 0.80 | 0.56 / 0.56 |
| 0.35 | 0 (no skill) | 0.07 / 0.03 | 0.02 / 0.01 |
| 0.35 | +0.3 | 0.36 / 0.36 | 0.16 / 0.16 |

Fat tails (t5) change these by ≤ 0.02. ρ = 0.995 behaves almost identically.

**Reading:**
- (a) At Δ ≥ 0.2 the pass probability equals P(C4) alone, so **C4 is effectively an absolute-Sharpe test and C1 adds almost nothing.** Whether a candidate passes depends mostly on how good the 2008–16 regime was for all equal-weight-like portfolios.
- (b) At N = 2, a candidate that is no better than EW passes 14% of the time, and one of the two passes 23% of the time.
- (c) A Memmel-p ≤ 0.20 version of C1 halves the false-pass rate and costs almost no power at the effect sizes we could plausibly detect.
- (d) Going to N = 4 roughly halves power at every Δ. A second family should start its own cycle (CIO condition) rather than join this one.
- (e) The minimum detectable Sharpe gap against EW (one-sided 5%/80%) is about 0.27 at ρ = 0.95, 0.38 at 0.90, 0.17 at 0.98, and 0.6 only at ρ ≈ 0.75. The plan's "about 0.6" is therefore conservative for these highly EW-correlated candidates.

**Recommendation (ruling item for CoS).** Before the holdout, amend C1 to "Memmel (2003) one-sided p ≤ 0.20 vs capped EW". This would need Addendum 2 with its own hash. Otherwise, keep C1 as a point estimate and state the 14% / 23% no-skill pass rates beside any PASS.

## 5. Ruling items raised by this appendix
1. Candidate #2: 2-A (faithful KWZ, reverts to GMV, long-only projection caveat), 2-B (EW/GMV blend, needs a waiver, δ̂ ≈ 0.8), or N_holdout = 1.
2. C1 tightening (Memmel p ≤ 0.20) via Addendum 2, or the disclosure-only alternative.
3. No θ-smoothing amendment recommended. Selectable slots used for #1: 3 of 6.
4. Disclosure lines (prior use of the 2008–16 window; DSR at N = 2 beside N = 13 and N ≈ 117; about 117 trials project-wide vs 12 in the allocator line; 2008-09 MaxDD vs EW and the core) are mandatory on any page that shows the stage-2 results. See prereg §6.

## 6. Code index (`stage2_code/`)
| File | Purpose | Output |
|---|---|---|
| common.py | firewall, caps projection, LW2004, metrics | – |
| kwz_rules.py | KWZ eqs 7–26/43, 2-B blend | – |
| calib.py | dev-window truth Σ and μ for the Monte Carlo | – |
| kwz_mc.py, summarize_kwz_mc.py | §1.3 Monte Carlo, Lemma check, reversion curve | kwz_mc.csv, kwz_mc_checks.json, kwz_mc_tables.md |
| dev_engine.py, dev_study.py | §2.1–2.4 selection, sensitivity, placebo, bootstrap | dev_study.json, dev_variant_log.csv |
| dev_diag_smoothing.py | §2.2 surface and cost channels, §2.5 smoothing | dev_diag_smoothing.json, dev_diag_variant_log.csv |
| replicate.py | §3 replications (public Ken French data) | replications.json |
| hurdles.py, power.py, power2.py | §4 | hurdles.json, power.json, power2.json |
| dsr_recompute.py | ex-BIL DSR recompute (deliverable C) | ../QUANT_dsr_exbil_recompute.csv |
