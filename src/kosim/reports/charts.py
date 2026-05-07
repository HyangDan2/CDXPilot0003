from __future__ import annotations

import os
import tempfile
from pathlib import Path

from kosim.simulation.engine import SimulationResult
from kosim.simulation.metrics import ConditionMetrics


def generate_charts(result: SimulationResult, output_dir: str | Path, case_limit: int = 20) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    try:
        os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "kosim_matplotlib"))
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []

    charts: list[Path] = []
    charts.extend(
        [
            _heatmap(plt, result.metrics, output / "summary_heatmap_total_return.png", "total_return_pct", "Total Return %"),
            _heatmap(plt, result.metrics, output / "summary_heatmap_win_rate.png", "win_rate", "Win Rate"),
            _heatmap(plt, result.metrics, output / "summary_heatmap_trade_count.png", "trade_count", "Trade Count"),
            _heatmap(plt, result.metrics, output / "summary_heatmap_loss_probability.png", "loss_probability", "Loss Probability"),
        ]
    )
    charts = [path for path in charts if path is not None]

    sent = 0
    for metric in [item for item in result.metrics if item.trade_count > 0][:case_limit]:
        returns = [
            trade.net_return_pct
            for trade in result.trades
            if trade.condition_name == metric.condition_name and trade.signal_time == metric.signal_time and trade.exit_time == metric.exit_time
        ]
        if not returns:
            continue
        safe_condition = metric.condition_name.replace("/", "_").replace(" ", "_")
        path = output / f"case_{safe_condition}_{metric.signal_time.replace(':', '')}_{metric.exit_time.replace(':', '')}_return_distribution.png"
        _distribution(plt, returns, path, f"{metric.condition_name} {metric.signal_time} -> {metric.exit_time} Return Distribution")
        charts.append(path)
        sent += 1
        if sent >= case_limit:
            break
    return charts


def summary_chart_paths(chart_paths: list[Path]) -> list[Path]:
    return [path for path in chart_paths if path.name.startswith("summary_")]


def case_chart_paths(chart_paths: list[Path]) -> list[Path]:
    return [path for path in chart_paths if path.name.startswith("case_")]


def _heatmap(plt, metrics: list[ConditionMetrics], path: Path, attr: str, title: str) -> Path | None:
    if not metrics:
        return None
    signals = sorted({f"{item.condition_name}\n{item.signal_time}" for item in metrics})
    exits = sorted({item.exit_time for item in metrics})
    values = []
    for signal in signals:
        row = []
        for exit_time in exits:
            metric = next((item for item in metrics if f"{item.condition_name}\n{item.signal_time}" == signal and item.exit_time == exit_time), None)
            row.append(float(getattr(metric, attr)) if metric else 0.0)
        values.append(row)

    fig, ax = plt.subplots(figsize=(max(8, len(exits) * 0.35), max(4, len(signals) * 0.7)))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn")
    ax.set_title(title)
    ax.set_xlabel("Exit Time")
    ax.set_ylabel("Signal Time")
    ax.set_xticks(range(len(exits)))
    ax.set_xticklabels(exits, rotation=90, fontsize=7)
    ax.set_yticks(range(len(signals)))
    ax.set_yticklabels(signals)
    fig.colorbar(image, ax=ax, shrink=0.85)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def _distribution(plt, returns: list[float], path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    bins = min(20, max(5, len(returns)))
    ax.hist(returns, bins=bins, color="#2563eb", alpha=0.75, edgecolor="white")
    ax.axvline(0, color="#dc2626", linewidth=1)
    ax.set_title(title)
    ax.set_xlabel("Net Return %")
    ax.set_ylabel("Frequency")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
