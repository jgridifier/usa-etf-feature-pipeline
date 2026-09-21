"""Conditional factor-correlation gate tests (Book-2 upgrade)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.vol_cond_factor_corr import (
    VolCondFactorCorrTrial,
    build_category_sleeve_returns,
    correlation_gate,
    mean_pairwise_abs_corr,
    rolling_mean_pairwise_abs_corr,
    run_vol_cond_factor_corr_trial,
)
from usa_etf_features.vol_target import OPTION_A_WEIGHTS, scale_factor, target_weights


def _prices(n_days: int = 900, sigma: float = 0.01, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-02", periods=n_days)
    data = {}
    for i, t in enumerate(["VOO", "QQQM", "IJR", "QUAL", "BIL", "IWM", "VEA", "GLD", "TLT"]):
        vol = 0.0002 if t == "BIL" else sigma * (1 + i * 0.04)
        mu = 0.00005 if t == "BIL" else 0.0003
        data[t] = 100 * np.cumprod(1 + rng.normal(mu, vol, n_days))
    return pd.DataFrame(data, index=idx)


def _universe() -> pd.DataFrame:
    rows = [
        ("VOO", "US Large / Broad Blend"),
        ("QQQM", "US Large / Broad Blend"),
        ("IJR", "US Small Blend"),
        ("IWM", "US Small Blend"),
        ("QUAL", "US Large / Broad Blend"),
        ("VEA", "International Developed Equity"),
        ("GLD", "Commodities / Metals"),
        ("TLT", "US Treasuries / Govt / Cash-like"),
        ("BIL", "US Treasuries / Govt / Cash-like"),
        ("SGOV", "US Treasuries / Govt / Cash-like"),
        ("GBIL", "US Treasuries / Govt / Cash-like"),
        ("SHV", "US Treasuries / Govt / Cash-like"),
    ]
    return pd.DataFrame(
        {
            "Ticker": [r[0] for r in rows],
            "Source_Section": ["APPENDIX 2"] * len(rows),
            "Category": [r[1] for r in rows],
        }
    )


def _monthly_from_prices(px: pd.DataFrame) -> pd.DataFrame:
    me = px.resample("ME").last()
    # align to business month-ends present in prices
    me = px.groupby(px.index.to_period("M")).last()
    me.index = me.index.to_timestamp("M")
    return me.pct_change().dropna(how="all")


def test_correlation_gate_binds_when_both_elevated():
    g, binding, corr_hi, z_hi = correlation_gate(0.8, 0.30, 0.4, 0.15, g_min=0.25, z_rule="mkt_vol")
    assert binding and corr_hi and z_hi
    assert g == pytest.approx(0.25)
    g2, binding2, *_ = correlation_gate(0.2, 0.30, 0.4, 0.15, g_min=0.25, z_rule="mkt_vol")
    assert not binding2
    assert g2 == pytest.approx(1.0)


def test_f_tilde_scales_cash():
    f = scale_factor(0.20, 0.10, f_min=0.25, f_max=1.0)
    assert f == pytest.approx(0.5)
    g = 0.5
    w = target_weights(OPTION_A_WEIGHTS, "BIL", f * g)
    assert w.sum() == pytest.approx(1.0)
    assert w["BIL"] == pytest.approx(0.75)


def test_mean_pairwise_abs_corr_known():
    idx = pd.date_range("2020-01-31", periods=12, freq="ME")
    rng = np.random.default_rng(1)
    a = rng.normal(0, 0.02, len(idx))
    df = pd.DataFrame({"A": a, "B": a, "C": -a}, index=idx)
    # |corr(A,B)|=1, |corr(A,C)|=1, |corr(B,C)|=1 → mean 1
    assert mean_pairwise_abs_corr(df) == pytest.approx(1.0, abs=1e-9)


def test_no_same_month_leakage_sigma_corr_weights(tmp_path):
    px = _prices(n_days=520)
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    monthly = _monthly_from_prices(px)
    trial = VolCondFactorCorrTrial(
        "leak",
        lookback=63,
        corr_lookback_months=6,
        g_min=0.5,
        sigma_star=0.15,
    )
    w0, r0, _ = run_vol_cond_factor_corr_trial(
        px,
        trial,
        universe_csv=uni_path,
        monthly=monthly,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    assert not w0.empty
    # pick a mid decision date
    decision = pd.Timestamp(w0["date"].iloc[len(w0) // 2])
    before = w0.loc[w0["date"].eq(decision)].iloc[0]

    mutated = px.copy()
    mutated.loc[mutated.index > decision, ["VOO", "QQQM", "IJR", "IWM", "VEA", "GLD"]] *= 5.0
    monthly_m = _monthly_from_prices(mutated)
    w1, _, _ = run_vol_cond_factor_corr_trial(
        mutated,
        trial,
        universe_csv=uni_path,
        monthly=monthly_m,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    after = w1.loc[w1["date"].eq(decision)].iloc[0]
    assert after["sigma_hat"] == pytest.approx(before["sigma_hat"])
    assert after["mean_abs_corr"] == pytest.approx(before["mean_abs_corr"], abs=1e-12)
    assert after["g"] == pytest.approx(before["g"])
    assert after["f"] == pytest.approx(before["f"])
    assert after["f_tilde"] == pytest.approx(before["f_tilde"])
    for col in [c for c in before.index if str(c).startswith("w_")]:
        assert after[col] == pytest.approx(before[col])


def test_rolling_corr_invariant_to_future_sleeve_returns():
    idx = pd.date_range("2018-01-31", periods=36, freq="ME")
    rng = np.random.default_rng(2)
    sleeve = pd.DataFrame(
        {
            "A": rng.normal(0, 0.02, len(idx)),
            "B": rng.normal(0, 0.02, len(idx)),
            "C": rng.normal(0, 0.02, len(idx)),
        },
        index=idx,
    )
    me = pd.DatetimeIndex([idx[20], idx[21], idx[22]])
    before = rolling_mean_pairwise_abs_corr(sleeve, me, 12).loc[idx[21]]
    sleeve2 = sleeve.copy()
    sleeve2.loc[sleeve2.index > idx[21]] *= 10.0
    after = rolling_mean_pairwise_abs_corr(sleeve2, me, 12).loc[idx[21]]
    assert after == pytest.approx(before)


def test_sleeve_builder_excludes_buffer_and_respects_min_names():
    idx = pd.date_range("2020-01-31", periods=24, freq="ME")
    rng = np.random.default_rng(3)
    tickers = ["VOO", "QQQM", "IJR", "IWM", "BUF"]
    monthly = pd.DataFrame({t: rng.normal(0, 0.02, len(idx)) for t in tickers}, index=idx)
    uni = pd.DataFrame(
        {
            "Ticker": tickers,
            "Category": [
                "US Large / Broad Blend",
                "US Large / Broad Blend",
                "US Small Blend",
                "US Small Blend",
                "Defined Outcome / Buffer / Structured",
            ],
            "Source_Section": ["APPENDIX 2"] * 5,
        }
    )
    sleeve, meta = build_category_sleeve_returns(monthly, uni, min_sleeve_names=2)
    assert "Defined Outcome / Buffer / Structured" not in sleeve.columns
    assert set(sleeve.columns) == {"US Large / Broad Blend", "US Small Blend"}
    assert meta["n_names"].min() >= 2


def test_trial_emits_nulls_and_dsr_fields(tmp_path):
    px = _prices(n_days=520)
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    monthly = _monthly_from_prices(px)
    trial = VolCondFactorCorrTrial("smoke", lookback=63, corr_lookback_months=6, g_min=0.5, sigma_star=0.15)
    w, r, reg = run_vol_cond_factor_corr_trial(
        px,
        trial,
        universe_csv=uni_path,
        monthly=monthly,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    assert not r.empty
    for col in ["r_method", "r_null_a", "r_null_b", "r_null_c", "r_active_vs_a"]:
        assert col in r.columns
    assert reg["method"].iloc[0] == "vol_cond_factor_corr"
    assert "DeMiguel" in reg["citation"].iloc[0]
    assert "f_tilde" in w.columns and "g" in w.columns
