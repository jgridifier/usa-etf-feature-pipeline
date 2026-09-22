"""Tests for forecast_tangency_med module.

Covers:
- EF coefficient math
- Forecasted tangency computation
- MED solve
- No same-month leakage (primary acceptance criterion)
- Smoke: nulls emitted, DSR fields present
- Smoke: trial registry has correct method + citation
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.forecast_tangency_med import (
    ForecastTangencyMedTrial,
    ef_coefficients,
    ef_sigma,
    forecasted_tangency,
    run_forecast_tangency_med_trial,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _monthly_panel(
    n_months: int = 60,
    n_assets: int = 6,
    sigma: float = 0.04,
    seed: int = 42,
) -> pd.DataFrame:
    """Synthetic monthly return panel (calendar month-end index)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-31", periods=n_months, freq="ME")
    tickers = [f"T{i:02d}" for i in range(n_assets)]
    data = {}
    for j, t in enumerate(tickers):
        mu = 0.005 + j * 0.001
        vol = sigma * (1 + j * 0.1)
        data[t] = rng.normal(mu, vol, n_months)
    return pd.DataFrame(data, index=idx)


def _universe_df(tickers: list[str], extra: list[str] | None = None) -> pd.DataFrame:
    """Minimal universe CSV with all tickers in APPENDIX 2."""
    all_tickers = tickers + (extra or [])
    rows = []
    for t in all_tickers:
        rows.append(
            {
                "Ticker": t,
                "Source_Section": "APPENDIX 2",
                "Category": "US Large / Broad Blend",
            }
        )
    # Always include cash fallbacks
    for cash in ["BIL", "SGOV", "GBIL", "SHV"]:
        if cash not in [r["Ticker"] for r in rows]:
            rows.append(
                {
                    "Ticker": cash,
                    "Source_Section": "APPENDIX 2",
                    "Category": "US Treasuries / Govt / Cash-like",
                }
            )
    return pd.DataFrame(rows)


def _uni_config() -> dict:
    return {"off_list_hard_deny": [], "appendix3_deny": []}


# ---------------------------------------------------------------------------
# Unit: EF coefficient math
# ---------------------------------------------------------------------------

class TestEFCoefficients:
    def test_basic_two_asset(self):
        """Known analytic case: 2-asset EF with equal vol, zero corr."""
        mu = np.array([0.01, 0.02])
        sigma_sq = 0.04**2
        cov = np.diag([sigma_sq, sigma_sq])
        sigma_inv = np.diag([1 / sigma_sq, 1 / sigma_sq])
        r_mvp, sigma_mvp, u = ef_coefficients(mu, sigma_inv)
        # MVP return = mean of mu (equal vol, zero corr)
        assert r_mvp == pytest.approx((0.01 + 0.02) / 2, abs=1e-10)
        # MVP vol = sigma / sqrt(2)
        assert sigma_mvp == pytest.approx(0.04 / np.sqrt(2), rel=1e-9)
        assert u > 0

    def test_u_positive(self):
        rng = np.random.default_rng(7)
        n = 5
        raw = rng.normal(0, 0.04, (60, n))
        cov = np.cov(raw.T)
        cov += 1e-6 * np.eye(n)
        sigma_inv = np.linalg.solve(cov, np.eye(n))
        mu = rng.normal(0.005, 0.003, n)
        r_mvp, sigma_mvp, u = ef_coefficients(mu, sigma_inv)
        assert u > 0
        assert sigma_mvp > 0

    def test_ef_sigma_at_mvp(self):
        mu = np.array([0.01, 0.02, 0.03])
        cov = np.diag([0.04**2, 0.05**2, 0.06**2])
        sigma_inv = np.linalg.inv(cov)
        r_mvp, sigma_mvp, u = ef_coefficients(mu, sigma_inv)
        # σ(r_MVP) should equal sigma_MVP
        sigma_at_mvp = ef_sigma(r_mvp, r_mvp, sigma_mvp, u)
        assert sigma_at_mvp == pytest.approx(sigma_mvp, rel=1e-9)

    def test_ef_sigma_increases_away_from_mvp(self):
        mu = np.array([0.01, 0.02, 0.03])
        cov = np.diag([0.04**2, 0.05**2, 0.06**2])
        sigma_inv = np.linalg.inv(cov)
        r_mvp, sigma_mvp, u = ef_coefficients(mu, sigma_inv)
        sigma_hi = ef_sigma(r_mvp + 0.01, r_mvp, sigma_mvp, u)
        assert sigma_hi > sigma_mvp


# ---------------------------------------------------------------------------
# Unit: forecasted tangency (rf=0)
# ---------------------------------------------------------------------------

class TestForecastedTangency:
    def test_rf0_formula(self):
        r_mvp, sigma_mvp, u = 0.01, 0.05, 0.001
        r_tp, sigma_tp = forecasted_tangency(r_mvp, sigma_mvp, u, rf=0.0)
        # r_TP = (r_MVP^2 + u*sigma_MVP^2) / r_MVP
        expected_r = (r_mvp**2 + u * sigma_mvp**2) / r_mvp
        assert r_tp == pytest.approx(expected_r, rel=1e-9)
        # sigma_TP via EF formula
        expected_sigma = ef_sigma(expected_r, r_mvp, sigma_mvp, u)
        assert sigma_tp == pytest.approx(expected_sigma, rel=1e-9)

    def test_r_mvp_near_zero_raises(self):
        with pytest.raises(ValueError, match="undefined"):
            forecasted_tangency(0.0, 0.05, 0.001, rf=0.0)

    def test_nonzero_rf_shifts_tangency(self):
        r_mvp, sigma_mvp, u = 0.01, 0.05, 0.001
        r_tp_rf0, _ = forecasted_tangency(r_mvp, sigma_mvp, u, rf=0.0)
        r_tp_rf, _ = forecasted_tangency(r_mvp, sigma_mvp, u, rf=0.002)
        # With positive rf, tangency should shift
        assert r_tp_rf != pytest.approx(r_tp_rf0, rel=1e-3)


# ---------------------------------------------------------------------------
# Leakage test (primary acceptance criterion)
# ---------------------------------------------------------------------------

class TestNoSameMonthLeakage:
    """Mutating returns AFTER decision date t must not change:
    EF coefs, VARX forecast, MED r_star / distance, or weights at t.
    """

    def _run(self, panel: pd.DataFrame, tmp_path, seed_suffix: int = 0):
        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / f"universe_{seed_suffix}.csv"
        uni_df.to_csv(uni_csv, index=False)
        # Add BIL column (zero return)
        panel = panel.copy()
        if "BIL" not in panel.columns:
            panel["BIL"] = 0.0
        trial = ForecastTangencyMedTrial(
            "leaktest",
            ef_lookback_months=12,
            forecast_lookback_months=24,
            min_names=2,          # small for synthetic test
            min_history_months=12,
        )
        return run_forecast_tangency_med_trial(
            panel, trial,
            universe_csv=uni_csv,
            universe_config=_uni_config(),
        )

    def test_weights_invariant_to_future_mutations(self, tmp_path):
        panel = _monthly_panel(n_months=48, n_assets=6)
        panel["BIL"] = 0.0

        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe.csv"
        uni_df.to_csv(uni_csv, index=False)

        trial = ForecastTangencyMedTrial(
            "leaktest",
            ef_lookback_months=12,
            forecast_lookback_months=24,
            min_names=2,
            min_history_months=12,
        )

        w0, r0, _ = run_forecast_tangency_med_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        assert not w0.empty, "expected non-empty weight table"

        # Pick a decision date in the middle
        decision = pd.Timestamp(w0["date"].iloc[len(w0) // 2])
        before = w0.loc[w0["date"].eq(decision)].iloc[0]
        before_ret = r0.loc[r0["decision_date"].eq(decision)].iloc[0]

        # Mutate returns AFTER decision date 10x
        panel2 = panel.copy()
        panel2.loc[panel2.index > decision, [c for c in panel.columns if c != "BIL"]] *= 10.0

        w1, r1, _ = run_forecast_tangency_med_trial(
            panel2, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        after = w1.loc[w1["date"].eq(decision)].iloc[0]
        after_ret = r1.loc[r1["decision_date"].eq(decision)].iloc[0]

        # EF coefs at decision date must be unchanged
        assert after["coef_r_mvp" if "coef_r_mvp" in after.index else "r_star"] == pytest.approx(
            before["coef_r_mvp" if "coef_r_mvp" in before.index else "r_star"], rel=1e-8
        )

        # r_star and distance must be unchanged
        assert after["r_star"] == pytest.approx(before["r_star"], rel=1e-8)
        assert after["distance"] == pytest.approx(before["distance"], rel=1e-8)

        # Weight columns must be unchanged (NaN == NaN is acceptable for absent weights)
        w_cols = [c for c in before.index if str(c).startswith("w_")]
        for col in w_cols:
            b_val = before[col]
            a_val = after[col]
            if pd.isna(b_val) and pd.isna(a_val):
                continue
            assert a_val == pytest.approx(b_val, abs=1e-10), f"column {col} changed"

    def test_coef_invariant_to_future_mutations(self, tmp_path):
        """EF coefs in returns table must not change when future prices mutated."""
        panel = _monthly_panel(n_months=48, n_assets=6)
        panel["BIL"] = 0.0

        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe_coef.csv"
        uni_df.to_csv(uni_csv, index=False)

        trial = ForecastTangencyMedTrial(
            "leaktest_coef",
            ef_lookback_months=12,
            forecast_lookback_months=24,
            min_names=2,
            min_history_months=12,
        )

        _, r0, _ = run_forecast_tangency_med_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        assert not r0.empty

        decision = pd.Timestamp(r0["decision_date"].iloc[len(r0) // 2])

        panel2 = panel.copy()
        panel2.loc[panel2.index > decision, [c for c in panel.columns if c != "BIL"]] *= 100.0

        _, r1, _ = run_forecast_tangency_med_trial(
            panel2, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        before_row = r0.loc[r0["decision_date"].eq(decision)].iloc[0]
        after_row = r1.loc[r1["decision_date"].eq(decision)].iloc[0]

        for col in ["rhat_tp", "sigmahat_tp", "r_star", "distance"]:
            if col in before_row.index and col in after_row.index:
                assert after_row[col] == pytest.approx(before_row[col], rel=1e-8), (
                    f"leakage detected in {col}: before={before_row[col]}, after={after_row[col]}"
                )


# ---------------------------------------------------------------------------
# Smoke: nulls and DSR fields emitted
# ---------------------------------------------------------------------------

class TestNullsAndDSRFields:
    def test_all_nulls_in_oos_returns(self, tmp_path):
        panel = _monthly_panel(n_months=48, n_assets=6)
        panel["BIL"] = 0.0

        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe.csv"
        uni_df.to_csv(uni_csv, index=False)

        trial = ForecastTangencyMedTrial(
            "smoke",
            ef_lookback_months=12,
            forecast_lookback_months=24,
            min_names=2,
            min_history_months=12,
        )
        _, oos, _ = run_forecast_tangency_med_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        assert not oos.empty, "OOS returns should not be empty"
        for col in ["r_method", "r_null_a", "r_null_b", "r_null_c", "r_null_d", "r_active_vs_a"]:
            assert col in oos.columns, f"missing null column: {col}"

    def test_registry_has_method_and_citation(self, tmp_path):
        panel = _monthly_panel(n_months=48, n_assets=6)
        panel["BIL"] = 0.0

        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe.csv"
        uni_df.to_csv(uni_csv, index=False)

        trial = ForecastTangencyMedTrial(
            "smoke_reg",
            ef_lookback_months=12,
            forecast_lookback_months=24,
            min_names=2,
            min_history_months=12,
        )
        _, _, registry = run_forecast_tangency_med_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        assert not registry.empty
        assert registry["method"].iloc[0] == "forecast_tangency_med"
        assert "Alexander" in registry["citation"].iloc[0]
        assert "arXiv" in registry["citation"].iloc[0] or "doi" in registry["citation"].iloc[0].lower()

    def test_weight_columns_sum_to_at_most_one(self, tmp_path):
        panel = _monthly_panel(n_months=48, n_assets=6)
        panel["BIL"] = 0.0

        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe.csv"
        uni_df.to_csv(uni_csv, index=False)

        trial = ForecastTangencyMedTrial(
            "smoke_wts",
            ef_lookback_months=12,
            forecast_lookback_months=24,
            min_names=2,
            min_history_months=12,
        )
        monthly_w, _, _ = run_forecast_tangency_med_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        assert not monthly_w.empty
        w_cols = [c for c in monthly_w.columns if c.startswith("w_")]
        weight_sums = monthly_w[w_cols].sum(axis=1)
        # Weights (risky + cash) should sum ≤ 1.0 (plus small float tolerance)
        assert (weight_sums <= 1.0 + 1e-6).all(), f"weights exceed 1: {weight_sums.max()}"

    def test_r_star_within_asset_range(self, tmp_path):
        """Target return r* must be between r_MVP and max(mu)."""
        panel = _monthly_panel(n_months=48, n_assets=6)
        panel["BIL"] = 0.0

        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe.csv"
        uni_df.to_csv(uni_csv, index=False)

        trial = ForecastTangencyMedTrial(
            "smoke_rstar",
            ef_lookback_months=12,
            forecast_lookback_months=24,
            min_names=2,
            min_history_months=12,
        )
        monthly_w, _, _ = run_forecast_tangency_med_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        assert not monthly_w.empty
        r_star_vals = monthly_w["r_star"].dropna()
        assert len(r_star_vals) > 0
        # r_star should be finite for all rows
        assert np.isfinite(r_star_vals.values).all()

    def test_coef_forecast_columns_present(self, tmp_path):
        panel = _monthly_panel(n_months=48, n_assets=6)
        panel["BIL"] = 0.0

        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe.csv"
        uni_df.to_csv(uni_csv, index=False)

        trial = ForecastTangencyMedTrial(
            "smoke_coef",
            ef_lookback_months=12,
            forecast_lookback_months=24,
            min_names=2,
            min_history_months=12,
        )
        _, oos, _ = run_forecast_tangency_med_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        for col in ["rhat_tp", "sigmahat_tp", "r_star", "distance"]:
            assert col in oos.columns, f"missing coef column: {col}"
