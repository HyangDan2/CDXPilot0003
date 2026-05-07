from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    name: str
    market_cap: float
    rank: int


@dataclass(frozen=True)
class StockReturn:
    symbol: str
    name: str
    signal_time: str
    return_pct: float
    price: float


@dataclass(frozen=True)
class FuturesPrice:
    symbol: str
    time: str
    price: float


@dataclass(frozen=True)
class NxtSnapshot:
    simulation_date: date
    snapshot_time: str
    universe_basis_date: date
    symbol: str
    name: str
    price: float
    return_pct: float
    volume: float = 0.0
    source: str = "nxt"


@dataclass(frozen=True)
class RawMarketData:
    simulation_date: date
    universe_basis_date: date
    universe: list[UniverseMember]
    stock_returns: list[StockReturn]
    futures_prices: list[FuturesPrice]
