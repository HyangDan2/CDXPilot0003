from __future__ import annotations

from datetime import date, datetime, timedelta


def parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def date_range(start: str | date, end: str | date) -> list[date]:
    current = parse_date(start)
    last = parse_date(end)
    days: list[date] = []
    while current <= last:
        days.append(current)
        current += timedelta(days=1)
    return days


def is_trading_day(day: date, holidays: set[date] | None = None) -> bool:
    holidays = holidays or set()
    return day.weekday() < 5 and day not in holidays


def previous_trading_day(day: str | date, holidays: set[date] | None = None) -> date:
    current = parse_date(day) - timedelta(days=1)
    while not is_trading_day(current, holidays):
        current -= timedelta(days=1)
    return current


def trading_days(start: str | date, end: str | date, holidays: set[date] | None = None) -> list[date]:
    return [day for day in date_range(start, end) if is_trading_day(day, holidays)]


def parse_holidays(values: list[str] | None) -> set[date]:
    return {parse_date(value) for value in values or []}
