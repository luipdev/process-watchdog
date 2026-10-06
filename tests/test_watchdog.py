"""Runs the supervision loop against a scripted fake process and a fake clock."""

from datetime import datetime, timedelta

from watchdog_tool import StopReason, Watchdog, parse_config


class FakeClock:
    def __init__(self):
        self.t = datetime(2026, 1, 1, 0, 0, 0)

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.t += timedelta(seconds=seconds)


class FakeProcesses:
    """Each launch starts a process that lives for the next value in `lifetimes`.

    A lifetime of None means it never exits on its own.
    """

    def __init__(self, clock, lifetimes):
        self.clock = clock
        self.lifetimes = list(lifetimes)
        self.pid = None
        self.dies_at = None
        self.next_pid = 100
        self.launches = 0
        self.stops = 0

    def find_pid(self, name):
        if self.pid is not None and self.dies_at is not None and self.clock.now() >= self.dies_at:
            self.pid = None
        return self.pid

    def launch(self, command):
        self.launches += 1
        self.pid = self.next_pid
        self.next_pid += 1
        life = self.lifetimes.pop(0) if self.lifetimes else None
        self.dies_at = None if life is None else self.clock.now() + timedelta(seconds=life)

    def stop(self, name, timeout):
        self.stops += 1
        self.pid = None


def make(lifetimes, **overrides):
    clock = FakeClock()
    procs = FakeProcesses(clock, lifetimes)
    cfg = parse_config({"process_name": "w", "launch_command": "w", "relaunch_delay_seconds": 30, **overrides})
    return Watchdog(cfg, procs, now=clock.now, sleep=clock.sleep), procs, clock


def test_three_quick_crashes_stop_the_watchdog():
    wd, procs, _ = make([60, 60, 60, 60])
    assert wd.run() is StopReason.CRASH_LOOP
    assert procs.launches == 3
    assert procs.stops == 1


def test_crashes_spread_out_are_recovered_from():
    # Each run lasts 20 minutes, so a 30-minute window never holds 3 crashes.
    # The 4th process never dies; we stop by asking after enough loops.
    clock = FakeClock()
    procs = FakeProcesses(clock, [1200, 1200, 1200, 1200, 1200, None])
    cfg = parse_config({"process_name": "w", "launch_command": "w", "relaunch_delay_seconds": 30})
    stop_after = datetime(2026, 1, 1, 3, 0, 0)
    wd = Watchdog(cfg, procs, now=clock.now, sleep=clock.sleep, should_stop=lambda: clock.now() >= stop_after)
    assert wd.run() is StopReason.STOP_REQUESTED
    assert procs.launches == 6


def test_max_runtime_restart_is_not_counted_as_a_crash():
    clock = FakeClock()
    procs = FakeProcesses(clock, [None] * 10)
    cfg = parse_config(
        {"process_name": "w", "launch_command": "w", "max_runtime_minutes": 1, "relaunch_delay_seconds": 1}
    )
    stop_after = datetime(2026, 1, 1, 0, 10, 0)
    wd = Watchdog(cfg, procs, now=clock.now, sleep=clock.sleep, should_stop=lambda: clock.now() >= stop_after)
    assert wd.run() is StopReason.STOP_REQUESTED
    assert procs.launches >= 5          # several planned restarts
    assert wd.tracker.count(clock.now()) == 0


def test_process_that_never_starts():
    class NeverStarts(FakeProcesses):
        def launch(self, command):
            self.launches += 1

    clock = FakeClock()
    procs = NeverStarts(clock, [])
    cfg = parse_config({"process_name": "w", "launch_command": "w", "startup_timeout_seconds": 5})
    wd = Watchdog(cfg, procs, now=clock.now, sleep=clock.sleep)
    assert wd.run() is StopReason.STARTUP_FAILED


def test_already_running_process_is_adopted_not_relaunched():
    wd, procs, clock = make([])
    procs.pid = 42  # something already running before the watchdog started
    stop_after = clock.now() + timedelta(seconds=10)
    wd.should_stop = lambda: clock.now() >= stop_after
    assert wd.run() is StopReason.STOP_REQUESTED
    assert procs.launches == 0
