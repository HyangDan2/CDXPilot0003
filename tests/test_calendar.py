from datetime import date

from kosim.data.calendar import previous_trading_day, trading_days


def test_previous_trading_day_skips_weekend():
    assert previous_trading_day(date(2026, 5, 11)) == date(2026, 5, 8)


def test_trading_days_skips_weekends():
    assert trading_days("2026-05-07", "2026-05-11") == [
        date(2026, 5, 7),
        date(2026, 5, 8),
        date(2026, 5, 11),
    ]
