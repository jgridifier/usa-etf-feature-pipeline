# usa-etf-feature-pipeline

Transparent, unit-tested feature scorer for **GS USA pre-approved ETFs** (research tooling).

> **Not investment advice.** Outputs are research artifacts for personal portfolio exploration. No claim of future performance, guaranteed alpha, or personalized recommendations.

## Milestone 1 status

- Universe gate (CSV ∩ ¬ Appendix-3 / off-list)
- Features: Mom12_1, Vol63/252, MaxDD252, Quality IR−ER, Liquidity ADV$
- Category robust z-scores → composite \(S_i\) from `config/feature_weights.yaml`
- CLI: `score-universe`
- Stubs only: CAPM alpha / Newey–West, constrained portfolio optimizer, `--rotate-thematic`

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## CLI

```bash
python -m usa_etf_features.cli score-universe \
  --universe data/raw/usa_universe_categorized.csv \
  --prices data/raw/growth_alpha_adj_close_sample.csv \
  --out data/processed/scores_YYYYMMDD.csv
```

Optional ticker filter (must pass the universe gate):

```bash
python -m usa_etf_features.cli score-universe \
  --universe data/raw/usa_universe_categorized.csv \
  --prices /path/to/full_adj_close.csv \
  --tickers VOO,QQQ,XSD,QQQM \
  --out data/processed/scores_sample.csv
```

### Price data paths

| File | Role |
|------|------|
| `data/raw/usa_universe_categorized.csv` | Approved universe (committed) |
| `data/raw/growth_alpha_adj_close_sample.csv` | Slim sample (~2022–present) for CI / demos (committed) |
| `data/raw/growth_alpha_adj_close.csv` | Full history — **not committed** (often ~2MB); on the research box at `/workspace/investments/growth_alpha_adj_close.csv` |

Point `--prices` at the full CSV when available for production scoring runs.

## Thin-history flags

These names are marked `thin_history=True` in scores output (shorter listed history vs core peers):

- **QQQM**, **LOUP**, **GTEK**, **GINN**

Also emitted: `history_years` (calendar span of non-null adj close).

## Universe gate

1. Load `Ticker` from the universe CSV → \(U_{\mathrm{approved}}\).
2. Deny Appendix-3 list from `config/universe.yaml` (and any row tagged Appendix 3).
3. Hard deny off-list semis: **SMH, SOXX, SOXL, PSI** (never inject).
4. Eligible \(E = U_{\mathrm{approved}} \setminus \mathrm{deny}\). Any request for \(t \notin E\) **hard-fails**.

## Math appendix

Daily return \(r_{i,t} = P_{i,t}/P_{i,t-1}-1\).

### Momentum 12–1

Month-end prices \(P^m_{i,\tau}\), monthly \(R_{i,\tau}=P^m_{i,\tau}/P^m_{i,\tau-1}-1\).

\[
\mathrm{Mom12\_1}_{i,t}
= \Big(\prod_{k=2}^{12}(1+R^{\mathrm{lag}\,k}_{i,t})\Big)-1
\]

where lag 1 is the most recent month (skipped). Equivalently \(P^m_{t-1}/P^m_{t-12}-1\).

### Volatility

\[
\mathrm{Vol}_i(L)=\sqrt{252}\cdot\mathrm{std}(\{r_{i,t-L+1},\ldots,r_{i,t}\}),\quad \mathrm{ddof}=1
\]

Report `vol_63` and `vol_252`.

### Max drawdown (252d)

On window prices \(P_{i,t-251},\ldots,P_{i,t}\):

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

Default \(\lambda_{\mathrm{ER}}=1\). If ER missing → **0 penalty** and `er_missing=True`.

### Liquidity

\[
\mathrm{ADV\$}_i=\frac{1}{L}\sum_{j=0}^{L-1}\mathrm{Volume}_{i,t-j}\cdot P_{i,t-j},\quad L=21
\]

If volume absent → NaN and `liquidity_missing=True` (z-term treated as 0 in composite).

### Robust z-scores and composite

Within category \(c(i)\):

\[
z_{i,k}=\frac{x_{i,k}-\mathrm{median}_{j\in c(i)}(x_{j,k})}{\mathrm{MAD}\cdot 1.4826}
\]

(MAD=0 → fall back to sample std). Sign: higher Mom / Quality / Liquidity better; use \(-Vol\) and MaxDD (less negative better) before z-scoring.

\[
S_i=\sum_k w_k\,z_{i,k}
\]

**Default weights** (`config/feature_weights.yaml`):

| Feature | \(w_k\) |
|---------|--------:|
| Mom12_1 | 0.30 |
| Quality v1 (IR−ER) | 0.25 |
| −Vol_252 | 0.15 |
| −MaxDD_252 | 0.15 |
| Liquidity ADV$ | 0.10 |
| −Vol_63 | 0.05 |

## Layout

```text
usa-etf-feature-pipeline/
  README.md
  pyproject.toml
  config/
  src/usa_etf_features/
  data/raw/  data/processed/
  tests/
  notebooks/
```

## Disclaimer

This repository is **research infrastructure only**. It does not constitute investment advice, an offer to sell securities, or a recommendation to buy or sell any ETF. Past feature ranks and backtest-style constructs are not indicative of future results.
