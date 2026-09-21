# Vol-cond-factor-corr OOS artifacts

Research-only Book-2 upgrade: conditional factor-correlation gate on unconditional vol-target Option A.

**Not investment advice.** No claim of empirical success — tables are for A/B review vs Book-2 VT and static Option A under DSR + trial count.

## Reproduce

```bash
python -m usa_etf_features.cli walkforward-vol-cond-factor-corr \
  --universe /workspace/investments/usa_universe_categorized.csv \
  --monthly /workspace/investments/usa_universe_panel_monthly_returns.csv \
  --prices /workspace/investments/growth_alpha_adj_close.csv \
  --coverage /workspace/investments/usa_universe_panel_history_coverage.csv \
  --grid --cost-bps 5 \
  --out data/processed/vol_cond_factor_corr/vol_cfc_oos_summary.csv \
  --weights data/processed/vol_cond_factor_corr/vol_cfc_monthly_weights.csv \
  --registry data/processed/vol_cond_factor_corr/vol_cfc_trial_registry.csv
```

Nulls: (a) Book-2 unconditional VT, (b) static Option A, (c) EW category sleeves.
