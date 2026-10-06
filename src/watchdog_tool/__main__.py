"""Command line entry point: ``python -m watchdog_tool --config watchdog.yaml``."""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from .config import ConfigError, load_config
from .process_control import SystemProcessControl
from .watchdog import StopReason, Watchdog

EXIT_CODES = {
    StopReason.STOP_REQUESTED: 0,
    StopReason.CRASH_LOOP: 2,
    StopReason.STARTUP_FAILED: 3,
}


def setup_logging(log_file: str | None, verbose: bool) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
        handlers=handlers,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Keep a process running and stop on crash loops.")
    parser.add_argument("--config", default="watchdog.yaml", help="path to the YAML config")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 1

    setup_logging(config.log_file, args.verbose)
    log = logging.getLogger("watchdog_tool")

    # Any uncaught error ends up in the log file instead of a closed console.
    def log_uncaught(exc_type, value, tb):
        log.critical("uncaught exception", exc_info=(exc_type, value, tb))

    sys.excepthook = log_uncaught

    stop_requested = False

    def request_stop(signum, frame):
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    watchdog = Watchdog(config, SystemProcessControl(), should_stop=lambda: stop_requested)
    reason = watchdog.run()
    log.info("watchdog stopped: %s", reason.value)
    return EXIT_CODES[reason]


if __name__ == "__main__":
    sys.exit(main())
