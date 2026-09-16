import numpy as np
import pandas as pd

from usa_etf_features.features import quality_ir_er


def test_quality_er_missing_zero_penalty_and_flag():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    rng = np.random.default_rng(1)
    bench = pd.Series(rng.normal(0.0004, 0.01, size=300), index=idx)
    asset = bench + 0.0002  # constant excess
    q, missing = quality_ir_er(asset, bench, er=None, lambda_er=1.0, lookback=252)
    assert missing is True
    # IR only
    e = (asset - bench).iloc[-252:]
    ir = np.sqrt(252) * e.mean() / e.std(ddof=1)
    assert np.isclose(q, ir)


def test_quality_er_penalty_applied():
    idx = pd.date_range("2020-01-01", periods=300, freq="B")
    rng = np.random.default_rng(2)
    bench = pd.Series(rng.normal(0.0004, 0.01, size=300), index=idx)
    asset = bench + 0.0001
    q0, _ = quality_ir_er(asset, bench, er=None, lambda_er=1.0)
    q1, missing = quality_ir_er(asset, bench, er=0.005, lambda_er=1.0)
    assert missing is False
    assert np.isclose(q1, q0 - 0.005)
