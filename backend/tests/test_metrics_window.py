"""Verify the time window every metrics query filters by, and how it splits into buckets."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.metrics import TimeWindow, bucket_starts, fill_buckets

END = datetime(2026, 9, 27, 10, 0, tzinfo=UTC)
FIVE_MINUTES = timedelta(minutes=5)


def at(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 9, 27, hour, minute, second, tzinfo=UTC)


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


def test_buckets_align_to_round_clock_times_not_to_the_window_start() -> None:
    window = TimeWindow(start=at(9, 2, 37), end=at(10, 2, 37))
    starts = bucket_starts(window, FIVE_MINUTES)
    assert starts[0] == at(9, 0)  # before the window start; clipped when filled
    assert starts[-1] == at(10, 0)
    assert len(starts) == 13
    assert all(b - a == FIVE_MINUTES for a, b in zip(starts, starts[1:], strict=False))


def test_a_window_starting_on_a_boundary_has_no_partial_first_bucket() -> None:
    starts = bucket_starts(TimeWindow(start=at(9, 0), end=at(10, 0)), FIVE_MINUTES)
    assert (starts[0], starts[-1], len(starts)) == (at(9, 0), at(9, 55), 12)


def test_a_window_shorter_than_a_bucket_has_one_bucket() -> None:
    assert bucket_starts(TimeWindow(start=at(10, 1), end=at(10, 3)), FIVE_MINUTES) == [at(10, 0)]


def test_a_non_positive_bucket_is_rejected() -> None:
    """A zero-size bucket would loop forever."""
    with pytest.raises(ValueError, match="positive"):
        bucket_starts(TimeWindow.ending_at(END, 60), timedelta(0))


def test_filled_buckets_are_clipped_to_the_window_and_empty_ones_are_null() -> None:
    window = TimeWindow(start=at(9, 2, 37), end=at(9, 12, 37))
    row = SimpleNamespace(
        total_requests=4, server_errors=1, client_errors=0, avg_latency_ms=50.0, p95_latency_ms=90.0
    )
    first, middle, last = fill_buckets(window, FIVE_MINUTES, {at(9, 5): row})  # type: ignore[dict-item]
    assert (first.start, first.end) == (at(9, 2, 37), at(9, 5))
    assert (last.start, last.end) == (at(9, 10), at(9, 12, 37))
    assert (middle.total_requests, middle.error_rate) == (4, 0.25)
    assert (first.total_requests, first.avg_latency_ms, first.error_rate) == (0, None, None)


def test_a_database_bucket_outside_the_list_fails_loudly_instead_of_vanishing() -> None:
    row = SimpleNamespace(
        total_requests=1, server_errors=0, client_errors=0, avg_latency_ms=1.0, p95_latency_ms=1.0
    )
    misaligned = at(9, 7)  # what a different origin would produce
    with pytest.raises(RuntimeError, match="not in the window's buckets"):
        fill_buckets(TimeWindow.ending_at(END, 60), FIVE_MINUTES, {misaligned: row})  # type: ignore[dict-item]
