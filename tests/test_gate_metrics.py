"""Shared gate helper: cash_like tags, exclusion, excess-of-BIL Sharpe, TB3MS fallback,
reconciliation to Quant's cash-null audit, and archived-output regression."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from usa_etf_features import cash_null_audit as cna
from usa_etf_features.gate_metrics import (
    CASH_LIKE, SHORT_DURATION, apply_gate_universe, bil_first_full_month, cash_like_tickers,
    filter_cash_like, gate_sharpe_table, is_cash_like, load_bil_monthly, load_tb3ms,
    risk_free_monthly, run_gate_strategies, sharpe_excess, sharpe_exbil, short_duration_tickers,
    window_rf_coverage,
)
from usa_etf_features.nonlinear_shrinkage_gmv import NLSGMVTrial, run_nls_gmv_trial
from usa_etf_features.spectral_risk_parity import SpectralTrial, run_spectral_trial
from usa_etf_features.vol_target import sharpe_rf0

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data" / "raw" / "usa_universe_categorized.csv"
AUDIT_DIR = ROOT / "data" / "processed" / "cash_null_audit"


@pytest.fixture(scope="module")
def universe():
    return pd.read_csv(UNIVERSE)


@pytest.fixture(scope="module")
def rf():
    return risk_free_monthly()


# ------------------------------------------------------------------ tags
def test_tag_coverage(universe):
    assert universe["cash_like"].dtype == bool and universe["short_duration"].dtype == bool
    assert cash_like_tickers(universe) == CASH_LIKE == {"BIL", "SGOV", "SHV", "GBIL", "USFR", "GSST", "GUMI"}
    assert short_duration_tickers(universe) == SHORT_DURATION == {"SHY", "SPTS", "BSV", "STIP"}
    assert not CASH_LIKE & SHORT_DURATION
    cat = universe.set_index("Ticker")["Category"]
    assert cat["USFR"] == "US Treasuries / Govt / Cash-like"   # was "High Yield Credit"
    assert "High Yield Credit" in set(cat)                       # other HY names untouched
    assert is_cash_like("bil", universe) and not is_cash_like("SHY", universe)
    # The old category is not the tag: it holds duration and missed USFR/GUMI.
    assert {"SHY", "SPTS"} <= set(cat[cat == "US Treasuries / Govt / Cash-like"].index)
    assert cat["GUMI"] == "Municipal Bonds"


def test_filter_cash_like_flag(universe):
    names = ["VOO", "BIL", "SHY", "USFR", "QQQM", "SGOV"]
    assert filter_cash_like(names, universe) == ["VOO", "SHY", "QQQM"]          # default True
    assert filter_cash_like(names, universe, exclude_cash_like=False) == names    # archived no-op
    no_tags = universe.drop(columns=["cash_like"])
    assert filter_cash_like(names, no_tags, exclude_cash_like=False) == names
    with pytest.raises(KeyError):
        filter_cash_like(names, no_tags, exclude_cash_like=True)


def test_exclusion_applied_to_every_strategy(universe):
    rng = np.random.default_rng(3)
    cols = ["VOO", "QQQM", "IJR", "TLT", "SHY", "BIL", "SGOV", "USFR"]
    panel = pd.DataFrame(rng.normal(.005, .03, (60, len(cols))), columns=cols,
                         index=pd.date_range("2015-01-31", periods=60, freq="ME"))
    panel[["BIL", "SGOV", "USFR"]] = rng.normal(.002, .0003, (60, 3))   # the MinVar magnet
    panel["SHY"] = rng.normal(.002, .004, 60)                            # next-lowest vol: duration
    ew = lambda p: pd.Series(1 / p.shape[1], index=p.columns)
    minvar = lambda p: pd.Series(np.eye(p.shape[1])[p.var().argmin()], index=p.columns)
    inv_vol = lambda p: (1 / p.std()) / (1 / p.std()).sum()
    out = run_gate_strategies(panel, universe, {"method": inv_vol, "EW": ew, "MinVar": minvar})
    for w in out.values():
        assert not set(w.index[w > 0]) & CASH_LIKE
        assert np.isclose(w.sum(), 1)
    assert out["MinVar"].idxmax() == "SHY"            # without cash, the low-vol pick is duration
    kept = run_gate_strategies(panel, universe, {"MinVar": minvar}, exclude_cash_like=False)
    assert kept["MinVar"].idxmax() in CASH_LIKE
    rogue = lambda p: pd.Series({"BIL": 1.0})
    with pytest.raises(ValueError, match="outside the gate universe"):
        run_gate_strategies(panel, universe, {"rogue": rogue})
    assert list(apply_gate_universe(panel, universe).columns) == ["VOO", "QQQM", "IJR", "TLT", "SHY"]


def _tagged(names, cash):
    return pd.DataFrame({"Ticker": names, "Category": "Equity", "cash_like": [n in cash for n in names],
                         "short_duration": False})


def test_spectral_runner_excludes_cash_from_method_and_nulls():
    rng = np.random.default_rng(72)
    names = [f"T{i}" for i in range(106)] + ["BIL", "SGOV", "SHV", "GBIL"]
    r = rng.normal(0, .025, (70, 3)) @ rng.uniform(.1, 1, (3, 110)) + rng.normal(.003, .018, (70, 110))
    r[:, -4:] = rng.normal(.002, .0005, (70, 4))
    returns = pd.DataFrame(r, index=pd.date_range("2010-01-31", periods=70, freq="ME"), columns=names)
    uni = _tagged(names, CASH_LIKE)
    cov = pd.DataFrame({"ticker": names, "thin_lt5y": False, "adv_proxy": 2e7})
    on = run_spectral_trial(returns.iloc[:63], uni, cov, SpectralTrial(exclude_cash_like=True))["weights"]
    off = run_spectral_trial(returns.iloc[:63], uni, cov, SpectralTrial())["weights"]
    assert set(on.strategy_id) == set(off.strategy_id) == {
        "spectral_risk_parity", "erc", "minvar_lw", "equal_weight"}
    for sid, sub in on.groupby("strategy_id"):
        assert not set(sub.ticker) & CASH_LIKE, sid
        assert sub.n_names.eq(106).all()
    assert set(off.loc[off.strategy_id == "minvar_lw", "ticker"]) & CASH_LIKE   # archived default keeps them


def test_nls_runner_excludes_cash_from_method_and_nulls():
    rng = np.random.default_rng(29)
    names = [f"T{i}" for i in range(101)] + ["BIL", "SGOV", "USFR", "GSST"]
    weekly = pd.DataFrame(rng.normal(.001, .025, (400, 105)),
                          index=pd.date_range("2014-01-03", periods=400, freq="W-FRI"), columns=names)
    monthly = pd.DataFrame(rng.normal(.004, .04, (90, 105)),
                           index=pd.date_range("2014-01-31", periods=90, freq="BME"), columns=names)
    weekly[names[-4:]] = rng.normal(.0005, .0002, (400, 4))
    uni = _tagged(names, CASH_LIKE)
    cov = pd.DataFrame({"ticker": names, "thin_lt5y": False, "adv_proxy": 1e7})
    trial = NLSGMVTrial(120, min_names=100, oos_start="2020-01-31", oos_end="2020-02-28", exclude_cash_like=True)
    w = run_nls_gmv_trial(weekly, monthly, uni, cov, trial)["weights"]
    assert w.strategy_id.nunique() >= 4
    for sid, sub in w.groupby("strategy_id"):
        assert not set(sub.loc[sub.weight > 0, "ticker"]) & CASH_LIKE, sid


# ------------------------------------------------------- risk-free rate
def test_tb3ms_file_and_fallback_rule(rf):
    tb = load_tb3ms()
    raw = pd.read_csv(ROOT / "data" / "raw" / "fred_tb3ms.csv")
    assert list(raw.columns) == ["observation_date", "TB3MS"]
    assert str(tb.index.min()) == "1934-01" and tb.index.max() >= pd.Period("2026-08", "M")
    assert (np.diff(tb.index.asi8) == 1).all() and tb.between(0, 20 / 1200).all()
    bil = load_bil_monthly()
    first = bil_first_full_month(bil)
    assert str(first) == "2007-06" and pd.isna(bil[pd.Period("2007-05", "M")])
    assert (rf.loc[rf.index < first, "source"] == "TB3MS").all()
    assert (rf.loc[rf.index >= first, "source"] == "BIL").all()
    assert rf.loc[pd.Period("2005-03", "M"), "rf"] == pytest.approx(
        float(raw.loc[raw.observation_date == "2005-03-01", "TB3MS"].iloc[0]) / 1200)
    assert rf.loc[pd.Period("2007-06", "M"), "rf"] == bil[first]
    cov = window_rf_coverage(pd.date_range("2006-07-31", "2008-06-30", freq="ME"), rf)
    assert cov["n_months"] == 24 and cov["fallback_months"] == 11
    assert cov["fallback_share"] == pytest.approx(11 / 24)
    with pytest.raises(ValueError, match="no risk-free rate"):
        window_rf_coverage(pd.date_range("1920-01-31", periods=3, freq="ME"), rf)


def test_bil_priced_return_is_used_not_zero_proxy(rf):
    bil = load_bil_monthly()
    window = rf.loc[pd.Period("2021-02", "M"):pd.Period("2026-09", "M")]
    assert (window.source == "BIL").all()
    pd.testing.assert_series_equal(window["rf"], bil.loc[window.index], check_names=False)
    assert window["rf"].mean() > 0.001 and (window["rf"] != 0).sum() > 50
    # A zero-rf proxy would give the arithmetic rf=0 Sharpe, not the audited 0.966.
    sk = pd.read_csv(ROOT / "data/processed/skewness_managed/skew_managed_gatefirst_returns.csv",
                     parse_dates=["date"]).set_index("date")["r_method"]
    assert sharpe_exbil(sk, rf) == pytest.approx(0.9664, abs=1e-4)
    assert sharpe_excess(sk, np.zeros(len(sk))) > 1.2


def test_sharpe_formulas(rf):
    r = pd.Series([.02, -.01, .03, .005, -.02, .01])
    x = np.array([.001, .002, .001, .0015, .002, .001])
    ex = r.to_numpy() - x
    assert sharpe_excess(r, x) == pytest.approx(ex.mean() * 12 / (ex.std(ddof=1) * np.sqrt(12)))
    # Legacy stays CAGR / vol, exactly the existing helper.
    frame = pd.DataFrame({"a": r.to_numpy()}, index=pd.date_range("2015-01-31", periods=6, freq="ME"))
    tab = gate_sharpe_table(frame, rf)
    assert tab.loc["a", "Sharpe_rf0_legacy"] == sharpe_rf0(frame["a"])
    assert tab.loc["a", "rf_fallback_share"] == 0 and tab.loc["a", "rf_bil_share"] == 1


def test_all_bil_portfolio_scores_zero(rf):
    bil = load_bil_monthly().loc["2007-06":"2026-08"]
    series = pd.Series(bil.to_numpy(), index=bil.index.to_timestamp("M"))
    assert sharpe_exbil(series, rf) == pytest.approx(0.0, abs=1e-12)
    assert sharpe_exbil(load_bil_monthly().dropna(), rf) == 0.0          # monthly PeriodIndex accepted
    # The legacy rf=0 figure rewards pure T-bill carry; the excess figure does not.
    tab = gate_sharpe_table(pd.DataFrame({"BIL": series}), rf)
    assert tab.loc["BIL", "Sharpe_exBIL"] == 0.0
    assert tab.loc["BIL", "Sharpe_rf0_legacy"] > 2


# ------------------------------------------------------- reconciliation
def test_reconciles_to_quant_cash_null_audit(rf):
    rec = cna.reconciliation_table(rf=rf)
    memo = rec[rec.in_memo]
    assert len(memo) == len(cna.MEMO)
    bad = memo[~memo.reproduces.astype(bool)]
    assert set(zip(bad.gate, bad.strategy)) == set(cna.KNOWN_DIFFS)
    for key in cna.KNOWN_DIFFS:   # the known diff is a memo rounding, ex-BIL still matches exactly
        row = memo[(memo.gate == key[0]) & (memo.strategy == key[1])].iloc[0]
        assert abs(row.Sharpe_exBIL - cna.AUDIT_EXACT[key]) <= 1e-4
    # Memo VCFC row = trial L126_C12_g0p25 (65 months), first alphabetically, not the headline trial;
    # the memo now rounds its legacy Book-2 VT figure 0.8747 to 0.87, so every memo row reproduces.
    assert "L126_C12_g0p25, 65 months" in cna.VCFC_GATE and "not the headline trial" in cna.VCFC_GATE
    vc = rec[rec.gate == cna.VCFC_GATE].set_index("strategy")
    assert vc.loc["Book-2 VT", "n_months"] == 65 and vc.loc["Book-2 VT", "memo_rf0"] == "0.87"
    assert round(vc.loc["Book-2 VT", "Sharpe_rf0_legacy"], 4) == 0.8747 and vc.loc["Book-2 VT", "reproduces"]
    assert "0.8747 to 0.87" in vc.loc["Book-2 VT", "note"]
    six = rec[rec.gate == "#6 skew gate-first (live Book 2)"].set_index("strategy")
    assert round(six.loc["VT x gate-first", "Sharpe_exBIL"], 2) == 0.97
    assert round(six.loc["Book-2 VT (BIL priced)", "Sharpe_exBIL"], 2) == 0.84
    assert round(six.loc["Option A static", "Sharpe_exBIL"], 2) == 0.75
    vt0 = rec[rec.gate == "Book-2 VT committed run (cash = 0 proxy)"].set_index("strategy")
    assert round(vt0.loc["Book-2 VT", "Sharpe_exBIL"], 2) == 0.83
    assert cna.trial_counts(rf=rf) == cna.MEMO_COUNTS
    fb = cna.fallback_shares(rf=rf)
    assert (np.round(fb.bil_share * 100) == fb.memo_bil_share_pct).all()


def test_reconciliation_artifact_is_current(rf):
    committed = pd.read_csv(AUDIT_DIR / "reconciliation.csv")
    fresh = cna.reconciliation_table(rf=rf)
    for col in ("Sharpe_exBIL", "Sharpe_rf0_legacy", "rf_fallback_share"):
        np.testing.assert_allclose(committed[col], fresh[col], atol=1e-6)
    assert list(committed.strategy) == list(fresh.strategy)
    shares = pd.read_csv(AUDIT_DIR / "rf_fallback_share.csv")
    np.testing.assert_allclose(shares.fallback_share, cna.fallback_shares(rf=rf).fallback_share, atol=1e-6)
    counts = json.loads((AUDIT_DIR / "trial_counts.json").read_text())
    assert counts["helper"] == counts["memo"] == cna.MEMO_COUNTS


# ------------------------------------------------------- archived regression
def test_archived_committed_csvs_byte_identical():
    manifest = json.loads((ROOT / "tests" / "data" / "archived_csv_sha256.json").read_text())["files"]
    assert len(manifest) >= 60
    for rel, digest in manifest.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == digest, rel


# ------------------------------------------------------- Pages Sharpe switch
def _fmt(x, nd):
    return f"{x:.{nd}f}".replace("-", "−")


def test_site_sharpe_artifact_and_pages_figures(rf):
    site = json.loads((AUDIT_DIR / "site_sharpe.json").read_text())
    fresh = cna.site_sharpe_figures(rf=rf)
    assert json.loads(json.dumps(fresh)) == site
    books = site["books"]
    assert round(books["book1_static_core"]["exbil"], 2) == 0.75
    assert round(books["book2_vt_x_gatefirst"]["exbil"], 2) == 0.97
    assert round(books["uncond_vt_audit_null"]["exbil"], 2) == 0.84
    # Archive cards: "<excess of BIL> (legacy <rf = 0>)" at the card's own precision.
    cards = json.loads((ROOT / "apps/pages/src/data/archive_verdicts.json").read_text(encoding="utf-8"))["cards"]
    for card in cards:
        for row in card["rows"]:
            ex, legacy = row["sharpe"].split(" (legacy ")
            legacy = legacy.rstrip(")")
            nd = len(legacy.split(".")[1])
            fig = site["archive"][card["id"]][row["label"]]
            assert ex == _fmt(fig["exbil"], nd), (card["id"], row["label"])
            assert legacy == _fmt(fig["rf0_legacy"], nd), (card["id"], row["label"])
    metrics = json.loads((ROOT / "docs/data/viz_metrics.json").read_text())
    assert metrics["Sharpe_exbil_vt"] == site["vol_target_run"]["vt"]["exbil"]
    assert metrics["Sharpe_exbil_a"] == site["vol_target_run"]["option_a"]["exbil"]
    assert metrics["Sharpe_vt"] == pytest.approx(site["vol_target_run"]["vt"]["rf0_legacy"], abs=1e-4)
    comp = json.loads((ROOT / "docs/data/viz_comparison.json").read_text())["rows"]
    for row in comp:
        assert row["Sharpe_exBIL"] == site["comparison"][row["strategy_id"]]["exbil"]
        assert row["Sharpe_rf0"] == pytest.approx(site["comparison"][row["strategy_id"]]["rf0_legacy"], abs=1e-4)
    books_tsx = (ROOT / "apps/pages/src/pages/Books.tsx").read_text(encoding="utf-8")
    for needle in ("Sharpe 0.75 in excess of BIL", "Sharpe above BIL 0.97 (0.84, 0.75)",
                   "0.84 in excess of BIL", "legacy rf = 0"):
        assert needle in books_tsx
    for stale in ("Sharpe ~1.06", "higher Sharpe_rf0", "Sharpe ~0.92 ·"):
        assert stale not in books_tsx


BOOK2_STAT_LINE = ("Max drawdown −10.1% (VT backbone −20.1%, Book 1 −25.6%) · volatility ~10.6% (~13.9%, ~15.9%) · "
                   "return ~13.6% (~14.7%, ~14.7%) · Sharpe above BIL 0.97 (0.84, 0.75)")
BOOK2_BODY = (
    "Book 2 gives up about 1 point a year of return versus the VT backbone in exchange for shallower drawdowns "
    "and lower volatility. Its protection has been seen in one bear market: in 2022 its drawdown was about half "
    "of VT's (−10.1% vs −20.1%), and it also cushioned the autumn 2023 pullback (−3.9% vs −9.0%). The skew gate "
    "has not switched on since January 2024, so through the 2024–2026 pullbacks Book 2 tracked VT. Its Sharpe "
    "above BIL is 0.97 vs 0.84 for VT; that difference is not statistically significant.")


def _site_text(rel: str) -> str:
    import re
    text = (ROOT / rel).read_text(encoding="utf-8").replace("&rsquo;", "'")
    text = re.sub(r"\s*<br />\s*", " ", text)
    return re.sub(r"\s+", " ", text)


def test_book2_signed_off_drawdown_first_copy():
    """CIO-signed Book 2 copy (drawdown-first) ships verbatim; no better-Sharpe framing anywhere on the site."""
    for rel in ("apps/pages/src/pages/Books.tsx", "apps/pages/src/pages/Home.tsx"):
        text = _site_text(rel)
        assert BOOK2_STAT_LINE in text, rel
        assert BOOK2_BODY in text, rel
    for rel in ("apps/pages/src/pages/Books.tsx", "apps/pages/src/pages/Home.tsx", "apps/pages/src/pages/Runs.tsx",
                "apps/pages/src/components/TickerBanner.tsx", "apps/pages/src/data/archive_verdicts.json",
                "scripts/build_pages.py"):
        low = _site_text(rel).lower()
        for stale in ("higher sharpe", "better sharpe", "few episodes", "half the drawdown"):
            assert stale not in low, (rel, stale)


def test_methods_table_nulls_use_each_methods_own_window():
    """Methods / Archive table: headline configs and each null on its method's own window."""
    site = json.loads((AUDIT_DIR / "site_sharpe.json").read_text())["archive"]
    cards = {c["id"]: c for c in json.loads(
        (ROOT / "apps/pages/src/data/archive_verdicts.json").read_text(encoding="utf-8"))["cards"]}
    shipped = {c: {r["label"]: r["sharpe"] for r in cards[c]["rows"]} for c in ("regime_dual", "vcfc")}
    assert shipped["regime_dual"] == {"Best dual (vol_corr_spread ERC)": "0.37 (legacy 0.51)",
                                      "Uncond ERC (null)": "0.54 (legacy 0.74)"}
    assert shipped["vcfc"] == {"VCFC (best Sharpe trial)": "0.75 (legacy 1.05)",
                               "Book-2 VT, VCFC run window (null)": "0.89 (legacy 1.11)"}
    for cid in ("regime_dual", "vcfc"):
        assert len({(f["window"], f["n_months"]) for f in site[cid].values()}) == 1   # method and null share a window
    assert site["vcfc"]["Book-2 VT, VCFC run window (null)"]["n_months"] == 70        # best trial L21/C12/g0.5
    assert site["regime_dual"]["Uncond ERC (null)"]["n_months"] == 262
    for page in ("docs/methods/index.html", "docs/methods/justina_round1_scoreboard.html"):
        html = (ROOT / page).read_text(encoding="utf-8")
        for fig in ("0.37 (legacy 0.51)", "0.54 (legacy 0.74)", "0.75 (legacy 1.05)", "0.89 (legacy 1.11)"):
            assert fig in html, (page, fig)
        for wrong in ("0.67 (legacy", "0.84 (legacy", "0.67 (legacy 0.87)"):
            assert wrong not in html, (page, wrong)
