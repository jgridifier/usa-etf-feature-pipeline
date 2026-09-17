"""Strategy registry runner tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.strategy_registry import (
    load_strategy_registry,
    run_strategy_registry,
)
from usa_etf_features.universe import UniverseGateError
from usa_etf_features.walkforward import assert_no_same_period_leakage


def _prices(n_days: int = 520, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2020-01-02", periods=n_days)
    data = {}
    for i, t in enumerate(["VOO", "QQQM", "IJR", "XSD", "BIL"]):
        vol = 0.00015 if t == "BIL" else 0.008 + i * 0.0005
        mu = 0.00004 if t == "BIL" else 0.00025
        data[t] = 100 * np.cumprod(1 + rng.normal(mu, vol, n_days))
    return pd.DataFrame(data, index=idx)


def _universe(path) -> None:
    pd.DataFrame(
        {
            "Ticker": ["VOO", "QQQM", "IJR", "XSD", "BIL"],
            "Source_Section": ["APPENDIX 2"] * 5,
            "Category": ["Core", "Core", "Core", "Thematic", "Cash"],
        }
    ).to_csv(path, index=False)


def _registry(path, *, enabled_rotate: bool = False, ticker: str = "VOO") -> None:
    path.write_text(
        f"""
version: 1
strategies:
  - id: static_option_a
    display_name: Static Option A
    method_citation: baseline
    entrypoint: usa_etf_features.strategy_registry:static_option_a
    default_params:
      weights:
        {ticker}: 1.0
    enabled: true
  - id: score_rotate_xsd
    display_name: Rotate
    method_citation: rotate
    entrypoint: usa_etf_features.strategy_registry:score_rotate_xsd
    default_params:
      rotate_eligible: [XSD]
      use_vol_gate: false
      hysteresis_months: 0
    enabled: {str(enabled_rotate).lower()}
""",
        encoding="utf-8",
    )


def test_registry_load_and_disable_flag(tmp_path):
    reg = tmp_path / "strategies.yaml"
    _registry(reg, enabled_rotate=False)
    specs = load_strategy_registry(reg)
    assert [s.id for s in specs] == ["static_option_a", "score_rotate_xsd"]
    assert specs[0].enabled is True
    assert specs[1].enabled is False


def test_run_strategies_weight_sum_and_disable_skip(tmp_path):
    reg = tmp_path / "strategies.yaml"
    uni = tmp_path / "universe.csv"
    out = tmp_path / "out"
    _registry(reg, enabled_rotate=False)
    _universe(uni)

    result = run_strategy_registry(
        prices=_prices(),
        universe_csv=uni,
        registry_path=reg,
        out_dir=out,
        asof=pd.Timestamp("2021-12-31"),
    )

    weights = result["suggested_weights"]
    assert sorted(weights["strategy_id"].unique()) == ["static_option_a"]
    sums = weights.groupby("strategy_id")["weight"].sum()
    assert sums["static_option_a"] == pytest.approx(1.0)
    assert (out / "strategy_registry_used.csv").exists()
    used = pd.read_csv(out / "strategy_registry_used.csv")
    assert used.loc[used["strategy_id"].eq("score_rotate_xsd"), "enabled"].iloc[0] in {False, "False"}


def test_run_strategies_smh_hard_fails(tmp_path):
    reg = tmp_path / "strategies.yaml"
    uni = tmp_path / "universe.csv"
    out = tmp_path / "out"
    _registry(reg, ticker="SMH")
    _universe(uni)

    with pytest.raises(UniverseGateError):
        run_strategy_registry(
            prices=_prices().assign(SMH=lambda df: df["VOO"]),
            universe_csv=uni,
            registry_path=reg,
            out_dir=out,
            asof=pd.Timestamp("2021-12-31"),
        )


def test_registry_walkforward_leakage_helper():
    decision = pd.Timestamp("2024-03-28")
    assert_no_same_period_leakage(
        decision_date=decision,
        feature_end=decision,
        label_start=pd.Timestamp("2024-03-29"),
        label_end=pd.Timestamp("2024-04-30"),
    )
