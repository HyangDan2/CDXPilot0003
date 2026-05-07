from __future__ import annotations

from dataclasses import dataclass
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

    validate_config(raw)
    return AppConfig(path=config_path, values=raw)


def load_example_config(path: str | Path = "config.example.yaml") -> AppConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ConfigError("Root config must be a YAML mapping.")
    validate_config(raw, allow_placeholders=True)
    return AppConfig(path=config_path, values=raw)


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
    min_positive_count = int(_get(values, "simulation.signal_condition.min_positive_count", top_n))
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
    if _get(values, "app.mode") in {"kis_rest", "live"}:
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
