"""Robust category z-scores and composite S_i from config weights."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def load_feature_weights(path: str | Path | None = None) -> dict:
    if path is None:
        candidates = [
            Path("config/feature_weights.yaml"),
            Path(__file__).resolve().parents[2] / "config" / "feature_weights.yaml",
        ]
        for c in candidates:
            if c.exists():
                path = c
                break
        else:
            return {
                "weights": {
                    "mom12_1": 0.30,
                    "quality_v1": 0.25,
                    "neg_vol_252": 0.15,
                    "neg_maxdd_252": 0.15,
                    "liquidity_adv": 0.10,
                    "neg_vol_63": 0.05,
                },
                "robust_z": {"mad_scale": 1.4826},
            }
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def robust_z(series: pd.Series, mad_scale: float = 1.4826) -> pd.Series:
    """z = (x - median) / (MAD * 1.4826); if MAD=0 fall back to std."""
    x = series.astype(float)
    med = x.median()
    mad = (x - med).abs().median()
    if mad == 0 or np.isnan(mad):
        std = x.std(ddof=1)
        if std == 0 or np.isnan(std):
            return pd.Series(0.0, index=x.index)
        return (x - med) / std
    return (x - med) / (mad * mad_scale)


def prepare_signed_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Map raw features to signed scoring inputs (invert vol / maxdd)."""
    out = pd.DataFrame(index=raw.index)
    out["mom12_1"] = raw["mom12_1"]
    out["quality_v1"] = raw["quality_v1"]
    out["neg_vol_252"] = -raw["vol_252"]
    out["neg_maxdd_252"] = -raw["maxdd_252"]  # deeper (more neg) MaxDD → larger positive after negate? 
    # MaxDD is negative (e.g. -0.3). Worse = more negative. -MaxDD = +0.3 for deep DD → higher is worse if we z(-MaxDD) wait.
    # Spec: "higher Vol and deeper MaxDD (more negative) = worse → use z(-Vol), z(-MaxDD)"
    # -Vol: higher vol → more negative -Vol → worse after z (lower z). Good.
    # -MaxDD: MaxDD=-0.4 (deep) → -MaxDD=+0.4; MaxDD=-0.1 (shallow) → -MaxDD=+0.1.
    # Then higher -MaxDD means deeper drawdown = worse. But we want higher score = better,
    # so we should NOT want higher -MaxDD to increase S. Spec says use z(-MaxDD) as the feature
    # with the understanding it's a "risk" feature that... wait, weights are on neg_vol and neg_maxdd
    # as if they're the features entering the sum. If deeper DD → larger -MaxDD → higher z → higher S,
    # that would REWARD deep drawdowns. That's wrong.
    #
    # Re-read: "Sign conventions: higher Mom, IR/Quality, Liquidity = better; higher Vol and deeper MaxDD
    # (more negative) = worse → use z(-Vol), z(-MaxDD) or invert before scoring."
    #
    # z(-Vol): high vol → low -Vol → low z → lower S. Correct.
    # z(-MaxDD): MaxDD is negative. Deep MaxDD = -0.5, -MaxDD = +0.5. Shallow = -0.1, -MaxDD = +0.1.
    # High -MaxDD (deep DD) → high z → high S. WRONG.
    #
    # Unless they mean the feature stored as -MaxDD but want lower (more negative MaxDD magnitude)...
    # Alternative reading: use z of (-Vol) so the feature points "up = better". For MaxDD,
    # "better" = less negative = closer to 0. So the upward feature should be MaxDD itself
    # ( -0.1 > -0.5 ) or equivalently -|MaxDD|. Spec says z(-MaxDD) which points the wrong way
    # if MaxDD is signed negative.
    #
    # If MaxDD is reported as a positive magnitude (depth), then -MaxDD works.
    # Spec formula returns min(drawdowns) which is ≤ 0. I'll invert by using MaxDD directly
    # as the "better when higher" signal (less negative is better), labeled neg_maxdd_252 in weights
    # for documentation alignment with "-MaxDD_252" meaning "penalize drawdown".
    #
    # Practical fix matching intent (penalize deep DD): score feature = MaxDD (already ≤0),
    # or = -abs(MaxDD). Using MaxDD as signed feature: higher (closer to 0) is better.
    # Weight key remains neg_maxdd_252 per config naming.
    out["neg_maxdd_252"] = raw["maxdd_252"]  # less negative = better
    out["liquidity_adv"] = raw["liquidity_adv"]
    out["neg_vol_63"] = -raw["vol_63"]
    return out


def category_zscores(
    signed: pd.DataFrame,
    categories: pd.Series,
    feature_cols: list[str],
    mad_scale: float = 1.4826,
) -> pd.DataFrame:
    z = pd.DataFrame(index=signed.index)
    for col in feature_cols:
        z[f"z_{col}"] = np.nan
    for cat, idx in categories.groupby(categories).groups.items():
        sub = signed.loc[list(idx)]
        for col in feature_cols:
            # If all NaN (e.g. liquidity), leave NaN
            if sub[col].notna().sum() == 0:
                continue
            z.loc[list(idx), f"z_{col}"] = robust_z(sub[col], mad_scale=mad_scale)
    return z


def composite_scores(
    raw_features: pd.DataFrame,
    categories: pd.Series | dict[str, str],
    weights_cfg: dict | None = None,
) -> pd.DataFrame:
    """
    Within-category robust z-scores → S_i = sum_k w_k z_{i,k}.
    Missing z (e.g. no liquidity) → treat as 0 for that term and note flag.
    """
    cfg = weights_cfg or load_feature_weights()
    weights = cfg["weights"]
    mad_scale = float(cfg.get("robust_z", {}).get("mad_scale", 1.4826))
    feature_cols = list(weights.keys())

    if isinstance(categories, dict):
        cat = pd.Series(categories)
    else:
        cat = categories
    cat = cat.reindex(raw_features.index)
    cat = cat.fillna("Unknown")

    signed = prepare_signed_features(raw_features)
    z = category_zscores(signed, cat, feature_cols, mad_scale=mad_scale)

    # Re-weight: if a feature is all-NaN cross-section (liquidity), redistribute is optional;
    # M1: use 0 for missing z and keep weights as configured (documented).
    S = pd.Series(0.0, index=raw_features.index, dtype=float)
    for col, w in weights.items():
        zcol = z[f"z_{col}"].fillna(0.0)
        S = S + float(w) * zcol

    out = raw_features.copy()
    out["category"] = cat
    for col in feature_cols:
        out[f"z_{col}"] = z[f"z_{col}"]
    out["S_i"] = S
    return out.sort_values("S_i", ascending=False)
