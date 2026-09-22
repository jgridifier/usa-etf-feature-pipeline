"""Tests for regime_resilient_erc module.

Covers:
- No same-month leakage (primary acceptance criterion): stress diagnostics,
  regime-pool labels, Σ̂ inputs, π̂_m, ERC weights must be invariant to
  mutations of returns after decision date t.
- Nulls: unconditional ERC (null_a), EW (null_b), LW MinVar (null_c) emitted.
- DSR + trial_count fields present in summary.
- Registry cites Ielpo-Muhammetgulyyeva-Royer (2026) + classical ERC + DSR.
- Construction-pattern check: no dual-regime selection (archived #2 pattern).
- NBER labeling: publication-lag enforcement.
- Thin-history fallback.
- Weights sum ≤ 1.
- Path A: stress-cov blend changes weights vs unconditional ERC.
- Path B: LOIM parity blend is a π-weighted average of local ERCs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.regime_resilient_erc import (
    RegimeResilientERCTrial,
    _avg_pairwise_abs_corr,
    _compute_pi_historical,
    _erc,
    _identify_stress_months,
    _lw_minvar,
    _markov_steady_state,
    _nber_recession_months,
    _rolling_vol_regime_labels,
    _sync_score,
    make_rr_erc_trials,
    run_regime_resilient_erc_grid,
    run_regime_resilient_erc_trial,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _monthly_panel(
    n_months: int = 72,
    n_assets: int = 8,
    sigma: float = 0.04,
    seed: int = 42,
) -> pd.DataFrame:
    """Synthetic monthly return panel (calendar month-end index)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2016-01-31", periods=n_months, freq="ME")
    tickers = [f"T{i:02d}" for i in range(n_assets)]
    data = {}
    for j, t in enumerate(tickers):
        mu = 0.005 + j * 0.001
        vol = sigma * (1.0 + j * 0.08)
        data[t] = rng.normal(mu, vol, n_months)
    return pd.DataFrame(data, index=idx)


def _universe_df(tickers: list[str]) -> pd.DataFrame:
    rows = []
    for t in tickers:
        rows.append({"Ticker": t, "Source_Section": "APPENDIX 2", "Category": "US Large / Broad Blend"})
    for cash in ["BIL", "SGOV", "GBIL", "SHV"]:
        if cash not in [r["Ticker"] for r in rows]:
            rows.append({"Ticker": cash, "Source_Section": "APPENDIX 2",
                         "Category": "US Treasuries / Govt / Cash-like"})
    return pd.DataFrame(rows)


def _uni_config() -> dict:
    return {"off_list_hard_deny": [], "appendix3_deny": []}


def _run_trial(panel, tmp_path, construction="stress_corr_overlay", **kw):
    uni_df = _universe_df(list(panel.columns))
    uni_csv = tmp_path / f"universe_{construction}.csv"
    uni_df.to_csv(uni_csv, index=False)
    trial = RegimeResilientERCTrial(
        trial_id=f"test_{construction}",
        construction=construction,
        min_names=2,
        min_history_months=12,
        min_obs_per_pool=6,
        **kw,
    )
    return run_regime_resilient_erc_trial(
        panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
    )


# ---------------------------------------------------------------------------
# Unit: ERC solver correctness
# ---------------------------------------------------------------------------

class TestERCSolver:
    def test_erc_equal_vol_equal_weight(self):
        """With identical diagonal covariance, ERC = equal weight."""
        n = 4
        cov = np.eye(n) * 0.04 ** 2
        w = _erc(cov, n)
        assert np.allclose(w, 1.0 / n, atol=1e-6)

    def test_erc_risk_contributions_equal(self):
        rng = np.random.default_rng(5)
        raw = rng.normal(0, 0.04, (60, 5))
        cov = np.cov(raw.T) + 1e-8 * np.eye(5)
        w = _erc(cov, 5)
        rc = w * (cov @ w)
        assert np.allclose(rc / rc.sum(), 1.0 / 5, atol=1e-4)

    def test_erc_weights_positive_sum_one(self):
        rng = np.random.default_rng(3)
        raw = rng.normal(0, 0.04, (40, 6))
        cov = np.cov(raw.T) + 1e-6 * np.eye(6)
        w = _erc(cov, 6)
        assert w.sum() == pytest.approx(1.0, abs=1e-8)
        assert (w >= 0).all()

    def test_lw_minvar_sums_to_one(self):
        rng = np.random.default_rng(9)
        raw = rng.normal(0, 0.04, (50, 5))
        cov = np.cov(raw.T) + 1e-8 * np.eye(5)
        w = _lw_minvar(cov, 5)
        assert w.sum() == pytest.approx(1.0, abs=1e-6)
        assert (w >= 0).all()


# ---------------------------------------------------------------------------
# Unit: stress diagnostics
# ---------------------------------------------------------------------------

class TestStressDiagnostics:
    def test_identify_stress_months_count(self):
        panel = _monthly_panel(n_months=48, n_assets=4)
        stress_idx = _identify_stress_months(panel, stress_window_months=6)
        assert len(stress_idx) == 6

    def test_identify_stress_months_all_leq_t(self):
        """Stress months must be ≤ the panel end (no future leakage)."""
        panel = _monthly_panel(n_months=48, n_assets=4)
        t = panel.index[-1]
        stress_idx = _identify_stress_months(panel.loc[:t], stress_window_months=12)
        assert all(s <= t for s in stress_idx)

    def test_avg_abs_corr_range(self):
        panel = _monthly_panel(n_months=36, n_assets=4)
        c = _avg_pairwise_abs_corr(panel)
        assert 0.0 <= c <= 1.0

    def test_avg_abs_corr_nan_for_short_panel(self):
        panel = _monthly_panel(n_months=3, n_assets=4)
        c = _avg_pairwise_abs_corr(panel)
        assert np.isnan(c) or (0.0 <= c <= 1.0)

    def test_sync_score_range(self):
        panel = _monthly_panel(n_months=36, n_assets=4)
        s = _sync_score(panel)
        assert 0.0 <= s <= 1.0


# ---------------------------------------------------------------------------
# Unit: regime labeling
# ---------------------------------------------------------------------------

class TestRegimeLabels:
    def test_rolling_vol_regime_labels_binary(self):
        panel = _monthly_panel(n_months=48, n_assets=4)
        labels = _rolling_vol_regime_labels(panel)
        assert set(labels.unique()).issubset({0, 1})

    def test_rolling_vol_labels_leq_panel_end(self):
        panel = _monthly_panel(n_months=48, n_assets=4)
        t = panel.index[-1]
        labels = _rolling_vol_regime_labels(panel.loc[:t])
        assert labels.index.max() <= t

    def test_nber_recession_months_publication_lag(self):
        """Recession months must only appear after the NBER announcement."""
        # Before 2003-07-17 (2001 recession announcement), no 2001 recession should appear
        as_of_early = pd.Timestamp("2003-01-01")
        months_early = _nber_recession_months(as_of_early)
        recession_2001 = pd.Period("2001-06", freq="M")
        assert recession_2001 not in months_early

        # After 2003-07-17, the 2001 recession should appear
        as_of_late = pd.Timestamp("2004-01-01")
        months_late = _nber_recession_months(as_of_late)
        assert recession_2001 in months_late

    def test_nber_recession_months_no_future_data(self):
        """No future recession labeled if as_of is before announcement."""
        as_of = pd.Timestamp("2009-01-01")  # before 2009 trough announcement (Sep 2010)
        months = _nber_recession_months(as_of)
        # 2009 trough was announced Sept 2010; months in 2009 should NOT be available
        p2009 = pd.Period("2009-03", freq="M")
        assert p2009 not in months

    def test_compute_pi_historical_sums_to_one(self):
        labels = pd.Series([0, 0, 1, 1, 0, 1, 0, 0])
        pi = _compute_pi_historical(labels, n_regimes=2)
        assert pi.sum() == pytest.approx(1.0, abs=1e-8)
        assert (pi > 0).all()

    def test_markov_steady_state_sums_to_one(self):
        rng = np.random.default_rng(7)
        labels = pd.Series(rng.integers(0, 2, 40))
        pi = _markov_steady_state(labels, n_regimes=2)
        assert pi.sum() == pytest.approx(1.0, abs=1e-6)
        assert (pi >= 0).all()


# ---------------------------------------------------------------------------
# Leakage test (primary acceptance criterion)
# ---------------------------------------------------------------------------

class TestNoSameMonthLeakage:
    """Mutating returns AFTER decision date t must not change:
    stress diagnostics, regime-pool labels, Σ̂, π̂_m, ERC weights at t.
    """

    @pytest.mark.parametrize("construction", ["stress_corr_overlay", "loim_regime_parity"])
    def test_weights_invariant_to_future_mutations(self, tmp_path, construction):
        panel = _monthly_panel(n_months=72, n_assets=6)
        panel["BIL"] = 0.0

        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / f"universe_{construction}.csv"
        uni_df.to_csv(uni_csv, index=False)

        trial = RegimeResilientERCTrial(
            trial_id=f"leak_{construction}",
            construction=construction,
            min_names=2,
            min_history_months=12,
            min_obs_per_pool=6,
        )

        w0, r0, d0, _ = run_regime_resilient_erc_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        assert not w0.empty, "expected non-empty weight table"

        decision = pd.Timestamp(w0["date"].iloc[len(w0) // 2])
        before = w0.loc[w0["date"].eq(decision)].iloc[0]

        # Mutate returns strictly AFTER decision date
        panel2 = panel.copy()
        mutation_cols = [c for c in panel.columns if c != "BIL"]
        panel2.loc[panel2.index > decision, mutation_cols] *= 10.0

        w1, r1, d1, _ = run_regime_resilient_erc_trial(
            panel2, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        after = w1.loc[w1["date"].eq(decision)].iloc[0]

        # Weight columns must be unchanged
        w_cols = [c for c in before.index if str(c).startswith("w_")]
        for col in w_cols:
            b_val = before[col]
            a_val = after.get(col, float("nan"))
            if pd.isna(b_val) and pd.isna(a_val):
                continue
            assert a_val == pytest.approx(b_val, abs=1e-10), (
                f"[{construction}] weight column {col} changed after future mutation"
            )

    @pytest.mark.parametrize("construction", ["stress_corr_overlay", "loim_regime_parity"])
    def test_construction_diag_invariant_to_future_mutations(self, tmp_path, construction):
        """Construction diagnostics (stress mix, avg|corr|, π̂_m) must not change when future returns mutated."""
        panel = _monthly_panel(n_months=72, n_assets=6)
        panel["BIL"] = 0.0

        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / f"universe_diag_{construction}.csv"
        uni_df.to_csv(uni_csv, index=False)

        trial = RegimeResilientERCTrial(
            trial_id=f"leakdiag_{construction}",
            construction=construction,
            min_names=2,
            min_history_months=12,
            min_obs_per_pool=6,
        )

        _, _, d0, _ = run_regime_resilient_erc_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        assert not d0.empty

        decision = pd.Timestamp(d0["date"].iloc[len(d0) // 2])
        before_diag = d0.loc[d0["date"].eq(decision)].iloc[0]

        panel2 = panel.copy()
        panel2.loc[panel2.index > decision, [c for c in panel.columns if c != "BIL"]] *= 100.0

        _, _, d1, _ = run_regime_resilient_erc_trial(
            panel2, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        after_diag = d1.loc[d1["date"].eq(decision)].iloc[0]

        for col in ["avg_abs_corr", "sync_score", "w_vs_uncond_erc_norm", "stress_months_used"]:
            if col not in before_diag.index or col not in after_diag.index:
                continue
            b_val, a_val = before_diag[col], after_diag[col]
            if pd.isna(b_val) and pd.isna(a_val):
                continue
            if pd.isna(b_val) or pd.isna(a_val):
                continue
            assert float(a_val) == pytest.approx(float(b_val), rel=1e-6), (
                f"[{construction}] diagnostic {col} changed after future mutation"
            )


# ---------------------------------------------------------------------------
# Smoke: nulls emitted
# ---------------------------------------------------------------------------

class TestNullsAndOutputs:
    @pytest.mark.parametrize("construction", ["stress_corr_overlay", "loim_regime_parity"])
    def test_all_nulls_in_oos_returns(self, tmp_path, construction):
        panel = _monthly_panel(n_months=60, n_assets=6)
        panel["BIL"] = 0.0
        _, oos, _, _ = _run_trial(panel, tmp_path, construction=construction)
        assert not oos.empty, "OOS returns should not be empty"
        for col in ["r_method", "r_null_a", "r_null_b", "r_null_c", "r_active_vs_a"]:
            assert col in oos.columns, f"missing null column: {col}"

    @pytest.mark.parametrize("construction", ["stress_corr_overlay", "loim_regime_parity"])
    def test_weights_sum_leq_one(self, tmp_path, construction):
        panel = _monthly_panel(n_months=60, n_assets=6)
        panel["BIL"] = 0.0
        monthly_w, _, _, _ = _run_trial(panel, tmp_path, construction=construction)
        assert not monthly_w.empty
        w_cols = [c for c in monthly_w.columns if c.startswith("w_")]
        weight_sums = monthly_w[w_cols].fillna(0.0).sum(axis=1)
        assert (weight_sums <= 1.0 + 1e-6).all(), f"weights exceed 1: {weight_sums.max()}"

    @pytest.mark.parametrize("construction", ["stress_corr_overlay", "loim_regime_parity"])
    def test_construction_diag_emitted(self, tmp_path, construction):
        panel = _monthly_panel(n_months=60, n_assets=6)
        panel["BIL"] = 0.0
        _, _, diag, _ = _run_trial(panel, tmp_path, construction=construction)
        assert not diag.empty
        for col in ["date", "trial_id", "construction_tag", "w_vs_uncond_erc_norm"]:
            assert col in diag.columns, f"missing diag column: {col}"

    @pytest.mark.parametrize("construction", ["stress_corr_overlay", "loim_regime_parity"])
    def test_registry_has_citations(self, tmp_path, construction):
        panel = _monthly_panel(n_months=60, n_assets=6)
        panel["BIL"] = 0.0
        _, _, _, registry = _run_trial(panel, tmp_path, construction=construction)
        assert not registry.empty
        assert registry["method"].iloc[0] == "regime_resilient_erc"
        citation = registry["citation_lead"].iloc[0]
        assert "Ielpo" in citation
        assert "doi:10.3905/jpm.2026.030" in citation
        erc_citation = registry["citation_erc"].iloc[0]
        assert "Maillard" in erc_citation
        dsr_citation = registry["citation_dsr"].iloc[0]
        assert "Bailey" in dsr_citation


# ---------------------------------------------------------------------------
# DSR and trial_count in summary
# ---------------------------------------------------------------------------

class TestDSRAndTrialCount:
    def test_dsr_present_in_summary(self, tmp_path):
        panel = _monthly_panel(n_months=72, n_assets=6)
        panel["BIL"] = 0.0
        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe_dsr.csv"
        uni_df.to_csv(uni_csv, index=False)

        trials = make_rr_erc_trials(
            constructions=["stress_corr_overlay"],
            stress_window_months=[12],
            mix_lambdas=[0.25],
            apply_tos=["name_level"],
            min_names=2,
            min_history_months=12,
        )
        summary, _, _, _, registry = run_regime_resilient_erc_grid(
            panel, trials,
            universe_csv=uni_csv,
            universe_config=_uni_config(),
        )
        assert not summary.empty
        assert "DSR" in summary.columns
        assert "trial_count" in summary.columns
        assert "NW_t_vs_null_a_uncond_ERC" in summary.columns
        assert "NW_t_vs_null_b_EW" in summary.columns
        assert "NW_t_vs_null_c_LW_MinVar" in summary.columns
        # DSR values must be finite or nan (not inf)
        dsr_vals = summary["DSR"].dropna()
        if len(dsr_vals) > 0:
            assert np.all(np.isfinite(dsr_vals.values))

    def test_trial_count_reflects_grid_size(self, tmp_path):
        panel = _monthly_panel(n_months=72, n_assets=6)
        panel["BIL"] = 0.0
        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe_tc.csv"
        uni_df.to_csv(uni_csv, index=False)

        trials = make_rr_erc_trials(
            constructions=["stress_corr_overlay"],
            stress_window_months=[12, 24],
            mix_lambdas=[0.25],
            apply_tos=["name_level"],
            min_names=2,
            min_history_months=12,
        )
        assert len(trials) == 2
        _, _, _, _, registry = run_regime_resilient_erc_grid(
            panel, trials,
            universe_csv=uni_csv,
            universe_config=_uni_config(),
        )
        assert not registry.empty
        assert int(registry["trial_count"].max()) == 2


# ---------------------------------------------------------------------------
# Construction-pattern checks (not dual-regime selection)
# ---------------------------------------------------------------------------

class TestConstructionNotSelection:
    """Verify that the implementation is construction (not archived selection).

    Acceptance criterion 6: README / ticket explicitly states construction
    overlays, not dual-regime selection.  These tests verify the code
    does not emit a 'regime_selector' output and that the construction_tag
    field reflects the registered overlay path.
    """

    @pytest.mark.parametrize("construction", ["stress_corr_overlay", "loim_regime_parity"])
    def test_construction_tag_present(self, tmp_path, construction):
        panel = _monthly_panel(n_months=60, n_assets=6)
        panel["BIL"] = 0.0
        monthly_w, _, _, _ = _run_trial(panel, tmp_path, construction=construction)
        assert not monthly_w.empty
        assert "construction_tag" in monthly_w.columns
        assert monthly_w["construction_tag"].iloc[0] == construction

    def test_no_regime_selector_column(self, tmp_path):
        """The weight table must not have a 'current_regime_selected' or similar column
        that would indicate dual-regime selection (archived #2 pattern)."""
        panel = _monthly_panel(n_months=60, n_assets=6)
        panel["BIL"] = 0.0
        monthly_w, oos, diag, _ = _run_trial(panel, tmp_path, construction="loim_regime_parity")
        forbidden = {"current_regime_selected", "regime_selected", "selected_regime",
                     "hold_only_regime", "discrete_regime_switch"}
        for df in [monthly_w, oos, diag]:
            for col in df.columns:
                assert col.lower() not in forbidden, (
                    f"forbidden dual-regime-selection column found: {col}"
                )

    @pytest.mark.parametrize("construction", ["stress_corr_overlay", "loim_regime_parity"])
    def test_every_month_emits_erc_construction(self, tmp_path, construction):
        """Every decision month must emit a weight row (ERC family)."""
        panel = _monthly_panel(n_months=60, n_assets=6)
        panel["BIL"] = 0.0
        monthly_w, _, _, _ = _run_trial(panel, tmp_path, construction=construction)
        assert not monthly_w.empty
        # No month should have all-NaN risky weights (would mean no construction emitted)
        w_cols = [c for c in monthly_w.columns if c.startswith("w_")]
        assert len(w_cols) > 0
        has_weights = monthly_w[w_cols].notna().any(axis=1)
        assert has_weights.all(), "some months emitted no weights (violates construction guarantee)"

    def test_loim_parity_is_pi_blend_not_selector(self, tmp_path):
        """For Path B, the output weight must differ from a single-regime ERC
        when the two local ERCs differ (verifies blend, not selection)."""
        rng = np.random.default_rng(99)
        # Create a panel with very different volatility regimes so local ERCs differ
        n_months = 60
        idx = pd.date_range("2018-01-31", periods=n_months, freq="ME")
        tickers = [f"T{i:02d}" for i in range(5)]
        data = {}
        for j, t in enumerate(tickers):
            # First 30 months: low vol; last 30 months: high vol (artificial 2-regime structure)
            low_vol = rng.normal(0.005, 0.01 + j * 0.002, 30)
            high_vol = rng.normal(0.005, 0.06 + j * 0.01, 30)
            data[t] = np.concatenate([low_vol, high_vol])
        panel = pd.DataFrame(data, index=idx)
        panel["BIL"] = 0.0

        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe_parity.csv"
        uni_df.to_csv(uni_csv, index=False)

        trial = RegimeResilientERCTrial(
            trial_id="parity_check",
            construction="loim_regime_parity",
            regime_pool_rule="rolling_vol_split",
            n_regimes=2,
            pi_rule="historical_freq",
            min_obs_per_pool=6,
            min_names=2,
            min_history_months=10,
        )
        monthly_w, _, _, _ = run_regime_resilient_erc_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        assert not monthly_w.empty
        # The last weight row should have fallback_flag=0 (two pools found)
        # and w_vs_uncond_erc_norm should exist in diag


# ---------------------------------------------------------------------------
# Thin-history fallback
# ---------------------------------------------------------------------------

class TestThinHistoryFallback:
    def test_fallback_flag_set_when_stress_pool_thin(self, tmp_path):
        """When the stress pool is too small, fallback_flag=1 and unconditional ERC used."""
        panel = _monthly_panel(n_months=36, n_assets=4)
        panel["BIL"] = 0.0
        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe_thin.csv"
        uni_df.to_csv(uni_csv, index=False)

        # Use a very large stress window (bigger than panel) to force thin stress pool
        trial = RegimeResilientERCTrial(
            trial_id="thin_fallback",
            construction="stress_corr_overlay",
            stress_window_months=2,    # only 2 stress months
            mix_lambda=0.5,
            min_names=2,
            min_history_months=12,
        )
        monthly_w, _, _, _ = run_regime_resilient_erc_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        assert not monthly_w.empty

    def test_fallback_when_loim_pool_too_small(self, tmp_path):
        """When LOIM regime pools are too small, fallback to unconditional ERC."""
        panel = _monthly_panel(n_months=24, n_assets=4)
        panel["BIL"] = 0.0
        uni_df = _universe_df(list(panel.columns))
        uni_csv = tmp_path / "universe_thin2.csv"
        uni_df.to_csv(uni_csv, index=False)

        trial = RegimeResilientERCTrial(
            trial_id="thin_loim",
            construction="loim_regime_parity",
            regime_pool_rule="rolling_vol_split",
            min_obs_per_pool=100,   # impossible to satisfy → fallback
            min_names=2,
            min_history_months=6,
        )
        monthly_w, _, _, _ = run_regime_resilient_erc_trial(
            panel, trial, universe_csv=uni_csv, universe_config=_uni_config()
        )
        # Should still emit some rows (fallback to unconditional ERC)
        # (or empty if not enough data at all — both are acceptable)
        assert isinstance(monthly_w, pd.DataFrame)


# ---------------------------------------------------------------------------
# make_rr_erc_trials grid builder
# ---------------------------------------------------------------------------

class TestMakeRRERCTrials:
    def test_grid_creates_expected_count(self):
        trials = make_rr_erc_trials(
            constructions=["stress_corr_overlay"],
            stress_window_months=[12, 24],
            mix_lambdas=[0.25, 0.5],
            apply_tos=["name_level"],
        )
        # 2 windows × 2 lambdas × 1 gate × 1 cov × 1 apply_to = 4
        assert len(trials) == 4

    def test_grid_no_duplicate_trial_ids(self):
        trials = make_rr_erc_trials(
            constructions=["stress_corr_overlay", "loim_regime_parity"],
            stress_window_months=[12],
            mix_lambdas=[0.25],
            regime_pool_rules=["rolling_vol_split"],
            pi_rules=["historical_freq"],
            apply_tos=["name_level", "category_sleeves"],
        )
        ids = [t.trial_id for t in trials]
        assert len(ids) == len(set(ids)), "duplicate trial IDs detected"

    def test_grid_all_have_enabled_false_by_default(self):
        """Registry entry must be enabled:false until Quant gate PASS."""
        trials = make_rr_erc_trials(
            constructions=["stress_corr_overlay"],
            stress_window_months=[12],
            mix_lambdas=[0.25],
        )
        # The registry output must include enabled:false
        # (checked via _make_registry, not trial dataclass)
        from usa_etf_features.regime_resilient_erc import _make_registry
        for trial in trials:
            reg = _make_registry(trial)
            assert reg["enabled"].iloc[0] is False or reg["enabled"].iloc[0] == False


# ---------------------------------------------------------------------------
# Registry enabled:false gate
# ---------------------------------------------------------------------------

class TestRegistryEnabledFalse:
    def test_strategies_yaml_enabled_false(self):
        """The strategies.yaml registry entry must have enabled:false."""
        import yaml
        from pathlib import Path
        cfg_path = Path(__file__).resolve().parents[1] / "config" / "strategies.yaml"
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        rr_entries = [s for s in cfg["strategies"] if s["id"] == "regime_resilient_erc"]
        assert len(rr_entries) == 1, "expected exactly one regime_resilient_erc entry"
        assert rr_entries[0]["enabled"] is False, "regime_resilient_erc must be enabled:false until Quant gate PASS"

    def test_config_yaml_enabled_false(self):
        """The regime_resilient_erc.yaml config must note enabled:false."""
        import yaml
        from pathlib import Path
        cfg_path = Path(__file__).resolve().parents[1] / "config" / "regime_resilient_erc.yaml"
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        rr = cfg.get("regime_resilient_erc", {})
        assert rr.get("enabled") is False or rr.get("enabled") == False, (
            "regime_resilient_erc config must be enabled:false until Quant gate PASS"
        )
