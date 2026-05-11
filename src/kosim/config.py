from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid."""


SECRET_PLACEHOLDERS = {
    "YOUR_KIS_APP_KEY",
    "YOUR_KIS_APP_SECRET",
    "YOUR_TELEGRAM_BOT_TOKEN",
    "YOUR_TELEGRAM_CHAT_ID",
    "YOUR_NVIDIA_API_KEY",
    "YOUR_LLM_API_KEY",
}


@dataclass(frozen=True)
class AppConfig:
    path: Path
    values: dict[str, Any]

    def get(self, dotted_path: str, default: Any = None) -> Any:
        value: Any = self.values
        for part in dotted_path.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        example = Path("config.example.yaml")
        hint = f" Copy {example} to {config_path} and fill private values." if example.exists() else ""
        raise ConfigError(f"Config file not found: {config_path}.{hint}")

    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ConfigError("Root config must be a YAML mapping.")

    raw = normalize_config(raw)
    validate_config(raw)
    return AppConfig(path=config_path, values=raw)


def load_example_config(path: str | Path = "config.example.yaml") -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ConfigError("Root config must be a YAML mapping.")
    raw = normalize_config(raw)
    validate_config(raw, allow_placeholders=True)
    return AppConfig(path=config_path, values=raw)


def normalize_config(values: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(values)

    app = normalized.setdefault("app", {})
    if app.get("mode") == "live":
        app["mode"] = "kis_rest"

    simulation = normalized.setdefault("simulation", {})
    legacy_condition = simulation.get("signal_condition")
    if legacy_condition and not simulation.get("signal_conditions"):
        condition = dict(legacy_condition)
        condition.setdefault("name", condition.get("rule", "signal_condition"))
        simulation["signal_conditions"] = [condition]
    if not simulation.get("strategy_conditions"):
        simulation["strategy_conditions"] = _default_strategy_conditions(simulation.get("signal_conditions", []))

    llm = normalized.setdefault("llm", {})
    budget = llm.setdefault("context_budget", {})
    if "max_bridge_chars" not in budget and "max_raw_summary_chars" in budget:
        budget["max_bridge_chars"] = budget["max_raw_summary_chars"]
    queue = llm.setdefault("queue", {})
    queue.setdefault("enabled", True)
    queue.setdefault("stateless_per_condition", True)
    queue.setdefault("max_items", 6)
    queue.setdefault("send_final_summary", False)
    queue.setdefault("include_empty_results", False)

    telegram = normalized.setdefault("telegram", {})
    telegram_queue = telegram.setdefault("queue", {})
    telegram_queue.setdefault("send_only_llm_queue_items", True)
    telegram_queue.setdefault("send_condition_charts", True)
    telegram_queue.setdefault("max_condition_charts", 3)

    schedule = _default_schedule_config()
    schedule.update(normalized.get("schedule") or {})
    normalized["schedule"] = schedule

    return normalized


def validate_config(values: dict[str, Any], allow_placeholders: bool = False) -> None:
    required = [
        "app.timezone",
        "market.universe.top_n",
        "market.nxt.signal_times",
        "market.futures.symbol",
        "simulation.date_range.start",
        "simulation.date_range.end",
        "simulation.exit_sweep.start",
        "simulation.exit_sweep.end",
        "simulation.exit_sweep.interval_minutes",
        "llm.temperature",
        "llm.timeout_seconds",
        "llm.max_output_tokens",
    ]
    missing = [item for item in required if _get(values, item) is None]
    if missing:
        raise ConfigError(f"Missing required config values: {', '.join(missing)}")

    top_n = int(_get(values, "market.universe.top_n"))
    min_positive_count = _max_condition_min_positive_count(values, top_n)
    if top_n <= 0:
        raise ConfigError("market.universe.top_n must be positive.")
    if min_positive_count > top_n:
        raise ConfigError("simulation.signal_condition.min_positive_count cannot exceed top_n.")

    temp = float(_get(values, "llm.temperature"))
    if not 0 <= temp <= 2:
        raise ConfigError("llm.temperature must be between 0 and 2.")

    if allow_placeholders:
        return
    placeholders = _find_placeholders(values)
    enabled_paths = [
        ("telegram.enabled", ["telegram.bot_token", "telegram.chat_id"]),
        ("llm.enabled", ["llm.api_key", "llm.base_url"]),
    ]
    for enabled_path, secret_paths in enabled_paths:
        if bool(_get(values, enabled_path, False)):
            used = [path for path in secret_paths if _get(values, path) in SECRET_PLACEHOLDERS]
            if used:
                raise ConfigError(f"Enabled integration still has placeholder secrets: {', '.join(used)}")
    if _get(values, "app.mode") == "kis_rest":
        live_used = [path for path in ["kis.app_key", "kis.app_secret"] if _get(values, path) in SECRET_PLACEHOLDERS]
        if live_used:
            raise ConfigError(f"KIS REST mode still has placeholder KIS secrets: {', '.join(live_used)}")
    if placeholders:
        return


def _get(values: dict[str, Any], dotted_path: str, default: Any = None) -> Any:
    current: Any = values
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _max_condition_min_positive_count(values: dict[str, Any], default: int) -> int:
    strategy_cases = _get(values, "simulation.strategy_conditions", [])
    if isinstance(strategy_cases, list) and strategy_cases:
        counts = [
            int(case.get("signal", {}).get("min_count", default))
            for case in strategy_cases
            if isinstance(case, dict)
        ]
        return max(counts) if counts else default
    cases = _get(values, "simulation.signal_conditions", [])
    if isinstance(cases, list) and cases:
        counts = [int(case.get("min_positive_count", default)) for case in cases if isinstance(case, dict)]
        return max(counts) if counts else default
    return int(_get(values, "simulation.signal_condition.min_positive_count", default))


def _default_strategy_conditions(signal_conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if signal_conditions:
        converted = []
        for case in signal_conditions:
            min_count = int(case.get("min_positive_count", 10))
            converted.append(
                {
                    "name": _sanitize_condition_name(case.get("name", f"top10_{min_count}_up_long")),
                    "enabled": True,
                    "llm_queue": True,
                    "rule": case.get("rule", "min_positive_count"),
                    "comparison": case.get("comparison", "greater_than"),
                    "signal": {
                        "direction": "up",
                        "threshold_pct": float(case.get("positive_threshold_pct", 0.0)),
                        "min_count": min_count,
                    },
                    "trade": {
                        "instrument": "kospi200_futures",
                        "side": "long",
                        "label": "long",
                        "entry_time": "08:50",
                    },
                }
            )
        return converted
    cases = []
    for count in [5, 7, 10]:
        cases.append(_strategy_condition(f"top10_{count}_up_long", "up", count, "long", "long", True))
    for count in [5, 7, 10]:
        cases.append(_strategy_condition(f"top10_{count}_down_inverse", "down", count, "short", "inverse", True))
    return cases


def _strategy_condition(name: str, direction: str, min_count: int, side: str, label: str, llm_queue: bool) -> dict[str, Any]:
    return {
        "name": _sanitize_condition_name(name),
        "enabled": True,
        "llm_queue": llm_queue,
        "rule": "min_positive_count",
        "comparison": "greater_than",
        "signal": {
            "direction": direction,
            "threshold_pct": 0.0,
            "min_count": min_count,
        },
        "trade": {
            "instrument": "kospi200_futures",
            "side": side,
            "label": label,
            "entry_time": "08:50",
        },
    }


def _sanitize_condition_name(value: Any) -> str:
    text = str(value or "condition").lower()
    chars = [char if char.isalnum() else "_" for char in text]
    sanitized = "_".join("".join(chars).split("_"))
    return sanitized or "condition"


def _default_schedule_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "timezone": "Asia/Seoul",
        "run_times": ["08:50", "12:50", "16:50", "20:50"],
        "startup_delay_seconds": 30,
        "skip_if_running": True,
        "lock_file": "data/scheduler.lock",
        "state_file": "data/scheduler_state.json",
        "log_dir": "logs",
    }


def _find_placeholders(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for nested in value.values():
            found.extend(_find_placeholders(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_find_placeholders(nested))
    elif isinstance(value, str) and value in SECRET_PLACEHOLDERS:
        found.append(value)
    return found
