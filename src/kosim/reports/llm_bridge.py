from __future__ import annotations

from kosim.reports.evidence import (
    condition_names,
    costs_label,
    daily_best_cases,
    exit_sweep_label,
    signal_summary_rows,
    signal_times,
    trade_markdown_row,
    trades_by_date,
)
from kosim.simulation.engine import SimulationResult


def llm_bridge_markdown(config: dict, result: SimulationResult) -> str:
    bridge_cfg = config.get("report", {}).get("llm_bridge", {})
    daily_limit = int(bridge_cfg.get("daily_best_case_limit", 5))
    per_condition_limit = int(bridge_cfg.get("per_condition_limit", 2))
    one_best = bool(bridge_cfg.get("one_best_case_per_date", True))
    max_chars = int(bridge_cfg.get("max_chars", 50000))

    lines = [
        "# LLM Bridge Evidence",
        "",
        "This bridge is the compact evidence layer between raw market data and sweep metrics.",
        "It intentionally includes selected daily best cases rather than the full raw ledger.",
        "",
        "## Context",
        "",
        f"- Raw dates: {len(result.raw_data)}",
        f"- App mode: {config.get('app', {}).get('mode', 'unknown')}",
        f"- Signal times: {', '.join(signal_times(config, result.raw_data))}",
        f"- Exit sweep: {exit_sweep_label(config)}",
        f"- Conditions: {', '.join(condition_names(config))}",
        f"- Cost assumptions: {costs_label(config)}",
        "",
        "## Aggregate Best Evidence",
        "",
        _aggregate_table(result),
        "",
        "## Daily Evidence",
        "",
    ]

    grouped_trades = trades_by_date(result)

    for raw in result.raw_data:
        daily_trades = grouped_trades.get(raw.simulation_date, [])
        lines.extend(
            [
                f"### {raw.simulation_date.isoformat()}",
                "",
                f"- Universe basis date: {raw.universe_basis_date.isoformat()}",
                f"- Universe: {', '.join(member.symbol for member in raw.universe)}",
                "",
                "#### Signal Snapshot",
                "",
                "| Signal Time | Positive Count | Average Return % | Passed Conditions |",
                "|---|---:|---:|---|",
            ]
        )
        for signal_time, positives, total, avg, passed in signal_summary_rows(raw, daily_trades):
            lines.append(f"| {signal_time} | {positives}/{total} | {avg:.3f} | {passed} |")
        lines.extend(
            [
                "",
                "#### Daily Best Cases",
                "",
                "| Rank | Signal Date | Condition | Entry Time | Exit Time | Entry Price | Exit Price | Net Return % | Win | Positives |",
                "|---:|---|---|---|---|---:|---:|---:|---|---:|",
            ]
        )
        daily_best = daily_best_cases(daily_trades, daily_limit, one_best, per_condition_limit)
        for rank, trade in enumerate(daily_best, start=1):
            lines.append(trade_markdown_row(rank, trade))
        if not daily_best:
            lines.append("| - | - | No passed condition | - | - | - | - | - | - | - |")
        lines.append("")

    text = "\n".join(lines)
    if max_chars > 0 and len(text) > max_chars:
        half = max_chars // 2
        text = (
            text[:half]
            + "\n\n[LLM_BRIDGE_COMPRESSION_NOTICE]\n"
            + f"Bridge evidence exceeded {max_chars} chars. Middle daily evidence rows were omitted; rely on aggregate tables and CSV sections for final ranking.\n\n"
            + text[-half:]
        )
    return text


def _aggregate_table(result: SimulationResult) -> str:
    lines = [
        "| Condition | Entry Time | Exit Time | Trades | Winning Rate | Avg Net Return % | Total Net Return % |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for item in result.metrics[:30]:
        lines.append(
            f"| {item.condition_name} | {item.signal_time} | {item.exit_time} | {item.trade_count} | "
            f"{item.win_rate:.1%} | {item.avg_return_pct:.3f} | {item.total_return_pct:.3f} |"
        )
    return "\n".join(lines)
