import pytest

from watchdog_tool import ConfigError, load_config, parse_config

MINIMAL = {"process_name": "worker.exe", "launch_command": "worker.exe"}


def test_minimal_config_uses_defaults():
    cfg = parse_config(MINIMAL)
    assert cfg.launch_command == ["worker.exe"]
    assert cfg.restart_threshold == 3
    assert cfg.restart_window_minutes == 30
    assert cfg.max_runtime_minutes is None


def test_command_list_is_kept():
    cfg = parse_config({**MINIMAL, "launch_command": ["python", "bot.py", "--fast"]})
    assert cfg.launch_command == ["python", "bot.py", "--fast"]


@pytest.mark.parametrize(
    "override",
    [
        {"process_name": ""},
        {"launch_command": 42},
        {"restart_threshold": 0},
        {"restart_threshold": 2.5},
        {"restart_window_minutes": -1},
        {"max_runtime_minutes": 0},
        {"relaunch_delay_seconds": -5},
        {"typo_key": 1},
    ],
)
def test_invalid_values_are_rejected(override):
    with pytest.raises(ConfigError):
        parse_config({**MINIMAL, **override})


def test_load_config_from_yaml(tmp_path):
    path = tmp_path / "watchdog.yaml"
    path.write_text(
        "process_name: worker.exe\n"
        "launch_command: [worker.exe, --headless]\n"
        "max_runtime_minutes: 150\n",
        encoding="utf-8",
    )
    cfg = load_config(path)
    assert cfg.max_runtime_minutes == 150
    assert cfg.launch_command == ["worker.exe", "--headless"]


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.yaml")
