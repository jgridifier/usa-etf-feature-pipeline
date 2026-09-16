import pandas as pd
import pytest

from usa_etf_features.universe import (
    UniverseGateError,
    assert_eligible,
    eligible_tickers,
    load_universe_config,
)


def _uni():
    return pd.DataFrame(
        {
            "Ticker": ["VOO", "QQQ", "XSD", "VTI"],
            "Category": ["Core", "Growth", "Thematic", "Core"],
            "Source_Section": ["APPENDIX 2"] * 4,
        }
    )


def test_appendix3_hard_fail():
    uni = _uni()
    cfg = load_universe_config()
    with pytest.raises(UniverseGateError):
        assert_eligible(["VUG"], uni, cfg)


def test_offlist_semis_hard_fail():
    uni = _uni()
    cfg = load_universe_config()
    for t in ["SMH", "SOXX", "SOXL", "PSI"]:
        with pytest.raises(UniverseGateError):
            assert_eligible([t], uni, cfg)


def test_eligible_includes_approved():
    uni = _uni()
    cfg = load_universe_config()
    e = eligible_tickers(uni, cfg)
    assert "VOO" in e and "XSD" in e
    assert "SMH" not in e


def test_approved_passes():
    uni = _uni()
    cfg = load_universe_config()
    assert_eligible(["VOO", "XSD"], uni, cfg)  # no raise
