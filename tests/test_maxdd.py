import numpy as np
import pandas as pd

from usa_etf_features.features import maxdd_252


def test_maxdd_peak_to_trough_path():
    # Peak at 100, trough at 70 → MaxDD = -0.30
    idx = pd.date_range("2020-01-01", periods=10, freq="B")
    px = pd.Series([80, 90, 100, 95, 85, 70, 75, 80, 90, 95], index=idx, dtype=float)
    assert np.isclose(maxdd_252(px, lookback=10), -0.30)


def test_maxdd_trailing_window():
    idx = pd.date_range("2020-01-01", periods=20, freq="B")
    # Early deep DD outside window should be ignored if lookback short
    vals = [100, 50] + [60] * 8 + [100, 100, 90, 90, 90, 90, 90, 90, 90, 90]
    px = pd.Series(vals, index=idx, dtype=float)
    # lookback=10 → last 10 pts: mostly flat near 90-100, maxdd = 90/100-1 = -0.10
    assert np.isclose(maxdd_252(px, lookback=10), -0.10)
