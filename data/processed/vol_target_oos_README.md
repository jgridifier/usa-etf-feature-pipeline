# vol_target_oos_returns.csv / vol_target_oos_summary.csv: moved (2026-10-04)

The top-level copies were retired. They ended at the partial day 2026-09-16 and used the cash = 0 proxy.

- **Live series (every page, hub and app reads this):** `data/processed/live/vol_target_oos_returns.csv` and
  `data/processed/live/vol_target_oos_summary.csv` (68 months, 2021-02 to 2026-09, BIL priced). `docs/data/` carries
  build-time copies of these (`scripts/build_pages.py`).
- **Frozen research run (cash = 0, ends 2026-09-16), bytes unchanged:** `data/processed/frozen/vol_target_cash0_2026-09-16/`.
  Only the gate audits read it (`cash_null_audit.gate_frames`, `epo_allocator.PUBLISHED_BOOK1`).

`tests/test_vol_target_live_only.py` fails if a page build, hub builder or app data import reads `vol_target_oos_*`
from anywhere but `live/`.
