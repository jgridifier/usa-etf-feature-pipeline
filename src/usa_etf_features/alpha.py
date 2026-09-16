"""Alpha helpers (stub for Milestone 1; full CAPM + Newey–West in later milestone)."""

from __future__ import annotations

import pandas as pd


def excess_returns(asset: pd.Series, benchmark: pd.Series) -> pd.Series:
    """Daily excess return x = r_i - r_b."""
    a = asset.dropna()
    b = benchmark.dropna()
    aligned = pd.concat([a, b], axis=1, join="inner").dropna()
    if aligned.empty:
        return pd.Series(dtype=float)
    return aligned.iloc[:, 0] - aligned.iloc[:, 1]


def capm_alpha_stub(*_args, **_kwargs) -> float:
    """Placeholder — CAPM alpha + Newey–West SE arrives in a later milestone."""
    raise NotImplementedError("capm_alpha / Newey–West not implemented in Milestone 1")
