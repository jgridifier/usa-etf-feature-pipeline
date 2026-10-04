"""Complete-month policy and explicit archived/book compatibility."""
import hashlib
import logging
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from usa_etf_features.monthly_panel import (
    PanelProvenance, panel_provenance,
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
    assert actual.attrs == dict(dropped_partial_month="2024-07", source_asof="2024-07-16", complete_months_only=True,
                                monthly_panel_provenance=PanelProvenance("synthetic.csv", True, "2024-07", "2024-07-16"))
    assert "monthly panel synthetic.csv: dropped partial final month 2024-07" in caplog.text
    assert "last session 2024-07-31" in caplog.text
    assert caplog.records[0].name == "usa_etf_features.monthly_panel"
    caplog.clear()
    legacy = load_monthly_panel(panel_path, complete_months_only=False)
    assert_frame_equal(legacy, plain)
    assert legacy.attrs == dict(dropped_partial_month=None, source_asof="2024-07-16", complete_months_only=False,
                                monthly_panel_provenance=PanelProvenance("synthetic.csv", False, None, "2024-07-16"))
    assert panel_provenance(legacy.loc[:"2024-06-30"]) == panel_provenance(legacy)   # survives slicing
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
    assert partial_final_month(plain.index, coverage=COVERAGE) is None
    assert all(date == last_session(date) for date in plain.index)
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
# Re-pinned 2026-10-01: data refresh through 2026-09-30 close
PUBLISHED_SHA256 = {
    'data/processed/skewness_managed/skew_managed_gatefirst_returns.csv': '68ad0748fc3af670d7eb2e6d665ccf40131ab0b8e4469779ade3fc6891aab0f3',
    'data/processed/vol_target_oos_returns.csv': '3434b1a569a77d2e8f17fd6b465267ab9e2c898317755cca70b63468c1fae358',
    'docs/data/vol_target_oos_returns.csv': 'a0e76aa34212821d4cad5b5dd6d473696af4997139129078afa0279cceb452c6',
    'docs/data/viz_metrics.json': 'b00ae1db0d390f52834c25811676a0e15dd3fde22266d770e7b4021f0bd42993',
    # Re-pinned 2026-10-01: audit-null stance quotes the live Book 2 Sharpe (1.00); label 'VT' -> 'Backbone'.
    # Re-pinned 2026-10-04 (#55 after #56): m3_p2_core_rotate 2026-09 restored (68 months) plus the 'window' label
    # ("2021-02 to 2026-09 (68 months)"); rows identical to main's 0797179 copy.
    'docs/data/viz_comparison.json': '7a5bc24c5edf66bb141bcdfdd09f257d36dd62a7752126db79149632150829e9',
    # Re-pinned 2026-10-01: archive.epo_anchored_trend appended (EPO card on the Archive tab); everything else
    # is unchanged, see test_site_sharpe_only_gains_epo_archive_rows (previous pin 1e72c305…3f52fde).
    # Re-pinned 2026-10-04: m3_p2_core_rotate 2026-09 restored from its complete-month re-run (comparison Sharpes over 68 months).
    'data/processed/cash_null_audit/site_sharpe.json': '7620da2c56250f430b59182f83a52aaae7a76fd347f3789fae126826c6d6d9d0',
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
    'data/processed/live/skew_managed_gatefirst_registry.csv': '66e244bb744397665e837d60654974d2e221f65be26eb3c10c289abe3b4e5d78',
    'data/processed/live/skew_managed_gatefirst_returns.csv': 'dfee6ca05ef24a847c13d9b9cecd2275846d5ad31a8e056e444f40f323703f02',
    'data/processed/live/skew_managed_gatefirst_state.csv': 'd1f3eeb9f469bc94b8de9b3c7b572a3f25421a285ef06def43ffc2e12b4feac1',
    'data/processed/live/skew_managed_gatefirst_summary.csv': '0e95eab5d021042331a0aa1a131e6e879a76711530c2ea230219d6d489d35ad2',
    'data/processed/live/skew_managed_gatefirst_weights.csv': 'cd66db8cd45f12d17ab10a199275d5249b401f637e4d1e2a31172cd447368a92',
    # Re-pinned 2026-10-04: m3_p2_core_rotate 2026-09 cell restored from its re-run (only that cell changed).
    'data/processed/live/strategy_returns.csv': '6894c538852f3e329e4c68aca6a79c0354b085ff02480e0f28df0fed7ba2f628',
    'data/processed/live/vol_target_monthly_weights.csv': '1b54802c6feeedf8ea42d2609202a456fede2b46f70431081801d1bc2bc44f2a',
    'data/processed/live/vol_target_oos_returns.csv': 'a0e76aa34212821d4cad5b5dd6d473696af4997139129078afa0279cceb452c6',
    'data/processed/live/vol_target_oos_summary.csv': 'dee50a537e650f15ee680e6aa60279ab98d1127aa30188b4ae4bf1bd36cda09d',
    'data/processed/live/vol_target_regime_table.csv': 'fe2a8ef21f7043463a970bdd51151d91fc08f9e1586d94b1d108a001ff24a2cd',
    'data/processed/live/vol_target_trial_registry.csv': 'f98634cd626f932dd4957de94b88371c9ff7c65eea5152998d5eaa3662ab305d',
    'docs/data/viz_weights.json': '148c7452df4d685a2e5d309f740e9f959c8c953824378c74e97509cdafc1b5dd',
    'docs/data/viz_ft_history.json': '48528ed030c0005beac4fe526755551b298e58aca0c3d013ec6b3bdfe6184fce',
    'docs/data/viz_xsd_timeline.json': '5b1acb8b21533d6d09c020040b5bb13038f1de43f00bb32ec80f1511730a913d',
    'docs/data/viz_equity_drawdown.json': '030e0d1163b0c239d93e7d09f86d1479f19aba6677503c713d15a3a400aef32a',
    'docs/data/vol_target_trial_registry.csv': 'f98634cd626f932dd4957de94b88371c9ff7c65eea5152998d5eaa3662ab305d',
    'docs/data/vol_target_oos_summary.csv': 'dee50a537e650f15ee680e6aa60279ab98d1127aa30188b4ae4bf1bd36cda09d',
    'docs/data/vol_target_monthly_weights.csv': '1b54802c6feeedf8ea42d2609202a456fede2b46f70431081801d1bc2bc44f2a',
    'docs/data/vol_target_regime_table.csv': 'fe2a8ef21f7043463a970bdd51151d91fc08f9e1586d94b1d108a001ff24a2cd',
    'docs/data/cio_book_shortlist/book1_static_option_a_weights.csv': 'a1ca1d9eb0cacc221868463affe6aacf678083d2ee538218c491dc8e2d829878',
    'docs/data/cio_book_shortlist/shortlist_comparison.csv': '8c5aa6c1852ede1461f4509c583ca912015da498bc955aa1f515d03b51930d16',
    'docs/data/cio_book_shortlist/book2_vol_target_option_a_weights.csv': '0a98eb83ec3acd5167669fc4cf89d3572e53ff8c2cf6ab1f21afa30435926b27',
    'docs/data/cio_book_shortlist/run_latest/strategy_registry_used.csv': 'fa8cf2898b5ab45fb4e9578f0cade53e93bba43d04e13ffe9c10eed543bb030d',
    'docs/data/cio_book_shortlist/run_latest/strategy_diagnostics.csv': 'adaf7de3b3e266c3b1b30ca4935ead92b9447a2276dd856f0e9d004a4e288f21',
    'docs/data/cio_book_shortlist/run_latest/suggested_weights.csv': '708152bca4373923f7ab198b70fc1b5c8f57b7a0d99994102b6bfd6b6154b544',
    # Re-pinned 2026-10-04: m3_p2_core_rotate 2026-09 restored from its re-run (68-month comparison).
    'docs/data/cio_book_shortlist/run_latest/strategy_comparison.csv': '0bd0484264493325a22dbd6b72b0d739fbafcb37f888aa08dbe4041e7b9ba4dc',
    'docs/data/growth_alpha_adj_close.csv': '6af174a5a0f9096e68e22a9a25695ba770c9877e1c761abe121432835b7c6d5c',
    'docs/data/growth_panel_history_coverage.csv': '01fc48143a73a22a0a8fea0464bcf969fa2b07d1703a40548579d48ade36a7d4',
    # Re-pinned 2026-10-04: m3_p2_core_rotate 2026-09 restored from its re-run (68-month comparison).
    'docs/data/strategy_comparison.csv': '0bd0484264493325a22dbd6b72b0d739fbafcb37f888aa08dbe4041e7b9ba4dc',
    'docs/data/strategy_diagnostics.csv': 'adaf7de3b3e266c3b1b30ca4935ead92b9447a2276dd856f0e9d004a4e288f21',
    'docs/data/suggested_weights.csv': '708152bca4373923f7ab198b70fc1b5c8f57b7a0d99994102b6bfd6b6154b544',
    'docs/data/shortlist_comparison.csv': '8c5aa6c1852ede1461f4509c583ca912015da498bc955aa1f515d03b51930d16',
    'docs/data/book1_static_option_a_weights.csv': 'a1ca1d9eb0cacc221868463affe6aacf678083d2ee538218c491dc8e2d829878',
    'docs/data/book2_vol_target_option_a_weights.csv': '0a98eb83ec3acd5167669fc4cf89d3572e53ff8c2cf6ab1f21afa30435926b27',
    'docs/data/latest_weights_snapshot.csv': '08df3c1ce3c9658de5a84112452d883d01491740fe48d2888ed59ce67b7b7bf3',
}


# Re-pinned 2026-10-04 (Sep-core fix, scripts/repair_live_partial_month.py): docs/data/viz_metrics.json, docs/data/viz_comparison.json, data/processed/cash_null_audit/site_sharpe.json, data/processed/live/skew_managed_gatefirst_returns.csv, data/processed/live/strategy_returns.csv, data/processed/live/vol_target_oos_returns.csv
def test_published_books_and_v3_byte_identical():
    for name, expected in PUBLISHED_SHA256.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name


def test_site_sharpe_only_gains_epo_archive_rows():
    """Without the appended EPO archive rows, site_sharpe.json is byte-identical to the previous pin."""
    import json
    site = json.loads((ROOT / 'data/processed/cash_null_audit/site_sharpe.json').read_text(encoding='utf-8'))
    assert list(site['archive'])[-1] == 'epo_anchored_trend'
    del site['archive']['epo_anchored_trend']
    before = (json.dumps(site, indent=2) + '\n').encode()
    assert hashlib.sha256(before).hexdigest() == '24b7b84da26f9acaf5c68386a3f6f42d3b29d399277f7bbad444825687e2c92c'  # re-pinned 2026-10-04: 2026-09 live row rebuilt from the complete-month panel; m3_p2_core_rotate 2026-09 restored from its re-run (68 months)


def test_books_page_data_through_last_complete_month():
    """Books date equals the panel's last complete calendar month."""
    from usa_etf_features.monthly_panel import partial_final_month
    panel = pd.read_csv(ROOT / 'data/raw/usa_universe_panel_monthly_returns.csv', index_col=0, parse_dates=True)
    last = panel.index.max()
    month = partial_final_month(panel.index, coverage=ROOT / 'data/raw/usa_universe_panel_history_coverage.csv')
    assert month is None
    assert last == last_session(last)
    assert load_monthly_panel(PANEL).index.max() == last
    books = (ROOT / 'apps/pages/src/pages/Books.tsx').read_text(encoding='utf-8')
    assert f"Data through {last.day} {last:%b %Y}." in books
    assert "September is a partial month" not in books
