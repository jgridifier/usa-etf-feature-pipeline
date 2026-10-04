# Stage 2 wrap-up: nothing beat the static core

*CIO · 4 Oct 2026 · Research on an experimental ETF panel. Not investment advice.*

## 1. Bottom line

Across stage 1 and stage 2, nothing on this panel beat the static core after costs.

The static core (70/20/10 VOO/QQQM/IJR) stays the default.

The Books are unchanged, and no candidate is Book-eligible.

## 2. What we tested and why

Stage 1 logged 12 trials in the third-book search. Some are re-runs of the same paper, so that's trials, not papers. Counting every registry on the panel gives about 117. None of the 12 passed; most failed and several were ruled void. The covariance-only allocators drifted toward low-vol funds, bonds or cash and lost to capped equal weight (EW).

Stage 2 asked a narrower question: can a method that uses *return* information, anchored to EW or to the core, do better? Every candidate had a pre-declared grid, a cap of 6 logged variants, and a placebo.

| Method | Paper | Verdict |
|---|---|---|
| DeMiguel tilt | DeMiguel, Martín-Utrera, Nogales & Uppal (2020), *RFS* | Forward-track only; fails Book rule |
| KWZ blend | Kan, Wang & Zhou (2022), *Mgmt Sci* | Dropped before any run |
| A: core-anchored tilt | Deng, Gao & Wang (2026) + Antulov-Fantulin, Kolm & Šikić (2025) | Forward-only; no edge |
| B: core/cash timing | Guo & Wachter (2025) | Forward-only; can't tell |

Key numbers (dev window, Sharpe above BIL):

| Method | vs its null | vs the core |
|---|---|---|
| DeMiguel | 0.633 vs EW 0.600; CI −0.10 to +0.16 | CAGR 12.3% vs 16.6% at 10 bp |
| A (variant A6) | Placebo p 0.78 | 0.853 vs 0.887; CI −0.12 to +0.06; CAGR −0.7 pts at 10 bp |
| B (variant B3) | Placebo p 0.33 | 0.823 vs 0.822; CI −0.21 to +0.20; CAGR −2.7 pts at 10 bp |

CI is the block-bootstrap 95% interval for the Sharpe gap. To qualify for the holdout, its lower bound had to be above zero.

Windows differ by method:
- DeMiguel and B: Nov 2019 to Sep 2026 (83 months), against the stand-in core (IVV/QQQ/IJR).
- A: Nov 2020 to Sep 2026 (71 months), against the live core.

KWZ was dropped because, under estimation noise, it falls back to minimum variance, not EW. It also can't be computed on 45–96 funds with a 36-month lookback.

The older Tu & Zhou (2011) blend toward EW would avoid that problem, but it predates your 2020-or-later rule. It's set aside unless you choose to waive the rule for it.

## 3. Why it failed, by failure family

**Risk-only drift (stage 1).** The three NLS minimum-variance runs, Spectral RP, Schur and EPO estimated only risk. They either piled into cash, short bonds or USMV/EFAV, or ended up close to EW and still lost to it. EPO went to about 84% bonds.

**Forecast noise and turnover.** FT-MED's return forecast drove about 404% a year turnover and a −58% max drawdown.

DeMiguel had the same problem in a milder form. Its tilt choice jumped between the edges of its grid in 88% of months, and turnover was 178% a year one-way. Smoothing, a quadratic cost penalty and ridge shrinkage all lowered Sharpe without lowering turnover. Its placebo p of 0.08 is suggestive, not conclusive.

**No signal.** Regime-dual, VCFC and RR-ERC never found a usable signal. RR-ERC's overlay fell back to plain ERC at every rebalance.

**Anchored, but nothing to add (A).** Anchoring to the core fixed the drift, but tilting away from the core cost about as much as the signal earned.

The selected variant, A6, effectively made one decision. Its cost penalty froze the October 2020 portfolio (QQQ 51%, USMV 16%, SUSA 14%) and traded in only 24 of 71 months. A placebo with shuffled return estimates did as well or better (p 0.78). The paper's 10-industry result also didn't replicate in any of 8 settings.

**Cutting risk, not adding return (B).** A long-only core/cash switch can't hold more than 100% of the core. So it can only beat the core's CAGR by sidestepping drawdowns.

B3 had a shallower max drawdown than the core (−19.1% vs −25.6%), but it de-risked late in COVID. Its correlation with Book 2 is 0.95, so it mostly reproduces the vol-target logic we already hold.

## 4. What "forward-only" means for each candidate

| Candidate | Reading | Why |
|---|---|---|
| DeMiguel | Research line | Fails the Book rule on turnover and CAGR, whatever a holdout shows |
| A | No edge | Placebo p 0.78; paper didn't replicate |
| B | Can't tell | CI centred on zero; replication held up; every variant had a negative CAGR gap |

**Power caveat.** These candidates move 0.95–0.99 with the core. Over 71–83 months, the dev window can only reliably detect Sharpe gaps of about 0.17–0.35. A true +0.1 edge would qualify only 12–16% of the time.

So for B, "forward-only" means the data can't tell, not that B has no edge. For A, the evidence of no edge comes from the placebo and the failed replication, not from the CI.

## 5. What we kept

**The 2008–2016 holdout is unspent.** It's our last unused stretch of history, and it can be used honestly only once.

We decided not to run it for DeMiguel, because a pass couldn't become a Book. It's lightly used, not pristine: four stage-1 trials touched those years. That gets disclosed whenever it's used.

**The frozen protocol carries over:**
- Dev on the spent window, with every variant logged.
- One pre-registered holdout run.
- DSR counted at the number of candidates actually taken to the run, shown next to 13 (the 12 stage-1 trials plus the next one, as on the trial-13 DSR feasibility page) and about 117.
- C1 as a one-sided Memmel test at p ≤ 0.20.
- The Book rule: one-way turnover at or below 100% a year, and a positive CAGR edge over the core with costs doubled to 10 bp.

**Forward tracking.** DeMiguel, A and B can be paper-traded against the live core from Oct 2026. That costs nothing and adds evidence each month.

## 6. The decision for Jared

**The Books today** (Feb 2021 to Sep 2026, net of costs):

| Book | CAGR | Sharpe ex-BIL |
|---|---|---|
| Book 1 (core) | 15.0% | 0.77 |
| Backbone | 15.1% | 0.86 |
| Book 2 | 13.9% | 0.99 |

Book 2's Sharpe edge over the vol-target backbone isn't significant (p ≈ 0.30–0.38).

These figures use the corrected Sep 2026 core month (−0.11%, full month).

**Option 1: stop allocator tweaks on these ETFs.** Keep the core and the Books, and run the forward tracker. This needs only a monthly scoring job and a hub page.

**Option 2: go back to the growth-plus-extra-alpha mandate, framed as a semis timing question.** The question is whether rotating into and out of semiconductors, via XSD, earns anything over the core.

XSD is the only semis ETF in the research panel, with history from Feb 2006. That means it covers the unspent holdout.

What it would need:
- One pre-registered rule.
- A judgement against the core on CAGR at 10 bp, not just Sharpe.
- Acceptance that it's a single-sector bet with large drawdowns.

It would spend the holdout, and it may well fail.

**Option 3: costs, tax and implementation efficiency.** This means rebalancing bands, cash drag, and tax-aware rebalancing of the core and Books.

It's not a return edge, but any gain is mechanical rather than statistical, so it doesn't need the holdout. It would need your tax and account constraints.

**My lean: Option 1 now, plus Option 2 as the next research question.** Semis timing is the growth-alpha question you set at the start, and XSD's history covers the unspent holdout. That makes it the one candidate that could actually become a Book. Option 3 is cheap and mechanical, so it can run alongside without using the holdout. Either way, I'm not promising an edge.

## 7. Sources

**Papers**
- DeMiguel, Martín-Utrera, Nogales & Uppal (2020), *RFS* 33(5) 2180–2222. [doi:10.1093/rfs/hhz085](https://doi.org/10.1093/rfs/hhz085)
- Kan, Wang & Zhou (2022), *Management Science* 68(3) 2047–2068. [doi:10.1287/mnsc.2021.3989](https://doi.org/10.1287/mnsc.2021.3989)
- Tu & Zhou (2011), *JFE* 99(1) 204–215. [doi:10.1016/j.jfineco.2010.08.013](https://doi.org/10.1016/j.jfineco.2010.08.013)
- Deng, Gao & Wang (2026), arXiv:2606.13697. [arxiv.org/abs/2606.13697](https://arxiv.org/abs/2606.13697)
- Antulov-Fantulin, Kolm & Šikić (2025), SSRN 5782702. [doi:10.2139/ssrn.5782702](https://doi.org/10.2139/ssrn.5782702)
- Guo & Wachter (2025), "Forecast-Agnostic Portfolios", SSRN 5808182. [ssrn.com](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5808182)
- Bailey & López de Prado (2014), *JPM* 40(5) 94–107. [doi:10.3905/jpm.2014.40.5.094](https://doi.org/10.3905/jpm.2014.40.5.094)
- Memmel (2003), *Finance Letters* 1, 21–23.
- Hood & Raughtigan (2025), "Volatility Targeting Is Trendy", *JPM* 52(1). [SSRN 4773781](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4773781)

**Project notes**
- [Trial-13 DSR feasibility](https://jgridifier.github.io/usa-etf-feature-pipeline/methods/dsr_feasibility_trial13.html)
- Stage-2 plan, pre-registration with Addenda 1–2, robustness appendix, family-2 dev report, and the DeMiguel teaching page.
