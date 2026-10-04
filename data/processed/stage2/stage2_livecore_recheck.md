# Live-core recheck for family 2 (correction to Addendum 3 E4)

Date: 2026-10-04 (ET). Research only.

Addendum 3 E4 says the family-2 figures against the live core include the bad 2026-09 row. **That is wrong.** `analyze_A.py` and `run_B.py` rebuild the live core (70/20/10 VOO/QQQM/IJR) from the complete-month panel through `static_core(...)`. They read the repo's `data/processed/live/strategy_returns.csv` only for a cross-check.

- The family-2 live core has 2026-09 = −0.1115%. The repo file reads +0.2412%. Over the window, the largest absolute difference between the two series is 0.3527 pp, and it falls in 2026-09.
- Every other month from 2020-11 to 2026-08 matches to within 1.2e-5, which is rounding.
- So every family-2 live-core figure in Addendum 3 §1.3 and E3 already uses the corrected month. **Nothing needs recomputing, and the figures stand:** A6's CI is [−0.123, +0.058] and its gap is −0.73 pp; B3's CI is [−0.119, +0.269] and its gap is −1.4 pp; the core's Sharpe is 0.887 over 2020-11 to 2026-09.
- Engineering's every-month test can use the same check: the rebuilt `static_option_a` should match the panel-derived core to within 1e-4 in every month.

Pages that read the repo file directly need a rebuild after the fix: Books and the own-window figures, as the CIO noted in #55 item 6. DeMiguel's dev figures use the stand-in core, so they aren't affected.
