from __future__ import annotations

from kosim.data.models import RawMarketData
from kosim.reports.evidence import (
    daily_best_cases,
    exit_sweep_label,
    selected_futures_prices,
    signal_summary_rows,
    signal_times,
    trade_markdown_row,
)
from kosim.simulation.engine import SimulationResult


def raw_data_markdown(result_or_raw_items, config: dict | None = None) -> str:
    if isinstance(result_or_raw_items, SimulationResult):
        result = result_or_raw_items
        raw_items = result.raw_data
        trades = result.trades
    else:
        raw_items = list(result_or_raw_items)
        trades = []

    raw_cfg = (config or {}).get("report", {}).get("raw", {})
    daily_limit = int(raw_cfg.get("daily_best_case_limit", 5))
    key_prices = bool(raw_cfg.get("include_futures_key_prices", True))
    one_best = bool(raw_cfg.get("one_best_case_per_date", True))
    lines = [
        "# Raw Data Report",
        "",
        "This report is a compact raw-data review. It keeps NXT signal evidence, key futures prices, and each date's best simulated entry-exit cases.",
        "",
        "## Run Settings",
        "",
        f"- App mode: {(config or {}).get('app', {}).get('mode', 'unknown')}",
        f"- Signal times: {', '.join(signal_times(config, raw_items))}",
        f"- Exit sweep: {exit_sweep_label(config)}",
        f"- Daily best case limit: {daily_limit}",
        "",
    ]
    for raw in raw_items:
        daily_trades = [trade for trade in trades if trade.simulation_date == raw.simulation_date]
        lines.extend(
            [
                f"## {raw.simulation_date.isoformat()}",
                f"- Universe basis date: {raw.universe_basis_date.isoformat()}",
                f"- Universe: {', '.join(member.symbol for member in raw.universe)}",
                "",
                "### NXT Signal Summary",
                "",
                "| Signal Time | Positive Count | Average Return % | Passed Conditions |",
                "|---|---:|---:|---|",
            ]
        )
        for signal_time, positives, total, avg, passed in signal_summary_rows(raw, daily_trades):
            lines.append(f"| {signal_time} | {positives}/{total} | {avg:.3f} | {passed} |")
        lines.append("")

        if key_prices:
            lines.extend(["### Futures Key Prices", "", "| Time | Symbol | Price |", "|---|---|---:|"])
            for row in selected_futures_prices(raw):
                lines.append(f"| {row.time} | {row.symbol} | {row.price:.3f} |")
            lines.append("")

        lines.extend(
            [
                "### Daily Best Entry-Exit Cases",
                "",
                "| Rank | Signal Date | Condition | Entry Time | Exit Time | Entry Price | Exit Price | Net Return % | Win | Positives |",
                "|---:|---|---|---|---|---:|---:|---:|---|---:|",
            ]
        )
        best = daily_best_cases(daily_trades, daily_limit, one_best)
        if best:
            for rank, trade in enumerate(best, start=1):
                lines.append(trade_markdown_row(rank, trade))
        else:
            lines.append("| - | - | No passed condition | - | - | - | - | - | - | - |")
        lines.append("")
    return "\n".join(lines)
