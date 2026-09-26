# Raw data

- `usa_universe_categorized.csv` — USA research-universe universe (committed). Boolean tag columns
  (2026-09-26, cash-null audit): `cash_like` = {BIL, SGOV, SHV, GBIL, USFR, GSST, GUMI} (T-bill / floating-rate /
  ultrashort, duration ≤ ~1y; excluded by the shared gate helper when `exclude_cash_like=True`) and
  `short_duration` = {SHY, SPTS, BSV, STIP} (diagnostic only, never excluded). USFR's Category was corrected from
  "High Yield Credit" to "US Treasuries / Govt / Cash-like". The Category column is otherwise unchanged and is not
  the cash tag (it still mixes duration such as GOVT/IEF/TLT/SHY). Archived committed outputs were not re-run;
  re-running an archived category-sleeve spec on this file would move USFR between sleeves.
  `near_cash` (2026-09-26, after the NLS GMV v2 VOID) = {FTSL, SRLN}: stored values, set by hand like `cash_like`.
  Why these two: they are floating-rate senior / bank-loan ETFs (the fund's own name says senior loan, bank loan,
  leveraged loan or floating-rate corporate / CLO) that are not already `cash_like` (USFR, a floating-rate Treasury
  fund, stays `cash_like` only); no other ticker in the file qualified. The rule is documentation only: code reads
  the stored column and never derives the tag from names, and new loan funds are tagged by hand and reviewed.
  `near_cash` never excludes a name; it feeds the default-on composition tripwire (cash_like + short_duration +
  near_cash > 50% ⇒ VOID) for future gates. Nothing past is re-scored.
- `fred_tb3ms.csv` — FRED series TB3MS (3-Month Treasury Bill Secondary Market Rate, discount basis, percent,
  monthly, not seasonally adjusted), 1934-01 → 2026-08, verbatim CSV from
  https://fred.stlouisfed.org/graph/fredgraph.csv?id=TB3MS (source: Board of Governors of the Federal Reserve System,
  H.15, via FRED, Federal Reserve Bank of St. Louis). Downloaded by Quant on 2026-09-26 for the cash-null audit;
  a re-fetch from the build box timed out (FRED blocks it), so this is Quant's copy, byte-identical. Used as the
  risk-free fallback rf = TB3MS / 1200 for months before BIL's first full month (2007-06).
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
