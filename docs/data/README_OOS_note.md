# Real-BIL vol-target OOS note (Quant)

**Date:** 2026-09-17 ET
**Command:** `walkforward-vol-target` on `usa-etf-feature-pipeline` main (`1fdc409` lineage)
**Prices:** `/workspace/investments/growth_alpha_adj_close.csv` (BIL from 2007-05-30)
**Artifacts:** this folder

## Gate check
- `cash_price_source=prices` (not `zero_return_proxy_rf0`)
- Cash ticker BIL; scale-down only `f_max=1`; lookback 63; expanding σ*

## Primary trial vs static Option A (2021-02 → 2026-09, 68 months)

| | Vol-target A | Static Option A |
|--|--:|--:|
| AnnReturn | 14.73% | 14.68% |
| AnnVol | 13.90% | 15.89% |
| MaxDD | -20.1% | -25.6% |
| Sharpe_rf0 | 1.059 | 0.924 |
| NW t (VT−A) | -0.22 | — |
| mean f | 0.93 | 1 |
| % months f<1 | 26.5% | — |

## Read for CIO shortlist
- Risk improvement is the story (vol/MaxDD), not a significant return edge (NW t ≈ 0).
- Research-only; not a trade greenlight. Moreira & Muir (2017) JF cite remains the method backbone with f_max=1 constraint.
