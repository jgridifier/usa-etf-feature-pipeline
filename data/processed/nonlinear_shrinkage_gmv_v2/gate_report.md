# NLS GMV v2 ex-cash research gate

PENDING — Quant decides

Research only. Registry enabled:false. Snapshot universe implies survivorship bias. No live-book wiring.

Ticket: `/workspace/investments/justina_shortlist/ENGINEERING_TICKET_nonlinear_shrinkage_gmv_v2_excash.md`

Criterion 1: method AnnVol < weekly LW MinVar AnnVol and p_gate = max(p_one_sided_hac, p_one_sided_boot) <= 0.10; both LW2011 variants must pass.

Spectral RP name settings plus exclude_cash_like=True; pre-registered floor 95, skip-and-list.
Weekly windows end at the decision month; next-month evaluation, half-L1 turnover including initial entry, 5 bp costs.
Previous weights carry across skipped months. Monthly LW MinVar is reference only.

Configuration: `{"adv_min": 0.0, "below_floor": "skip", "cost_bps": 5.0, "exclude_cash_like": true, "exclude_categories": ["Defined Outcome / Buffer / Structured", "Specialty / Other"], "include_thin": false, "min_names": 95, "oos_end": "2026-08-31", "oos_start": "2021-04-30", "reference_lookback_months": 60, "thin_min_months": 60, "window_weeks": 156}`

Configuration: `{"adv_min": 0.0, "below_floor": "skip", "cost_bps": 5.0, "exclude_cash_like": true, "exclude_categories": ["Defined Outcome / Buffer / Structured", "Specialty / Other"], "include_thin": false, "min_names": 95, "oos_end": "2026-08-31", "oos_start": "2021-04-30", "reference_lookback_months": 60, "thin_min_months": 60, "window_weeks": 260}`

156w eligible N per rebalance: min 98, mean 105.71, max 114; months under 100: 8; skipped months: none.

260w eligible N per rebalance: min 98, mean 105.71, max 114; months under 100: 8; skipped months: none.

## 156-week configuration

| Strategy | AnnVol | Sharpe ex-BIL | Sharpe legacy (rf = 0) | MaxDD | short_duration share | eff N | names held | turnover/yr | NW t vs primary | DSR (ex-BIL) | LW2011 p (one-sided, HAC / boot / gate) | largest category (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NLS GMV (method) | 1.87% | -0.489 | 1.307 | -4.52% | 84.12% | 2.21 | 7.77 | 54.30% | -1.14 | 0.0180 | 0.000 / 0.000 / 0.000 | US Treasuries / Govt / Cash-like (83.95%) |
| Weekly LW MinVar (primary null) | 2.48% | -0.183 | 1.144 | -6.15% | 67.07% | 6.55 | 13.71 | 32.12% | — | 0.0822 | — / — / — | US Treasuries / Govt / Cash-like (50.35%) |
| EW | 11.19% | 0.552 | 0.817 | -19.10% | 3.79% | 105.71 | 105.71 | 12.01% | 2.12 | 0.6211 | 1.000 / 1.000 / 1.000 | International Developed Equity (18.88%) |
| ERC | 6.41% | 0.325 | 0.816 | -12.69% | 23.50% | 38.13 | 105.71 | 22.89% | 1.62 | 0.4137 | 1.000 / 1.000 / 1.000 | US Treasuries / Govt / Cash-like (29.02%) |
| Monthly LW MinVar (reference only) | 2.90% | -0.231 | 0.894 | -6.98% | 55.85% | 10.36 | 16.85 | 33.24% | -0.61 | 0.0667 | 0.999 / 0.969 / 0.999 | US Treasuries / Govt / Cash-like (43.77%) |

## 260-week configuration

| Strategy | AnnVol | Sharpe ex-BIL | Sharpe legacy (rf = 0) | MaxDD | short_duration share | eff N | names held | turnover/yr | NW t vs primary | DSR (ex-BIL) | LW2011 p (one-sided, HAC / boot / gate) | largest category (share) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NLS GMV (method) | 1.89% | -0.527 | 1.247 | -4.62% | 90.84% | 1.74 | 7.62 | 37.49% | -0.67 | 0.0145 | 0.000 / 0.000 / 0.000 | US Treasuries / Govt / Cash-like (90.84%) |
| Weekly LW MinVar (primary null) | 2.44% | -0.303 | 1.044 | -5.92% | 74.21% | 6.02 | 12.28 | 23.10% | — | 0.0476 | — / — / — | US Treasuries / Govt / Cash-like (57.15%) |
| EW | 11.19% | 0.552 | 0.817 | -19.10% | 3.79% | 105.71 | 105.71 | 12.01% | 2.19 | 0.6211 | 1.000 / 1.000 / 1.000 | International Developed Equity (18.88%) |
| ERC | 6.19% | 0.306 | 0.816 | -12.26% | 26.56% | 31.63 | 105.71 | 18.01% | 1.74 | 0.3972 | 1.000 / 1.000 / 1.000 | US Treasuries / Govt / Cash-like (33.91%) |
| Monthly LW MinVar (reference only) | 2.90% | -0.231 | 0.894 | -6.98% | 55.85% | 10.36 | 16.85 | 33.24% | 0.12 | 0.0667 | 1.000 / 0.997 / 1.000 | US Treasuries / Govt / Cash-like (43.77%) |

## Mechanical reading of criteria 1–5 (not a verdict)

Mechanical overall: VOID.

w156:
- c1: True; vol 1.87% vs 2.48%; p_gate 0.000 <= 0.100 (direction: True).
- c2: False; Sharpe ex-BIL -0.489 >= primary -0.183 and > ERC 0.325.
- c3: True; MaxDD -4.52% vs -6.15%.
- c5 VOID tripwires: method short_duration 84.12%, eff N 2.21; primary short_duration 67.07%, eff N 6.55. Thresholds: share > 50.00% or eff N < 5.00.

w260:
- c1: True; vol 1.89% vs 2.44%; p_gate 0.000 <= 0.100 (direction: True).
- c2: False; Sharpe ex-BIL -0.527 >= primary -0.303 and > ERC 0.306.
- c3: True; MaxDD -4.62% vs -5.92%.
- c5 VOID tripwires: method short_duration 90.84%, eff N 1.74; primary short_duration 74.21%, eff N 6.02. Thresholds: share > 50.00% or eff N < 5.00.

c4: 260w same way on volatility direction and criterion 2: False.

156w VOID tripwires: void_method_short_duration, void_method_effN, void_primary_short_duration.
Failing criteria: c2, c4.
260w informational tripwires: void_method_short_duration, void_method_effN, void_primary_short_duration.
260w tripwires are information only; do not void the 156w gate

DSR is non-decisive; trial_count 6: 4 carried from v1 incl. the invalidated run + 2 v2 configs + 0 extra previews. DSR uses monthly Sharpe = annual Sharpe / sqrt(12).
Extra previews: none.

LW2011: 4999 paired circular bootstrap replicates; block size 4 months; seed 20260926. VAR(1) prewhitening, spectral radius capped at 0.97, Andrews automatic QS bandwidth, T/(T−4) correction. Common RMS return units are removed before the equal-weight moment bandwidth fits; final partial bootstrap blocks are truncated.
Sharpe ex-BIL uses priced BIL monthly returns with TB3MS fallback; fallback shares are in summary.csv.

Monthly LW MinVar is reference only. Quant decides.
