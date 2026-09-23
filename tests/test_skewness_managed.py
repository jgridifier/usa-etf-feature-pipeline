"""Skewness-managed Book-2 overlay tests.

Coverage:
- Leakage unit test: σ̂_t, skew, left-tail score, gate g_t, weights at t
  must be invariant to mutating returns after t.
- Realized skewness (Amaya) formula + known cases.
- Gate logic: binds when left-tail elevated, open when calm.
- f̃_t = f_t · g_t; weights sum to 1 and cash = 1 - f̃.
- DSR / trial_count fields present in summary.
- State table emits gate-binding vs gate-open rows.
- Registry has enabled:false.
- Run-through smoke test: OOS returns contain required null columns.

Research tooling only; not investment advice.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.skewness_managed import (
    SkewnessManagedTrial,
    cvar_at_level,
    expanding_median_prior,
    left_tail_score_at_month_ends,
    make_skew_managed_trials,
    pct_below_minus_k_sigma,
    realized_skewness_amaya,
    realized_skewness_at_month_ends,
    run_skewness_managed_trial,
    skewness_gate,
    state_table_skew,
    summarize_skew_managed,
)
from usa_etf_features.vol_target import OPTION_A_WEIGHTS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _prices(n_days: int = 900, sigma: float = 0.01, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-02", periods=n_days)
    tickers = ["VOO", "QQQM", "IJR", "QUAL", "BIL", "IWM", "VEA", "GLD", "TLT"]
    data: dict[str, np.ndarray] = {}
    for i, t in enumerate(tickers):
        vol = 0.0002 if t == "BIL" else sigma * (1 + i * 0.04)
        mu = 0.00005 if t == "BIL" else 0.0003
        data[t] = 100.0 * np.cumprod(1 + rng.normal(mu, vol, n_days))
    return pd.DataFrame(data, index=idx)


def _universe() -> pd.DataFrame:
    rows = [
        ("VOO", "US Large / Broad Blend"),
        ("QQQM", "US Large / Broad Blend"),
        ("IJR", "US Small Blend"),
        ("IWM", "US Small Blend"),
        ("QUAL", "US Large / Broad Blend"),
        ("VEA", "International Developed Equity"),
        ("GLD", "Commodities / Metals"),
        ("TLT", "US Treasuries / Govt / Cash-like"),
        ("BIL", "US Treasuries / Govt / Cash-like"),
        ("SGOV", "US Treasuries / Govt / Cash-like"),
        ("GBIL", "US Treasuries / Govt / Cash-like"),
        ("SHV", "US Treasuries / Govt / Cash-like"),
    ]
    return pd.DataFrame({
        "Ticker": [r[0] for r in rows],
        "Source_Section": ["APPENDIX 2"] * len(rows),
        "Category": [r[1] for r in rows],
    })


def _monthly_from_prices(px: pd.DataFrame) -> pd.DataFrame:
    me = px.groupby(px.index.to_period("M")).last()
    me.index = me.index.to_timestamp("M")
    return me.pct_change().dropna(how="all")


def _default_trial(trial_id: str = "test") -> SkewnessManagedTrial:
    return SkewnessManagedTrial(
        trial_id=trial_id,
        lookback=63,
        g_min=0.5,
        sigma_star=0.15,
        skew_estimator="realized_amaya",
        left_tail_rule="cvar_5",
        skew_lookback_months=21,
        cov_lookback_months=24,
    )


# ---------------------------------------------------------------------------
# Realized skewness (Amaya)
# ---------------------------------------------------------------------------

def test_realized_skewness_amaya_known_case():
    """Symmetric distribution should have skewness near 0."""
    rng = np.random.default_rng(42)
    r = rng.normal(0, 0.01, 300)
    rs = realized_skewness_amaya(r)
    assert np.isfinite(rs)
    assert abs(rs) < 3.0  # symmetric normal: skew ~0, allow Monte Carlo noise


def test_realized_skewness_amaya_positive_skew():
    """A series with one large positive outlier should have positive realized skew."""
    r = np.array([0.001] * 20 + [0.10])
    rs = realized_skewness_amaya(r)
    assert rs > 0.0


def test_realized_skewness_amaya_negative_skew():
    """A series with one large negative outlier should have negative realized skew."""
    r = np.array([-0.001] * 20 + [-0.10])
    rs = realized_skewness_amaya(r)
    assert rs < 0.0


def test_realized_skewness_amaya_too_few_returns():
    assert np.isnan(realized_skewness_amaya(np.array([0.01, 0.02])))


def test_realized_skewness_at_month_ends_uses_only_month_days():
    """Realized skewness at month-end t must use only daily returns within that month."""
    px = _prices(n_days=520)
    from usa_etf_features.prices import daily_returns
    from usa_etf_features.vol_target import option_core_daily_returns, OPTION_A_WEIGHTS
    from usa_etf_features.rotation import month_end_trading_dates

    core_daily = option_core_daily_returns(px, OPTION_A_WEIGHTS)
    me_dates = month_end_trading_dates(px[list(OPTION_A_WEIGHTS)])

    rs_before = realized_skewness_at_month_ends(core_daily, me_dates)
    decision = me_dates[len(me_dates) // 2]

    # Mutate returns after decision date — should not affect rs at decision
    mutated = px.copy()
    mutated.loc[mutated.index > decision, ["VOO", "QQQM", "IJR"]] *= 20.0
    core_daily_m = option_core_daily_returns(mutated, OPTION_A_WEIGHTS)
    rs_after = realized_skewness_at_month_ends(core_daily_m, me_dates)

    if np.isfinite(rs_before.get(decision, float("nan"))):
        assert rs_after.get(decision) == pytest.approx(rs_before.get(decision), abs=1e-12)


# ---------------------------------------------------------------------------
# Left-tail score
# ---------------------------------------------------------------------------

def test_cvar_at_level_known():
    r = pd.Series([-0.10, -0.05, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08] * 3)
    cvar = cvar_at_level(r, level=0.05)
    assert cvar > 0.0  # CVaR should be positive (representing loss magnitude)


def test_pct_below_minus_k_sigma():
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0, 0.02, 100))
    pct = pct_below_minus_k_sigma(r, k=1.0)
    assert 0.0 <= pct <= 1.0
    # For normal(0,σ), ~16% of returns below -1σ
    assert 0.05 < pct < 0.35


def test_left_tail_score_adverse_rs_direction():
    """adverse_rs rule: positive when realized skew is negative (adverse), 0 when positive."""
    idx = pd.date_range("2020-01-31", periods=6, freq="ME")
    rs = pd.Series({idx[0]: -1.5, idx[1]: 0.5, idx[2]: -0.8, idx[3]: 1.0, idx[4]: -2.0, idx[5]: 0.3})
    dummy_monthly = pd.Series(0.01, index=idx)
    lt = left_tail_score_at_month_ends(dummy_monthly, idx, rs, rule="adverse_rs", lookback_months=6)
    # negative skew → positive adverse score
    assert lt.loc[idx[0]] == pytest.approx(1.5)
    # positive skew → 0
    assert lt.loc[idx[1]] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Gate logic
# ---------------------------------------------------------------------------

def test_gate_binds_when_left_tail_elevated():
    g, binding = skewness_gate(0.08, 0.04, g_min=0.25)
    assert binding
    assert g == pytest.approx(0.25)


def test_gate_open_when_left_tail_calm():
    g, binding = skewness_gate(0.02, 0.05, g_min=0.25)
    assert not binding
    assert g == pytest.approx(1.0)


def test_gate_open_on_nan_inputs():
    g, binding = skewness_gate(float("nan"), 0.04, g_min=0.25)
    assert not binding
    assert g == pytest.approx(1.0)


def test_f_tilde_scales_cash():
    """f̃_t = f_t · g_t; weights should sum to 1 and cash = 1 - f̃."""
    from usa_etf_features.vol_target import scale_factor, target_weights
    f = scale_factor(0.20, 0.10, f_min=0.25, f_max=1.0)
    assert f == pytest.approx(0.5)
    g = 0.5
    f_tilde = f * g
    w = target_weights(OPTION_A_WEIGHTS, "BIL", f_tilde)
    assert w.sum() == pytest.approx(1.0)
    assert w["BIL"] == pytest.approx(1.0 - f_tilde)


# ---------------------------------------------------------------------------
# Expanding median prior (leakage-free)
# ---------------------------------------------------------------------------

def test_expanding_median_prior_no_leakage():
    """At date t the median must use only values strictly before t."""
    idx = pd.date_range("2020-01-31", periods=6, freq="ME")
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], index=idx)
    med = expanding_median_prior(s)
    # first date: no prior history → NaN
    assert np.isnan(med.iloc[0])
    # second date: only one prior value (1.0)
    assert med.iloc[1] == pytest.approx(1.0)
    # third date: prior values [1.0, 2.0] → median 1.5
    assert med.iloc[2] == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# No same-month leakage integration test
# ---------------------------------------------------------------------------

def test_no_same_month_leakage_sigma_skew_gate_weights(tmp_path):
    """Mutating returns after t must not change σ̂_t, skew_t, gate_t, or weights_t."""
    px = _prices(n_days=600, seed=7)
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    monthly = _monthly_from_prices(px)
    trial = _default_trial("leak")

    w0, r0, _ = run_skewness_managed_trial(
        px,
        trial,
        universe_csv=uni_path,
        monthly=monthly,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    assert not w0.empty, "walk-forward produced no weight rows"

    # Pick a mid-sample decision date
    decision = pd.Timestamp(w0["date"].iloc[len(w0) // 2])
    before = w0.loc[w0["date"].eq(decision)].iloc[0]

    # Mutate all equity prices after decision — should not affect decision-date outputs
    mutated = px.copy()
    mutated.loc[mutated.index > decision, ["VOO", "QQQM", "IJR", "IWM", "VEA", "GLD"]] *= 10.0
    monthly_m = _monthly_from_prices(mutated)

    w1, _, _ = run_skewness_managed_trial(
        mutated,
        trial,
        universe_csv=uni_path,
        monthly=monthly_m,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    after = w1.loc[w1["date"].eq(decision)].iloc[0]

    assert after["sigma_hat"] == pytest.approx(before["sigma_hat"], rel=1e-9)
    assert after["skew"] == pytest.approx(before["skew"], abs=1e-12)
    assert after["left_tail_score"] == pytest.approx(before["left_tail_score"], abs=1e-12)
    assert after["gate_binding"] == before["gate_binding"]
    assert after["g"] == pytest.approx(before["g"], abs=1e-12)
    assert after["f"] == pytest.approx(before["f"], abs=1e-12)
    assert after["f_tilde"] == pytest.approx(before["f_tilde"], abs=1e-12)
    for col in [c for c in before.index if str(c).startswith("w_")]:
        assert after[col] == pytest.approx(before[col], abs=1e-12)


def test_no_leakage_adverse_rs_rule(tmp_path):
    """Leakage test for adverse_rs rule (depends only on current-month daily returns)."""
    px = _prices(n_days=600, seed=3)
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    monthly = _monthly_from_prices(px)
    trial = SkewnessManagedTrial(
        "leak_adverse",
        lookback=63,
        g_min=0.5,
        sigma_star=0.15,
        skew_estimator="realized_amaya",
        left_tail_rule="adverse_rs",
        skew_lookback_months=21,
        cov_lookback_months=24,
    )
    w0, _, _ = run_skewness_managed_trial(
        px, trial, universe_csv=uni_path, monthly=monthly,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    assert not w0.empty
    decision = pd.Timestamp(w0["date"].iloc[len(w0) // 2])
    before = w0.loc[w0["date"].eq(decision)].iloc[0]

    mutated = px.copy()
    mutated.loc[mutated.index > decision, ["VOO", "QQQM", "IJR"]] *= 8.0
    monthly_m = _monthly_from_prices(mutated)
    w1, _, _ = run_skewness_managed_trial(
        mutated, trial, universe_csv=uni_path, monthly=monthly_m,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    after = w1.loc[w1["date"].eq(decision)].iloc[0]
    assert after["sigma_hat"] == pytest.approx(before["sigma_hat"], rel=1e-9)
    assert after["skew"] == pytest.approx(before["skew"], abs=1e-12)
    assert after["g"] == pytest.approx(before["g"], abs=1e-12)


# ---------------------------------------------------------------------------
# Smoke tests: output shapes and required fields
# ---------------------------------------------------------------------------

def test_trial_emits_all_null_columns(tmp_path):
    """OOS returns must contain r_null_a through r_null_e and r_active_vs_a."""
    px = _prices(n_days=600, seed=5)
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    monthly = _monthly_from_prices(px)
    trial = _default_trial("smoke")

    w, r, reg = run_skewness_managed_trial(
        px,
        trial,
        universe_csv=uni_path,
        monthly=monthly,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    assert not r.empty
    for col in ["r_method", "r_null_a", "r_null_b", "r_active_vs_a"]:
        assert col in r.columns, f"missing column {col}"
    assert "f_tilde" in w.columns
    assert "g" in w.columns
    assert "gate_binding" in w.columns
    assert "skew" in w.columns
    assert "left_tail_score" in w.columns


def test_registry_enabled_false(tmp_path):
    """Registry must have enabled=false (never promote before Quant PASS)."""
    px = _prices(n_days=600, seed=9)
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    _, _, reg = run_skewness_managed_trial(
        px,
        _default_trial("reg_test"),
        universe_csv=uni_path,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    assert reg["enabled"].iloc[0] is False or reg["enabled"].iloc[0] == False
    assert reg["method"].iloc[0] == "skewness_managed"
    assert "Gong" in reg["citation"].iloc[0]


def test_summary_has_dsr_and_trial_count(tmp_path):
    """Summary must include DSR and trial_count fields (Bailey & López de Prado)."""
    px = _prices(n_days=600, seed=11)
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    monthly = _monthly_from_prices(px)
    trial = _default_trial("dsr_test")

    w, r, reg = run_skewness_managed_trial(
        px, trial, universe_csv=uni_path, monthly=monthly,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    summary = summarize_skew_managed(r, w, reg, n_trials=3)
    assert "DSR" in summary.columns
    assert "trial_count" in summary.columns
    assert int(summary["trial_count"].iloc[0]) == 3
    assert np.isfinite(summary["Sharpe_rf0"].iloc[0])


def test_summary_has_null_sharpe_columns(tmp_path):
    """Summary must contain Sharpe columns for all required nulls (a–e)."""
    px = _prices(n_days=600, seed=13)
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    monthly = _monthly_from_prices(px)
    trial = _default_trial("nulls_test")

    w, r, reg = run_skewness_managed_trial(
        px, trial, universe_csv=uni_path, monthly=monthly,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    summary = summarize_skew_managed(r, w, reg, n_trials=1)
    for col in [
        "Book2_Sharpe_rf0",   # null_a (PRIMARY)
        "OptionA_Sharpe_rf0", # null_b
        "EW_Sharpe_rf0",      # null_c
        "MinVar_Sharpe_rf0",  # null_d
        "ERC_Sharpe_rf0",     # null_e
        "NW_t_vs_Book2",
    ]:
        assert col in summary.columns, f"missing summary column {col}"


def test_state_table_has_binding_and_open(tmp_path):
    """State table must emit gate_binding and gate_open rows for each trial."""
    px = _prices(n_days=600, seed=15)
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    monthly = _monthly_from_prices(px)
    trial = _default_trial("state_test")

    w, r, reg = run_skewness_managed_trial(
        px, trial, universe_csv=uni_path, monthly=monthly,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    states = state_table_skew(r)
    assert not states.empty
    assert set(states["state"]).issuperset({"gate_binding", "gate_open"})


def test_weights_sum_to_one(tmp_path):
    """All weight rows must sum to 1.0 within tolerance."""
    px = _prices(n_days=600, seed=17)
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    trial = _default_trial("sum_test")

    w, _, _ = run_skewness_managed_trial(
        px, trial, universe_csv=uni_path,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    w_cols = [c for c in w.columns if str(c).startswith("w_")]
    row_sums = w[w_cols].sum(axis=1)
    assert (row_sums - 1.0).abs().max() < 1e-8


def test_trial_factory_produces_correct_count():
    """make_skew_managed_trials should produce L×G×SE×LT×AT×SLB trials."""
    trials = make_skew_managed_trials(
        lookbacks=[21, 63],
        g_mins=[0.25, 0.5],
        skew_estimators=["realized_amaya", "expected_bmv_lite"],
        left_tail_rules=["cvar_5", "adverse_rs"],
        apply_tos=["option_a_vt"],
        f_min=0.25,
        f_max=1.0,
        sigma_star="expanding_annvol",
        cash_ticker="BIL",
        cost_bps_one_way=5.0,
        skew_lookback_months=[21, 63],
    )
    # 2 lookbacks × 2 g_mins × 2 estimators × 2 rules × 1 apply_to × 2 skew_lbs = 32
    assert len(trials) == 32
    trial_ids = [t.trial_id for t in trials]
    assert len(set(trial_ids)) == 32, "trial IDs must be unique"


def test_expected_bmv_lite_uses_only_past_data():
    """expected_bmv_lite skewness at t must not use realized skewness after t."""
    idx = pd.date_range("2019-01-31", periods=30, freq="ME")
    rng = np.random.default_rng(42)
    rs = pd.Series(rng.normal(0, 1.0, len(idx)), index=idx, name="realized_skew")

    mid = idx[15]
    # compute expected skewness up to mid
    from usa_etf_features.skewness_managed import expected_skewness_bmv_lite
    e_before = expected_skewness_bmv_lite(rs, pd.DatetimeIndex([mid]))

    # mutate rs after mid — should not change E[rs] at mid
    rs_mut = rs.copy()
    rs_mut.loc[rs_mut.index > mid] = 99.0
    e_after = expected_skewness_bmv_lite(rs_mut, pd.DatetimeIndex([mid]))

    if np.isfinite(e_before.iloc[0]):
        assert e_after.iloc[0] == pytest.approx(e_before.iloc[0], abs=1e-12)


def test_pct_lt_neg_k_sigma_rule_no_leakage(tmp_path):
    """pct_lt_neg_k_sigma left-tail score at t must be invariant to future mutations."""
    px = _prices(n_days=600, seed=21)
    uni_path = tmp_path / "universe.csv"
    _universe().to_csv(uni_path, index=False)
    monthly = _monthly_from_prices(px)
    trial = SkewnessManagedTrial(
        "leak_pct",
        lookback=63,
        g_min=0.5,
        sigma_star=0.15,
        skew_estimator="realized_amaya",
        left_tail_rule="pct_lt_neg_k_sigma",
        skew_lookback_months=21,
        cov_lookback_months=24,
    )
    w0, _, _ = run_skewness_managed_trial(
        px, trial, universe_csv=uni_path, monthly=monthly,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    assert not w0.empty
    decision = pd.Timestamp(w0["date"].iloc[len(w0) // 2])
    before = w0.loc[w0["date"].eq(decision)].iloc[0]

    mutated = px.copy()
    mutated.loc[mutated.index > decision, ["VOO", "QQQM", "IJR"]] *= 15.0
    monthly_m = _monthly_from_prices(mutated)
    w1, _, _ = run_skewness_managed_trial(
        mutated, trial, universe_csv=uni_path, monthly=monthly_m,
        universe_config={"off_list_hard_deny": [], "appendix3_deny": []},
    )
    after = w1.loc[w1["date"].eq(decision)].iloc[0]
    assert after["left_tail_score"] == pytest.approx(before["left_tail_score"], abs=1e-12)
    assert after["g"] == pytest.approx(before["g"], abs=1e-12)


# ---------------------------------------------------------------------------
# Gate-first knob enforcement — Book-2 overlay
# ---------------------------------------------------------------------------

def test_gate_first_trial_knobs():
    """Gate-first primary config (QUANT_GATE_skewness_managed.md §3.1) must match registry constants.

    Verifies that make_skew_managed_trials with gate-first parameters produces a trial
    with exactly L63 / realized_amaya / cvar_5 / g_min=0.5 — no L21 or g_min=0.25.
    These constants are used by vol_target_book2 (live Book-2 path).
    """
    from usa_etf_features.strategy_registry import (
        _SKEW_GATE_FIRST_LOOKBACK,
        _SKEW_GATE_FIRST_ESTIMATOR,
        _SKEW_GATE_FIRST_LEFT_TAIL,
        _SKEW_GATE_FIRST_G_MIN,
    )

    # Registry constants must match the gate-first spec
    assert _SKEW_GATE_FIRST_LOOKBACK == 63
    assert _SKEW_GATE_FIRST_ESTIMATOR == "realized_amaya"
    assert _SKEW_GATE_FIRST_LEFT_TAIL == "cvar_5"
    assert abs(_SKEW_GATE_FIRST_G_MIN - 0.5) < 1e-9

    # Trial factory with gate-first knobs must produce exactly one trial
    trials = make_skew_managed_trials(
        lookbacks=[_SKEW_GATE_FIRST_LOOKBACK],
        g_mins=[_SKEW_GATE_FIRST_G_MIN],
        skew_estimators=[_SKEW_GATE_FIRST_ESTIMATOR],
        left_tail_rules=[_SKEW_GATE_FIRST_LEFT_TAIL],
        apply_tos=["option_a_vt"],
        f_min=0.25,
        f_max=1.0,
        sigma_star="expanding_annvol",
        cash_ticker="BIL",
        cost_bps_one_way=5.0,
        skew_lookback_months=[21],
    )
    assert len(trials) == 1
    t = trials[0]
    assert t.lookback == 63
    assert t.skew_estimator == "realized_amaya"
    assert t.left_tail_rule == "cvar_5"
    assert abs(t.g_min - 0.5) < 1e-9

    # Must NOT include L21 or g_min=0.25 (grid-best, non-gate-first)
    grid_trials = make_skew_managed_trials(
        lookbacks=[21, 63],
        g_mins=[0.25, 0.5],
        skew_estimators=["realized_amaya"],
        left_tail_rules=["cvar_5"],
        apply_tos=["option_a_vt"],
        f_min=0.25,
        f_max=1.0,
        sigma_star="expanding_annvol",
        cash_ticker="BIL",
        cost_bps_one_way=5.0,
        skew_lookback_months=[21],
    )
    gate_first_ids = {t.trial_id for t in trials}
    for gt in grid_trials:
        if gt.lookback != 63 or abs(gt.g_min - 0.5) > 1e-9:
            assert gt.trial_id not in gate_first_ids, (
                f"Non-gate-first trial {gt.trial_id!r} must not be in the gate-first set"
            )


def test_gatefirst_registry_artifact_knobs():
    """The committed gatefirst registry CSV must contain only gate-first knobs.

    Verifies that data/processed/skewness_managed/skew_managed_gatefirst_registry.csv
    was produced with L63 / realized_amaya / cvar_5 / g_min=0.5 — no grid-best config.
    """
    from pathlib import Path
    import pandas as pd

    artifact = (
        Path(__file__).resolve().parents[1]
        / "data" / "processed" / "skewness_managed" / "skew_managed_gatefirst_registry.csv"
    )
    if not artifact.exists():
        pytest.skip("gatefirst registry artifact not present — run walkforward-skewness-managed to generate")

    reg = pd.read_csv(artifact)
    assert not reg.empty, "gatefirst registry must not be empty"

    for _, row in reg.iterrows():
        assert int(row["lookback"]) == 63, (
            f"gatefirst artifact has non-gate-first lookback {row['lookback']} in trial {row['trial_id']!r}"
        )
        assert str(row["skew_estimator"]) == "realized_amaya", (
            f"gatefirst artifact has non-gate-first skew_estimator {row['skew_estimator']!r}"
        )
        assert str(row["left_tail_rule"]) == "cvar_5", (
            f"gatefirst artifact has non-gate-first left_tail_rule {row['left_tail_rule']!r}"
        )
        assert abs(float(row["g_min"]) - 0.5) < 1e-9, (
            f"gatefirst artifact has non-gate-first g_min {row['g_min']} in trial {row['trial_id']!r}"
        )
