"""Portfolio caps and rotate path integration."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.portfolio import (
    build_portfolio,
    build_static_from_scores,
    enforce_thematic_caps,
    proportional_core_trim,
    validate_weights,
)
from usa_etf_features.universe import UniverseGateError


def test_thematic_cap_enforced():
    w = enforce_thematic_caps({"XSD": 0.20, "XBI": 0.20}, thematic_cap=0.25, single_cap=0.15)
    assert w["XSD"] <= 0.15 + 1e-12
    assert w["XBI"] <= 0.15 + 1e-12
    assert sum(w.values()) <= 0.25 + 1e-9


def test_validate_weights_thematic_breach():
    with pytest.raises(ValueError, match="thematic sleeve"):
        validate_weights(
            {"VOO": 0.60, "XSD": 0.20, "XBI": 0.20},
            thematic_tickers={"XSD", "XBI"},
            thematic_cap=0.25,
            single_thematic_cap=0.25,
        )


def test_static_from_scores_sums_to_one():
    scores = pd.DataFrame(
        {
            "ticker": ["VOO", "QQQ", "IJR", "QUAL", "XSD"],
            "S_i": [1.0, 0.9, 0.8, 0.7, 0.6],
            "category": ["Core", "Growth", "Core", "Factor", "Thematic"],
        }
    )
    w = build_static_from_scores(scores)
    assert abs(w["weight"].sum() - 1.0) < 1e-8
    them = w.loc[w["role"] == "thematic", "weight"].sum()
    assert them <= 0.25 + 1e-9


def test_rotate_requires_prices():
    scores = pd.DataFrame({"ticker": ["VOO"], "S_i": [1.0]})
    with pytest.raises(ValueError, match="prices"):
        build_portfolio(scores=scores, rotate_thematic=True)


def test_smh_in_eligible_raises():
    idx = pd.bdate_range("2020-01-01", periods=400)
    rng = np.random.default_rng(0)
    px = pd.DataFrame(
        {
            "VOO": 100 * np.cumprod(1 + rng.normal(0.0004, 0.01, len(idx))),
            "QQQM": 100 * np.cumprod(1 + rng.normal(0.0005, 0.012, len(idx))),
            "IJR": 100 * np.cumprod(1 + rng.normal(0.0003, 0.011, len(idx))),
            "SMH": 100 * np.cumprod(1 + rng.normal(0.0006, 0.02, len(idx))),
        },
        index=idx,
    )
    cfg = {
        "core_when_thematic_off": {"VOO": 0.70, "QQQM": 0.20, "IJR": 0.10},
        "thematic_rotate_eligible": ["SMH"],
        "thematic_tickers": ["SMH"],
        "thematic_cap": 0.25,
        "single_name_cap_thematic": 0.15,
        "rotate_on_weight": 0.10,
        "hysteresis_months": 0,
        "rotate_benchmark": "VOO",
    }
    with pytest.raises(UniverseGateError):
        build_portfolio(prices=px, rotate_thematic=True, use_vol_gate=False, constraints=cfg)
