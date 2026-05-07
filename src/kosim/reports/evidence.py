from __future__ import annotations

from collections import defaultdict

from kosim.data.models import RawMarketData
from kosim.simulation.engine import SimulationResult, Trade


def trades_by_date(result: SimulationResult) -> dict:
    grouped: dict = defaultdict(list)
    for trade in result.trades:
        grouped[trade.simulation_date].append(trade)
    return grouped


def daily_best_cases(
    trades: list[Trade],
    daily_limit: int,
    one_best_case_per_date: bool = True,
    per_condition_limit: int = 0,
) -> list[Trade]:
    if daily_limit <= 0:
        return []
    sorted_trades = sorted(trades, key=trade_sort_key, reverse=True)
    if one_best_case_per_date:
        return sorted_trades[:1]
    selected: list[Trade] = []
    counts: dict[str, int] = defaultdict(int)
    for trade in sorted_trades:
        if per_condition_limit > 0 and counts[trade.condition_name] >= per_condition_limit:
            continue
        selected.append(trade)
        counts[trade.condition_name] += 1
        if len(selected) >= daily_limit:
            break
    return selected


def signal_summary_rows(raw: RawMarketData, trades: list[Trade]) -> list[tuple[str, int, int, float, str]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in raw.stock_returns:
        grouped[row.signal_time].append(row.return_pct)
    rows = []
    for signal_time in sorted(grouped):
        values = grouped[signal_time]
        positives = sum(1 for value in values if value > 0)
        avg = sum(values) / len(values) if values else 0.0
        rows.append((signal_time, positives, len(values), avg, passed_conditions(trades, signal_time)))
    return rows


def selected_futures_prices(raw: RawMarketData):
    rows = sorted(raw.futures_prices, key=lambda item: item.time)
    if len(rows) <= 12:
        return rows
    keep_times = {"08:50", "09:00", "09:30", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "15:20"}
    selected = [row for row in rows if row.time in keep_times]
    return selected or rows[:5] + rows[-5:]


def signal_times(config: dict | None, raw_items: list[RawMarketData]) -> list[str]:
    if config:
        historical = config.get("simulation", {}).get("historical_signal_time")
        if historical:
            return [str(historical)]
        configured = config.get("market", {}).get("nxt", {}).get("signal_times")
        if configured:
            return [str(item) for item in configured]
    return sorted({row.signal_time for raw in raw_items for row in raw.stock_returns})


def exit_sweep_label(config: dict | None) -> str:
    if not config:
        return "unknown"
    sweep = config.get("simulation", {}).get("exit_sweep", {})
    return f"{sweep.get('start', '?')}~{sweep.get('end', '?')} / {sweep.get('interval_minutes', '?')}min"


def condition_names(config: dict) -> list[str]:
    cases = config.get("simulation", {}).get("signal_conditions") or []
    return [case.get("name", case.get("rule", "condition")) for case in cases]


def costs_label(config: dict) -> str:
    costs = config.get("simulation", {}).get("costs", {})
    return (
        f"fee_rate={costs.get('fee_rate', 0)}, "
        f"slippage_ticks={costs.get('slippage_ticks', 0)}, "
        f"tick_value_pct={costs.get('tick_value_pct', 0)}"
    )


def passed_conditions(trades: list[Trade], signal_time: str) -> str:
    names = sorted({trade.condition_name for trade in trades if trade.signal_time == signal_time})
    return ", ".join(names) if names else "-"


def trade_markdown_row(rank: int, trade: Trade) -> str:
    win = "Y" if trade.net_return_pct > 0 else "N"
    return (
        f"| {rank} | {trade.simulation_date.isoformat()} | {trade.condition_name} | {trade.signal_time} | {trade.exit_time} | "
        f"{trade.entry_price:.3f} | {trade.exit_price:.3f} | {trade.net_return_pct:.3f} | {win} | {trade.positive_count} |"
    )


def trade_sort_key(trade: Trade) -> tuple[float, int, str]:
    return (trade.net_return_pct, -condition_threshold_hint(trade.condition_name), trade.condition_name)


def condition_threshold_hint(condition_name: str) -> int:
    for token in condition_name.split("_"):
        if token.isdigit():
            return int(token)
    return 999
