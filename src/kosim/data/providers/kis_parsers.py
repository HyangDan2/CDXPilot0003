from __future__ import annotations


def extract_futures_price_at_or_before(rows: list[dict], target_time: str) -> float | None:
    target = int(target_time.replace(":", "")[:4])
    candidates: list[tuple[int, float]] = []
    for row in rows:
        row_time_text = str(
            row.get("stck_cntg_hour")
            or row.get("cntg_hour")
            or row.get("futs_cntg_hour")
            or row.get("hour")
            or ""
        )[:4]
        if not row_time_text.isdigit():
            continue
        row_time = int(row_time_text)
        price = to_float(row.get("futs_prpr") or row.get("stck_prpr") or row.get("prpr"))
        if price and row_time <= target:
            candidates.append((row_time, price))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def to_float(value) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0
