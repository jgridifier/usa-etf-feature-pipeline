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

## Disclaimer

This repository is **research infrastructure only**. It does not constitute investment advice, an offer to sell securities, or a recommendation to buy or sell any ETF. Past feature ranks, rotation gates, and backtest-style constructs are not indicative of future results.

## GitHub Pages research lab

The committed site in `docs/` includes Home, Methods, Books, and Runs. Enable it in
**Settings → Pages → Deploy from branch → `main` → `/docs`** after merging this branch.
Preview locally with `python -m http.server 8000 --directory docs`.

After a new `run-strategies --asof YYYY-MM-DD` run:

1. Copy the intended CSV artifacts into `docs/data/` (or rely on `scripts/build_pages.py`, which
   copies from `/workspace/investments/cio_book_shortlist/` when present: shortlist/strategy
   comparison, suggested weights, strategy diagnostics, book weight CSVs). Refresh the
   `vol_target_*.csv` set together after a new vol-target run, and copy its `README_OOS_note.md`.
   Pages reads this directory, not `data/processed/`.
2. Scrub brand names and institutional policy claims from imported artifacts and teaching HTML
   before publication. Keep academic citations and neutral research framing. Universe legal names
   are neutralized where necessary; every source section is `experimental_research_universe`.
3. Run `python scripts/build_pages.py`. This (a) copies CIO CSVs when available, (b) builds
   `docs/data/viz_*.json` snapshots (equity/drawdown from `r_vt`/`r_option_a`, `f_t` + `w_BIL`,
   weight bars, XSD diagnostics snapshot, comparison table), and (c) regenerates Home/Books/Runs
   HTML plus shared Methods chrome. Charts load via Apache ECharts CDN + `docs/assets/app.js`.
4. Run `pytest`, preview with `python -m http.server 8000 --directory docs`, and commit `docs/`
   alongside source changes. No GitHub build step is required. Branding is gated by
   `tests/test_no_brand_tokens.py`.

All pages describe an experimental panel: research only; not investment advice; no performance
guarantees. `tests/test_no_brand_tokens.py` enforces the brand scrub across source, tests,
configuration, raw data, scripts, and the published site with no content allowlist.

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
