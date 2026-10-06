"""Thin wrappers around psutil/subprocess so the watchdog logic stays testable."""

from __future__ import annotations

import logging
import subprocess
from typing import Protocol

import psutil

log = logging.getLogger(__name__)


class ProcessControl(Protocol):
    def find_pid(self, name: str) -> int | None: ...
    def launch(self, command: list[str]) -> None: ...
    def stop(self, name: str, timeout: float) -> int: ...


def _matches(proc: psutil.Process, name: str) -> bool:
    """Exact, case-insensitive name match that ignores dead (zombie) processes.

    The first version used a substring match, so "game" also matched
    "gamelauncher.exe". Exact matching avoids stopping the wrong program.
    """
    if proc.info.get("status") == psutil.STATUS_ZOMBIE:
        return False
    proc_name = (proc.info.get("name") or "").lower()
    return proc_name == name.lower()


class SystemProcessControl:
    """Real implementation used in production."""

    def __init__(self) -> None:
        self._children: list[subprocess.Popen] = []

    def _reap_children(self) -> None:
        # Collect exit codes of processes we launched so they don't linger as zombies.
        self._children = [c for c in self._children if c.poll() is None]

    def find_pid(self, name: str) -> int | None:
        self._reap_children()
        for proc in psutil.process_iter(["pid", "name", "status"]):
            if _matches(proc, name):
                return proc.info["pid"]
        return None

    def launch(self, command: list[str]) -> None:
        log.info("launching: %s", " ".join(command))
        self._children.append(subprocess.Popen(command))  # noqa: S603 - command comes from the user's own config

    def stop(self, name: str, timeout: float) -> int:
        """Asks every matching process to exit, then kills the ones that don't.

        Returns how many processes were stopped.
        """
        targets = [p for p in psutil.process_iter(["pid", "name", "status"]) if _matches(p, name)]
        for proc in targets:
            try:
                proc.terminate()
            except psutil.NoSuchProcess:
                pass
            except psutil.AccessDenied:
                log.warning("access denied terminating pid %s", proc.pid)

        _, alive = psutil.wait_procs(targets, timeout=timeout)
        for proc in alive:
            log.warning("pid %s ignored terminate after %ss, killing it", proc.pid, timeout)
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                log.error("could not kill pid %s: %s", proc.pid, exc)
        self._reap_children()
        return len(targets)
