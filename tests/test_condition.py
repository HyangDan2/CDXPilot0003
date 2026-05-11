from kosim.data.models import StockReturn
from kosim.simulation.condition import signal_passes


def _row(value: float) -> StockReturn:
    return StockReturn(symbol="000000", name="T", signal_time="08:00", return_pct=value, price=100.0)


def test_all_positive_uses_strict_positive_by_default():
    assert signal_passes([_row(0.1), _row(0.01)], {"rule": "all_positive", "positive_threshold_pct": 0.0})
    assert not signal_passes([_row(0.1), _row(0.0)], {"rule": "all_positive", "positive_threshold_pct": 0.0})


def test_min_positive_count():
    assert signal_passes(
        [_row(0.1), _row(-0.1), _row(0.2)],
        {"rule": "min_positive_count", "positive_threshold_pct": 0.0, "min_positive_count": 2},
    )


def test_down_strategy_condition_counts_negative_returns():
    rows = [_row(-0.1), _row(-0.2), _row(0.1)]
    condition = {
        "rule": "min_positive_count",
        "signal": {"direction": "down", "threshold_pct": 0.0, "min_count": 2},
    }
    assert signal_passes(rows, condition)
