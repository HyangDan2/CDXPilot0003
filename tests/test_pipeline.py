from pathlib import Path

import yaml

from kosim.config import AppConfig
from kosim.pipeline import DailyPipelineRunner


def test_pipeline_runs_in_mock_mode(tmp_path: Path):
    config = yaml.safe_load(Path("config.example.yaml").read_text(encoding="utf-8"))
    config["simulation"]["date_range"] = {"start": "2026-05-07", "end": "2026-05-08"}
    config["data"]["storage"]["path"] = str(tmp_path / "market.sqlite3")
    config["data"]["report_output_dir"] = str(tmp_path / "reports")
    config["telegram"]["enabled"] = False
    config["llm"]["enabled"] = False

    events = []
    runner = DailyPipelineRunner(AppConfig(path=tmp_path / "config.yaml", values=config), emit=events.append)
    artifacts = runner.run()

    assert artifacts.simulation_report_path.exists()
    assert artifacts.raw_report_path.exists()
    assert artifacts.result.metrics
    assert any(event.step == "completed" and event.status == "success" for event in events)


def test_pipeline_runs_recent_complete_data_mode(tmp_path: Path):
    config = yaml.safe_load(Path("config.example.yaml").read_text(encoding="utf-8"))
    config["simulation"]["date_range"] = {"start": "2026-05-07", "end": "2026-05-08"}
    config["data"]["storage"]["path"] = str(tmp_path / "market.sqlite3")
    config["data"]["report_output_dir"] = str(tmp_path / "reports")
    config["telegram"]["enabled"] = False
    config["llm"]["enabled"] = False

    first = DailyPipelineRunner(AppConfig(path=tmp_path / "config.yaml", values=config))
    first.run()

    config["simulation"]["date_selection"] = {"mode": "recent_complete_data_days", "recent_complete_days": 1}
    events = []
    second = DailyPipelineRunner(AppConfig(path=tmp_path / "config.yaml", values=config), emit=events.append)
    artifacts = second.run()

    assert len(artifacts.result.raw_data) == 1
    assert any(event.step == "storage_availability_scan" and event.status == "success" for event in events)
