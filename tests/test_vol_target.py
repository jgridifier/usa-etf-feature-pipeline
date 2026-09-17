"""Volatility-managed Option A tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.universe import UniverseGateError
from usa_etf_features.vol_target import (
    OPTION_A_WEIGHTS,
    VolTargetTrial,
    annualized_vol,
    half_turnover,
    realized_ann_vol_at_month_ends,
    run_vol_target_trial,
    scale_factor,
    sharpe_rf0,
    target_weights,
    turnover_cost_return,
)


def _prices(n_days: int = 900, sigma: float = 0.01, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-02", periods=n_days)
    data = {}
    for i, t in enumerate(["VOO", "QQQM", "IJR", "QUAL", "BIL"]):
        vol = 0.0002 if t == "BIL" else sigma * (1 + i * 0.05)
        mu = 0.00005 if t == "BIL" else 0.0003
        data[t] = 100 * np.cumprod(1 + rng.normal(mu, vol, n_days))
    return pd.DataFrame(data, index=idx)


def _universe(tickers: list[str] | None = None) -> pd.DataFrame:
    tickers = tickers or ["VOO", "QQQM", "IJR", "QUAL", "BIL", "SGOV", "GBIL", "SHV"]
    return pd.DataFrame(
        {
            "Ticker": tickers,
            "Source_Section": ["APPENDIX 2"] * len(tickers),
            "Category": ["Core"] * len(tickers),
        }
    )


def test_vol_estimator_no_future_leakage():
    px = _prices(n_days=180)
    core = px[list(OPTION_A_WEIGHTS)].pct_change().mul(pd.Series(OPTION_A_WEIGHTS), axis=1).sum(axis=1)
    me = pd.DatetimeIndex([pd.Timestamp("2019-04-30"), pd.Timestamp("2019-05-31"), pd.Timestamp("2019-06-28")])
    before = realized_ann_vol_at_month_ends(core, me, 63).loc[pd.Timestamp("2019-05-31")]

    mutated = px.copy()
    mutated.loc[mutated.index > pd.Timestamp("2019-05-31"), ["VOO", "QQQM", "IJR"]] *= 10.0
    core_mut = mutated[list(OPTION_A_WEIGHTS)].pct_change().mul(pd.Series(OPTION_A_WEIGHTS), axis=1).sum(axis=1)
    after = realized_ann_vol_at_month_ends(core_mut, me, 63).loc[pd.Timestamp("2019-05-31")]
    assert after == pytest.approx(before)


def test_scale_down_high_vol_weights_sum_and_cash():
    f = scale_factor(0.80, 0.10, f_min=0.25, f_max=1.0)
    w = target_weights(OPTION_A_WEIGHTS, "BIL", f)
    assert f == pytest.approx(0.25)
    assert w.sum() == pytest.approx(1.0)
    assert w["BIL"] == pytest.approx(0.75)


def test_calm_markets_bind_at_fmax_one_with_no_cash():
    f = scale_factor(0.03, 0.12, f_min=0.25, f_max=1.0)
    w = target_weights(OPTION_A_WEIGHTS, "BIL", f)
    assert f == pytest.approx(1.0)
    assert w["BIL"] == pytest.approx(0.0)
    assert w["VOO"] == pytest.approx(0.70)
    assert w["QQQM"] == pytest.approx(0.20)
    assert w["IJR"] == pytest.approx(0.10)


def test_universe_rejects_smh_and_appendix3_cash(tmp_path):
    uni = _universe(["VOO", "QQQM", "IJR", "SMH", "BIL"])
    uni_path = tmp_path / "universe.csv"
    uni.to_csv(uni_path, index=False)
    with pytest.raises(UniverseGateError):
        run_vol_target_trial(
            _prices().rename(columns={"BIL": "SMH"}),
            VolTargetTrial("bad_cash", cash_ticker="SMH"),
            universe_csv=uni_path,
            universe_config={"off_list_hard_deny": ["SMH"], "appendix3_deny": []},
        )

    uni2 = _universe(["VOO", "QQQM", "IJR", "BIL"])
    uni2.loc[uni2["Ticker"].eq("BIL"), "Source_Section"] = "APPENDIX 3"
    uni2_path = tmp_path / "universe2.csv"
    uni2.to_csv(uni2_path, index=False)
    with pytest.raises(UniverseGateError):
        run_vol_target_trial(
            _prices(),
            VolTargetTrial("bad_appendix3_cash", cash_ticker="BIL"),
            universe_csv=uni2_path,
            universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
        )


def test_turnover_cost_known_case():
    prev = pd.Series({"VOO": 0.70, "QQQM": 0.20, "IJR": 0.10, "BIL": 0.0})
    curr = pd.Series({"VOO": 0.35, "QQQM": 0.10, "IJR": 0.05, "BIL": 0.50})
    turnover = half_turnover(prev, curr)
    assert turnover == pytest.approx(0.50)
    assert turnover_cost_return(turnover, 5) == pytest.approx(0.00025)


def test_qqqm_first_valid_binds_oos_start(tmp_path):
    px = _prices(n_days=520)
    px.loc[px.index < pd.Timestamp("2020-04-01"), "QQQM"] = np.nan
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    weights, returns, registry = run_vol_target_trial(
        px,
        VolTargetTrial("qqqm_bound", lookback=63, sigma_star=0.15),
        universe_csv=uni_path,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    assert not returns.empty
    assert pd.Timestamp(returns["decision_date"].min()) >= pd.Timestamp("2020-04-01")
    assert weights["qqqm_first_valid"].iloc[0] == "2020-04-01"
    assert registry["cash_ticker"].iloc[0] == "BIL"


def test_metric_parity_annvol_sharpe_rf0():
    r = pd.Series([0.01, -0.02, 0.03, 0.00, 0.02, -0.01])
    expected_vol = r.std(ddof=1) * np.sqrt(12)
    expected_ann = (1 + r).prod() ** (12 / len(r)) - 1
    assert annualized_vol(r) == pytest.approx(expected_vol)
    assert sharpe_rf0(r) == pytest.approx(expected_ann / expected_vol)
