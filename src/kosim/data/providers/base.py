from __future__ import annotations

from datetime import date
from typing import Protocol

from kosim.data.models import FuturesPrice, StockReturn, UniverseMember


class MarketDataProvider(Protocol):
    def get_market_cap_top(self, basis_date: date, market: str, top_n: int) -> list[UniverseMember]:
        ...

    def get_nxt_stock_returns(
        self,
        simulation_date: date,
        universe: list[UniverseMember],
        signal_times: list[str],
    ) -> list[StockReturn]:
        ...

    def get_futures_prices(
        self,
        simulation_date: date,
        symbol: str,
        times: list[str],
    ) -> list[FuturesPrice]:
        ...
