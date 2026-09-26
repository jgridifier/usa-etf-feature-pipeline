# usa-etf-feature-pipeline

Transparent, unit-tested feature scorer and **optional thematic rotation sleeve** for **experimental USA ETF research universe** (research tooling).

> **Not investment advice.** Outputs are research artifacts for personal portfolio exploration. No claim of future performance, guaranteed alpha, or personalized recommendations. Research-only.

## Status

| Milestone | Contents |
|-----------|----------|
| **M1** | Universe gate, transparent features, `score-universe` CLI |
| **M2** | `--rotate-thematic` (ScoreSimple Mom+vol vs VOO), caps, walk-forward IC |
| **M3** | `--optimize` / `--walkforward-optimize` research optimizer artifacts |
| **Allocation alpha** | `walkforward-vol-target` scale-down-only volatility-managed Option A research |
| **Book-2 upgrade** | `walkforward-vol-cond-factor-corr` conditional factor-correlation gate on Book-2 VT |
| **Shortlist #4 — Archive FAIL (PR #24)** | `walkforward-forecast-tangency-med` — forecast EF coefficients → MED portfolio (Alexander & Scherer 2023); Archive FAIL (PR #24) |
| **Shortlist #3 — Archive FAIL (PR #26)** | `walkforward-regime-resilient-erc` — regime-resilient ERC construction (stress/corr overlays + LOIM regime-parity π-blend); Archive FAIL (PR #26) |
| **Shortlist #6 — live Book-2 overlay** | `walkforward-skewness-managed` — Book-2 overlay: skewness / left-tail gate on unconditional Book-2 VT (Gong–Lynch–Ogden); primary null = Book-2 VT; live Book-2 overlay, VT × gate-first (PR #29) |

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# optional Excel writer
pip install openpyxl
pytest
```

## CLI

### Score universe (M1)

```bash
python -m usa_etf_features.cli score-universe \
  --universe data/raw/usa_universe_categorized.csv \
  --prices data/raw/growth_alpha_adj_close_sample.csv \
  --out data/processed/scores_YYYYMMDD.csv
```

### Build portfolio — static (rotate **default OFF**)

```bash
python -m usa_etf_features.cli build-portfolio \
  --scores data/processed/scores_YYYYMMDD.csv \
  --mode growth \
  --out data/processed/weights_YYYYMMDD.csv
```

### Build portfolio — thematic rotation (M2)

`--rotate-thematic` is **OFF by default**. Enable explicitly:

```bash
# ScoreSimple: Mom12_1 vs VOO (+ optional vol gate)
python -m usa_etf_features.cli build-portfolio \
  --prices /path/to/growth_alpha_adj_close.csv \
  --universe data/raw/usa_universe_categorized.csv \
  --rotate-thematic \
  --rotate-vol-gate \
  --out data/processed/weights_rotate_YYYYMMDD.csv \
  --xlsx data/processed/weights_rotate_YYYYMMDD.xlsx
```

| Flag | Meaning |
|------|---------|
| `--rotate-thematic` | Enable rotation sleeve (default eligible: **XSD** only) |
| `--rotate-vol-gate` | ScoreSimple vol gate: `vol_63 ≤ expanding Q90` through **t−1** only |
| `--hysteresis-months N` | Stay ON until signal fails N consecutive month-ends (config default **2**) |

**Signal (ScoreSimple when vol gate on):**

\[
\mathrm{ON}_{i,t}
\iff
\bigl(z(\mathrm{Mom12\_1}_{i,t})>0 \;\lor\; \mathrm{Mom12\_1}_{i,t}>\mathrm{Mom12\_1}_{\mathrm{VOO},t}\bigr)
\;\land\;
\mathrm{vol}_{63,i,t}\le Q_{0.90}^{\mathrm{expanding}}(\mathrm{vol}_{63,i})\big|_{t-1}
\]

Without `--rotate-vol-gate`: \(\mathrm{ON}\iff\mathrm{Mom12\_1}_i>\mathrm{Mom12\_1}_{\mathrm{VOO}}\).

**Funding rule (proportional core-trim):** core Option A spirit VOO 70 / QQQM 20 / IJR 10 when thematic OFF; when ON at weight \(w\):

\[
w_i^{\mathrm{core}}=\mathrm{CORE}_i\cdot(1-w),\quad i\in\{\mathrm{VOO},\mathrm{QQQM},\mathrm{IJR}\}
\]

**Caps:** thematic sleeve \(\le 25\%\); single satellite \(\le 15\%\). **SMH / SOXX / SOXL / PSI** hard-fail (never inject).

Research backing: `xsd_rotation_memo.md` (2026-09-16 ET) on the investments box.

### Build portfolio — optimized (M3)

```bash
python -m usa_etf_features.cli build-portfolio \
  --scores data/processed/scores_YYYYMMDD.csv \
  --prices /path/to/growth_alpha_adj_close.csv \
  --universe data/raw/usa_universe_categorized.csv \
  --optimize \
  --optimizer P2 \
  --window-months 36 \
  --out data/processed/weights_optimize_YYYYMMDD.csv \
  --registry-out data/processed/wf_strategy_registry_YYYYMMDD.csv
```

| Flag | Meaning |
|------|---------|
| `--optimize` | Build a current M3 optimized research portfolio |
| `--optimizer {P1,P2,P3}` | `P1` constrained MV, `P2` hierarchical core/satellite, `P3` risk-parity top-N |
| `--window-months N` | Monthly estimation window length (default **36**) |
| `--top-n N` | Top-N by `S_i` for `P3` (default **6**) |
| `--registry-out PATH` | Strategy registry CSV path |

M3 primary expected returns use `0.5 * James-Stein historical excess mean + 0.5 * score→mu map`; covariance uses Ledoit-Wolf shrinkage. P2 keeps core weight at least 60% and applies ScoreSimple gates to thematic satellites, so thematics such as `XSD` can be written at weight `0.0`.

### Walk-forward optimize (M3)

```bash
python -m usa_etf_features.cli build-portfolio \
  --prices /path/to/growth_alpha_adj_close.csv \
  --universe data/raw/usa_universe_categorized.csv \
  --walkforward-optimize \
  --optimizer P2 \
  --window-months 36 \
  --min-history-months 36 \
  --out data/processed/wf_optimization_monthly_weights_YYYYMMDD.csv \
  --ic-out data/processed/wf_optimization_ic_by_date_YYYYMMDD.csv \
  --registry-out data/processed/wf_strategy_registry_YYYYMMDD.csv
```

| Flag | Meaning |
|------|---------|
| `--walkforward-optimize` | Write walk-forward optimized monthly weights plus IC and registry |
| `--ic-out PATH` | Walk-forward IC CSV path |
| `--min-history-months N` | Earliest rebalance history requirement (default **36**) |
| `--tickers A,B,C` | Optional ticker filter for walk-forward optimization |
| `--benchmark TICKER` | Benchmark for excess labels / expected return blend (default **VOO**) |
| `--weights PATH` | Feature weights YAML for walk-forward scoring |

Walk-forward decisions at month-end `t` use data `<= t`; evaluation labels are next-month returns on `(t,t+1]`, forbidding same-month label leakage. Turnover-cost documentation follows the reference study: **5 bps one-way** on monthly turnover, recorded in the strategy registry and monthly weights artifact.

### Walk-forward IC (M2)

```bash
python -m usa_etf_features.cli walkforward-ic \
  --universe data/raw/usa_universe_categorized.csv \
  --prices /path/to/growth_alpha_adj_close.csv \
  --tickers VOO,QQQ,QQQM,IJR,XSD,XBI,QUAL,IWM \
  --out data/processed/ic_walkforward_YYYYMMDD.csv \
  --rotate-table data/processed/rotate_on_off_next_month.csv
```

- Features / scores at decision month-end \(T_{k-1}\) use prices **through \(T_{k-1}\) only**.
- Labels = **next-month** excess vs VOO on \((T_{k-1}, T_k]\) — **no same-month leakage**.
- IC = cross-sectional Spearman of \(S_i\) vs next-month excess.

### Walk-forward vol target — allocation alpha

```bash
python -m usa_etf_features.cli walkforward-vol-target \
  --prices /workspace/investments/growth_alpha_adj_close.csv \
  --universe /workspace/investments/usa_universe_categorized.csv \
  --core option_a \
  --lookback 63 \
  --f-max 1.0 \
  --cash BIL \
  --cost-bps 5 \
  --out data/processed/vol_target_oos_summary.csv \
  --weights data/processed/vol_target_monthly_weights.csv \
  --registry data/processed/vol_target_trial_registry.csv
```

This command keeps selection fixed at Option A (VOO 70 / QQQM 20 / IJR 10), estimates realized portfolio volatility at each month-end with data `<= t`, applies the resulting scale factor to month `t+1`, and parks residual weight in eligible cash (`BIL`; fallbacks remain subject to the universe gate). If the growth-panel price file does not include BIL, the engine records `cash_price_source=zero_return_proxy_rf0`, matching the rf=0 research parity convention.

Outputs include `vol_target_oos_summary.csv`, `vol_target_monthly_weights.csv`, `vol_target_oos_returns.csv`, `vol_target_trial_registry.csv`, and `vol_target_regime_table.csv`.

### Walk-forward vol-cond-factor-corr — Book-2 upgrade

Conditional correlation / vol-state gate on top of Book-2 `f_t` (DeMiguel–Martín-Utrera–Uppal JF mapping on ETF category sleeves). Research only; not investment advice.

```bash
python -m usa_etf_features.cli walkforward-vol-cond-factor-corr \
  --universe /workspace/investments/usa_universe_categorized.csv \
  --monthly /workspace/investments/usa_universe_panel_monthly_returns.csv \
  --prices /workspace/investments/growth_alpha_adj_close.csv \
  --coverage /workspace/investments/usa_universe_panel_history_coverage.csv \
  --null book2_vol_target \
  --cost-bps 5 \
  --lookback 63 --g-min 0.5 --z-rule mkt_vol \
  --out data/processed/vol_cond_factor_corr/vol_cfc_oos_summary.csv \
  --weights data/processed/vol_cond_factor_corr/vol_cfc_monthly_weights.csv \
  --registry data/processed/vol_cond_factor_corr/vol_cfc_trial_registry.csv
```

Use `--grid` for the registered robustness sweep (`config/vol_cond_factor_corr.yaml`). Outputs include DSR + trial_count, NW t vs Book-2 VT and static Option A, and a gate state table. Teaching note: `docs/methods/allocation_alpha_vol_cond_factor_corr.html`.

Math appendix (gate form):

\[
f_t=\mathrm{clip}(\sigma^*/\hat\sigma_t, f_{\min}, f_{\max}),\quad
g_t\in[g_{\min},1],\quad
\tilde f_t=f_t\cdot g_t
\]

Gate binds when high market vol coincides with elevated mean pairwise |corr| of category sleeves (data ≤ t only). Residual weight → BIL. Costs: 5 bps one-way on monthly turnover.



### Regime-aware category allocation

`regime_aware_dual_regime` runs K=2 expanding (or rolling) inference with conditional
category eligibility. The fixed grid has four trials (two feature sets × ERC/EW),
with unconditional ERC, unconditional EW and always-calm ERC nulls. Every decision
at t is evaluated at t+1. DSR uses monthly Sharpe and the predeclared trial count.

```bash
python -m usa_etf_features.cli walkforward-regime-dual --out-dir /tmp/regime-dual
```

Inputs default to the three `usa_universe_*` CSVs under `/workspace/investments/`;
override with `--panel-returns-path`, `--categorized-path`, and `--coverage-path`
(or the underscore parameter names in the strategy registry). The command writes
weights, OOS returns, summary, trial registry, states, and transition diagnostics.
The registry uses its selected variant's last evaluated decision as suggested
weights, marked `asset_type=category_sleeve`. Missing inputs raise a file error.

Sleeves require 12 prior monthly observations per name. Features and covariance
use only data through the decision; the final incomplete source month is excluded.
Unknown categories remain in unconditional nulls but require an explicit
`eligibility` mapping to enter conditional policies. Crypto is excluded unless
`crypto_calm: true`. Coverage `thin_lt5y` flags are carried on name-level holdings and listed in
diagnostics. Optional secondary stress: set `name_level: true` (or CLI
`--name-level`) to allocate on ≥100 liquid names while regimes still come from
category-sleeve features; prefer non-thin names, and fall back to thin names
only if needed to reach the minimum count.
Returns are gross of costs, missing held returns invalidate that month, and the
static universe retains survivorship bias. Ex-post stress diagnostics use the
bottom quintile of realized sleeve-market returns, never as model inputs.
See the [teaching note](docs/methods/regime_aware_dual_regime_allocation.html).

### Run strategy registry

```bash
python -m usa_etf_features.cli run-strategies \
  --asof 2026-09-16 \
  --prices /workspace/investments/growth_alpha_adj_close.csv \
  --universe /workspace/investments/usa_universe_categorized.csv \
  --registry config/strategies.yaml \
  --out-dir data/processed/strategy_run_20260916/
```

```bash
python -m usa_etf_features.cli run-strategies \
  --walkforward \
  --prices /workspace/investments/growth_alpha_adj_close.csv \
  --universe /workspace/investments/usa_universe_categorized.csv \
  --registry config/strategies.yaml \
  --out-dir data/processed/strategy_wf/
```

The registry runner writes `suggested_weights.csv`, `strategy_diagnostics.csv`, `strategy_comparison.csv`, `strategy_registry_used.csv`, and `strategy_comparison.xlsx`. Every artifact carries the research-only disclaimer. The v1 registry is in `config/strategies.yaml` and includes `static_option_a`, `vol_target_option_a`, `score_rotate_xsd`, and `m3_p2_core_rotate`.

`run-strategies --walkforward` keeps `suggested_weights.csv` as the latest available decision book. The comparison table is built from each strategy's generated out-of-sample monthly return path where signals/weights use data through the decision date and the evaluated return is the next month; the flag also stamps `strategy_diagnostics.csv` with `walkforward=True`.

The full growth price panel is on the investments box at `/workspace/investments/growth_alpha_adj_close.csv`. The committed sample at `data/raw/growth_alpha_adj_close_sample.csv` includes `BIL`, `SGOV`, `GBIL`, and `SHV`; when BIL is present, vol target records `cash_price_source=prices` instead of using the zero-return proxy.

### Add a Strategy

1. Add a new entry to `config/strategies.yaml` with `id`, `display_name`, stable `method_citation_id`, human-readable `method_citation`, `entrypoint`, `default_params`, and `enabled`.
2. Point `entrypoint` at an existing runner path in `usa_etf_features.strategy_registry` or add a small adapter there that calls the existing math module.
3. Keep universe validation unchanged: only approved tickers, Appendix 3 deny, and hard-deny semis such as `SMH` / `SOXX` must fail.
4. Add a focused test proving the registry loads the entry, disabled entries skip, and emitted weights sum to 1.

## Sample artifacts (committed)

| Path | Contents |
|------|----------|
| `data/processed/ic_walkforward_sample.csv` | Walk-forward IC panel |
| `data/processed/rotate_on_off_next_month_sample.csv` | ScoreSimple ON/OFF next-month excess |
| `data/processed/weights_rotate_scoresimple_sample.csv` | Latest rotate+vol-gate weights |
| `data/processed/weights_rotate_mom_only_sample.csv` | Latest rotate Mom-only weights |

## Thin-history flags

**QQQM**, **LOUP**, **GTEK**, **GINN** marked `thin_history=True` in scores; also `history_years`.

## Universe gate

1. Load `Ticker` from universe CSV → \(U_{\mathrm{approved}}\).
2. Deny Appendix-3 list from `config/universe.yaml`.
3. Hard deny off-list semis: **SMH, SOXX, SOXL, PSI**.
4. Eligible \(E = U_{\mathrm{approved}} \setminus \mathrm{deny}\). Any \(t \notin E\) **hard-fails**. Semiconductor exposure is XSD-only under rotation/optimization paths.

## Shared gate helper: cash-like tag and excess-of-BIL Sharpe

`usa_etf_features.gate_metrics` (cash-null audit follow-up, 2026-09-26):

- **Tags** in `data/raw/usa_universe_categorized.csv`: `cash_like` = {BIL, SGOV, SHV, GBIL, USFR, GSST, GUMI};
  `short_duration` = {SHY, SPTS, BSV, STIP} (diagnostic only). `filter_cash_like(names, universe, exclude_cash_like=True)`
  is applied once to the eligible list shared by the method and every null (`SpectralTrial` / `NLSGMVTrial` expose
  `exclude_cash_like`, pinned `False` for the archived gates so committed outputs stay byte-identical; new gates set it True).
- **rf**: BIL priced monthly return from BIL's first full month (2007-06); FRED TB3MS / 1200 before
  (`data/raw/fred_tb3ms.csv`). `window_rf_coverage` reports the fallback share of a window.
- **Sharpe_exBIL** = mean(r − rf)·12 / (std(r − rf)·√12), arithmetic on monthly returns (headline everywhere on Pages).
  **Sharpe_rf0** stays CAGR / vol, labelled "legacy (rf = 0)".
- `scripts/reconcile_cash_null_audit.py` writes `data/processed/cash_null_audit/` (reconciliation to Quant's audit,
  fallback shares, and `site_sharpe.json` used by the Pages build).
- **`near_cash`** tag = {FTSL, SRLN} (floating-rate senior / bank-loan ETFs; not already `cash_like`): diagnostic only. `duration_composition` reports it next to `short_duration` with the combined share, and `composition_void_check` carries it into future gates' void checks as a flagged diagnostic; it never excludes a name and nothing past is re-scored.
- **Archived category-sleeve specs will differ at the 4th decimal if re-run** on the new universe file (USFR moved from High Yield Credit to Treasuries / cash-like); the committed outputs and `tests/data/archived_csv_sha256.json` are the archive record.

## Math appendix

Daily return \(r_{i,t} = P_{i,t}/P_{i,t-1}-1\).

### Momentum 12–1

Month-end prices \(P^m_{i,\tau}\), monthly \(R_{i,\tau}=P^m_{i,\tau}/P^m_{i,\tau-1}-1\).

\[
\mathrm{Mom12\_1}_{i,t}
= \Big(\prod_{k=2}^{12}(1+R^{\mathrm{lag}\,k}_{i,t})\Big)-1
\]

(lag 1 = most recent month, **skipped**).

### Volatility

\[
\mathrm{Vol}_i(L)=\sqrt{252}\cdot\mathrm{std}(\{r_{i,t-L+1},\ldots,r_{i,t}\}),\quad \mathrm{ddof}=1
\]

### Max drawdown (252d)

\[
\mathrm{MaxDD}_{i,t}
=\min_u\Big(\frac{P_{i,u}}{\max_{s\le u}P_{i,s}}-1\Big)
\]

### Quality v1

Benchmark \(b=\) VOO (fallback VTI). Excess \(e=r_i-r_b\).

\[
\mathrm{IR}_i=\frac{\sqrt{252}\cdot\overline{e}}{\mathrm{std}(e)},\quad
Q^{\mathrm{v1}}_i=\mathrm{IR}_i-\lambda_{\mathrm{ER}}\cdot\mathrm{ER}_i
\]

Default \(\lambda_{\mathrm{ER}}=1\). Missing ER → 0 penalty + `er_missing=True`.

### Liquidity

\[
\mathrm{ADV\$}_i=\frac{1}{L}\sum_{j=0}^{L-1}\mathrm{Volume}_{i,t-j}\cdot P_{i,t-j},\quad L=21
\]

### Composite

Within-category robust z-scores; \(S_i=\sum_k w_k z_{i,k}\).

| Feature | \(w_k\) |
|---------|--------:|
| Mom12_1 | 0.30 |
| Quality v1 | 0.25 |
| −Vol_252 | 0.15 |
| −MaxDD_252 | 0.15 |
| Liquidity ADV$ | 0.10 |
| −Vol_63 | 0.05 |

Weights live in `config/feature_weights.yaml`.

### Purged / embargo sketch

For overlapping label horizons, purge ± embargo around test folds so label windows do not leak into training (Lopez de Prado-style). M2 IC uses non-overlapping next-month labels after each decision ME.

### Allocation alpha: volatility-managed Option A

Static policy weights:

\[
w^A=(w_{\mathrm{VOO}},w_{\mathrm{QQQM}},w_{\mathrm{IJR}})=(0.70,0.20,0.10)
\]

Daily core return:

\[
r^A_\tau=\sum_i w_i^A r_{i,\tau}
\]

At month-end \(t\), estimate realized portfolio volatility with data through \(t\) only:

\[
\hat\sigma_t=\sqrt{252}\cdot\mathrm{std}(\{r^A_\tau\}_{\tau=t-L+1}^{t})
\]

Primary scale-down-only rule:

\[
f_t=\mathrm{clip}\left(\frac{\sigma^*}{\hat\sigma_t}, f_{\min}, f_{\max}\right),
\quad f_{\min}=0.25,\ f_{\max}=1.0
\]

Default \(\sigma^*\) is expanding Option A annualized volatility through \(t-1\); fixed grid values such as 0.12 or 0.15 are registered in the trial registry when swept. Portfolio weights are:

\[
w_{i,t}=f_t w_i^A,\quad
w_{\mathrm{BIL},t}=1-f_t
\]

Weights decided at \(t\) earn next-month returns on \((t,t+1]\). Monthly cost is `cost_bps_one_way * 0.5 * sum(abs(delta weights)) / 10000`. The benchmark is static Option A with rf=0 Sharpe parity. Internal method references: `/workspace/investments/allocation_alpha_method_memo.md` and teaching HTML `/workspace/investments/methods/allocation_alpha_vol_target.html`.

## Layout

```text
usa-etf-feature-pipeline/
  README.md
  pyproject.toml
  config/                 # universe, feature_weights, portfolio_constraints
  src/usa_etf_features/   # features, scores, rotation, portfolio, walkforward, cli
  data/raw/  data/processed/
  tests/
  notebooks/              # 03_walkforward_ic.ipynb
```

## Price data paths

| File | Role |
|------|------|
| `data/raw/usa_universe_categorized.csv` | Approved universe (committed) |
| `data/raw/growth_alpha_adj_close_sample.csv` | Slim sample for CI / demos |
| Full adj closes | Often at `/workspace/investments/growth_alpha_adj_close.csv` (not always committed) |

### Allocation alpha: Forecast Tangency + MED (Justina shortlist #4 — gate pending)

Walk-forward algorithm (Alexander & Scherer 2023, *Engineering Proceedings* 39(1):34):

**Step 1 — EF coefficients** at month-end *t* (data ≤ *t* only, Ledoit–Wolf Σ̂):

\[
A = \mathbf{1}'\Sigma^{-1}\mathbf{1},\quad
B = \hat\mu'\Sigma^{-1}\mathbf{1},\quad
C = \hat\mu'\Sigma^{-1}\hat\mu
\]
\[
r_\text{MVP} = B/A,\quad \sigma_\text{MVP} = 1/\sqrt{A},\quad u = (AC-B^2)/A
\]

EF shape: \(\sigma^2(r) = \sigma_\text{MVP}^2 + (r-r_\text{MVP})^2/u\).

**Step 2 — VARX(1) forecast** of \((r_\text{MVP},\sigma_\text{MVP},u)\) using EF-coef history ≤ *t* (no peeking):

\[
\hat r_\text{TP} = \frac{\hat r_\text{MVP}^2 + \hat u\,\hat\sigma_\text{MVP}^2}{\hat r_\text{MVP}}\quad(\text{rf}=0),\qquad
\hat\sigma_\text{TP} = \sigma(\hat r_\text{TP})
\]

**Step 3 — MED solve** on the *current* frontier:

\[
r^* = \operatorname*{argmin}_{r}\sqrt{(\hat r_\text{TP}-r)^2+(\hat\sigma_\text{TP}-\sigma_\text{cur}(r))^2}
\]

\[
\mathbf{w}^*_t = \operatorname*{argmin}_{\mathbf{w}}\;\mathbf{w}'\hat\Sigma_t\mathbf{w}
\quad\text{s.t.}\quad \mathbf{w}'\hat\mu_t=r^*,\;\mathbf{1}'\mathbf{w}\le1,\;\mathbf{w}\ge0
\]

Residual → BIL. Costs: 5 bps one-way. v1: long-only, leverage\_cap = 1.0. rf = 0 (Sharpe\_rf0).

Required nulls (CIO gate): **(a)** EW, **(b)** LW MinVar, **(c)** ERC; also (d) LW MVO, (e) optional Book-2 VT.
DSR + trial\_count mandatory (Bailey & López de Prado 2014). **No book cut until Quant gate PASS.**

Teaching HTML: `/workspace/investments/methods/allocation_alpha_forecast_tangency_med.html` (workspace-only; not committed)
Deep Pages stub: `docs/methods/allocation_alpha_forecast_tangency_med.html`

### Walk-forward regime-resilient ERC — Justina shortlist #3

Regime-resilient ERC construction (LOIM regime-parity + stress/corr-breakdown overlays).
**Construction only — NOT dual-regime asset selection (archived #2).**
Primary null: unconditional ERC. Registry `enabled:false` until Quant gate PASS.
Research only; not investment advice.

Lead citation: Ielpo, Muhammetgulyyeva & Royer (2026), *Journal of Portfolio Management* 52(9):189–213.
[doi:10.3905/jpm.2026.030](https://doi.org/10.3905/jpm.2026.030)

```bash
python -m usa_etf_features.cli walkforward-regime-resilient-erc \
  --universe /workspace/investments/usa_universe_categorized.csv \
  --monthly /workspace/investments/usa_universe_panel_monthly_returns.csv \
  --coverage /workspace/investments/usa_universe_panel_history_coverage.csv \
  --constructions stress_corr_overlay,loim_regime_parity \
  --stress-windows 12,24 \
  --mix-lambdas 0.25,0.5 \
  --regime-pool-rules rolling_vol_split,nber_lag \
  --pi-rules historical_freq \
  --apply-to name_level,category_sleeves \
  --cost-bps 5 \
  --out data/processed/rr_erc_oos_summary.csv \
  --weights data/processed/rr_erc_monthly_weights.csv \
  --registry data/processed/rr_erc_trial_registry.csv \
  --returns data/processed/rr_erc_oos_returns.csv \
  --diag-out data/processed/rr_erc_construction_diag.csv
```

**Math appendix — construction paths (not selection):**

*Path A — Stress / corr-breakdown overlay:*

\[
\hat\Sigma_{\text{resilient},t} = (1-\lambda)\hat\Sigma_{\text{uncond},t} + \lambda\hat\Sigma_{\text{stress},t},
\qquad \mathbf{w}^*_t = \mathrm{ERC}(\hat\Sigma_{\text{resilient},t})
\]

*Path B — LOIM regime-parity construction (NOT current-regime selection):*

\[
\mathbf{w}^*_t = \sum_{m}\hat\pi_{m,t}\cdot\mathrm{ERC}(\hat\Sigma_{m,t}),
\qquad \hat\pi_{m,t} = \text{historical frequency or Markov steady-state } (\le t)
\]

Required nulls: **(a) Unconditional ERC (PRIMARY)**, **(b) EW**, **(c) LW MinVar**; optional (d) Book-2 VT.
DSR + trial\_count mandatory. No book cut until Quant gate PASS.

Teaching HTML: `docs/methods/allocation_alpha_regime_resilient_erc.html`
Deep Pages stub: `docs/methods/regime_resilient_erc_stub.html`

### Allocation alpha: Skewness-Managed Book-2 Overlay (Justina shortlist #6 — gate pending)

Walk-forward **Book-2 vol-target overlay** that gates / rescales unconditional Book-2 VT
using skewness / left-tail diagnostics (Gong, Lynch &amp; Ogden 2025/2026).
**Primary null = unconditional Book-2 VT**. Not a third book. Registry `enabled:false`.

```bash
python -m usa_etf_features.cli walkforward-skewness-managed \
  --prices /workspace/investments/usa_universe_adj_close.csv \
  --universe /workspace/investments/usa_universe_categorized.csv \
  --monthly /workspace/investments/usa_universe_panel_monthly_returns.csv \
  --coverage /workspace/investments/usa_universe_panel_history_coverage.csv \
  --null book2_vol_target \
  --cost-bps 5 \
  --out data/processed/skew_managed_oos_summary.csv \
  --weights data/processed/skew_managed_monthly_weights.csv \
  --registry data/processed/skew_managed_trial_registry.csv \
  --returns data/processed/skew_managed_oos_returns.csv \
  --state-out data/processed/skew_managed_state_table.csv \
  --grid   # runs full robustness grid (lookbacks × g_mins × skew-estimators × left-tail-rules)
```

**Math appendix (see teaching HTML for full derivation):**

*Book-2 vol-target backbone (Moreira &amp; Muir 2017):*
```
σ̂_t = √252 · stdev(last L daily returns)   # data ≤ t only
f_t  = clip(σ* / σ̂_t, f_min, f_max)        # scale-down only; f_max=1
```

*Skewness / left-tail gate (Gong–Lynch–Ogden mapping):*
```
rs_t  = realized skewness (Amaya): √N · Σr³ / RV^(3/2)   # daily within month ≤ t
ℓ_t   = left-tail score ≤ t (CVaR_5 | adverse_rs | pct_lt_neg_k_sigma)
g_t   = g_min  if ℓ_t > expanding-median(ℓ)   # gate binds: left-tail adverse
      = 1      otherwise                        # gate open: tail is calm
f̃_t  = f_t · g_t                              # effective equity scale
w̃_t  = f̃_t · w^A + (1 − f̃_t) · e_cash       # residual → BIL
```

Required nulls: **(a) unconditional Book-2 VT (PRIMARY)**, **(b) static Option A**,
**(c) EW**, **(d) LW MinVar**, **(e) ERC**.
DSR + trial\_count mandatory. No book cut until Quant gate PASS.

Teaching HTML: `docs/methods/allocation_alpha_skewness_managed.html`
Deep Pages stub: `docs/methods/skewness_managed_stub.html`

## Disclaimer

This repository is **research infrastructure only**. It does not constitute investment advice, an offer to sell securities, or a recommendation to buy or sell any ETF. Past feature ranks, rotation gates, and backtest-style constructs are not indicative of future results.

## Pages layout frozen

The GitHub Pages layout, IA (nav/routes/sections), and paper-editorial theme (Newsreader/Playfair, cream/navy) are frozen as of 2026-09-25.
Future Pages PRs should only change verdicts and content (e.g. `apps/pages/src/data/archive_verdicts.json`, copy, numbers from repo artifacts), not layout, CSS, tokens or navigation.
A redesign needs an explicit CIO ask.

## GitHub Pages research lab (v2 — Vite + React)

The site in `docs/` is a **Vite + React + Tailwind** app (source: `apps/pages/`), statically
exported to `docs/` so GitHub Pages deploys from `docs/` on `main` with no build server.

Enable Pages in **Settings → Pages → Deploy from branch → `main` → `/docs`** after merging.

**Preview locally:**

```bash
python3 -m http.server 8000 --directory docs
# then open http://localhost:8000/
```

### Rebuild Pages after app or data changes

#### Full rebuild (JS + data)

```bash
bash scripts/build_pages_v2.sh
```

This: (1) reruns `scripts/build_pages.py` to refresh `docs/data/viz_*.json` snapshots, (2) cleans
stale `v2-*` assets from `docs/assets/`, and (3) runs `npm run build` in `apps/pages/`.

#### Data only (after a new `run-strategies` run, no JS changes)

```bash
bash scripts/build_pages_v2.sh --data-only
```

Or manually:

```bash
# 1. Copy CSVs into docs/data/ (or rely on build_pages.py for CIO inputs)
python3 scripts/build_pages.py

# 2. Rebuild JS
cd apps/pages && npm run build
```

#### After editing React source only (no data changes)

```bash
cd apps/pages
npm run build
```

Vite outputs directly to `docs/` (`emptyOutDir: false`). The `docs/data/`, `docs/explorer/`,
and `docs/methods/` directories are preserved.

### Commit after rebuild

```bash
git add docs/
git commit -m "chore: rebuild Pages v2"
```

### Brand scrub

`tests/test_no_brand_tokens.py` scans `docs/` (and source) for forbidden institutional
branding tokens. Run before committing rebuilt pages:

```bash
pytest tests/test_no_brand_tokens.py
```

### IA

| Route | Surface |
|-------|---------|
| `/#/` | Home / live shortlist front door |
| `/#/books` | Books — static core + Book-2 VT (CIO copy slot) |
| `/#/runs` | OOS equity / drawdown / f_t charts |
| `/#/explorer` | Redirects to `docs/explorer/index.html` |
| `/#/archive` | Methods Archive — Justina fails + #13 (muted, not promoted) |

Archive (`/#/archive`) links to legacy teaching HTML in `docs/methods/` but is never surfaced
as a primary nav destination — it is visually de-emphasised in the nav.

### App structure

```
apps/pages/              # Vite React source
  src/
    pages/               # Home · Books · Runs · Explorer · Archive
    components/          # Nav · Layout · EChart · charts/ · ui/
    hooks/useJsonData.ts # JSON data fetcher
    lib/utils.ts         # cn · pct · num · dataUrl helpers
  vite.config.ts         # outDir: ../../docs · emptyOutDir: false
  tailwind.config.ts     # dark editorial tokens
scripts/
  build_pages.py         # data pipeline (viz JSON snapshots)
  build_pages_v2.sh      # wrapper: data + Vite build
docs/
  index.html             # React SPA entry point
  assets/v2-*.{js,css}  # Vite build output
  data/                  # CSV + JSON data (not overwritten by build)
  explorer/              # Static Time Series Explorer
  methods/               # Static teaching HTML pages (archive)
```

All pages carry the research-only disclaimer. No GitHub Actions build step needed.

### Experimental Spectral Risk Parity

```bash
usa-etf-features walkforward-spectral-rp \
  --returns data/raw/usa_universe_panel_monthly_returns.csv \
  --universe data/raw/usa_universe_categorized.csv \
  --coverage data/raw/usa_universe_panel_history_coverage.csv \
  --out-dir data/processed/spectral_rp/ \
  --lookback 60 --gamma 1.0 --mode name --include-thin false
```

Use `--mode sleeve` for equal-weight category constituents, or `--include-thin true`
for the thin-history sensitivity. `--adv-min 10000000` enables the snapshot liquidity
filter; the primary name run raises if fewer than 100 names remain. Inception
warm-up waits for 100 names using past data only. `--asof YYYY-MM-DD` truncates input.
The enabled `spectral_risk_parity` registry entry uses the full panel; remove its
`returns_csv` parameter to derive monthly returns from `run-strategies` daily prices.

Outputs include `oos_returns.csv`, `weights.csv`, `summary.csv`,
`eigen_diagnostics.csv`, `trial_registry.csv`, and `null_comparison.csv`.
Nulls are asset ERC, genuine Ledoit–Wolf long-only MinVar, and equal weight.
Costs are 5 bps times half absolute target-weight changes, including initial entry.
DSR is the existing normal approximation using monthly Sharpe and four trials
(one configuration plus three nulls). For a combined search use
`run_spectral_grid(panel, universe, coverage, trials)` with `SpectralTrial` objects
for every tested lookback/gamma/mode/thin setting; it counts every executed trial
and aligns summaries to shared OOS dates. Supported MP rule: `unit`.

Snapshot membership/coverage can introduce survivorship bias. Missing held OOS
returns fail explicitly. This is a teaching-note research mapping, not an exact
ADIA solver or a claim of outperformance. See the
[method page](docs/methods/spectral_risk_parity.html) for conventions and limitations.

### Research: Analytical nonlinear shrinkage GMV (Bet 1)

```bash
usa-etf-features walkforward-nls-gmv --out-dir data/processed/nonlinear_shrinkage_gmv
```

Runs exactly the pre-registered 156- and 260-week configurations, mirroring the
Spectral RP name gate's universe, monthly evaluation calendar, long-only solver,
turnover and 5 bp costs. NLS, weekly LW MinVar (primary null), ERC and EW use the
same weekly estimation window. The committed monthly LW MinVar is reference only.
Outputs include returns, weights, shrinkage diagnostics, summary/null comparison,
trial registry, weekly-versus-monthly LW comparison, and JSON/Markdown gate reports.
The estimator is a clean-room implementation of the published Ledoit–Wolf
analytical equations; no reference code was copied. Registry `enabled: false`.
Research only. **v1 verdict (Quant, 2026-09-26): VOID — cash-dominated, no evidence of
estimator edge** (method and primary null mostly T-bill ETFs; Sharpe_rf0 rewards cash;
DSR at low trial_count non-decisive). trial_count = 4 (includes the invalidated first run).
Follow-up: v2 re-spec on an ex-cash universe with Sharpe in excess of BIL (also VOID; see below).

Reference-code license check (2026-09-25): the `covShrinkage` repositories
(github.com/oledoit/covShrinkage, MikeWolf007/covShrinkage, pald22/covShrinkage) are
MIT-licensed but contain the 2022 QIS/LIS/GIS and linear estimators, not the 2020
analytical estimator. The 2020 Matlab ZIP on Michael Wolf's UZH publications page
could not be retrieved (TLS error / HTTP 502), so its license is unverified and it is
treated as unlicensed. Nothing was copied or vendored, and no reference-code fixture
was generated; the kernel/Hilbert pieces are cross-checked against numerical
quadrature instead. The far-field (|x| >= 10) Hilbert transform uses an exact series
because the closed form cancels catastrophically in float64 for widely dispersed
spectra (regression-tested).

### Research: NLS GMV v2 (ex-cash, Bet 1)

```bash
usa-etf-features walkforward-nls-gmv-v2 --out-dir data/processed/nonlinear_shrinkage_gmv_v2
```

Pre-registered re-run of the same estimator (`nonlinear_shrinkage_gmv_v2.py`) per Quant's v2 ticket.
Changes vs v1: the `cash_like` tag is removed from the one eligible list shared by the method and every
null (Spectral RP name settings otherwise); name floor 95 (a rebalance below it is skipped for all
strategies and listed; eligible N per rebalance and months under 100 are reported); Sharpe in excess of
BIL (`gate_metrics`) is the headline, with rf = 0 kept as legacy. Configs: 156w primary, 260w sensitivity.
Nulls: weekly LW MinVar (primary), EW, ERC; a monthly LW MinVar on the same ex-cash names is reference
only. Criterion 1 is the Ledoit–Wolf (2011) log-variance-difference test, pre-registered as
p = max(HAC p, studentized circular block bootstrap p) ≤ 0.10, one-sided, with lower OOS vol.
VOID tripwires: method or primary null average `short_duration` weight > 50% or effective N < 5.
trial_count = 6 (4 carried from v1 incl. the invalidated run + 2). DSR is reported, not decisive.
Registry entry `nonlinear_shrinkage_gmv_v2_excash` is `enabled: false`.
**v2 verdict: VOID: short-duration dominated (pre-registered tripwire) — Quant, 2026-09-26.** The 156w
method averages 84.1% short_duration (effective N 2.21) and the primary null 67.1%; short_duration plus FTSL
is 96.58% of the 156w method book (FTSL not re-scored). Even without the tripwire it would FAIL (excess-of-BIL
Sharpe −0.49 vs the null's −0.18; 260w points the same way). The estimator cut OOS vol by about a quarter vs
linear LW (1.87% vs 2.48%, LW2011 p < 0.001 in both windows), consistent with Ledoit & Wolf (2017); the
failure comes from the min-variance objective on a mixed stock-and-bond universe. The GMV line on the mixed
universe is closed, with no v3.
