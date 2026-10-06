"""The supervision loop: launch, watch, recover, and know when to give up."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable

from .config import WatchdogConfig
from .process_control import ProcessControl
from .restart_tracker import RestartTracker

log = logging.getLogger(__name__)


class StopReason(Enum):
    CRASH_LOOP = "crash_loop"
    STARTUP_FAILED = "startup_failed"
    STOP_REQUESTED = "stop_requested"


class SessionEnd(Enum):
    EXITED = "exited"          # the process disappeared on its own
    RESTARTED = "restarted"    # a different PID appeared (relaunched by something else)
    MAX_RUNTIME = "max_runtime"
    STOP_REQUESTED = "stop_requested"


@dataclass
class Watchdog:
    config: WatchdogConfig
    processes: ProcessControl
    now: Callable[[], datetime] = datetime.now
    sleep: Callable[[float], None] = time.sleep
    should_stop: Callable[[], bool] = lambda: False
    tracker: RestartTracker = field(init=False)

    def __post_init__(self) -> None:
        self.tracker = RestartTracker(
            self.config.restart_threshold,
            timedelta(minutes=self.config.restart_window_minutes),
        )

    # -- public API ---------------------------------------------------------

    def run(self) -> StopReason:
        """Supervises the target until a crash loop or a stop request.

        This is a plain loop on purpose. The first version restarted itself by
        calling main() again, which grows the call stack on every cycle.
        """
        while True:
            pid = self.processes.find_pid(self.config.process_name)
            if pid is None:
                self.processes.launch(self.config.launch_command)
                pid = self._wait_for_start()
                if pid is None:
                    log.error("process did not start within %ss", self.config.startup_timeout_seconds)
                    return StopReason.STARTUP_FAILED

            end = self._monitor(pid)

            if end is SessionEnd.STOP_REQUESTED:
                return StopReason.STOP_REQUESTED

            if end is SessionEnd.MAX_RUNTIME:
                # Planned restart: not a failure, so it does not count toward a crash loop.
                log.info("max runtime reached, doing a clean restart")
                self.processes.stop(self.config.process_name, self.config.stop_timeout_seconds)
                self.sleep(self.config.relaunch_delay_seconds)
                continue

            # EXITED or RESTARTED: an unplanned restart.
            at = self.now()
            if self.tracker.record(at):
                log.critical(
                    "crash loop: %d restarts within %s min, stopping everything",
                    self.tracker.count(at),
                    self.config.restart_window_minutes,
                )
                self.processes.stop(self.config.process_name, self.config.stop_timeout_seconds)
                return StopReason.CRASH_LOOP

            log.warning(
                "unplanned restart (%s), %d in the last %s min",
                end.value,
                self.tracker.count(at),
                self.config.restart_window_minutes,
            )
            if end is SessionEnd.EXITED:
                self.sleep(self.config.relaunch_delay_seconds)

    # -- internals ----------------------------------------------------------

    def _wait_for_start(self) -> int | None:
        waited = 0.0
        while waited < self.config.startup_timeout_seconds:
            pid = self.processes.find_pid(self.config.process_name)
            if pid is not None:
                log.info("process running with pid %s", pid)
                return pid
            self.sleep(self.config.check_interval_seconds)
            waited += self.config.check_interval_seconds
        return None

    def _monitor(self, pid: int) -> SessionEnd:
        started = self.now()
        max_runtime = (
            timedelta(minutes=self.config.max_runtime_minutes)
            if self.config.max_runtime_minutes
            else None
        )
        while True:
            if self.should_stop():
                return SessionEnd.STOP_REQUESTED
            current = self.processes.find_pid(self.config.process_name)
            if current is None:
                log.warning("pid %s exited", pid)
                return SessionEnd.EXITED
            if current != pid:
                log.warning("pid changed %s -> %s", pid, current)
                return SessionEnd.RESTARTED
            if max_runtime and self.now() - started >= max_runtime:
                return SessionEnd.MAX_RUNTIME
            self.sleep(self.config.check_interval_seconds)
