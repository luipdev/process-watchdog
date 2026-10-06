"""Sliding-window counter that tells a normal restart from a crash loop."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta


class RestartTracker:
    """Counts unplanned restarts inside a moving time window.

    A single crash is normal and should be recovered from. Several crashes in a
    short time mean something is really broken, and restarting again only hides
    the problem. ``record`` returns True once that point is reached.
    """

    def __init__(self, threshold: int, window: timedelta) -> None:
        if threshold < 1:
            raise ValueError("threshold must be at least 1")
        if window <= timedelta(0):
            raise ValueError("window must be positive")
        self.threshold = threshold
        self.window = window
        self._events: deque[datetime] = deque()

    def _expire(self, now: datetime) -> None:
        cutoff = now - self.window
        while self._events and self._events[0] < cutoff:
            self._events.popleft()

    def record(self, now: datetime) -> bool:
        """Register a restart at ``now``. Returns True if this is a crash loop."""
        self._events.append(now)
        self._expire(now)
        return len(self._events) >= self.threshold

    def count(self, now: datetime) -> int:
        """Number of restarts still inside the window at ``now``."""
        self._expire(now)
        return len(self._events)

    def reset(self) -> None:
        self._events.clear()
