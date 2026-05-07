from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from kosim.data.providers.base import MarketDataProvider
from kosim.data.models import RawMarketData
from kosim.data.storage import SQLiteStore
from kosim.data.universe import UniverseResolver
from kosim.simulation.condition import signal_passes
from kosim.simulation.metrics import ConditionMetrics, compute_metrics
from kosim.simulation.sweep import all_needed_futures_times, time_range


@dataclass(frozen=True)
class RunEvent:
    step: str
    status: str
    message: str
    payload: dict = field(default_factory=dict)


@dataclass
class Trade:
    condition_name: str
    simulation_date: date
    signal_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    gross_return_pct: float
    fee_pct: float
    slippage_pct: float
    net_return_pct: float
    positive_count: int
    triggered_symbols: list[str]

    @property
    def return_pct(self) -> float:
        return self.net_return_pct


@dataclass
class SimulationResult:
    raw_data: list[RawMarketData]
    trades: list[Trade]
    metrics: list[ConditionMetrics]


EventCallback = Callable[[RunEvent], None]


class SweepSimulationEngine:
    def __init__(
        self,
        provider: MarketDataProvider,
        universe_resolver: UniverseResolver,
        config: dict,
        store: SQLiteStore | None = None,
        emit: EventCallback | None = None,
    ):
        self.provider = provider
        self.universe_resolver = universe_resolver
        self.config = config
        self.store = store
        self.emit = emit or (lambda event: None)

    def run(self, simulation_dates: list[date]) -> SimulationResult:
        signal_times = _simulation_signal_times(self.config)
        exit_cfg = self.config["simulation"]["exit_sweep"]
        exit_times = time_range(exit_cfg["start"], exit_cfg["end"], int(exit_cfg["interval_minutes"]))
        futures_times = all_needed_futures_times(signal_times, exit_times)
        futures_symbol = self.config["market"]["futures"]["symbol"]
        condition_cases = _condition_cases(self.config)
        costs_cfg = self.config["simulation"].get("costs", {})

        raw_items: list[RawMarketData] = []
        trades: list[Trade] = []

        for index, simulation_date in enumerate(simulation_dates, start=1):
            self.emit(
                RunEvent(
                    "previous_trading_day_resolution",
                    "running",
                    f"Resolving D-1 universe basis for {simulation_date}",
                    {"current": index, "total": len(simulation_dates), "date": simulation_date.isoformat()},
                )
            )
            universe = self.universe_resolver.resolve(simulation_date)
            self.emit(
                RunEvent(
                    "universe_fetch",
                    "success",
                    f"Resolved KOSPI top {len(universe.members)} from {universe.basis_date}",
                    {"basis_date": universe.basis_date.isoformat(), "symbols": [m.symbol for m in universe.members]},
                )
            )

            self.emit(RunEvent("nxt_raw_fetch", "running", f"Fetching NXT raw stock data for {simulation_date}"))
            stock_returns = self.provider.get_nxt_stock_returns(simulation_date, universe.members, signal_times)
            self.emit(RunEvent("nxt_raw_fetch", "success", f"Fetched {len(stock_returns)} NXT stock rows"))

            self.emit(RunEvent("futures_fetch", "running", f"Fetching futures prices for {simulation_date}"))
            futures_prices = self.provider.get_futures_prices(simulation_date, futures_symbol, futures_times)
            self.emit(RunEvent("futures_fetch", "success", f"Fetched {len(futures_prices)} futures price rows"))

            raw = RawMarketData(
                simulation_date=simulation_date,
                universe_basis_date=universe.basis_date,
                universe=universe.members,
                stock_returns=stock_returns,
                futures_prices=futures_prices,
            )
            raw_items.append(raw)
            if self.store:
                self.store.save_raw_data(raw)
                self.emit(RunEvent("raw_data_save", "success", f"Saved raw data for {simulation_date}"))

            trades.extend(_simulate_raw_item(raw, signal_times, exit_times, condition_cases, costs_cfg))

        self.emit(RunEvent("sweep_simulation", "running", "Computing sweep metrics"))
        metrics = _compute_all_metrics(condition_cases, signal_times, exit_times, trades)
        metrics.sort(key=lambda item: (item.total_return_pct, item.stability_score, -abs(item.max_drawdown_pct)), reverse=True)
        self.emit(RunEvent("sweep_simulation", "success", f"Computed {len(metrics)} condition metrics"))
        return SimulationResult(raw_data=raw_items, trades=trades, metrics=metrics)

    def run_from_raw(self, raw_items: list[RawMarketData]) -> SimulationResult:
        signal_times = _simulation_signal_times(self.config)
        exit_cfg = self.config["simulation"]["exit_sweep"]
        exit_times = time_range(exit_cfg["start"], exit_cfg["end"], int(exit_cfg["interval_minutes"]))
        condition_cases = _condition_cases(self.config)
        costs_cfg = self.config["simulation"].get("costs", {})

        trades: list[Trade] = []

        self.emit(RunEvent("raw_data_save", "skipped", "Using already stored complete raw data"))
        for raw in raw_items:
            trades.extend(_simulate_raw_item(raw, signal_times, exit_times, condition_cases, costs_cfg))

        self.emit(RunEvent("sweep_simulation", "running", "Computing sweep metrics from stored raw data"))
        metrics = _compute_all_metrics(condition_cases, signal_times, exit_times, trades)
        metrics.sort(key=lambda item: (item.total_return_pct, item.stability_score, -abs(item.max_drawdown_pct)), reverse=True)
        self.emit(RunEvent("sweep_simulation", "success", f"Computed {len(metrics)} condition metrics"))
        return SimulationResult(raw_data=raw_items, trades=trades, metrics=metrics)


def _simulate_raw_item(
    raw: RawMarketData,
    signal_times: list[str],
    exit_times: list[str],
    condition_cases: list[dict],
    costs_cfg: dict,
) -> list[Trade]:
    trades: list[Trade] = []
    by_signal = {
        signal_time: [row for row in raw.stock_returns if row.signal_time == signal_time]
        for signal_time in signal_times
    }
    price_by_time = {row.time: row.price for row in raw.futures_prices}

    for signal_time in signal_times:
        signal_rows = by_signal[signal_time]
        entry_price = price_by_time.get(signal_time)
        if entry_price is None:
            continue
        for condition_cfg in condition_cases:
            if not signal_passes(signal_rows, condition_cfg):
                continue
            positive_count, triggered_symbols = _positive_context(signal_rows, condition_cfg)
            for exit_time in exit_times:
                exit_price = price_by_time.get(exit_time)
                if exit_price is None or exit_time <= signal_time:
                    continue
                gross_return_pct, fee_pct, slippage_pct, net_return_pct = _futures_return_components(
                    entry_price, exit_price, costs_cfg
                )
                trades.append(
                    Trade(
                        condition_name=condition_cfg.get("name", condition_cfg.get("rule", "condition")),
                        simulation_date=raw.simulation_date,
                        signal_time=signal_time,
                        exit_time=exit_time,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        gross_return_pct=gross_return_pct,
                        fee_pct=fee_pct,
                        slippage_pct=slippage_pct,
                        net_return_pct=net_return_pct,
                        positive_count=positive_count,
                        triggered_symbols=triggered_symbols,
                    )
                )
    return trades


def _compute_all_metrics(condition_cases: list[dict], signal_times: list[str], exit_times: list[str], trades: list[Trade]) -> list[ConditionMetrics]:
    condition_names = [case.get("name", case.get("rule", "condition")) for case in condition_cases]
    returns_by_condition: dict[tuple[str, str, str], list[float]] = {
        (c, s, e): [] for c in condition_names for s in signal_times for e in exit_times
    }
    for trade in trades:
        returns_by_condition[(trade.condition_name, trade.signal_time, trade.exit_time)].append(trade.net_return_pct)
    return [
        compute_metrics(condition_name, signal_time, exit_time, returns)
        for (condition_name, signal_time, exit_time), returns in returns_by_condition.items()
    ]


def _condition_cases(config: dict) -> list[dict]:
    cases = config["simulation"].get("signal_conditions")
    if cases:
        return list(cases)
    legacy = dict(config["simulation"].get("signal_condition", {}))
    legacy.setdefault("name", legacy.get("rule", "signal_condition"))
    return [legacy]


def _simulation_signal_times(config: dict) -> list[str]:
    historical = config["simulation"].get("historical_signal_time")
    if historical:
        return [historical]
    return list(config["market"]["nxt"]["signal_times"])


def _positive_context(signal_rows, condition_cfg: dict) -> tuple[int, list[str]]:
    threshold = float(condition_cfg.get("positive_threshold_pct", 0.0))
    comparison = condition_cfg.get("comparison", "greater_than")
    if comparison == "greater_or_equal":
        positives = [row for row in signal_rows if row.return_pct >= threshold]
    else:
        positives = [row for row in signal_rows if row.return_pct > threshold]
    return len(positives), [row.symbol for row in positives]


def _futures_return_components(entry_price: float, exit_price: float, costs_cfg: dict) -> tuple[float, float, float, float]:
    fee = float(costs_cfg.get("fee_rate", 0.0)) * 100
    slippage_ticks = float(costs_cfg.get("slippage_ticks", 0))
    tick_value_pct = float(costs_cfg.get("tick_value_pct", 0.0))
    slippage = slippage_ticks * tick_value_pct
    gross = ((exit_price - entry_price) / entry_price * 100)
    return gross, fee, slippage, gross - fee - slippage


def _futures_return_pct(entry_price: float, exit_price: float, costs_cfg: dict) -> float:
    return _futures_return_components(entry_price, exit_price, costs_cfg)[3]
