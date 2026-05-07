from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from kosim.config import AppConfig
from kosim.data.calendar import parse_holidays, trading_days
from kosim.data.availability import recent_complete_days
from kosim.data.providers import create_market_data_provider
from kosim.data.storage import SQLiteStore
from kosim.data.universe import UniverseResolver
from kosim.reports.llm_client import OpenAICompatibleLLMClient
from kosim.reports.llm_prompt import build_llm_prompt
from kosim.reports.llm_bridge import llm_bridge_markdown
from kosim.reports.raw_markdown import raw_data_markdown
from kosim.reports.charts import case_chart_paths, generate_charts, summary_chart_paths
from kosim.reports.simulation_markdown import simulation_report_markdown
from kosim.reports.telegram import TelegramClient
from kosim.simulation.engine import RunEvent, SimulationResult, SweepSimulationEngine
from kosim.simulation.sweep import all_needed_futures_times, time_range


@dataclass
class PipelineArtifacts:
    result: SimulationResult
    raw_report_path: Path
    llm_bridge_path: Path
    simulation_report_path: Path
    llm_prompt_path: Path | None
    llm_report_path: Path | None
    chart_paths: list[Path]


EventCallback = Callable[[RunEvent], None]


class DailyPipelineRunner:
    STEPS = [
        "config_validation",
        "storage_availability_scan",
        "previous_trading_day_resolution",
        "universe_fetch",
        "nxt_raw_fetch",
        "futures_fetch",
        "raw_data_save",
        "telegram_raw_send",
        "sweep_simulation",
        "markdown_report_generation",
        "chart_generation",
        "llm_prompt_build",
        "llm_analysis",
        "telegram_llm_report_send",
        "completed",
    ]

    def __init__(self, config: AppConfig, emit: EventCallback | None = None):
        self.config = config
        self.emit = emit or (lambda event: None)

    def run(self) -> PipelineArtifacts:
        cfg = self.config.values
        self.emit(RunEvent("config_validation", "success", f"Loaded config from {self.config.path}"))

        provider = self._provider()
        holidays = parse_holidays(cfg.get("data", {}).get("holidays", []))
        store_cfg = cfg["data"]["storage"]
        store = SQLiteStore(store_cfg["path"]) if store_cfg.get("type") == "sqlite" else None
        if store is None:
            raise ValueError("Only sqlite storage is currently supported.")

        date_selection = cfg["simulation"].get("date_selection", {"mode": "date_range"})
        selection_mode = date_selection.get("mode", "date_range")
        resolver = UniverseResolver(provider, cfg["market"]["universe"], holidays)
        engine = SweepSimulationEngine(provider, resolver, cfg, store, self.emit)

        data_limitations: list[str] = []
        if selection_mode == "recent_complete_data_days":
            requested_days = int(date_selection.get("recent_complete_days", 30))
            self.emit(RunEvent("storage_availability_scan", "running", f"Scanning stored raw data for {requested_days} complete days"))
            selection = recent_complete_days(store, cfg, requested_days)
            if not selection.selected_dates:
                raise ValueError(
                    "No complete raw-data days found. Run date_range mode first to fetch/store raw data, "
                    "or import a raw data archive."
                )
            if len(selection.selected_dates) < requested_days:
                data_limitations.append(
                    f"Requested {requested_days} complete data days but only {len(selection.selected_dates)} were available."
                )
                self.emit(
                    RunEvent(
                        "storage_availability_scan",
                        "warning",
                        f"Only {len(selection.selected_dates)} complete data days available out of {requested_days} requested",
                    )
                )
            else:
                self.emit(
                    RunEvent(
                        "storage_availability_scan",
                        "success",
                        f"Selected {len(selection.selected_dates)} complete stored raw-data days",
                    )
                )
            raw_items = store.load_raw_data_many(selection.selected_dates)
            dates = selection.selected_dates
            result = engine.run_from_raw(raw_items)
        elif selection_mode == "stored_snapshots":
            dates = trading_days(
                cfg["simulation"]["date_range"]["start"],
                cfg["simulation"]["date_range"]["end"],
                holidays,
            )
            signal_times = [cfg["simulation"].get("historical_signal_time", "08:50")]
            exit_cfg = cfg["simulation"]["exit_sweep"]
            exit_times = time_range(exit_cfg["start"], exit_cfg["end"], int(exit_cfg["interval_minutes"]))
            futures_times = all_needed_futures_times(signal_times, exit_times)
            futures_symbol = cfg["market"]["futures"]["symbol"]
            raw_items = [
                raw
                for raw in (store.build_raw_from_snapshots(day, signal_times, futures_times, futures_symbol) for day in dates)
                if raw is not None
            ]
            if not raw_items:
                raise ValueError("No stored NXT/futures snapshots found for simulation date range.")
            dates = [raw.simulation_date for raw in raw_items]
            result = engine.run_from_raw(raw_items)
        else:
            dates = trading_days(
                cfg["simulation"]["date_range"]["start"],
                cfg["simulation"]["date_range"]["end"],
                holidays,
            )
            if not dates:
                raise ValueError("No trading dates in configured date range.")
            result = engine.run(dates)

        report_dir = Path(cfg["data"].get("report_output_dir", "reports"))
        report_dir.mkdir(parents=True, exist_ok=True)
        run_tag = f"{dates[0].isoformat()}_{dates[-1].isoformat()}"

        self.emit(RunEvent("markdown_report_generation", "running", "Generating markdown reports"))
        raw_path = report_dir / f"raw_data_{run_tag}.md"
        bridge_path = report_dir / f"llm_bridge_{run_tag}.md"
        sim_path = report_dir / f"simulation_report_{run_tag}.md"
        raw_path.write_text(raw_data_markdown(result, cfg), encoding="utf-8")
        bridge_path.write_text(llm_bridge_markdown(cfg, result), encoding="utf-8")
        sim_path.write_text(
            simulation_report_markdown(result, int(cfg.get("report", {}).get("markdown", {}).get("top_n_conditions", 20))),
            encoding="utf-8",
        )
        self.emit(RunEvent("markdown_report_generation", "success", f"Reports written to {report_dir}"))

        self.emit(RunEvent("chart_generation", "running", "Generating simulation charts"))
        chart_cfg = cfg.get("telegram", {}).get("charts", {})
        chart_dir = report_dir / "charts" / run_tag
        chart_paths = generate_charts(result, chart_dir, int(chart_cfg.get("case_chart_send_limit", 20)))
        self.emit(
            RunEvent(
                "chart_generation",
                "success" if chart_paths else "warning",
                f"Generated {len(chart_paths)} charts" if chart_paths else "No charts generated",
            )
        )

        telegram = TelegramClient(cfg.get("telegram", {}))
        delivery_cfg = cfg.get("telegram", {}).get("delivery", {})
        if delivery_cfg.get("send_raw_markdown_files", True):
            self.emit(RunEvent("telegram_raw_send", "running", "Sending raw data report to Telegram"))
            telegram.send_file(raw_path, "Raw data summary")
            if delivery_cfg.get("send_llm_bridge_file", False):
                telegram.send_file(bridge_path, "LLM bridge evidence")
            telegram.send_file(sim_path, "Simulation result markdown")
            self.emit(RunEvent("telegram_raw_send", "success" if telegram.enabled else "skipped", "Raw Telegram step finished"))
        if telegram.enabled and chart_paths:
            if chart_cfg.get("send_summary_charts", True):
                for path in summary_chart_paths(chart_paths):
                    telegram.send_photo(path, path.stem)
            if chart_cfg.get("send_case_charts", True):
                for path in case_chart_paths(chart_paths)[: int(chart_cfg.get("case_chart_send_limit", 20))]:
                    telegram.send_photo(path, path.stem)

        prompt_path: Path | None = None
        llm_report_path: Path | None = None
        if bool(cfg.get("llm", {}).get("enabled", False)):
            self.emit(RunEvent("llm_prompt_build", "running", "Building stateless LLM prompt"))
            prompt = build_llm_prompt(cfg, result, data_limitations=data_limitations or ["No known limitations reported by pipeline."])
            prompt_path = report_dir / f"llm_prompt_{run_tag}.txt"
            prompt_path.write_text(prompt, encoding="utf-8")
            self.emit(RunEvent("llm_prompt_build", "success", "LLM prompt written"))

            self.emit(RunEvent("llm_analysis", "running", "Calling Nvidia Nemotron-compatible endpoint"))
            llm_client = OpenAICompatibleLLMClient(cfg["llm"])
            llm_response = llm_client.analyze(prompt)
            llm_report_path = report_dir / f"llm_report_{run_tag}.md"
            llm_report_path.write_text(llm_response.content, encoding="utf-8")
            self.emit(RunEvent("llm_analysis", "success", f"LLM report generated by {llm_response.model}"))

            self.emit(RunEvent("telegram_llm_report_send", "running", "Sending LLM report to Telegram"))
            if cfg.get("telegram", {}).get("delivery", {}).get("send_llm_report_as_text", True):
                telegram.send_text_chunks(
                    llm_response.content,
                    int(cfg.get("telegram", {}).get("text", {}).get("chunk_size", 3500)),
                )
            if cfg.get("telegram", {}).get("delivery", {}).get("send_llm_report_file", False):
                telegram.send_file(llm_report_path, "LLM strategy report")
            self.emit(RunEvent("telegram_llm_report_send", "success" if telegram.enabled else "skipped", "LLM Telegram step finished"))
        else:
            self.emit(RunEvent("llm_prompt_build", "skipped", "LLM is disabled"))
            self.emit(RunEvent("llm_analysis", "skipped", "LLM is disabled"))
            self.emit(RunEvent("telegram_llm_report_send", "skipped", "LLM is disabled"))

        self.emit(RunEvent("completed", "success", "Pipeline completed"))
        return PipelineArtifacts(result, raw_path, bridge_path, sim_path, prompt_path, llm_report_path, chart_paths)

    def _provider(self):
        return create_market_data_provider(self.config.values)
