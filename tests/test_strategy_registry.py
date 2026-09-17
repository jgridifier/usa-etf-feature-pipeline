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
            "Category": ["Core", "Core", "Core", "Specialty / Other", "Cash"],
        }
    ).to_csv(path, index=False)


def _registry(path, *, enabled_rotate: bool = False, ticker: str = "VOO") -> None:
    path.write_text(
        f"""
version: 1
strategies:
  - id: static_option_a
    display_name: Static Option A
    method_citation_id: baseline_id
    method_citation: baseline
    entrypoint: usa_etf_features.strategy_registry:static_option_a
    default_params:
      weights:
        {ticker}: 1.0
    enabled: true
  - id: score_rotate_xsd
    display_name: Rotate
    method_citation_id: rotate_id
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


def _registry_vol_rotate(path) -> None:
    path.write_text(
        """
version: 1
strategies:
  - id: vol_target_option_a
    display_name: Vol Target Option A
    method_citation_id: moreira_muir_2017_vol_managed
    method_citation: Moreira and Muir 2017 Journal of Finance doi:10.1111/jofi.12513
    entrypoint: usa_etf_features.strategy_registry:vol_target_option_a
    default_params:
      core: option_a
      lookback: 21
      f_min: 0.25
      f_max: 1.0
      sigma_star: expanding_annvol
      cash_ticker: BIL
      cost_bps_one_way: 5.0
    enabled: true
  - id: score_rotate_xsd
    display_name: Rotate
    method_citation_id: xsd_rotation_memo_2026_09_16
    method_citation: XSD rotation memo 2026-09-16
    entrypoint: usa_etf_features.strategy_registry:score_rotate_xsd
    default_params:
      rotate_eligible: [XSD]
      benchmark: VOO
      use_vol_gate: false
      hysteresis_months: 0
    enabled: true
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
    assert specs[0].method_citation_id == "baseline_id"


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
    assert "method_citation_id" in used.columns
    assert "method_citation" in used.columns


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


def test_registry_vol_target_and_rotate_walkforward_dates_do_not_leak(tmp_path):
    reg = tmp_path / "strategies.yaml"
    uni = tmp_path / "universe.csv"
    out = tmp_path / "out"
    _registry_vol_rotate(reg)
    _universe(uni)

    result = run_strategy_registry(
        prices=_prices(n_days=900),
        universe_csv=uni,
        registry_path=reg,
        out_dir=out,
        asof=pd.Timestamp("2023-05-31"),
        walkforward=True,
        universe_config_path=None,
    )

    returns = result["strategy_returns"].copy()
    for sid in ["vol_target_option_a", "score_rotate_xsd"]:
        sub = returns.loc[returns["strategy_id"].eq(sid)].dropna(subset=["decision_date", "feature_end", "date"])
        assert not sub.empty
        assert (pd.to_datetime(sub["feature_end"]) <= pd.to_datetime(sub["decision_date"])).all()
        assert (pd.to_datetime(sub["date"]) > pd.to_datetime(sub["decision_date"])).all()
        for _, row in sub.iterrows():
            assert_no_same_period_leakage(
                decision_date=pd.Timestamp(row["decision_date"]),
                feature_end=pd.Timestamp(row["feature_end"]),
                label_start=pd.Timestamp(row["decision_date"]) + pd.Timedelta(days=1),
                label_end=pd.Timestamp(row["date"]),
            )

    diagnostics = result["strategy_diagnostics"]
    assert diagnostics["walkforward"].eq(True).all()
