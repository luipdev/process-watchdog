"""Keep a long-running process alive, and stop cleanly when it keeps crashing."""

from .config import ConfigError, WatchdogConfig, load_config, parse_config
from .restart_tracker import RestartTracker
from .watchdog import StopReason, Watchdog

__all__ = [
    "ConfigError",
    "RestartTracker",
    "StopReason",
    "Watchdog",
    "WatchdogConfig",
    "load_config",
    "parse_config",
]
__version__ = "2.0.0"
