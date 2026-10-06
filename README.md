# process-watchdog

Keep a long-running process alive, and stop cleanly when it keeps crashing.

A watchdog that restarts a program forever hides real failures. This one recovers
from occasional crashes, but if the program crashes **3 times within 30 minutes**
it stops everything, logs why, and exits with a non-zero code so you notice.

```
2026-10-06 18:46:29 INFO     launching: worker.exe
2026-10-06 18:46:29 INFO     process running with pid 227
2026-10-06 18:46:30 WARNING  pid 227 exited
2026-10-06 18:46:30 WARNING  unplanned restart (exited), 1 in the last 30 min
...
2026-10-06 18:46:34 CRITICAL crash loop: 3 restarts within 30 min, stopping everything
2026-10-06 18:46:34 INFO     watchdog stopped: crash_loop
```

## Features

- **Crash-loop detection** with a sliding time window (threshold and window are configurable).
- **Graceful stop, then force:** every process gets `terminate()` and a timeout before `kill()`.
- **Planned restarts:** optional maximum runtime per session for programs that degrade
  over time. Planned restarts don't count as crashes.
- **Adopts a running process** instead of launching a second copy.
- **External restarts are detected** (a new PID means something else relaunched it).
- **Everything is logged** to the console and a file, including uncaught exceptions.
- **Clean shutdown** on Ctrl+C / SIGTERM.
- Cross-platform (Windows, Linux, macOS) through `psutil`.

## Usage

```bash
pip install .
cp config.example.yaml watchdog.yaml   # edit it
process-watchdog --config watchdog.yaml
```

| Exit code | Meaning |
|---|---|
| 0 | Stopped on request (Ctrl+C / SIGTERM) |
| 1 | Invalid configuration |
| 2 | Crash loop detected |
| 3 | The process never started |

## Configuration

```yaml
process_name: worker.exe             # exact process name to watch
launch_command: [C:/apps/worker.exe, --headless]
restart_threshold: 3                 # crashes...
restart_window_minutes: 30           # ...within this window = crash loop
max_runtime_minutes: 150             # optional planned restart (omit to disable)
check_interval_seconds: 1
startup_timeout_seconds: 60
stop_timeout_seconds: 5              # wait after terminate() before kill()
relaunch_delay_seconds: 30
log_file: watchdog.log               # null to log only to the console
```

Unknown keys and invalid values are rejected at startup with a clear message,
so a typo can't silently fall back to a default.

## Design

```
src/watchdog_tool/
  restart_tracker.py   pure sliding-window logic, no I/O
  config.py            YAML loading and validation
  process_control.py   the only module that touches real processes (psutil)
  watchdog.py          the supervision loop
  __main__.py          CLI, logging, signal handling
```

The loop receives the process layer, the clock and `sleep` as dependencies.
Tests replace them with a fake process and a fake clock, so hours of crashes and
restarts are simulated in milliseconds without starting real programs.

```bash
pip install -e ".[dev]"
pytest
```

## Background: version 1

This is a rewrite of a watchdog I wrote while learning Python. It kept an
automation system running 24/7 for years across about 20 instances. Rewriting it
fixed what I would now do differently:

| Version 1 | Version 2 |
|---|---|
| One copy of the script per machine, values hardcoded | One package, one YAML config per deployment |
| Restarted by calling `main()` again, so the call stack grew on every cycle | A plain `while` loop |
| Substring name match (`"game"` also matched `"gamelauncher.exe"`) | Exact, case-insensitive match |
| Launched processes were never reaped and lingered as zombies | Children are polled and reaped |
| Errors printed to a console that might be closed | Structured logging to console and file |
| Tested by running it and watching | 24 automated tests with a fake clock |

The sliding-window crash detection and the terminate-then-kill escalation come
straight from version 1; they worked and were kept.

## License

MIT
