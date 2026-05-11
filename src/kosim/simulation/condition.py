from __future__ import annotations

from kosim.data.models import StockReturn


def signal_passes(rows: list[StockReturn], config: dict) -> bool:
    rule = config.get("rule", "all_positive")
    signal = config.get("signal", {})
    direction = signal.get("direction", config.get("direction", "up"))
    threshold = float(signal.get("threshold_pct", config.get("positive_threshold_pct", 0.0)))
    comparison = config.get("comparison", "greater_than")
    min_count = int(signal.get("min_count", config.get("min_positive_count", len(rows))))

    if direction == "down":
        if comparison == "greater_or_equal":
            count = sum(1 for row in rows if row.return_pct <= -threshold)
        else:
            count = sum(1 for row in rows if row.return_pct < -threshold)
    else:
        if comparison == "greater_or_equal":
            count = sum(1 for row in rows if row.return_pct >= threshold)
        else:
            count = sum(1 for row in rows if row.return_pct > threshold)

    if rule == "all_positive":
        return count == len(rows)
    if rule == "min_positive_count":
        return count >= min_count
    raise ValueError(f"Unsupported signal rule: {rule}")
