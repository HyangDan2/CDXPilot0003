from __future__ import annotations

from collections import defaultdict

from kosim.data.models import RawMarketData


def raw_data_markdown(raw_items: list[RawMarketData]) -> str:
    lines = ["# Raw Data Summary", ""]
    for raw in raw_items:
        lines.extend(
            [
                f"## {raw.simulation_date.isoformat()}",
                f"- Universe basis date: {raw.universe_basis_date.isoformat()}",
                f"- Universe: {', '.join(member.symbol for member in raw.universe)}",
                "",
                "| Signal Time | Positive Count | Average Return % |",
                "|---|---:|---:|",
            ]
        )
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in raw.stock_returns:
            grouped[row.signal_time].append(row.return_pct)
        for signal_time in sorted(grouped):
            values = grouped[signal_time]
            positives = sum(1 for value in values if value > 0)
            avg = sum(values) / len(values) if values else 0.0
            lines.append(f"| {signal_time} | {positives}/{len(values)} | {avg:.3f} |")
        lines.append("")
    return "\n".join(lines)
