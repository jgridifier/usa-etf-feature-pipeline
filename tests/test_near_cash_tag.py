"""near_cash tag: diagnostic only (composition + void-check inputs), never an exclusion."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from usa_etf_features.gate_metrics import (
    CASH_LIKE, NEAR_CASH, SHORT_DURATION, cash_like_tickers, composition_void_check, duration_composition,
    filter_cash_like, near_cash_tickers, run_gate_strategies, short_duration_tickers,
)

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = pd.read_csv(ROOT / "data/raw/usa_universe_categorized.csv")


def test_near_cash_tags_floating_rate_loan_etfs_only():
    assert near_cash_tickers(UNIVERSE) == NEAR_CASH == frozenset({"FTSL", "SRLN"})
    names = UNIVERSE.set_index("Ticker").Name_Clean
    for t in NEAR_CASH:
        assert "SENIOR LOAN" in names[t].upper()
    # Disjoint from the other tags: USFR (floating-rate Treasury) stays cash_like only.
    assert not near_cash_tickers(UNIVERSE) & cash_like_tickers(UNIVERSE)
    assert not near_cash_tickers(UNIVERSE) & short_duration_tickers(UNIVERSE)
    assert "USFR" in cash_like_tickers(UNIVERSE) and "USFR" not in NEAR_CASH
    assert set(UNIVERSE.near_cash.astype(str).unique()) == {"True", "False"}


def test_near_cash_never_excludes_names():
    names = ["FTSL", "SRLN", "SHY", "VOO", "BIL"]
    assert filter_cash_like(names, UNIVERSE, True) == ["FTSL", "SRLN", "SHY", "VOO"]
    rng = np.random.default_rng(0)
    panel = pd.DataFrame(rng.normal(0, .01, (36, 5)), columns=names)
    out = run_gate_strategies(panel, UNIVERSE, {"ew": lambda p: pd.Series(1 / p.shape[1], index=p.columns)})
    assert set(out["ew"].index) == {"FTSL", "SRLN", "SHY", "VOO"}


def test_duration_composition_and_void_check():
    dates = ["2021-01-29", "2021-02-26"]
    w = pd.DataFrame([dict(strategy_id="m", date=d, ticker=t, weight=v) for d in dates
                      for t, v in (("SHY", .40), ("FTSL", .15), ("VOO", .45))]
                     + [dict(strategy_id="n", date=d, ticker="VOO", weight=1.) for d in dates])
    comp = duration_composition(w, UNIVERSE).set_index("strategy_id")
    assert comp.loc["m", "short_duration_share_mean"] == pytest.approx(.40)
    assert comp.loc["m", "near_cash_share_mean"] == pytest.approx(.15)
    assert comp.loc["m", "short_duration_plus_near_cash_share_mean"] == pytest.approx(.55)
    assert comp.loc["n"].tolist() == [0., 0., 0.]
    check = composition_void_check(.40, 6., .15)
    assert not check["void_short_duration"] and not check["void_effN"]
    assert check["flag_short_duration_plus_near_cash"] and check["short_duration_plus_near_cash_share"] == pytest.approx(.55)
    assert composition_void_check(.50, 5.)["void_short_duration"] is False     # boundaries as in the v2 gate
    assert composition_void_check(.51, 4.99)["void_short_duration"] and composition_void_check(.51, 4.99)["void_effN"]


def test_nothing_past_is_rescored():
    # The #37 artifacts are unchanged and carry no near_cash column; the recorded 96.58% equals
    # short_duration + near_cash on the committed 156w method weights (SRLN is not in that gate).
    d = ROOT / "data/processed/nonlinear_shrinkage_gmv_v2"
    assert "near_cash" not in (d / "summary.csv").read_text().splitlines()[0]
    comp = duration_composition(pd.read_csv(d / "weights.csv").query("window_weeks == 156"), UNIVERSE)
    m = comp.set_index("strategy_id").loc["nonlinear_shrinkage_gmv"]
    assert f"{m.short_duration_plus_near_cash_share_mean:.2%}" == "96.58%"
    assert "96.58%" in (d / "gate_report.md").read_text(encoding="utf-8")
    manifest = json.loads((ROOT / "tests/data/archived_csv_sha256.json").read_text())
    assert manifest  # byte-identity itself is enforced by tests/test_gate_metrics.py
