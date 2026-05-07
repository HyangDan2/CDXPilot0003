from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from kosim.data.calendar import previous_trading_day
from kosim.data.providers.base import MarketDataProvider
from kosim.data.models import UniverseMember


@dataclass(frozen=True)
class UniverseResolution:
    simulation_date: date
    basis_date: date
    members: list[UniverseMember]


class UniverseResolver:
    def __init__(self, provider: MarketDataProvider, config: dict, holidays: set[date] | None = None):
        self.provider = provider
        self.config = config
        self.holidays = holidays or set()

    def resolve(self, simulation_date: date) -> UniverseResolution:
        source = self.config.get("source", "previous_trading_day_kospi_market_cap")
        top_n = int(self.config.get("top_n", 10))
        basis_date = previous_trading_day(simulation_date, self.holidays)

        if source == "previous_trading_day_kospi_market_cap":
            members = self.provider.get_market_cap_top(basis_date, self.config.get("market", "KOSPI"), top_n)
        elif source == "manual":
            symbols = self.config.get("symbols", [])
            members = [
                UniverseMember(symbol=symbol, name=symbol, market_cap=0.0, rank=index)
                for index, symbol in enumerate(symbols[:top_n], start=1)
            ]
        else:
            fallback = self.config.get("fallback", {})
            symbols = fallback.get("symbols", [])
            members = [
                UniverseMember(symbol=symbol, name=symbol, market_cap=0.0, rank=index)
                for index, symbol in enumerate(symbols[:top_n], start=1)
            ]

        if len(members) < top_n:
            raise ValueError(f"Universe resolver returned {len(members)} members, expected {top_n}.")
        return UniverseResolution(simulation_date=simulation_date, basis_date=basis_date, members=members[:top_n])
