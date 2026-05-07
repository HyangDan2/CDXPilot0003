from kosim.simulation.sweep import time_range


def test_time_range_inclusive():
    assert time_range("09:00", "09:30", 10) == ["09:00", "09:10", "09:20", "09:30"]
