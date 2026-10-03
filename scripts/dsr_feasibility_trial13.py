"""Trial-13 DSR feasibility check (Quant, 2026-10-03; approved by CoS).

Registry-only arithmetic: no gate run, no new trial, and no signal on the panel is looked at.
Reads the committed trial registry (data/processed/schur_allocator/trial_registry.csv) and the Schur
summary.csv (capped equal weight's Sharpe ex-BIL, a reference point from an earlier trial), and uses the
repo's deflated_sharpe_bailey_lp with T = 119 months (the Schur OOS window) and N = 13 trials.

For each case it finds the annualized Sharpe ex-BIL at which DSR reaches 0.5, 0.9 and 0.95 (C4).
Cases, per Quant: normal returns (skew 0, raw kurtosis 3) and two fat-tail cases, skew -0.5 with raw
kurtosis 5 and skew -1 with raw kurtosis 7 (raw kurtosis, as deflated_sharpe_bailey_lp takes it).
As a check, the same function at N = 12 reproduces the Schur DSR (normal moments).
Writes data/processed/dsr_feasibility_trial13/feasibility.json.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import ndtri

from usa_etf_features.nonlinear_shrinkage_gmv_v3 import cross_trial_sharpe_var, deflated_sharpe_bailey_lp

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = 'data/processed/schur_allocator/trial_registry.csv'
SUMMARY = 'data/processed/schur_allocator/summary.csv'
OUT = ROOT / 'data/processed/dsr_feasibility_trial13/feasibility.json'
T, N, N_SCHUR = 119, 13, 12
TARGETS = (0.5, 0.9, 0.95)
C4_TARGET = 0.95
CASES = (
    ('normal', 'Normal returns', 0.0, 3.0),
    ('fat_tail_moderate', 'Skew −0.5, kurtosis 5', -0.5, 5.0),
    ('fat_tail_severe', 'Skew −1, kurtosis 7', -1.0, 7.0),
)
EULER_GAMMA = 0.5772156649015329
# CIO's request (2026-10-03), verbatim; rendered as "<label>: <text>" directly under the options.
CIO_RECOMMENDATION = dict(
    label='CIO recommendation',
    text=("park the allocator search. Loosening C4 after 12 trials would weaken the main guard against overfitting. "
          "If the idea is kept alive, choose a forward-only paper trade with C4 still required to pass, over loosening "
          "C4 on history we've already used. The decision is Jared's."),
)


def sr0_monthly(var_monthly: float, n_trials: int) -> float:
    """Expected max Sharpe of n_trials noise strategies (the SR0 inside deflated_sharpe_bailey_lp)."""
    g = EULER_GAMMA
    return float(np.sqrt(var_monthly) * ((1 - g) * ndtri(1 - 1 / n_trials) + g * ndtri(1 - 1 / (n_trials * np.e))))


def hurdle_annual(target: float, var_monthly: float, skew: float, kurt: float, n_obs: int = T, n_trials: int = N) -> float:
    """Annualized Sharpe ex-BIL at which deflated_sharpe_bailey_lp equals target."""
    f = lambda sr_ann: deflated_sharpe_bailey_lp(sr_ann / math.sqrt(12), n_obs, n_trials, var_monthly, skew, kurt) - target
    return float(brentq(f, 0.0, 3.0, xtol=1e-12))


def compute(root: Path = ROOT) -> dict:
    registry = pd.read_csv(root / REGISTRY)
    var = cross_trial_sharpe_var(registry)
    summary = pd.read_csv(root / SUMMARY).set_index('strategy_id')
    full = summary.loc[summary.period_role.eq('full window')]
    ew = float(full.loc['equal_weight', 'Sharpe_exBIL'])
    schur_sr = float(full.loc['schur_g050', 'Sharpe_exBIL'])
    if int(full.loc['schur_g050', 'n_months']) != T:
        raise SystemExit('Schur OOS window is not T months')
    cases = []
    for key, label, skew, kurt in CASES:
        cases.append(dict(key=key, label=label, skew=skew, kurtosis_raw=kurt,
                          hurdles=[dict(dsr=t, sharpe_exbil_annual=hurdle_annual(t, var, skew, kurt)) for t in TARGETS]))
    normal = cases[0]
    c4 = next(h['sharpe_exbil_annual'] for h in normal['hurdles'] if h['dsr'] == C4_TARGET)
    fat_c4 = [next(h['sharpe_exbil_annual'] for h in c['hurdles'] if h['dsr'] == C4_TARGET) for c in cases[1:]]
    return dict(
        title='Trial-13 DSR feasibility check',
        method='Bailey & López de Prado (2014) deflated Sharpe ratio, deflated_sharpe_bailey_lp '
               '(src/usa_etf_features/nonlinear_shrinkage_gmv_v3.py); hurdles solved by root-finding',
        scope='Registry only: no gate run, no new trial, no signal on the panel looked at',
        sources=dict(registry=REGISTRY, summary=SUMMARY),
        inputs=dict(T=T, N=N, sr_var_cross_trial_monthly=var,
                    registry_trials=int(len(registry)),
                    registry_trials_with_sharpe=int(registry.Sharpe_exBIL_annual.notna().sum()),
                    kurtosis_convention='raw (normal = 3)'),
        sr0_annual=sr0_monthly(var, N) * math.sqrt(12),
        c4=dict(rule='DSR >= 0.95', dsr=C4_TARGET, hurdle_normal=c4, hurdle_fat_tail_range=[min(fat_c4), max(fat_c4)]),
        cases=cases,
        reference=dict(capped_equal_weight_sharpe_exbil=ew, capped_equal_weight_source=f'{SUMMARY} (equal_weight, full window)',
                       hurdle_to_ew_ratio=c4 / ew),
        check=dict(schur_sharpe_exbil=schur_sr, N=N_SCHUR,
                   schur_dsr_reproduced=deflated_sharpe_bailey_lp(schur_sr / math.sqrt(12), T, N_SCHUR, var, 0.0, 3.0),
                   schur_dsr_recorded=float(full.loc['schur_g050', 'DSR_exBIL']),
                   note='normal moments here; the recorded value used realized skew and kurtosis'),
        decision=dict(status='pending', owner='Jared',
                      options=['Park the search', 'Report C4 without requiring it', 'Run a forward-only paper trade']),
        cio_recommendation=dict(CIO_RECOMMENDATION),
    )


def main() -> None:
    payload = compute()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
