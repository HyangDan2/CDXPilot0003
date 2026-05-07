from datetime import date

from kosim.data.models import FuturesPrice, RawMarketData, StockReturn, UniverseMember
from kosim.simulation.engine import SweepSimulationEngine


def test_engine_runs_multiple_positive_count_conditions():
    config = {
        "market": {"nxt": {"signal_times": ["08:50"]}, "futures": {"symbol": "FUT"}},
        "simulation": {
            "historical_signal_time": "08:50",
            "signal_conditions": [
                {"name": "top10_5_positive", "rule": "min_positive_count", "min_positive_count": 5},
                {"name": "top10_7_positive", "rule": "min_positive_count", "min_positive_count": 7},
                {"name": "top10_10_positive", "rule": "min_positive_count", "min_positive_count": 10},
            ],
            "exit_sweep": {"start": "09:00", "end": "09:00", "interval_minutes": 10},
            "costs": {"fee_rate": 0.0, "slippage_ticks": 0, "tick_value_pct": 0.0},
        },
    }
    universe = [UniverseMember(f"{index:06d}", f"S{index}", 1.0, index) for index in range(10)]
    raw = RawMarketData(
        simulation_date=date(2026, 5, 7),
        universe_basis_date=date(2026, 5, 6),
        universe=universe,
        stock_returns=[
            StockReturn(member.symbol, member.name, "08:50", 0.1 if index < 7 else -0.1, 100.0)
            for index, member in enumerate(universe)
        ],
        futures_prices=[FuturesPrice("FUT", "08:50", 350.0), FuturesPrice("FUT", "09:00", 351.0)],
    )
    engine = SweepSimulationEngine(provider=None, universe_resolver=None, config=config)

    result = engine.run_from_raw([raw])

    trade_conditions = {trade.condition_name for trade in result.trades}
    assert "top10_5_positive" in trade_conditions
    assert "top10_7_positive" in trade_conditions
    assert "top10_10_positive" not in trade_conditions
