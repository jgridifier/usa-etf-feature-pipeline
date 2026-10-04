# Results hub data (generated)

Written by `scripts/build_hub_data.py` from saved artifacts only. Nothing here re-runs a strategy, gate or optimizer.
Tests: `tests/test_hub_data.py` recomputes every file from the saved series and compares it with what's committed.

- `manifest.json`: the 14 subjects, each with the saved file, filter and column for the method, nulls, weights, trials, pre-registration and verdict. Also holds the static-core definition, the common window, the regime rules and the stress windows.
- `leaderboard.json`: ranked by CAGR difference vs the static core over the common window, 2021-04..2026-08 (65 months). Sortable on CAGR, Sharpe ex-BIL and MaxDD difference. VOID runs are listed below the ranking, with no Sharpe. Book 1 is the zero line.
- `subjects/<id>.json`: every figure a subject page shows:
  - vs the static core (own window, common window, and the stand-in sensitivity), then vs its own nulls, each with HAC tests and a power caveat
  - curves, drawdowns, rolling 36-month Sharpe, calendar years, turnover, weights and concentration
  - regime and stress-window tables, trials, DSR (as recorded, with its basis), gates and the timing audit
- `static_core_monthly.csv`: S1 (the live Book 1 series), the panel-derived core (equal to S1 except 2026-09) and the stand-in core (70% IVV / 20% QQQ / 10% IJR, sensitivity only).
- `market_regimes.csv`: SPY monthly return, drawdown state (Up / Correction / Bear) and 12-month vol state, from the saved panel.
- `dsr_exbil_recompute.csv` (not yet present): the slot for Quant's ex-BIL DSR recompute. When it lands, `build_hub_data.py` adds it beside the recorded DSR (columns: `subject_id,dsr_exbil,trial_count`).

Partial final months (several archived runs end on 2026-09-16) are dropped and listed per subject; they're never paired with a complete month.
