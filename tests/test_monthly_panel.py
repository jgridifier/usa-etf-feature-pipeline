"""Complete-month policy and explicit archived/book compatibility."""
import hashlib
import logging
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from usa_etf_features.monthly_panel import (
    drop_partial_final_month, last_session, load_monthly_panel,
    partial_final_month, source_asof, USEquityHolidayCalendar,
    SPECIAL_FULL_DAY_CLOSURES,
)
from usa_etf_features.rotation import month_end_trading_dates

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data/raw/usa_universe_panel_monthly_returns.csv"
COVERAGE = ROOT / "data/raw/usa_universe_panel_history_coverage.csv"


@pytest.fixture
def panel_path(tmp_path):
    dates = [last_session(m) for m in pd.period_range("2024-01", "2024-06", freq="M")]
    dates.append(pd.Timestamp("2024-07-16"))
    frame = pd.DataFrame({"ETF": range(len(dates))}, index=pd.DatetimeIndex(dates, name="date"))
    path = tmp_path / "synthetic.csv"
    frame.to_csv(path)
    return path


def test_partial_and_legacy(panel_path, caplog):
    plain = pd.read_csv(panel_path, index_col=0, parse_dates=True)
    with caplog.at_level(logging.WARNING):
        actual = load_monthly_panel(panel_path)
    assert_frame_equal(actual, plain.iloc[:-1])
    assert actual.attrs == dict(dropped_partial_month="2024-07", source_asof="2024-07-16", complete_months_only=True)
    assert "monthly panel synthetic.csv: dropped partial final month 2024-07" in caplog.text
    assert "last session 2024-07-31" in caplog.text
    assert caplog.records[0].name == "usa_etf_features.monthly_panel"
    caplog.clear()
    legacy = load_monthly_panel(panel_path, complete_months_only=False)
    assert_frame_equal(legacy, plain)
    assert legacy.attrs == dict(dropped_partial_month=None, source_asof="2024-07-16", complete_months_only=False)
    assert not caplog.records


def test_complete(panel_path, caplog):
    plain = pd.read_csv(panel_path, index_col=0, parse_dates=True).iloc[:-1]
    plain.to_csv(panel_path)
    actual = load_monthly_panel(panel_path)
    assert_frame_equal(actual, plain)
    assert actual.attrs["dropped_partial_month"] is None
    assert not caplog.records


def test_asof_precedence(panel_path, tmp_path):
    index = pd.read_csv(panel_path, index_col=0, parse_dates=True).index
    coverage = pd.DataFrame({"end": ["2024-07-17", "2024-07-25", None]})
    coverage_path = tmp_path / "coverage.csv"
    coverage.to_csv(coverage_path, index=False)
    for value in (coverage, coverage_path):
        assert source_asof(index, value) == pd.Timestamp("2024-07-25")
        assert partial_final_month(index, coverage=value) == pd.Period("2024-07")
        for asof in ("2024-07-31", "2024-08-01"):
            assert partial_final_month(index, coverage=value, asof=asof) is None
            assert len(load_monthly_panel(panel_path, coverage=value, asof=asof)) == len(index)
    assert source_asof(index, asof="2024-07-20") == pd.Timestamp("2024-07-20")


@pytest.mark.parametrize("month, expected", [
    ("2026-09", "2026-09-30"), ("2024-03", "2024-03-28"),
    ("2021-05", "2021-05-28"), ("2022-12", "2022-12-30"),
])
def test_last_session(month, expected):
    for value in (month, pd.Period(month), pd.Timestamp(month)):
        assert last_session(value) == pd.Timestamp(expected)
    assert partial_final_month(pd.DatetimeIndex([expected])) is None


def test_good_friday_differs_from_old_heuristic():
    last = pd.Timestamp("2024-03-28")
    assert last < last + pd.offsets.BMonthEnd(0)
    assert partial_final_month([last]) is None


def test_calendar_observances_and_special_closures():
    holidays = USEquityHolidayCalendar().holidays("1997-01-01", "2025-12-31")
    for day in ("1998-01-19", "2022-06-20", "2021-07-05", "2021-12-24"):
        assert pd.Timestamp(day) in holidays
    for day in ("1997-01-20", "2021-06-18", "2021-12-31"):
        assert pd.Timestamp(day) not in holidays
    offset = pd.offsets.CustomBusinessDay(calendar=USEquityHolidayCalendar(), holidays=list(SPECIAL_FULL_DAY_CLOSURES))
    for day in SPECIAL_FULL_DAY_CLOSURES:
        assert not offset.is_on_offset(pd.Timestamp(day))


def test_in_memory_drops_every_row_and_preserves_input():
    frame = pd.DataFrame({"x": [1, 2, 3]}, index=pd.to_datetime(["2024-07-16", "2024-06-28", "2024-07-01"]))
    logger = logging.getLogger("test.monthly_panel")
    result = drop_partial_final_month(frame, logger=logger)
    assert list(result.x) == [2]
    assert len(frame) == 3
    assert frame.attrs == {}
    empty = drop_partial_final_month(frame.iloc[:0])
    assert empty.empty
    assert empty.attrs["dropped_partial_month"] is None


def test_committed_panel_compatibility():
    from usa_etf_features.spectral_risk_parity import read_returns

    plain = pd.read_csv(PANEL, index_col=0, parse_dates=True).sort_index()
    assert partial_final_month(plain.index, coverage=COVERAGE) == pd.Period("2026-09")
    assert all(date == last_session(date) for date in plain.index[:-1])
    last = plain.index[-1]
    old = plain.iloc[:-1] if last < last + pd.offsets.BMonthEnd(0) else plain
    assert_frame_equal(read_returns(PANEL), old)
    assert_frame_equal(load_monthly_panel(PANEL, complete_months_only=False), plain)


def test_legacy_bil_and_rotation():
    from usa_etf_features.gate_metrics import load_bil_monthly

    assert load_bil_monthly().index[-1] == pd.Period("2026-09")
    prices = pd.DataFrame({"ETF": 1.0}, index=pd.bdate_range("2024-06-01", "2024-07-16"))
    assert list(month_end_trading_dates(prices)) == list(pd.to_datetime(["2024-06-28", "2024-07-16"]))
    assert list(month_end_trading_dates(prices, complete_months_only=True)) == [pd.Timestamp("2024-06-28")]
    assert month_end_trading_dates(prices, complete_months_only=True, asof="2024-07-31").equals(month_end_trading_dates(prices))


# Pinned before policy validation; never regenerate published artifacts in this test.
PUBLISHED_SHA256 = {
    'data/processed/skewness_managed/skew_managed_gatefirst_returns.csv': '68ad0748fc3af670d7eb2e6d665ccf40131ab0b8e4469779ade3fc6891aab0f3',
    'data/processed/vol_target_oos_returns.csv': '3434b1a569a77d2e8f17fd6b465267ab9e2c898317755cca70b63468c1fae358',
    'docs/data/vol_target_oos_returns.csv': '79601675dfc5684623e0cd67f60b75d3392f1b750946432d8909ad15c7379299',
    'docs/data/viz_metrics.json': '3076f571dfc7db07997675ce727e4266611b905a9e6fcf7b5f61eba0dbb877f8',
    'docs/data/viz_comparison.json': 'af3eb118f01e0b0fb5265e44abaa19bf36151a08623fe47e2b33d8dbee3ad222',
    'data/processed/cash_null_audit/site_sharpe.json': '8202e853718caecaba7535742b0ccb963f9fd61aea85abc88f213f89240bd9f1',
    'data/processed/nonlinear_shrinkage_gmv_v3/composition_tripwire.csv': '672e1661f238d4699574cc94bec50be44fbe5677bae3c8286316b771ccecbf66',
    'data/processed/nonlinear_shrinkage_gmv_v3/coverage_gaps.csv': 'a4d825ec2855d73d02c2b1ce22fa278c17fe35e06d55cee7b3a5eb719f9e9346',
    'data/processed/nonlinear_shrinkage_gmv_v3/final_month_unpriced.csv': '0c20686dc1794a0e4a08650c9914589a09da7a1f20ac0bf6e84271dbad935068',
    'data/processed/nonlinear_shrinkage_gmv_v3/name_counts.csv': '224ba6f7015b6a17af2b9d358dd8a4da3af5780399c9a03560bfbf49228ea41d',
    'data/processed/nonlinear_shrinkage_gmv_v3/oos_returns.csv': '4f3deae11e66e053b30cd9530775e41ded38ebb5c36102446ccda2dfdd5734cc',
    'data/processed/nonlinear_shrinkage_gmv_v3/shrinkage_diagnostics.csv': '09088f98de0a7c6720807dcabe8a4be291d4425ac6c29b5b78ff7e5051141b19',
    'data/processed/nonlinear_shrinkage_gmv_v3/summary.csv': '589716e32777005b9c321b8e87e67f8201ee60c88c7aa20c754cc612965bde06',
    'data/processed/nonlinear_shrinkage_gmv_v3/trial_registry.csv': '76bd29d3e63a7febb267d09ac15f235e0384f06b679efca1f7b46e97baed04cd',
    'data/processed/nonlinear_shrinkage_gmv_v3/variance_tests.csv': '957b13d432b9d512a3265db8bdd444ddd2b6abc90c3c6e377532fc65b422ed5c',
    'data/processed/nonlinear_shrinkage_gmv_v3/weights.csv': 'd23fe0ba9655e0da05945940cea45dbd2f5b5b04e9a58a8ef24418710dc3b060',
}


def test_published_books_and_v3_byte_identical():
    for name, expected in PUBLISHED_SHA256.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name


def test_books_page_says_data_ends_in_a_partial_month():
    """Books copy: 'Data through <panel's last date> (<month> is a partial month)', derived from the panel."""
    from usa_etf_features.monthly_panel import partial_final_month
    panel = pd.read_csv(ROOT / 'data/raw/usa_universe_panel_monthly_returns.csv', index_col=0, parse_dates=True)
    last = panel.index.max()
    month = partial_final_month(panel.index, coverage=ROOT / 'data/raw/usa_universe_panel_history_coverage.csv')
    assert month == last.to_period('M')
    books = (ROOT / 'apps/pages/src/pages/Books.tsx').read_text(encoding='utf-8')
    assert f"Data through {last.day} {last:%b %Y} ({last:%B} is a partial month)." in books
