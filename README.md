# usa-etf-feature-pipeline

Transparent, unit-tested feature scorer and **optional thematic rotation sleeve** for **GS USA pre-approved ETFs** (research tooling).

> **Not investment advice.** Outputs are research artifacts for personal portfolio exploration. No claim of future performance, guaranteed alpha, or personalized recommendations. Research-only.

## Status

| Milestone | Contents |
|-----------|----------|
| **M1** | Universe gate, transparent features, `score-universe` CLI |
| **M2** | `--rotate-thematic` (ScoreSimple Mom+vol vs VOO), caps, walk-forward IC |
| M3 | Optimizer study — **out of scope** for this branch |

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
4. Eligible \(E = U_{\mathrm{approved}} \setminus \mathrm{deny}\). Any \(t \notin E\) **hard-fails**.

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
