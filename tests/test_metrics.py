from kosim.simulation.metrics import compute_metrics, percentile


def test_compute_metrics_adds_probability_and_percentiles():
    metrics = compute_metrics("top10_5_positive", "08:10", "11:00", [-1.0, 0.5, 1.5])

    assert metrics.trade_count == 3
    assert metrics.profit_probability == 2 / 3
    assert metrics.loss_probability == 1 / 3
    assert metrics.p05_return_pct < metrics.p95_return_pct


def test_percentile_interpolates():
    assert percentile([0.0, 10.0], 0.5) == 5.0
