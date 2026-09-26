"""near_cash stored tag + default-on composition tripwire (cash_like + short_duration + near_cash)."""
import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import usa_etf_features.gate_metrics as gm
from usa_etf_features.gate_metrics import (
    INCOMPLETE_LABEL, NEAR_CASH, cash_like_tickers, composition_report_lines, composition_shares,
    composition_tripwire, filter_cash_like, final_gate_label, near_cash_tickers, run_gate_strategies,
    short_duration_tickers,
)

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = pd.read_csv(ROOT / "data/raw/usa_universe_categorized.csv")
DATES = ["2021-01-29", "2021-02-26"]


def _w(**books):
    """Long weights: books = {strategy: {ticker: weight}} held on every date."""
    return pd.DataFrame([dict(strategy_id=s, date=d, ticker=t, weight=v)
                         for s, h in books.items() for d in DATES for t, v in h.items()])


# ------------------------------------------------------------------------------ stored tag
def test_near_cash_is_a_stored_column_like_cash_like():
    header = (ROOT / "data/raw/usa_universe_categorized.csv").read_text().splitlines()[0].split(",")
    assert header[-3:] == ["cash_like", "short_duration", "near_cash"]
    stored = UNIVERSE.set_index("Ticker").near_cash.astype(str)
    assert set(stored.unique()) == {"True", "False"}
    assert set(stored[stored.eq("True")].index) == set(NEAR_CASH) == {"FTSL", "SRLN"}
    assert near_cash_tickers(UNIVERSE) == NEAR_CASH
    # The tag is read from the column only: flipping the stored value flips the result.
    flipped = UNIVERSE.assign(near_cash=UNIVERSE.Ticker.eq("VOO"))
    assert near_cash_tickers(flipped) == {"VOO"}
    assert "Name_" not in inspect.getsource(gm)            # no runtime derivation from fund names
    assert not near_cash_tickers(UNIVERSE) & cash_like_tickers(UNIVERSE)
    assert not near_cash_tickers(UNIVERSE) & short_duration_tickers(UNIVERSE)


def test_near_cash_never_excludes_names():
    names = ["FTSL", "SRLN", "SHY", "VOO", "BIL"]
    assert filter_cash_like(names, UNIVERSE, True) == ["FTSL", "SRLN", "SHY", "VOO"]
    panel = pd.DataFrame(np.random.default_rng(0).normal(0, .01, (36, 5)), columns=names)
    out = run_gate_strategies(panel, UNIVERSE, {"ew": lambda p: pd.Series(1 / p.shape[1], index=p.columns)})
    assert set(out["ew"].index) == {"FTSL", "SRLN", "SHY", "VOO"}


# ------------------------------------------------------------------- composition tripwire
def test_void_at_5001_for_method_and_pass_at_exactly_50():
    w = _w(m={"BIL": .2, "SHY": .2, "FTSL": .1001, "VOO": .4999}, n={"VOO": 1.})
    r = composition_tripwire(w, UNIVERSE, method="m", primary_null="n")
    assert r["status"] == "VOID" and r["void_method"] and not r["void_null"]
    assert r["method_share"] == pytest.approx(.5001)
    t = r["table"].set_index("strategy_id").loc["m"]
    assert (t.cash_like_share_mean, t.short_duration_share_mean, t.near_cash_share_mean) == pytest.approx((.2, .2, .1001))
    ok = composition_tripwire(_w(m={"BIL": .25, "SHY": .25, "VOO": .5}, n={"VOO": 1.}), UNIVERSE,
                              method="m", primary_null="n")
    assert ok["method_share"] == pytest.approx(.5) and ok["status"] == "PASS"          # strictly greater only


def test_void_for_the_primary_null_alone():
    r = composition_tripwire(_w(m={"VOO": 1.}, n={"SGOV": .3, "SPTS": .3, "VOO": .4}), UNIVERSE,
                             method="m", primary_null="n")
    assert r["status"] == "VOID" and r["void_null"] and not r["void_method"] and r["method_share"] == 0


def test_equity_only_reads_zero():
    r = composition_tripwire(_w(m={"VOO": .7, "QQQM": .2, "IJR": .1}, n={"VOO": 1.}), UNIVERSE,
                             method="m", primary_null="n")
    assert r["status"] == "PASS" and r["method_share"] == 0 and r["null_share"] == 0 and r["computable"]


def test_opt_out_requires_and_prints_a_written_reason():
    w = _w(m={"BIL": 1.}, n={"VOO": 1.})
    reason = "Cash-timing overlay: holding BIL is the method itself (ticket section 3)."
    r = composition_tripwire(w, UNIVERSE, method="m", primary_null="n", opt_out=True, opt_out_reason=reason)
    assert r["status"] == "OPTED OUT" and r["method_share"] == 1.0
    assert any(reason in line for line in composition_report_lines(r))
    for bad in (None, "", "   "):
        with pytest.raises(ValueError, match="written reason"):
            composition_tripwire(w, UNIVERSE, method="m", primary_null="n", opt_out=True, opt_out_reason=bad)
    with pytest.raises(ValueError, match="without opt_out"):
        composition_tripwire(w, UNIVERSE, method="m", primary_null="n", opt_out_reason=reason)


def test_sleeve_look_through_to_constituents():
    # A 'US Treasuries' sleeve mixing bills and duration; weights are held on sleeves.
    w = _w(m={"US Treasuries": .6, "US Equity": .4}, n={"US Equity": 1.})
    constituents = pd.DataFrame([("US Treasuries", "BIL", .5), ("US Treasuries", "SHY", .25),
                                 ("US Treasuries", "TLT", .25), ("US Equity", "VOO", 1.)],
                                columns=["sleeve", "ticker", "weight"])
    r = composition_tripwire(w, UNIVERSE, method="m", primary_null="n", constituents=constituents)
    assert r["computable"] and r["method_share"] == pytest.approx(.6 * .75) and r["status"] == "PASS"
    t = r["table"].set_index("strategy_id").loc["m"]
    assert t.cash_like_share_mean == pytest.approx(.3) and t.short_duration_share_mean == pytest.approx(.15)
    # Time-varying membership: the second date's sleeve is all bills -> average (0.45 + 0.6) / 2.
    dated = pd.concat([constituents.assign(date=DATES[0]),
                       pd.DataFrame([("US Treasuries", "BIL", 1.), ("US Equity", "VOO", 1.)],
                                    columns=["sleeve", "ticker", "weight"]).assign(date=DATES[1])])
    r = composition_tripwire(w, UNIVERSE, method="m", primary_null="n", constituents=dated)
    assert r["method_share"] == pytest.approx((.45 + .6) / 2)
    bad = constituents.assign(weight=constituents.weight * 2)
    with pytest.raises(ValueError, match="sum to 1"):
        gm.look_through(w, bad)


def test_not_computable_is_reported_not_zero():
    w = _w(m={"US Treasuries": .6, "US Equity": .4}, n={"VOO": 1.})
    r = composition_tripwire(w, UNIVERSE, method="m", primary_null="n")
    assert r["status"] == "NOT COMPUTABLE" and not r["computable"] and np.isnan(r["method_share"])
    assert "US Treasuries" in r["not_computable_reason"]
    text = "\n".join(composition_report_lines(r))
    assert "- Method `m`: not computable" in text and INCOMPLETE_LABEL in text
    assert "- Primary null `n`: 0.00%" in text
    shares = composition_shares(w, UNIVERSE).set_index("strategy_id")
    assert not shares.loc["m", "computable"] and shares.loc["n", "computable"]


# ------------------------------------------------------------------ final label (INCOMPLETE rule)
def test_not_computable_blocks_a_pass_but_not_a_fail():
    nc = composition_tripwire(_w(m={"SLEEVE_X": 1.}, n={"VOO": 1.}), UNIVERSE, method="m", primary_null="n")
    assert nc["status"] == "NOT COMPUTABLE"
    assert final_gate_label("PASS", nc) == "INCOMPLETE: composition not computable" == INCOMPLETE_LABEL
    assert final_gate_label("FAIL", nc) == "FAIL"
    assert final_gate_label("VOID", nc) == "VOID"            # other tripwires still win
    reason = "Sleeve gate predating constituent weights; composition reviewed by hand (ticket note)."
    opted = composition_tripwire(_w(m={"SLEEVE_X": 1.}, n={"VOO": 1.}), UNIVERSE, method="m", primary_null="n",
                                 opt_out=True, opt_out_reason=reason)
    assert final_gate_label("PASS", opted) == "PASS"
    assert any(reason in line for line in composition_report_lines(opted))
    void = composition_tripwire(_w(m={"BIL": .6, "VOO": .4}, n={"VOO": 1.}), UNIVERSE, method="m", primary_null="n")
    assert final_gate_label("PASS", void) == "VOID" and final_gate_label("FAIL", void) == "VOID"
    ok = composition_tripwire(_w(m={"VOO": 1.}, n={"VOO": 1.}), UNIVERSE, method="m", primary_null="n")
    assert final_gate_label("PASS", ok) == "PASS" and final_gate_label("FAIL", ok) == "FAIL"
    with pytest.raises(ValueError):
        final_gate_label("MAYBE", ok)


# ------------------------------------------------------------------- not retroactive
def test_skew_gatefirst_book2_sanity_from_committed_weights():
    """#6 (live Book 2, VT x skew gate-first): method holdings are committed (w_VOO/w_QQQM/w_IJR/w_BIL).

    The primary null (unconditional Book-2 VT) has no committed holdings columns; its weights are the same
    70/20/10 core scaled by the committed VT factor f, with 1 - f in BIL (the method is f_tilde = f * g).
    """
    f = pd.read_csv(ROOT / "data/processed/skewness_managed/skew_managed_gatefirst_weights.csv")
    assert len(f) == 68 and np.allclose(f.w_BIL, 1 - f.f_tilde)
    held = {"VOO": .7, "QQQM": .2, "IJR": .1}
    rows = [dict(strategy_id="vt_x_gatefirst", date=r.date, ticker=t, weight=getattr(r, f"w_{t}"))
            for r in f.itertuples() for t in ("VOO", "QQQM", "IJR", "BIL")]
    rows += [dict(strategy_id="book2_vt", date=r.date, ticker=t, weight=r.f * held[t] if t in held else 1 - r.f)
             for r in f.itertuples() for t in ("VOO", "QQQM", "IJR", "BIL")]
    r = composition_tripwire(pd.DataFrame(rows), UNIVERSE, method="vt_x_gatefirst", primary_null="book2_vt")
    t = r["table"].set_index("strategy_id")
    assert r["status"] == "PASS" and final_gate_label("PASS", r) == "PASS"
    assert round(r["method_share"], 4) == 0.2427                   # all BIL (cash_like)
    assert t.loc["vt_x_gatefirst", "cash_like_share_mean"] == pytest.approx(r["method_share"], abs=1e-15)
    assert round(r["null_share"], 4) == 0.0696
    assert t.loc["vt_x_gatefirst", ["short_duration_share_mean", "near_cash_share_mean"]].sum() == 0


def test_archived_outputs_untouched_manifest_covers_78():
    manifest = json.loads((ROOT / "tests/data/archived_csv_sha256.json").read_text())["files"]
    assert len(manifest) == 78   # byte-identity itself is enforced by tests/test_gate_metrics.py
    assert "near_cash" not in (ROOT / "data/processed/nonlinear_shrinkage_gmv_v2/summary.csv").read_text().splitlines()[0]
