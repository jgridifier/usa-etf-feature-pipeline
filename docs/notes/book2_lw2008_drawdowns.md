# Book 2 vs the vol-target backbone: is the Sharpe edge real, and where did the drawdown protection come from?

*Quant · October 2026 · Data through 30 Sep 2026 (68 complete months, Feb 2021 – Sep 2026). Research only, not investment advice.*

**What the "backbone" is.** The **vol-target backbone** (labelled "Backbone" in tables): Book 1's static 70/20/10 core (VOO, QQQM, IJR), scaled down toward BIL cash when its volatility runs high. It is not the Vanguard Total World ETF (ticker VT), and earlier drafts that called it "VT" meant the backbone. Book 2 is that backbone with a skewness-managed gate added. When the vol target isn't cutting exposure, the backbone holds exactly the Book 1 core, so in calm periods all three series move together.

## In short
- Above cash (BIL), Book 2's Sharpe ratio is **1.00**, against **0.86** for the backbone. The gap of **0.14** is **not statistically significant**: p is about 0.30–0.32 by HAC and about 0.37–0.38 by bootstrap. For significance at the 5% level, the gap would need to be about 0.27.
- Book 2's worst drawdown was **−10.1%**, against **−20.1%** for the backbone, a ratio of **0.50**. Both happened in the **2022 bear market**.
- That protection has shown up in **one bear market** (2022), plus a smaller cut in autumn 2023. In the 2024, 2025 and 2026 drawdowns the overlay did not engage, and Book 2 matched the backbone.

## Method
Ledoit, O. & Wolf, M. (2008), "Robust performance hypothesis testing with the Sharpe ratio," *Journal of Empirical Finance* 15(5), 850–859. [doi:10.1016/j.jempfin.2008.03.002](https://doi.org/10.1016/j.jempfin.2008.03.002)

The test asks whether two Sharpe ratios measured on the same months really differ. It allows for fat tails and for returns that are correlated over time, which the textbook test assumes away. We used two versions:
- The delta method with a HAC covariance, a standard error that is robust to autocorrelation. We tried Bartlett and Parzen kernels with bandwidths of 4 and 6 months.
- The paper's studentized circular block bootstrap, with 20,000 draws and blocks of 3, 4 and 6 months.

All returns are monthly and net of trading costs, measured in excess of BIL.

## Sharpe-difference results (annualized, excess of BIL)
| | Book 2 | Backbone | Difference | p (two-sided) |
|---|--:|--:|--:|--:|
| HAC, Bartlett, 4 months | 1.00 | 0.86 | +0.14 | 0.31 |
| HAC, Parzen, 4 months | 1.00 | 0.86 | +0.14 | 0.32 |
| HAC, Parzen, 6 months | 1.00 | 0.86 | +0.14 | 0.30 |
| Bootstrap, blocks of 3 / 4 / 6 | | | | 0.37 / 0.37 / 0.38 |

For reference: Book 2 vs Book 1, above BIL, is 1.00 vs 0.77, a gap of +0.23 with HAC p ≈ 0.20. That is not significant either.

## Drawdown episodes (month-end total returns; intra-month lows were deeper)
| Episode | Peak → trough | Book 1 | Backbone | Book 2 |
|---|---|--:|--:|--:|
| Sep 2021 | Aug → Sep 2021 | −4.6% | −4.6% | −4.6% |
| 2022 bear market | Dec 2021 → Sep 2022 | −25.6% | −20.1% | −10.1% |
| Autumn 2023 | Jul → Oct 2023 | −9.0%* | −9.0% | −3.9% |
| Apr 2024 | Mar → Apr 2024 | −4.2% | −4.2% | −4.2% |
| 2025 tariff selloff | Jan → Apr 2025 | −8.6% | −8.6% | −8.6% |
| Q1 2026 | Jan → Mar 2026 | −5.7% | −5.7% | −5.7% |

*Book 1 was still below its 2021 peak at the time.

## Why the record looks like this
Book 2 is the backbone with a skewness-managed risk gate on top. The gate cut exposure in just one continuous stretch, October 2021 to December 2023. In 40 of the 68 months Book 2's return equals the backbone's, and in 47 months the backbone's equals Book 1's, because the vol target only scales down in high-vol stretches. From January 2024 on, the two are identical apart from trading costs. So the halved worst drawdown comes from a single episode. A Sharpe gap this size, over fewer than six years, can't be told apart from luck.

## What would change the conclusion
More bear markets in which the gate engages. Until then, the honest description is "about half of the backbone's drawdown in one bear market, at a cost of roughly a point a year of return, with no statistically significant Sharpe edge."
