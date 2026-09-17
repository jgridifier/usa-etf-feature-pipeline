"""Causal regime fitting and policy integration on small monthly panels."""
import numpy as np
import pandas as pd
import pytest

from usa_etf_features import regime_dual as rd
from usa_etf_features.walkforward import assert_no_same_period_leakage


@pytest.fixture
def sleeves():
    rng = np.random.default_rng(7)
    n = 48
    shock = rng.normal(size=n) * np.r_[np.full(18, .005), np.full(18, .10), np.full(12, .005)]
    return pd.DataFrame({
        "US Large / Broad Blend": .007 + shock,
        "US Mid Blend": .005 + shock * 1.2 + rng.normal(0, .002, n),
        "US Treasuries / Govt / Cash-like": .002 - shock * .12 + rng.normal(0, .002, n),
        "Core / Aggregate Bonds": .002 - shock * .05 + rng.normal(0, .001, n),
    }, index=pd.date_range("2000-01-31", periods=n, freq="ME"))


def run(sleeves, **kwargs):
    return rd.run_regime_dual(sleeves, min_history_months=6, vol_window=3, corr_window=4, cov_window=12, **kwargs)


@pytest.mark.parametrize("mode", ["expanding", "rolling"])
def test_regimes_nulls_and_trial_count(sleeves, mode):
    result = run(sleeves, fit_mode=mode, rolling_window=18)
    assert set(result["states"].regime) == {"calm", "stress"}
    sums = result["monthly_weights"].groupby(["trial_id", "date"]).weight.sum()
    np.testing.assert_allclose(sums, 1)
    summary = result["summary"].set_index("trial_id")
    assert {"unconditional_erc", "unconditional_ew", "always_calm"} <= set(summary.index)
    assert summary.trial_count.eq(4).all()
    assert summary.DSR.between(0, 1).all()
    assert len(result["trial_registry"]) == 4
    assert summary.stress_months.gt(0).all()
    diag = result["diagnostics"].drop_duplicates(["feature_set", "state"])
    np.testing.assert_allclose(diag.groupby("feature_set").occupancy.sum(), 1)
    for _, sub in result["diagnostics"].groupby("feature_set"):
        assert sub.transition_count.sum() == len(result["states"]) // 2 - 1
    if mode == "rolling":
        state = result["states"]
        assert ((state.fit_end.dt.year - state.fit_start.dt.year) * 12
                + state.fit_end.dt.month - state.fit_start.dt.month).le(17).all()


def test_no_future_fit_features_or_weights(sleeves, monkeypatch):
    original = rd.fit_regime
    calls = []
    def spy(history, decision_date):
        assert history.index.max() <= decision_date
        calls.append(decision_date)
        return original(history, decision_date)
    monkeypatch.setattr(rd, "fit_regime", spy)
    baseline = run(sleeves)
    cutoff = sleeves.index[30]
    changed = sleeves.copy()
    changed.loc[changed.index > cutoff] = np.random.default_rng(4).normal(0, .5, changed.loc[changed.index > cutoff].shape)
    mutated = run(changed)
    truncated = run(sleeves.loc[:sleeves.index[31]])
    assert calls
    for table in ("states", "monthly_weights"):
        before = baseline[table].loc[lambda x: x.decision_date.le(cutoff)].reset_index(drop=True)
        for result in (mutated, truncated):
            after = result[table].loc[lambda x: x.decision_date.le(cutoff)].reset_index(drop=True)
            pd.testing.assert_frame_equal(before, after)
    for row in baseline["oos_returns"].itertuples():
        assert_no_same_period_leakage(row.decision_date, row.feature_end,
                                     row.decision_date + pd.Timedelta(days=1), row.date)


def test_membership_uses_prior_counts_and_skips_empty_months():
    panel = pd.DataFrame({"A": [1., 2., 3., 4.], "B": [np.nan, 10., 20., np.nan]},
                         index=pd.date_range("2020-01-31", periods=4, freq="ME"))
    cats = pd.DataFrame({"Ticker": ["A", "B"], "Category": ["C", "C"]})
    result = rd.build_category_sleeves(panel, cats, min_name_months=2)
    assert result.C.iloc[:2].isna().all()
    assert result.C.iloc[2] == 3
    assert result.C.iloc[3] == 4


def test_missing_held_return_is_not_zero_filled(sleeves):
    sleeves.iloc[35, 0] = np.nan
    result = run(sleeves)
    row = result["oos_returns"].loc[lambda x: x.trial_id.eq("unconditional_ew") & x.date.eq(sleeves.index[35])].iloc[0]
    assert pd.isna(row["return"])
    assert row.missing_held_returns == 1


def test_registry_and_cli_with_external_synthetic_inputs(sleeves, tmp_path):
    from usa_etf_features.cli import main
    from usa_etf_features.strategy_registry import run_strategy_registry
    import yaml

    names = ["AAA", "BBB", "CCC", "DDD"]
    panel = sleeves.set_axis(names, axis=1)
    panel.to_csv(tmp_path / "panel.csv")
    pd.DataFrame({"Ticker": names, "Category": sleeves.columns,
                  "Source_Section": "APPENDIX 2"}).to_csv(tmp_path / "categorized.csv", index=False)
    pd.DataFrame({"ticker": names, "thin_lt5y": [False, True, False, False]}).to_csv(tmp_path / "coverage.csv", index=False)
    params = dict(panel_returns_path=str(tmp_path / "panel.csv"), categorized_path=str(tmp_path / "categorized.csv"),
                  coverage_path=str(tmp_path / "coverage.csv"), min_history_months=12, min_name_months=2,
                  vol_window=3, corr_window=4, cov_window=12)
    registry = {"strategies": [dict(id="regime_aware_dual_regime", entrypoint="usa_etf_features.strategy_registry:regime_aware_dual_regime", default_params=params)]}
    (tmp_path / "registry.yaml").write_text(yaml.safe_dump(registry))
    prices = pd.DataFrame({"VOO": [100., 101.], "QQQM": [100., 101.], "IJR": [100., 101.]},
                          index=pd.to_datetime(["2003-10-31", "2003-11-28"]))
    tables = run_strategy_registry(prices=prices, universe_csv=tmp_path / "categorized.csv",
                                   registry_path=tmp_path / "registry.yaml", out_dir=tmp_path / "registry_out",
                                   asof=sleeves.index[-1])
    w = tables["suggested_weights"]
    assert w.asset_type.eq("category_sleeve").all()
    assert w.weight.sum() == pytest.approx(1)
    assert (w.feature_end <= w.decision_date).all()
    assert (w.eval_date > w.decision_date).all()
    assert "DSR" in tables["strategy_comparison"]
    assert tables["strategy_diagnostics"].thin_history_tickers.eq("BBB").all()
    with pytest.raises(SystemExit) as exit_info:
        main(["walkforward-regime-dual", "--panel-returns-path", params["panel_returns_path"],
              "--categorized-path", params["categorized_path"], "--coverage-path", params["coverage_path"],
              "--out-dir", str(tmp_path / "cli"), "--min-history-months", "12"])
    assert exit_info.value.code == 0
    assert len(list((tmp_path / "cli").glob("*.csv"))) == 6


def test_unregistered_variants_fail(sleeves):
    with pytest.raises(ValueError, match="K=2"):
        run(sleeves, k=3)


def test_loader_keeps_holiday_month_end_and_excludes_partial_month(tmp_path, monkeypatch):
    dates = pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-28", "2024-04-30", "2024-05-15"])
    pd.DataFrame({"A": [.01] * 5}, index=dates).to_csv(tmp_path / "panel.csv")
    pd.DataFrame({"Ticker": ["A"], "Category": ["Core / Aggregate Bonds"]}).to_csv(tmp_path / "cats.csv", index=False)
    pd.DataFrame({"ticker": ["A"], "thin_lt5y": [True]}).to_csv(tmp_path / "coverage.csv", index=False)
    captured = []
    def capture(sleeves, **kwargs):
        captured.append(sleeves)
        return {"diagnostics": pd.DataFrame([{}])}
    monkeypatch.setattr(rd, "run_regime_dual", capture)
    params = dict(panel_returns_path=tmp_path / "panel.csv", categorized_path=tmp_path / "cats.csv",
                  coverage_path=tmp_path / "coverage.csv", min_name_months=1)
    rd.load_and_run(params)
    assert captured[-1].index.max() == pd.Timestamp("2024-04-30")
    assert pd.Timestamp("2024-03-31") in captured[-1].index
    rd.load_and_run(params, asof=pd.Timestamp("2024-03-31"))
    assert captured[-1].index.max() == pd.Timestamp("2024-03-31")


def test_comparison_aligns_calendar_and_trading_month_ends():
    from usa_etf_features.strategy_registry import comparison_frame

    trading = pd.to_datetime(["2020-01-31", "2020-02-28", "2020-03-31"])
    calendar = trading.to_period("M").to_timestamp("M")
    returns = pd.DataFrame({"date": list(trading) + list(calendar),
                            "strategy_id": ["static"] * 3 + ["regime"] * 3,
                            "return": [.01, -.02, .03] * 2})
    result = comparison_frame(returns, pd.Series([.01, -.02, .03], index=trading))
    assert result.n_months.eq(3).all()
    assert result.Sharpe_rf0.nunique() == 1
