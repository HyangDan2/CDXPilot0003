from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median, pstdev


@dataclass(frozen=True)
class ConditionMetrics:
    condition_name: str
    signal_time: str
    exit_time: str
    trade_count: int
    win_rate: float
    avg_return_pct: float
    median_return_pct: float
    p05_return_pct: float
    p25_return_pct: float
    p75_return_pct: float
    p95_return_pct: float
    total_return_pct: float
    max_drawdown_pct: float
    profit_factor: float
    stability_score: float
    profit_probability: float
    loss_probability: float


def compute_metrics(condition_name: str, signal_time: str, exit_time: str, returns: list[float]) -> ConditionMetrics:
    if not returns:
        return ConditionMetrics(condition_name, signal_time, exit_time, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    wins = [value for value in returns if value > 0]
    losses = [value for value in returns if value < 0]
    total = sum(returns)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    volatility = pstdev(returns) if len(returns) > 1 else 0.0
    mdd = max_drawdown(returns)
    stability = (mean(returns) / volatility) if volatility else mean(returns)
    return ConditionMetrics(
        condition_name=condition_name,
        signal_time=signal_time,
        exit_time=exit_time,
        trade_count=len(returns),
        win_rate=len(wins) / len(returns),
        avg_return_pct=mean(returns),
        median_return_pct=median(returns),
        p05_return_pct=percentile(returns, 0.05),
        p25_return_pct=percentile(returns, 0.25),
        p75_return_pct=percentile(returns, 0.75),
        p95_return_pct=percentile(returns, 0.95),
        total_return_pct=total,
        max_drawdown_pct=mdd,
        profit_factor=(gross_profit / gross_loss) if gross_loss else float("inf"),
        stability_score=stability,
        profit_probability=len(wins) / len(returns),
        loss_probability=len(losses) / len(returns),
    )


def max_drawdown(returns: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for value in returns:
        equity += value
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return worst


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight
