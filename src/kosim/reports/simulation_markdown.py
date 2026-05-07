from __future__ import annotations

from kosim.simulation.engine import SimulationResult
from kosim.simulation.metrics import ConditionMetrics


def simulation_report_markdown(result: SimulationResult, top_n: int = 20) -> str:
    lines = [
        "# NXT Signal Sweep Simulation Report",
        "",
        f"- Raw dates: {len(result.raw_data)}",
        f"- Trades: {len(result.trades)}",
        f"- Conditions: {len(result.metrics)}",
        "",
        "## Top Conditions",
        "",
        _metrics_table(result.metrics[:top_n]),
        "",
        "## Condition Summary",
        "",
        _condition_summary_table(result.metrics),
        "",
        "## Exit Time Summary",
        "",
        _exit_time_summary_table(result.metrics),
        "",
        "## Trade Evidence",
        "",
        _trade_evidence_table(result, limit=50),
        "",
        "## Worst Conditions",
        "",
        _metrics_table(sorted(result.metrics, key=lambda item: item.total_return_pct)[:top_n]),
        "",
    ]
    return "\n".join(lines)


def metrics_to_csv(metrics: list[ConditionMetrics]) -> str:
    rows = [
        "condition_name,signal_time,exit_time,trade_count,win_rate,profit_probability,loss_probability,avg_return_pct,median_return_pct,p05_return_pct,p25_return_pct,p75_return_pct,p95_return_pct,total_return_pct,max_drawdown_pct,profit_factor,stability_score"
    ]
    for item in metrics:
        rows.append(
            ",".join(
                [
                    item.condition_name,
                    item.signal_time,
                    item.exit_time,
                    str(item.trade_count),
                    f"{item.win_rate:.6f}",
                    f"{item.profit_probability:.6f}",
                    f"{item.loss_probability:.6f}",
                    f"{item.avg_return_pct:.6f}",
                    f"{item.median_return_pct:.6f}",
                    f"{item.p05_return_pct:.6f}",
                    f"{item.p25_return_pct:.6f}",
                    f"{item.p75_return_pct:.6f}",
                    f"{item.p95_return_pct:.6f}",
                    f"{item.total_return_pct:.6f}",
                    f"{item.max_drawdown_pct:.6f}",
                    "inf" if item.profit_factor == float("inf") else f"{item.profit_factor:.6f}",
                    f"{item.stability_score:.6f}",
                ]
            )
        )
    return "\n".join(rows)


def _metrics_table(metrics: list[ConditionMetrics]) -> str:
    lines = [
        "| Condition | Signal | Exit | Trades | Win Rate | Loss Prob | Avg % | Median % | P05 % | P95 % | Total % | MDD % |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in metrics:
        lines.append(
            "| "
            f"{item.condition_name} | {item.signal_time} | {item.exit_time} | {item.trade_count} | "
            f"{item.win_rate:.1%} | {item.loss_probability:.1%} | {item.avg_return_pct:.3f} | "
            f"{item.median_return_pct:.3f} | {item.p05_return_pct:.3f} | {item.p95_return_pct:.3f} | "
            f"{item.total_return_pct:.3f} | {item.max_drawdown_pct:.3f} |"
        )
    return "\n".join(lines)


def trade_evidence_to_csv(result: SimulationResult, limit: int | None = None) -> str:
    rows = [
        "condition_name,simulation_date,signal_time,exit_time,entry_price,exit_price,gross_return_pct,fee_pct,slippage_pct,net_return_pct,positive_count,triggered_symbols"
    ]
    trades = result.trades if limit is None else result.trades[:limit]
    for trade in trades:
        rows.append(
            ",".join(
                [
                    trade.condition_name,
                    trade.simulation_date.isoformat(),
                    trade.signal_time,
                    trade.exit_time,
                    f"{trade.entry_price:.6f}",
                    f"{trade.exit_price:.6f}",
                    f"{trade.gross_return_pct:.6f}",
                    f"{trade.fee_pct:.6f}",
                    f"{trade.slippage_pct:.6f}",
                    f"{trade.net_return_pct:.6f}",
                    str(trade.positive_count),
                    "|".join(trade.triggered_symbols),
                ]
            )
        )
    return "\n".join(rows)


def _trade_evidence_table(result: SimulationResult, limit: int = 50) -> str:
    lines = [
        "| Condition | Date | Signal | Exit | Entry | Exit Price | Gross % | Net % | Positives |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for trade in result.trades[:limit]:
        lines.append(
            f"| {trade.condition_name} | {trade.simulation_date.isoformat()} | {trade.signal_time} | {trade.exit_time} | "
            f"{trade.entry_price:.3f} | {trade.exit_price:.3f} | {trade.gross_return_pct:.3f} | "
            f"{trade.net_return_pct:.3f} | {trade.positive_count} |"
        )
    if len(result.trades) > limit:
        lines.append(f"| ... | ... | ... | ... | ... | ... | ... | ... | {len(result.trades) - limit} more rows |")
    return "\n".join(lines)


def _exit_time_summary_table(metrics: list[ConditionMetrics]) -> str:
    by_exit: dict[str, list[ConditionMetrics]] = {}
    for item in metrics:
        by_exit.setdefault(item.exit_time, []).append(item)
    lines = [
        "| Exit | Trades | Avg Return % | Total Return % | Loss Prob | Best Condition |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for exit_time in sorted(by_exit):
        rows = by_exit[exit_time]
        trade_count = sum(item.trade_count for item in rows)
        avg = sum(item.avg_return_pct * item.trade_count for item in rows) / trade_count if trade_count else 0.0
        total = sum(item.total_return_pct for item in rows)
        loss = sum(item.loss_probability * item.trade_count for item in rows) / trade_count if trade_count else 0.0
        best = max(rows, key=lambda item: item.total_return_pct)
        lines.append(f"| {exit_time} | {trade_count} | {avg:.3f} | {total:.3f} | {loss:.1%} | {best.condition_name}/{best.signal_time} |")
    return "\n".join(lines)


def _condition_summary_table(metrics: list[ConditionMetrics]) -> str:
    by_condition: dict[str, list[ConditionMetrics]] = {}
    for item in metrics:
        by_condition.setdefault(item.condition_name, []).append(item)
    lines = [
        "| Condition | Best Exit | Trades | Win Rate | Avg Return % | Total Return % | MDD % |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for condition_name in sorted(by_condition):
        rows = by_condition[condition_name]
        best = max(rows, key=lambda item: item.total_return_pct)
        trades = sum(item.trade_count for item in rows)
        weighted_win = sum(item.win_rate * item.trade_count for item in rows)
        weighted_avg = sum(item.avg_return_pct * item.trade_count for item in rows)
        win_rate = weighted_win / trades if trades else 0.0
        avg = weighted_avg / trades if trades else 0.0
        total = sum(item.total_return_pct for item in rows)
        mdd = min(item.max_drawdown_pct for item in rows)
        lines.append(f"| {condition_name} | {best.exit_time} | {trades} | {win_rate:.1%} | {avg:.3f} | {total:.3f} | {mdd:.3f} |")
    return "\n".join(lines)
