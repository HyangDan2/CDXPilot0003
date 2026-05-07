from __future__ import annotations

from kosim.data.models import StockReturn


def signal_passes(rows: list[StockReturn], config: dict) -> bool:
    rule = config.get("rule", "all_positive")
    threshold = float(config.get("positive_threshold_pct", 0.0))
    comparison = config.get("comparison", "greater_than")
    min_positive_count = int(config.get("min_positive_count", len(rows)))

    if comparison == "greater_or_equal":
        positives = sum(1 for row in rows if row.return_pct >= threshold)
    else:
        positives = sum(1 for row in rows if row.return_pct > threshold)

    if rule == "all_positive":
        return positives == len(rows)
    if rule == "min_positive_count":
        return positives >= min_positive_count
    raise ValueError(f"Unsupported signal rule: {rule}")
