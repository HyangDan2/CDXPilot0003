from __future__ import annotations

import argparse
import sys

from kosim.config import ConfigError, load_config, load_example_config
from kosim.pipeline import DailyPipelineRunner
from kosim.simulation.engine import RunEvent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KOSPI NXT signal sweep simulator")
    parser.add_argument("--config", default="config.yaml", help="Path to config YAML")
    parser.add_argument("--example", action="store_true", help="Run using config.example.yaml in mock mode")
    parser.add_argument("--gui", action="store_true", help="Launch PySide6 GUI")
    args = parser.parse_args(argv)

    if args.gui:
        from kosim.ui.main_window import launch

        return launch(args.config)

    try:
        config = load_example_config() if args.example else load_config(args.config)
        runner = DailyPipelineRunner(config, emit=_print_event)
        artifacts = runner.run()
        print(f"Simulation report: {artifacts.simulation_report_path}")
        return 0
    except (ConfigError, Exception) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _print_event(event: RunEvent) -> None:
    print(f"[{event.status.upper()}] {event.step}: {event.message}")


if __name__ == "__main__":
    raise SystemExit(main())
