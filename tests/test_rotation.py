"""Rotation signal tests: ON/OFF, vol-gate, hysteresis, SMH hard-fail."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.portfolio import build_rotated_portfolio, proportional_core_trim
from usa_etf_features.rotation import (
    apply_hysteresis,
    assert_rotate_tickers_eligible,
    compute_rotation_signals,
    expanding_z,
    mom12_1_series,
    point_in_time_mom_on,
    signal_on_asof,
)
from usa_etf_features.universe import UniverseGateError


def _synth_trend_panel(
    n_months: int = 36,
    start: str = "2018-01-02",
    *,
    voo_monthly: float = 0.01,
    xsd_monthly: float = 0.005,
    xsd_boost_from: int | None = None,
    xsd_boost: float = 0.06,
    seed: int = 0,
) -> pd.DataFrame:
    """Business-day panel with approximately constant monthly returns (controllable Mom)."""
    rng = np.random.default_rng(seed)
    me = pd.date_range(pd.Timestamp(start) + pd.offsets.MonthEnd(0), periods=n_months, freq="ME")
    start_d = me[0] - pd.offsets.MonthBegin(1)
    idx = pd.bdate_range(start_d, me[-1])

    voo_m = np.full(n_months, voo_monthly)
    xsd_m = np.full(n_months, xsd_monthly)
    if xsd_boost_from is not None:
        xsd_m[xsd_boost_from:] = xsd_boost

    voo = np.empty(len(idx))
    xsd = np.empty(len(idx))
    v_lvl, x_lvl = 100.0, 100.0
    pos = 0
    for i, d in enumerate(me):
        month_idx = idx[(idx.to_period("M") == d.to_period("M"))]
        n = len(month_idx)
        # daily geometric steps with tiny noise; scale to hit monthly target at ME
        noise_v = 1.0 + rng.normal(0, 0.0005, n)
        noise_x = 1.0 + rng.normal(0, 0.0005, n)
        path_v = v_lvl * np.cumprod(noise_v)
        path_x = x_lvl * np.cumprod(noise_x)
        path_v = path_v / path_v[-1] * (v_lvl * (1.0 + voo_m[i]))
        path_x = path_x / path_x[-1] * (x_lvl * (1.0 + xsd_m[i]))
        voo[pos : pos + n] = path_v
        xsd[pos : pos + n] = path_x
        v_lvl, x_lvl = float(path_v[-1]), float(path_x[-1])
        pos += n

    df = pd.DataFrame(
        {
            "VOO": voo,
            "XSD": xsd,
            "QQQM": voo * 1.01,
            "IJR": voo * 0.99,
        },
        index=idx,
    )
    return df


def test_mom_cross_turns_on_without_lookahead():
    """XSD Mom12_1 crosses above VOO → ON on decision date; PIT uses only ≤ decision."""
    px = _synth_trend_panel(
        n_months=40,
        voo_monthly=0.01,
        xsd_monthly=0.0,
        xsd_boost_from=20,
        xsd_boost=0.05,
        seed=1,
    )
    me = px.groupby(px.index.to_period("M")).apply(lambda x: x.index.max())
    me = pd.DatetimeIndex(me.values).sort_values()
    me_px = px.loc[me, ["XSD", "VOO"]]
    me_ret = me_px.pct_change()
    mom_x = mom12_1_series(me_ret["XSD"])
    mom_v = mom12_1_series(me_ret["VOO"])
    excess = mom_x - mom_v
    valid = excess.dropna()
    assert len(valid) > 5
    decision = valid.index[-1]
    on_pit = point_in_time_mom_on(px["XSD"], px["VOO"], decision)
    assert on_pit == bool(mom_x.loc[decision] > mom_v.loc[decision])
    on = signal_on_asof(px, "XSD", asof=decision, use_vol_gate=False, hysteresis_months=0)
    assert on == (mom_x.loc[decision] > mom_v.loc[decision])


def test_on_off_flip_synthetic():
    """Series with XSD lagging then leading → OFF then ON."""
    px_off = _synth_trend_panel(n_months=30, xsd_monthly=-0.01, voo_monthly=0.015, seed=2)
    assert signal_on_asof(px_off, "XSD", use_vol_gate=False, hysteresis_months=0) is False

    px_on = _synth_trend_panel(
        n_months=36,
        xsd_monthly=0.0,
        voo_monthly=0.005,
        xsd_boost_from=12,
        xsd_boost=0.06,
        seed=3,
    )
    assert signal_on_asof(px_on, "XSD", use_vol_gate=False, hysteresis_months=0) is True


def test_vol_gate_forces_off_in_top_decile():
    """vol_63 forced into top expanding decile → OFF even if Mom positive (ScoreSimple)."""
    from usa_etf_features.rotation import expanding_vol_ok, score_simple_raw_on

    idx = pd.date_range("2020-01-31", periods=36, freq="ME")
    mom_i = pd.Series(np.linspace(0.05, 0.25, 36), index=idx)
    mom_b = pd.Series(np.linspace(0.02, 0.10, 36), index=idx)
    assert (mom_i - mom_b).iloc[-1] > 0

    vol = pd.Series(0.15, index=idx)
    vol.iloc[-1] = 0.80
    vok = expanding_vol_ok(vol, quantile=0.90, min_periods=6)
    assert bool(vok.iloc[-1]) is False

    raw = score_simple_raw_on(mom_i, mom_b, vok, use_vol_gate=True)
    assert bool(raw.iloc[-1]) is False
    raw_novol = score_simple_raw_on(mom_i, mom_b, vok, use_vol_gate=False)
    assert bool(raw_novol.iloc[-1]) is True


def test_hysteresis_one_month_fail_stays_on():
    """One-month Mom failure does not turn OFF if hysteresis_months=2."""
    raw = pd.Series(
        [True, True, True, False, True, True],
        index=pd.date_range("2020-01-31", periods=6, freq="ME"),
    )
    hyst = apply_hysteresis(raw, hysteresis_months=2)
    assert bool(hyst.iloc[3]) is True
    raw2 = pd.Series(
        [True, True, False, False, False],
        index=pd.date_range("2020-01-31", periods=5, freq="ME"),
    )
    hyst2 = apply_hysteresis(raw2, hysteresis_months=2)
    assert bool(hyst2.iloc[2]) is True
    assert bool(hyst2.iloc[3]) is False


def test_smh_under_rotate_hard_fails():
    for t in ["SMH", "SOXX", "SOXL", "PSI"]:
        with pytest.raises(UniverseGateError):
            assert_rotate_tickers_eligible([t])


def test_proportional_core_trim():
    core = {"VOO": 0.70, "QQQM": 0.20, "IJR": 0.10}
    w = proportional_core_trim(core, {"XSD": 0.10})
    assert abs(w["VOO"] - 0.63) < 1e-12
    assert abs(w["QQQM"] - 0.18) < 1e-12
    assert abs(w["IJR"] - 0.09) < 1e-12
    assert abs(w["XSD"] - 0.10) < 1e-12
    assert abs(sum(w.values()) - 1.0) < 1e-12


def test_build_rotated_respects_caps():
    px = _synth_trend_panel(
        n_months=36,
        xsd_boost_from=10,
        xsd_boost=0.06,
        voo_monthly=0.005,
        seed=7,
    )
    df = build_rotated_portfolio(px, use_vol_gate=False, hysteresis_months=0)
    them = df.loc[df["role"] == "thematic", "weight"].sum()
    assert them <= 0.25 + 1e-9
    xsd_row = df.loc[df["ticker"] == "XSD"]
    if not xsd_row.empty and bool(xsd_row["rotate_on"].iloc[0]):
        assert float(xsd_row["weight"].iloc[0]) <= 0.15 + 1e-9
    assert abs(df["weight"].sum() - 1.0) < 1e-8


def test_expanding_z_no_peek():
    s = pd.Series(np.arange(20, dtype=float))
    z = expanding_z(s, min_periods=5)
    assert pd.isna(z.iloc[0])
    mu = s.iloc[:10].mean()
    sd = s.iloc[:10].std(ddof=1)
    expected = (s.iloc[10] - mu) / sd
    assert abs(z.iloc[10] - expected) < 1e-12
