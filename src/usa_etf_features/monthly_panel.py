"""Complete calendar months for new gate runs and opt-in in-memory panels.

Use the panel's own daily source as-of date and the US equity trading calendar.
Archived gates and published Book 1 / Book 2 / VT numbers are not regenerated;
books adopt this rule at the next data refresh. Legacy callers explicitly opt out.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from pandas.tseries.holiday import (
    AbstractHolidayCalendar, GoodFriday, Holiday, USLaborDay, MO,
    USMemorialDay, USPresidentsDay, USThanksgivingDay, nearest_workday,
    sunday_to_monday,
)
from pandas.tseries.offsets import CustomBusinessMonthEnd

# Default for new gate runs; archived runners explicitly retain legacy behavior.
DEFAULT_COMPLETE_MONTHS_ONLY = True


class USEquityHolidayCalendar(AbstractHolidayCalendar):
    """NYSE recurring full-day holidays (early closes remain trading sessions)."""

    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=sunday_to_monday),
        Holiday("Martin Luther King Jr. Day", month=1, day=1,
                offset=pd.DateOffset(weekday=MO(3)), start_date="1998-01-01"),
        USPresidentsDay, GoodFriday, USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-06-19",
                observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay, USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


# Exceptional NYSE full-day closures: September 11 attacks, presidential
# funerals (Reagan, Ford, Bush, Carter), and Hurricane Sandy.
SPECIAL_FULL_DAY_CLOSURES = (
    "2001-09-11", "2001-09-12", "2001-09-13", "2001-09-14",
    "2004-06-11", "2007-01-02", "2012-10-29", "2012-10-30",
    "2018-12-05", "2025-01-09",
)
_MONTH_END = CustomBusinessMonthEnd(
    calendar=USEquityHolidayCalendar(), holidays=list(SPECIAL_FULL_DAY_CLOSURES),
)


def last_session(month: pd.Period | str | pd.Timestamp) -> pd.Timestamp:
    """Last US equity trading session of the supplied calendar month."""
    period = month.asfreq("M") if isinstance(month, pd.Period) else pd.Timestamp(month).to_period("M")
    return _MONTH_END.rollback(period.end_time.normalize())


def source_asof(panel_index, coverage=None, asof=None) -> pd.Timestamp:
    """Explicit as-of, else maximum daily coverage end, else latest panel date."""
    if asof is not None:
        return pd.Timestamp(asof)
    if coverage is not None:
        coverage = coverage if isinstance(coverage, pd.DataFrame) else pd.read_csv(coverage)
        end = pd.to_datetime(coverage["end"]).max()
        if pd.notna(end):
            return end
    return pd.DatetimeIndex(panel_index).max()


def partial_final_month(panel_index, *, coverage=None, asof=None) -> pd.Period | None:
    """Final row's calendar month when its daily source is still incomplete."""
    index = pd.DatetimeIndex(panel_index)
    if index.empty:
        return None
    month = index.max().to_period("M")
    return month if source_asof(index, coverage, asof) < last_session(month) else None


def _annotate(frame, asof, dropped, complete):
    frame.attrs.update(
        dropped_partial_month=str(dropped) if dropped is not None else None,
        source_asof=asof.strftime("%Y-%m-%d") if pd.notna(asof) else None,
        complete_months_only=complete,
    )
    return frame


def drop_partial_final_month(frame, *, coverage=None, asof=None, logger=None):
    """Copy a date-indexed frame, removing all rows in an incomplete final month."""
    end = source_asof(frame.index, coverage, asof)
    partial = partial_final_month(frame.index, asof=end)
    result = frame.copy()
    if partial is not None:
        result = result.loc[pd.DatetimeIndex(result.index).to_period("M") != partial].copy()
        (logger if logger is not None else logging.getLogger(__name__)).warning(
            "monthly panel %s: dropped partial final month %s (source data through %s; last session %s)",
            frame.attrs.get("monthly_panel_name", "<in-memory>"), partial,
            end.strftime("%Y-%m-%d"), last_session(partial).strftime("%Y-%m-%d"),
        )
    return _annotate(result, end, partial, True)


def load_monthly_panel(path, *, complete_months_only=DEFAULT_COMPLETE_MONTHS_ONLY,
                       coverage=None, asof=None, logger=None) -> pd.DataFrame:
    """Read a monthly CSV, cutting off its incomplete final month by default."""
    panel = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    if complete_months_only:
        panel.attrs["monthly_panel_name"] = Path(path).name
        result = drop_partial_final_month(panel, coverage=coverage, asof=asof, logger=logger)
        result.attrs.pop("monthly_panel_name", None)
        return result
    return _annotate(panel, source_asof(panel.index, coverage, asof), None, False)
