"""Mom12_1 unit tests on synthetic month-end series."""

import numpy as np
import pandas as pd

from usa_etf_features.features import mom12_1


def _daily_from_month_ends(me: pd.Series) -> pd.Series:
    """Expand month-end prices to daily (constant within month) for mom12_1 helper."""
    # mom12_1 resamples to month-end via last(); feeding business days with month-end values works
    idx = pd.date_range(me.index.min() - pd.offsets.MonthBegin(1), me.index.max(), freq="B")
    s = pd.Series(np.nan, index=idx, dtype=float)
    for t, v in me.items():
        # set value on/after month end date
        s.loc[t] = v
    return s.ffill().dropna()


def test_mom12_1_closed_form_product():
    # Construct 13+ month-end prices with known monthly returns
    # R = [nan, 0.01, 0.02, ..., ] then Mom = prod_{k=2..12}(1+R_lag_k)-1
    dates = pd.date_range("2020-01-31", periods=14, freq="ME")
    # Build prices so monthly returns are exactly r_i for month i
    rets = np.array([0.0] + [0.01 * i for i in range(1, 14)])  # length 14, first unused
    # Actually: me[0]=100; me[t]=me[t-1]*(1+r[t])
    px = [100.0]
    monthly_r = [0.01] * 13  # 13 returns → 14 prices
    for r in monthly_r:
        px.append(px[-1] * (1 + r))
    me = pd.Series(px, index=dates[: len(px)])
    daily = _daily_from_month_ends(me)

    # lag 1 = most recent monthly return = last = 0.01 (skipped)
    # lags 2..12 = eleven returns of 0.01 → (1.01)**11 - 1
    expected = (1.01**11) - 1
    got = mom12_1(daily)
    assert np.isclose(got, expected, rtol=1e-9), (got, expected)


def test_mom12_1_telescopes_to_price_ratio():
    dates = pd.date_range("2019-01-31", periods=15, freq="ME")
    rng = np.random.default_rng(0)
    rets = rng.normal(0.01, 0.02, size=14)
    px = [100.0]
    for r in rets:
        px.append(px[-1] * (1 + r))
    me = pd.Series(px, index=dates[: len(px)])
    daily = _daily_from_month_ends(me)
    # Classic: P_{t-1}/P_{t-12} - 1 using month-end levels
    # t = last month-end; P_{t-1}=me.iloc[-2], P_{t-12}=me.iloc[-13]
    expected = me.iloc[-2] / me.iloc[-13] - 1
    got = mom12_1(daily)
    assert np.isclose(got, expected, rtol=1e-9)


def test_mom12_1_insufficient_history_nan():
    dates = pd.date_range("2024-01-31", periods=5, freq="ME")
    me = pd.Series(np.linspace(100, 110, 5), index=dates)
    daily = _daily_from_month_ends(me)
    assert np.isnan(mom12_1(daily))
