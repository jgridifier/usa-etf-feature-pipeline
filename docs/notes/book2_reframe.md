# Book 2: the drawdown-controlled version of the same core

*CIO · October 2026 · Data through 30 Sep 2026 (68 complete months, Feb 2021 – Sep 2026). Research on an experimental ETF panel for personal decision-making, not investment advice.*

## What "backbone" means here
In these notes, the **vol-target backbone** is not the Vanguard Total World ETF (ticker VT). It holds Book 1's 70/20/10 core (VOO / QQQM / IJR) and scales part of it into cash (BIL) only when the core's volatility runs high. Book 2 adds a skewness-based risk gate on top of that backbone. All three lines therefore share the same US equity core.

## In short
Book 2 is best read as **Book 1's core with two brakes** (the vol target plus the risk gate), not as a higher-Sharpe book. It gave up about **1.2 points a year** of return against the vol-target backbone. In return, its volatility was lower and its worst drawdown was about **half of the backbone's** in the 2022 bear market. Its Sharpe edge over the backbone is **not statistically significant**.

## The three lines side by side
| | Return | Volatility | Max drawdown | Sharpe above BIL |
|---|--:|--:|--:|--:|
| Book 1 (static core) | 15.0% | ~15.9% | −25.6% | 0.77 |
| Backbone (vol target) | 15.1% | ~13.9% | −20.1% | 0.86 |
| Book 2 (backbone + risk gate) | 13.9% | ~10.6% | −10.1% | 1.00 |

Returns are annualized and net of trading costs. Sharpe is measured above cash (BIL).

## How to choose between them
- **Book 1** takes the full equity path and accepts drawdowns of about 25%.
- **Book 2** holds the same core but has cut drawdowns about in half in one bear market so far. The cost is roughly a point a year of return.

## What the evidence does and doesn't say
- **Sharpe:** Book 2 is at 1.00 against 0.86 for the backbone. Ledoit–Wolf (2008) tests put that gap at p ≈ 0.30–0.38, which is not significant. Against Book 1 (0.77), p ≈ 0.20, also not significant. The Sharpe gap isn't a reason on its own to pick Book 2.
- **Drawdowns:** the protection came from a **single stretch**. The gate was on from October 2021 to December 2023. That covers the 2022 bear market (−10.1% vs −20.1%) and the autumn 2023 pullback (−3.9% vs −9.0%). Since January 2024 the gate hasn't switched on, and Book 2 has tracked the backbone through the 2024, 2025 and 2026 pullbacks.
- **Sample size:** 68 months contain only one real bear market. The halving is large, but it rests on one episode.

## What would change this view
- **Strengthens it:** another bear market in which the gate engages and again roughly halves the drawdown.
- **Weakens it:** a sharp selloff in which the gate stays off, or a long gap in return against the backbone with no drawdown benefit to show for it.

See also: *Book 2 vs the vol-target backbone*, Quant's significance and drawdown-episode note.
