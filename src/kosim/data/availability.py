from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from kosim.data.models import RawMarketData
from kosim.data.storage import SQLiteStore
from kosim.simulation.sweep import all_needed_futures_times, time_range


@dataclass(frozen=True)
class DayCompleteness:
    simulation_date: date
    complete: bool
    reasons: list[str]


@dataclass(frozen=True)
class RecentCompleteSelection:
    requested_days: int
    selected_dates: list[date]
    complete_days_available: int
    incomplete: list[DayCompleteness]


def inspect_day_completeness(raw: RawMarketData, config: dict) -> DayCompleteness:
    reasons: list[str] = []
    top_n = int(config["market"]["universe"].get("top_n", 10))
    signal_times = list(config["market"]["nxt"]["signal_times"])
    exit_cfg = config["simulation"]["exit_sweep"]
    futures_times = all_needed_futures_times(
        signal_times,
        time_range(exit_cfg["start"], exit_cfg["end"], int(exit_cfg["interval_minutes"])),
    )

    if len(raw.universe) < top_n:
        reasons.append(f"universe has {len(raw.universe)} members, expected {top_n}")

    symbols = {member.symbol for member in raw.universe[:top_n]}
    for signal_time in signal_times:
        rows = [row for row in raw.stock_returns if row.signal_time == signal_time and row.symbol in symbols]
        if len({row.symbol for row in rows}) < top_n:
            reasons.append(f"missing NXT rows for signal_time={signal_time}")

    futures_by_time = {row.time for row in raw.futures_prices}
    for futures_time in futures_times:
        if futures_time not in futures_by_time:
            reasons.append(f"missing futures price for time={futures_time}")

    return DayCompleteness(raw.simulation_date, complete=not reasons, reasons=reasons)


def recent_complete_days(store: SQLiteStore, config: dict, requested_days: int) -> RecentCompleteSelection:
    complete: list[date] = []
    incomplete: list[DayCompleteness] = []
    for simulation_date in sorted(store.list_raw_data_dates(), reverse=True):
        raw = store.load_raw_data(simulation_date)
        if raw is None:
            continue
        status = inspect_day_completeness(raw, config)
        if status.complete:
            complete.append(simulation_date)
        else:
            incomplete.append(status)
    selected = sorted(complete[:requested_days])
    return RecentCompleteSelection(
        requested_days=requested_days,
        selected_dates=selected,
        complete_days_available=len(complete),
        incomplete=incomplete,
    )
