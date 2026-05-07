from datetime import date

from kosim.data.availability import inspect_day_completeness
from kosim.data.models import FuturesPrice, RawMarketData, StockReturn, UniverseMember


def test_day_completeness_requires_all_signal_and_futures_times():
    config = {
        "market": {
            "universe": {"top_n": 2},
            "nxt": {"signal_times": ["08:00", "08:10"]},
        },
        "simulation": {"exit_sweep": {"start": "09:00", "end": "09:10", "interval_minutes": 10}},
    }
    raw = RawMarketData(
        simulation_date=date(2026, 5, 7),
        universe_basis_date=date(2026, 5, 6),
        universe=[
            UniverseMember("005930", "Samsung", 1.0, 1),
            UniverseMember("000660", "Hynix", 1.0, 2),
        ],
        stock_returns=[
            StockReturn("005930", "Samsung", "08:00", 0.1, 100.0),
            StockReturn("000660", "Hynix", "08:00", 0.1, 100.0),
            StockReturn("005930", "Samsung", "08:10", 0.1, 100.0),
            StockReturn("000660", "Hynix", "08:10", 0.1, 100.0),
        ],
        futures_prices=[
            FuturesPrice("FUT", "08:00", 350.0),
            FuturesPrice("FUT", "08:10", 350.1),
            FuturesPrice("FUT", "09:00", 350.2),
            FuturesPrice("FUT", "09:10", 350.3),
        ],
    )

    status = inspect_day_completeness(raw, config)

    assert status.complete


def test_day_completeness_flags_missing_data():
    config = {
        "market": {
            "universe": {"top_n": 2},
            "nxt": {"signal_times": ["08:00"]},
        },
        "simulation": {"exit_sweep": {"start": "09:00", "end": "09:00", "interval_minutes": 10}},
    }
    raw = RawMarketData(
        simulation_date=date(2026, 5, 7),
        universe_basis_date=date(2026, 5, 6),
        universe=[UniverseMember("005930", "Samsung", 1.0, 1)],
        stock_returns=[StockReturn("005930", "Samsung", "08:00", 0.1, 100.0)],
        futures_prices=[FuturesPrice("FUT", "08:00", 350.0)],
    )

    status = inspect_day_completeness(raw, config)

    assert not status.complete
    assert status.reasons
