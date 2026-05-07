from datetime import date

from kosim.data.models import RawMarketData, UniverseMember
from kosim.reports.llm_bridge import llm_bridge_markdown
from kosim.reports.raw_markdown import raw_data_markdown
from kosim.simulation.engine import SimulationResult, Trade


def test_daily_best_reports_one_case_per_date_and_includes_signal_date():
    raw = RawMarketData(
        simulation_date=date(2026, 5, 7),
        universe_basis_date=date(2026, 5, 6),
        universe=[UniverseMember("005930", "Samsung", 1.0, 1)],
        stock_returns=[],
        futures_prices=[],
    )
    trades = [
        _trade("top10_7_positive", 0.30),
        _trade("top10_5_positive", 0.30),
        _trade("top10_5_positive", 0.20),
    ]
    result = SimulationResult(raw_data=[raw], trades=trades, metrics=[])
    config = {
        "app": {"mode": "kis_rest"},
        "report": {
            "raw": {"daily_best_case_limit": 5, "one_best_case_per_date": True},
            "llm_bridge": {"daily_best_case_limit": 5, "one_best_case_per_date": True, "max_chars": 0},
        },
        "simulation": {"historical_signal_time": "08:50", "exit_sweep": {"start": "09:00", "end": "15:20", "interval_minutes": 10}},
    }

    raw_text = raw_data_markdown(result, config)
    bridge_text = llm_bridge_markdown(config, result)

    assert "| Rank | Signal Date | Condition |" in raw_text
    assert "| Rank | Signal Date | Condition |" in bridge_text
    assert raw_text.count("| 1 | 2026-05-07 |") == 1
    assert bridge_text.count("| 1 | 2026-05-07 |") == 1
    assert "| 2 | 2026-05-07 |" not in raw_text
    assert "| 2 | 2026-05-07 |" not in bridge_text
    assert "top10_5_positive" in raw_text
    assert "top10_7_positive" not in raw_text


def _trade(condition_name: str, net_return_pct: float) -> Trade:
    return Trade(
        condition_name=condition_name,
        simulation_date=date(2026, 5, 7),
        signal_time="08:50",
        exit_time="15:20",
        entry_price=350.0,
        exit_price=351.0,
        gross_return_pct=net_return_pct,
        fee_pct=0.0,
        slippage_pct=0.0,
        net_return_pct=net_return_pct,
        positive_count=7,
        triggered_symbols=["005930"],
    )
