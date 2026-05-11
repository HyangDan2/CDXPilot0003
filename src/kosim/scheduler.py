from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from kosim.config import AppConfig, load_config
from kosim.pipeline import DailyPipelineRunner


LABEL = "com.kosim.scheduler"
DEFAULT_RUN_TIMES = ["08:50", "12:50", "16:50", "20:50"]


@dataclass
class SchedulerResult:
    status: str
    message: str
    state_path: Path
    report_path: Path | None = None


def default_schedule_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "timezone": "Asia/Seoul",
        "run_times": list(DEFAULT_RUN_TIMES),
        "startup_delay_seconds": 30,
        "skip_if_running": True,
        "lock_file": "data/scheduler.lock",
        "state_file": "data/scheduler_state.json",
        "log_dir": "logs",
    }


def run_once(config_path: str | Path = "config.yaml", force: bool = False, no_delay: bool = False) -> SchedulerResult:
    config = load_config(config_path)
    schedule = _schedule(config.values)
    state_path = Path(schedule["state_file"])
    if not force and not bool(schedule.get("enabled", False)):
        result = SchedulerResult("skipped", "Scheduler is disabled by config.", state_path)
        _write_state(schedule, result.status, result.message)
        return result

    delay = int(schedule.get("startup_delay_seconds", 30))
    if delay > 0 and not no_delay:
        time.sleep(delay)

    lock_path = Path(schedule["lock_file"])
    with _scheduler_lock(lock_path, bool(schedule.get("skip_if_running", True))) as acquired:
        if not acquired:
            result = SchedulerResult("skipped", "Another scheduler job is already running.", state_path)
            _write_state(schedule, result.status, result.message)
            return result

        _write_state(schedule, "running", "Scheduler job started.")
        try:
            artifacts = DailyPipelineRunner(config).run()
            result = SchedulerResult(
                "success",
                "Scheduler job completed.",
                state_path,
                artifacts.simulation_report_path,
            )
            _write_state(schedule, result.status, result.message, report_path=artifacts.simulation_report_path)
            return result
        except Exception as exc:
            result = SchedulerResult("failed", str(exc), state_path)
            _write_state(schedule, result.status, result.message)
            return result


def install_launchd(config_path: str | Path = "config.yaml", dry_run: bool = False) -> Path:
    config = load_config(config_path)
    schedule = _schedule(config.values)
    log_dir = Path(schedule["log_dir"]).expanduser().resolve()
    log_dir.mkdir(parents=True, exist_ok=True)

    plist_path = launchd_plist_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    config_abs = Path(config_path).expanduser().resolve()
    cwd = Path.cwd().resolve()
    env = {"PYTHONPATH": str(cwd / "src")}
    plist = {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            "-m",
            "kosim.scheduler",
            "run-once",
            "--config",
            str(config_abs),
        ],
        "WorkingDirectory": str(cwd),
        "EnvironmentVariables": env,
        "StartCalendarInterval": [_calendar_interval(time_value) for time_value in schedule["run_times"]],
        "StandardOutPath": str(log_dir / "scheduler.out.log"),
        "StandardErrorPath": str(log_dir / "scheduler.err.log"),
    }

    if dry_run:
        return plist_path

    with plist_path.open("wb") as handle:
        plistlib.dump(plist, handle)
    _launchctl_unload(plist_path)
    _launchctl_load(plist_path)
    return plist_path


def uninstall_launchd() -> Path:
    plist_path = launchd_plist_path()
    _launchctl_unload(plist_path)
    if plist_path.exists():
        plist_path.unlink()
    return plist_path


def scheduler_status(config_path: str | Path = "config.yaml") -> dict[str, Any]:
    config = load_config(config_path)
    schedule = _schedule(config.values)
    state_path = Path(schedule["state_file"])
    state: dict[str, Any] = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {"state_error": f"Invalid JSON in {state_path}"}
    plist_path = launchd_plist_path()
    return {
        "enabled": bool(schedule.get("enabled", False)),
        "run_times": schedule.get("run_times", DEFAULT_RUN_TIMES),
        "startup_delay_seconds": int(schedule.get("startup_delay_seconds", 30)),
        "launchd_installed": plist_path.exists(),
        "launchd_plist_path": str(plist_path),
        "state_file": str(state_path),
        "state": state,
    }


def launchd_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _schedule(values: dict[str, Any]) -> dict[str, Any]:
    schedule = default_schedule_config()
    schedule.update(values.get("schedule") or {})
    schedule["run_times"] = [str(item) for item in schedule.get("run_times") or DEFAULT_RUN_TIMES]
    return schedule


def _calendar_interval(time_value: str) -> dict[str, int]:
    hour_text, minute_text = time_value.split(":", 1)
    return {"Hour": int(hour_text), "Minute": int(minute_text)}


class _scheduler_lock:
    def __init__(self, path: Path, skip_if_running: bool):
        self.path = path
        self.skip_if_running = skip_if_running
        self.acquired = False

    def __enter__(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and _lock_is_stale(self.path):
            self.path.unlink(missing_ok=True)
        payload = json.dumps({"pid": os.getpid(), "started_at": _now_iso()}, ensure_ascii=False)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if self.skip_if_running:
                return False
            raise RuntimeError(f"Scheduler lock already exists: {self.path}")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        self.acquired = True
        return True

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)


def _lock_is_stale(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        pid = int(payload.get("pid", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return True
    if pid <= 0:
        return True
    if not _pid_exists(pid):
        return True
    return time.time() - path.stat().st_mtime > 24 * 60 * 60


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _write_state(schedule: dict[str, Any], status: str, message: str, report_path: Path | None = None) -> None:
    path = Path(schedule["state_file"])
    path.parent.mkdir(parents=True, exist_ok=True)
    previous: dict[str, Any] = {}
    if path.exists():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
    state = {
        **previous,
        "last_status": status,
        "last_message": message,
        "last_updated_at": _now_iso(),
        "last_report": str(report_path) if report_path else previous.get("last_report"),
    }
    if status == "running":
        state["last_started_at"] = state["last_updated_at"]
        state["last_finished_at"] = None
        state["last_error"] = None
    elif status in {"success", "failed", "skipped"}:
        state["last_finished_at"] = state["last_updated_at"]
        state["last_error"] = message if status == "failed" else None
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _launchctl_load(plist_path: Path) -> None:
    subprocess.run(["launchctl", "load", "-w", str(plist_path)], check=True)


def _launchctl_unload(plist_path: Path) -> None:
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", "-w", str(plist_path)], check=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KOSPI NXT simulator scheduler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-once")
    run_parser.add_argument("--config", default="config.yaml")
    run_parser.add_argument("--force", action="store_true")
    run_parser.add_argument("--no-delay", action="store_true")

    install_parser = subparsers.add_parser("install-launchd")
    install_parser.add_argument("--config", default="config.yaml")
    install_parser.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("uninstall-launchd")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--config", default="config.yaml")

    args = parser.parse_args(argv)
    if args.command == "run-once":
        result = run_once(args.config, force=args.force, no_delay=args.no_delay)
        print(f"{result.status}: {result.message}")
        if result.report_path:
            print(f"report: {result.report_path}")
        return 0 if result.status in {"success", "skipped"} else 1
    if args.command == "install-launchd":
        plist_path = install_launchd(args.config, dry_run=args.dry_run)
        print(f"launchd plist: {plist_path}")
        return 0
    if args.command == "uninstall-launchd":
        plist_path = uninstall_launchd()
        print(f"removed launchd plist: {plist_path}")
        return 0
    if args.command == "status":
        print(json.dumps(scheduler_status(args.config), ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
