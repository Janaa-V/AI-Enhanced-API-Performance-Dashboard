"""Verify the time window every metrics query filters by."""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.metrics import TimeWindow

END = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)


def test_a_window_ends_at_the_given_time_and_reaches_back_the_given_minutes() -> None:
    window = TimeWindow.ending_at(END, 60)
    assert (window.start, window.end) == (END - timedelta(hours=1), END)
    assert window.minutes == 60


def test_naive_bounds_are_rejected() -> None:
    """The database would read a naive time in its own time zone and shift the window."""
    with pytest.raises(ValueError, match="timezone-aware"):
        TimeWindow.ending_at(END.replace(tzinfo=None), 60)


def test_an_empty_or_reversed_window_is_rejected() -> None:
    with pytest.raises(ValueError, match="before its end"):
        TimeWindow(start=END, end=END)
