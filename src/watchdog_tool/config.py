"""Loads and validates the watchdog configuration from a YAML file."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    """Raised when the configuration file is missing values or has invalid ones."""


@dataclass(frozen=True)
class WatchdogConfig:
    process_name: str
    launch_command: list[str]
    restart_threshold: int = 3
    restart_window_minutes: float = 30
    max_runtime_minutes: float | None = None
    check_interval_seconds: float = 1.0
    startup_timeout_seconds: float = 60.0
    stop_timeout_seconds: float = 5.0
    relaunch_delay_seconds: float = 30.0
    log_file: str | None = "watchdog.log"


_POSITIVE_NUMBERS = (
    "restart_window_minutes",
    "check_interval_seconds",
    "startup_timeout_seconds",
    "stop_timeout_seconds",
)


def parse_config(data: dict[str, Any]) -> WatchdogConfig:
    """Builds a config from a plain dict, rejecting unknown or invalid keys."""
    if not isinstance(data, dict):
        raise ConfigError("configuration must be a mapping of keys to values")

    known = set(WatchdogConfig.__dataclass_fields__)
    unknown = set(data) - known
    if unknown:
        raise ConfigError(f"unknown keys: {', '.join(sorted(unknown))}")

    for required in ("process_name", "launch_command"):
        if not data.get(required):
            raise ConfigError(f"'{required}' is required")

    command = data["launch_command"]
    if isinstance(command, str):
        command = [command]
    if not isinstance(command, list) or not all(isinstance(p, str) for p in command):
        raise ConfigError("'launch_command' must be a string or a list of strings")

    values = {**data, "launch_command": command}

    for key in _POSITIVE_NUMBERS:
        if key in values and not (isinstance(values[key], (int, float)) and values[key] > 0):
            raise ConfigError(f"'{key}' must be a positive number")

    threshold = values.get("restart_threshold", 3)
    if not isinstance(threshold, int) or threshold < 1:
        raise ConfigError("'restart_threshold' must be an integer of at least 1")

    max_runtime = values.get("max_runtime_minutes")
    if max_runtime is not None and not (isinstance(max_runtime, (int, float)) and max_runtime > 0):
        raise ConfigError("'max_runtime_minutes' must be positive or omitted")

    delay = values.get("relaunch_delay_seconds", 30.0)
    if not isinstance(delay, (int, float)) or delay < 0:
        raise ConfigError("'relaunch_delay_seconds' must be zero or more")

    return WatchdogConfig(**values)


def load_config(path: str | Path) -> WatchdogConfig:
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return parse_config(data)
