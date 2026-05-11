from pathlib import Path

import yaml

from kosim.scheduler import install_launchd, run_once, scheduler_status


def test_scheduler_disabled_run_once_skips(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    values = yaml.safe_load(Path("config.example.yaml").read_text(encoding="utf-8"))
    values["schedule"]["enabled"] = False
    values["schedule"]["state_file"] = str(tmp_path / "scheduler_state.json")
    values["schedule"]["lock_file"] = str(tmp_path / "scheduler.lock")
    config_path.write_text(yaml.safe_dump(values, allow_unicode=True, sort_keys=False), encoding="utf-8")

    result = run_once(config_path, no_delay=True)

    assert result.status == "skipped"
    assert result.state_path.exists()


def test_scheduler_status_reports_configured_times(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    values = yaml.safe_load(Path("config.example.yaml").read_text(encoding="utf-8"))
    values["schedule"]["run_times"] = ["08:50", "12:50", "16:50", "20:50"]
    config_path.write_text(yaml.safe_dump(values, allow_unicode=True, sort_keys=False), encoding="utf-8")

    status = scheduler_status(config_path)

    assert status["run_times"] == ["08:50", "12:50", "16:50", "20:50"]
    assert status["startup_delay_seconds"] == 30


def test_install_launchd_dry_run_does_not_write_plist(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    values = yaml.safe_load(Path("config.example.yaml").read_text(encoding="utf-8"))
    config_path.write_text(yaml.safe_dump(values, allow_unicode=True, sort_keys=False), encoding="utf-8")

    plist_path = install_launchd(config_path, dry_run=True)

    assert plist_path.name == "com.kosim.scheduler.plist"
