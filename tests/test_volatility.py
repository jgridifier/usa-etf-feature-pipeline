import numpy as np
import pandas as pd

from usa_etf_features.features import vol_63, vol_252, volatility


def test_vol_annualization_sqrt252_ddof1():
    rng = np.random.default_rng(42)
    r = pd.Series(rng.normal(0, 0.01, size=300))
    window = 252
    expected = np.sqrt(252) * r.iloc[-window:].std(ddof=1)
    assert np.isclose(vol_252(r), expected)
    expected63 = np.sqrt(252) * r.iloc[-63:].std(ddof=1)
    assert np.isclose(vol_63(r), expected63)


def test_volatility_ddof1_explicit():
    r = pd.Series([0.01, -0.02, 0.015, -0.005, 0.0] * 20)
    got = volatility(r, window=63, ddof=1, ann=252)
    exp = np.sqrt(252) * r.iloc[-63:].std(ddof=1)
    assert np.isclose(got, exp)
