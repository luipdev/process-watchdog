from datetime import datetime, timedelta

import pytest

from watchdog_tool import RestartTracker

T0 = datetime(2026, 1, 1, 12, 0, 0)
WINDOW = timedelta(minutes=30)


def test_below_threshold_is_not_a_crash_loop():
    tracker = RestartTracker(3, WINDOW)
    assert tracker.record(T0) is False
    assert tracker.record(T0 + timedelta(minutes=5)) is False


def test_threshold_inside_window_is_a_crash_loop():
    tracker = RestartTracker(3, WINDOW)
    tracker.record(T0)
    tracker.record(T0 + timedelta(minutes=10))
    assert tracker.record(T0 + timedelta(minutes=20)) is True


def test_old_restarts_expire_from_the_window():
    tracker = RestartTracker(3, WINDOW)
    tracker.record(T0)
    tracker.record(T0 + timedelta(minutes=10))
    # 35 minutes later the first restart is outside the 30-minute window
    assert tracker.record(T0 + timedelta(minutes=35)) is False
    assert tracker.count(T0 + timedelta(minutes=35)) == 2


def test_restart_exactly_at_window_edge_still_counts():
    tracker = RestartTracker(2, WINDOW)
    tracker.record(T0)
    assert tracker.record(T0 + WINDOW) is True


def test_reset_clears_history():
    tracker = RestartTracker(2, WINDOW)
    tracker.record(T0)
    tracker.reset()
    assert tracker.record(T0 + timedelta(seconds=1)) is False


@pytest.mark.parametrize("threshold,window", [(0, WINDOW), (3, timedelta(0))])
def test_invalid_arguments(threshold, window):
    with pytest.raises(ValueError):
        RestartTracker(threshold, window)
