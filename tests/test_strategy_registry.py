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


# ---------------------------------------------------------------------------
# Justina #6 — vol_target_book2 (live Book-2 = VT × gate-first skew overlay)
# ---------------------------------------------------------------------------

def test_strategies_yaml_uncond_null_entry_preserved():
    """Live config/strategies.yaml must contain the unconditional VT null audit entry.

    vol_target_option_a_uncond must exist, be disabled, use the plain vol_target entrypoint,
    and carry L63/f_min=0.25/f_max=1.0 — so the primary null (Sharpe ≈ 1.059 / MaxDD ≈ −20.1%)
    remains reproducible for Quant audit without being a live shortlist book.
    """
    from pathlib import Path
    import yaml
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "strategies.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    entries = {s["id"]: s for s in raw.get("strategies", [])}

    assert "vol_target_option_a_uncond" in entries, (
        "vol_target_option_a_uncond (Quant audit null) not found in strategies.yaml"
    )
    null_entry = entries["vol_target_option_a_uncond"]

    # Must be disabled — it is the audit null, NOT a live shortlist book
    assert null_entry.get("enabled") is False, (
        "vol_target_option_a_uncond must have enabled:false — it is the audit null, not a live book"
    )

    # Must use the plain (unconditional) vol-target entrypoint, not the overlay
    assert null_entry.get("entrypoint") == "usa_etf_features.strategy_registry:vol_target_option_a", (
        "uncond null must use vol_target_option_a entrypoint (unconditional VT, no skew gate)"
    )

    # Params must match the unconditional VT (no skew knobs)
    params = null_entry.get("default_params", {})
    assert int(params.get("lookback", 0)) == 63
    assert "skew_estimator" not in params, (
        "uncond null must NOT have skew_estimator param — it is the unconditional baseline"
    )
    assert "g_min" not in params, (
        "uncond null must NOT have g_min param — it is the unconditional baseline"
    )


def test_strategies_yaml_book2_uses_gate_first_knobs():
    """Live config/strategies.yaml must have vol_target_option_a with gate-first skew knobs.

    vol_target_option_a is the live Book-2. Since CIO chose option (B), its entrypoint
    is vol_target_book2 and params must contain locked gate-first knobs:
      lookback=63, skew_estimator=realized_amaya, left_tail_rule=cvar_5, g_min=0.5
    No separate skewness_managed_book2 entry must exist.
    """
    from pathlib import Path
    import yaml
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "strategies.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    entries = {s["id"]: s for s in raw.get("strategies", [])}

    # No separate disabled overlay entry — #6 is wired into vol_target_option_a
    assert "skewness_managed_book2" not in entries, (
        "skewness_managed_book2 must not be a separate registry entry — "
        "overlay is wired into vol_target_option_a"
    )

    assert "vol_target_option_a" in entries, "vol_target_option_a (Book-2) not found in strategies.yaml"
    entry = entries["vol_target_option_a"]
    params = entry.get("default_params", {})

    # Book-2 must be live (enabled)
    assert entry.get("enabled") is True, "vol_target_option_a (Book-2) must be enabled:true"

    # Entrypoint must be the overlay adapter, not the plain vol-target
    assert entry.get("entrypoint") == "usa_etf_features.strategy_registry:vol_target_book2", (
        f"vol_target_option_a entrypoint must be vol_target_book2; got {entry.get('entrypoint')!r}"
    )

    # Gate-first knobs locked — none may deviate
    assert int(params["lookback"]) == 63, f"lookback must be 63 (gate-first); got {params['lookback']}"
    assert str(params["skew_estimator"]) == "realized_amaya", (
        f"skew_estimator must be realized_amaya; got {params['skew_estimator']!r}"
    )
    assert str(params["left_tail_rule"]) == "cvar_5", (
        f"left_tail_rule must be cvar_5; got {params['left_tail_rule']!r}"
    )
    assert abs(float(params["g_min"]) - 0.5) < 1e-9, f"g_min must be 0.5 (gate-first); got {params['g_min']}"


def test_vol_target_book2_enforcer_rejects_non_gatefirst_lookback(tmp_path):
    """vol_target_book2 adapter must raise ValueError if lookback != 63."""
    import numpy as np
    import pandas as pd

    from usa_etf_features.strategy_registry import StrategySpec, vol_target_book2

    uni_path = tmp_path / "universe.csv"
    pd.DataFrame({
        "Ticker": ["VOO", "QQQM", "IJR", "BIL"],
        "Source_Section": ["APPENDIX 2"] * 4,
        "Category": ["US Large / Broad Blend"] * 3 + ["US Treasuries / Govt / Cash-like"],
    }).to_csv(uni_path, index=False)

    rng = np.random.default_rng(99)
    idx = pd.bdate_range("2019-01-02", periods=600)
    px = pd.DataFrame(
        {t: 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, 600)) for t in ["VOO", "QQQM", "IJR", "BIL"]},
        index=idx,
    )

    bad_spec = StrategySpec(
        id="test_bad_lookback",
        display_name="test",
        method_citation_id="test",
        method_citation="test",
        entrypoint="usa_etf_features.strategy_registry:vol_target_book2",
        default_params={
            "lookback": 21,  # WRONG — gate-first requires 63
            "skew_estimator": "realized_amaya",
            "left_tail_rule": "cvar_5",
            "g_min": 0.5,
        },
    )
    with pytest.raises(ValueError, match="lookback must be 63"):
        vol_target_book2(px, bad_spec, universe_csv=uni_path, universe_config={}, asof=None)


def test_vol_target_book2_enforcer_rejects_non_gatefirst_g_min(tmp_path):
    """vol_target_book2 adapter must raise ValueError if g_min != 0.5."""
    import numpy as np
    import pandas as pd

    from usa_etf_features.strategy_registry import StrategySpec, vol_target_book2

    uni_path = tmp_path / "universe.csv"
    pd.DataFrame({
        "Ticker": ["VOO", "QQQM", "IJR", "BIL"],
        "Source_Section": ["APPENDIX 2"] * 4,
        "Category": ["US Large / Broad Blend"] * 3 + ["US Treasuries / Govt / Cash-like"],
    }).to_csv(uni_path, index=False)

    rng = np.random.default_rng(88)
    idx = pd.bdate_range("2019-01-02", periods=600)
    px = pd.DataFrame(
        {t: 100 * np.cumprod(1 + rng.normal(0.0003, 0.01, 600)) for t in ["VOO", "QQQM", "IJR", "BIL"]},
        index=idx,
    )

    bad_spec = StrategySpec(
        id="test_bad_gmin",
        display_name="test",
        method_citation_id="test",
        method_citation="test",
        entrypoint="usa_etf_features.strategy_registry:vol_target_book2",
        default_params={
            "lookback": 63,
            "skew_estimator": "realized_amaya",
            "left_tail_rule": "cvar_5",
            "g_min": 0.25,  # WRONG — gate-first requires 0.5
        },
    )
    with pytest.raises(ValueError, match="g_min must be 0.5"):
        vol_target_book2(px, bad_spec, universe_csv=uni_path, universe_config={}, asof=None)
