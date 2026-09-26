# Raw data

- `usa_universe_categorized.csv` — USA research-universe universe (committed).
- `growth_alpha_adj_close_sample.csv` — slim adj-close sample for demos/CI (committed).
- Full history `growth_alpha_adj_close.csv` is **gitignored**. On the research box use:
  `/workspace/investments/growth_alpha_adj_close.csv`

- `usa_universe_panel_monthly_returns.csv` — committed experimental research panel,
  405 dated rows × 339 ETFs; simple monthly returns, missing before inception.
  Dates are last observed trading days. The source snapshot ends September 16,
  2026; the spectral loader excludes the incomplete final month.
- `usa_universe_panel_history_coverage.csv` — committed snapshot coverage (~25 KB):
  ticker, history dates, `years_monthly`, `thin_lt5y`, and dollar `adv_proxy`.
  These are snapshot metadata, not a historical point-in-time membership feed.
  The categorized universe retains `Source_Section=experimental_research_universe`.

- `usa_universe_panel_weekly_returns.csv`: weekly simple returns on Friday dates,
  1756 rows × 339 ETFs, 1993-01-29 → 2026-09-18; missing before inception;
  same source snapshot as the monthly panel.
