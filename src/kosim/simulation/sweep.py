from __future__ import annotations

from datetime import datetime, timedelta


def time_range(start: str, end: str, interval_minutes: int) -> list[str]:
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be positive.")
    current = datetime.strptime(start, "%H:%M")
    last = datetime.strptime(end, "%H:%M")
    values: list[str] = []
    while current <= last:
        values.append(current.strftime("%H:%M"))
        current += timedelta(minutes=interval_minutes)
    return values


def all_needed_futures_times(signal_times: list[str], exit_times: list[str]) -> list[str]:
    return sorted(set(signal_times + exit_times))
