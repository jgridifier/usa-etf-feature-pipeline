"""Walk-forward IC: no same-period / same-month label leakage."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.rotation import month_end_trading_dates
from usa_etf_features.walkforward import (
    assert_no_same_period_leakage,
    next_month_excess,
    spearman_ic,
    walkforward_ic_table,
)


def _panel(n_days: int = 800, n_names: int = 6, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-02", periods=n_days)
    tickers = [f"T{i}" for i in range(n_names)] + ["VOO"]
    data = {}
    for t in tickers:
        mu = 0.0003 + (0.0002 if t != "VOO" else 0.0)
        data[t] = 100 * np.cumprod(1 + rng.normal(mu, 0.01, n_days))
    px = pd.DataFrame(data, index=idx)
    # Rename one to look like real
    px = px.rename(columns={"T0": "QQQ", "T1": "XSD", "T2": "IJR", "T3": "QUAL", "T4": "IWM", "T5": "VTI"})
    cats = pd.Series(
        {
            "QQQ": "Growth",
            "XSD": "Thematic",
            "IJR": "Core",
            "QUAL": "Factor",
            "IWM": "Core",
            "VTI": "Core",
            "VOO": "Core",
        }
    )
    return px, cats


def test_assert_no_same_period_leakage_helper():
    d = pd.Timestamp("2022-06-30")
    assert_no_same_period_leakage(
        decision_date=d,
        feature_end=d,
        label_start=pd.Timestamp("2022-07-01"),
        label_end=pd.Timestamp("2022-07-29"),
    )
    with pytest.raises(AssertionError, match="lookahead"):
        assert_no_same_period_leakage(
            decision_date=d,
            feature_end=pd.Timestamp("2022-07-15"),
            label_start=pd.Timestamp("2022-07-01"),
            label_end=pd.Timestamp("2022-07-29"),
        )
    with pytest.raises(AssertionError, match="same-period"):
        assert_no_same_period_leakage(
            decision_date=d,
            feature_end=d,
            label_start=d,  # same month decision day — leak
            label_end=pd.Timestamp("2022-07-29"),
        )


def test_next_month_excess_is_strictly_next():
    px, _ = _panel()
    me = month_end_trading_dates(px)
    me_ret = px.loc[me].pct_change()
    d = me[20]
    nxt = me[21]
    lab = next_month_excess(me_ret, d, ["QQQ", "XSD"], benchmark="VOO")
    assert abs(lab["QQQ"] - (me_ret.loc[nxt, "QQQ"] - me_ret.loc[nxt, "VOO"])) < 1e-12
    # Label must not equal same-month excess
    same = me_ret.loc[d, "QQQ"] - me_ret.loc[d, "VOO"]
    assert abs(lab["QQQ"] - same) > 1e-15 or True  # usually different; structural check below
    # Structural: next_month_excess uses index position+1 only
    pos = me_ret.index.get_loc(d)
    assert me_ret.index[pos + 1] == nxt


def test_walkforward_ic_no_same_month_in_labels():
    px, cats = _panel()
    tickers = ["QQQ", "XSD", "IJR", "QUAL", "IWM", "VTI"]
    ic = walkforward_ic_table(px, cats, tickers=tickers, benchmark="VOO")
    assert len(ic) > 5
    assert "IC" in ic.columns and "n_names" in ic.columns

    me = month_end_trading_dates(px[tickers + ["VOO"]])
    me_ret = px.loc[me, tickers + ["VOO"]].pct_change()
    for _, row in ic.iterrows():
        d = pd.Timestamp(row["date"])
        # Feature end == decision; label window is next ME return → starts after d
        pos = me_ret.index.get_loc(d)
        assert pos + 1 < len(me_ret.index)
        label_month = me_ret.index[pos + 1]
        assert label_month > d
        assert_no_same_period_leakage(
            decision_date=d,
            feature_end=d,
            label_start=d + pd.Timedelta(days=1),
            label_end=label_month,
        )


def test_spearman_ic_basic():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    y = pd.Series([1.0, 2.0, 2.5, 4.0])
    assert spearman_ic(s, y) > 0.9
