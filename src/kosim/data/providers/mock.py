from __future__ import annotations

import hashlib
from datetime import date
from math import sin, tau

from kosim.data.models import FuturesPrice, StockReturn, UniverseMember


class MockMarketDataProvider:
    """Deterministic offline provider used for development and tests."""

    DEFAULT_NAMES = {
        "005930": "Samsung Electronics",
        "000660": "SK Hynix",
        "373220": "LG Energy Solution",
        "207940": "Samsung Biologics",
        "005380": "Hyundai Motor",
        "068270": "Celltrion",
        "000270": "Kia",
        "105560": "KB Financial",
        "005490": "POSCO Holdings",
        "035420": "NAVER",
        "006400": "Samsung SDI",
        "051910": "LG Chem",
    }
    DEFAULT_SYMBOLS = list(DEFAULT_NAMES)

    def get_market_cap_top(self, basis_date: date, market: str, top_n: int) -> list[UniverseMember]:
        symbols = self.DEFAULT_SYMBOLS[: max(top_n, 1)]
        salt = int(basis_date.strftime("%Y%m%d"))
        members: list[UniverseMember] = []
        for index, symbol in enumerate(symbols, start=1):
            cap = 500_000_000_000_000 - index * 17_000_000_000_000 + (salt % 97) * 1_000_000_000
            members.append(UniverseMember(symbol=symbol, name=self.DEFAULT_NAMES[symbol], market_cap=float(cap), rank=index))
        return members[:top_n]

    def get_nxt_stock_returns(
        self,
        simulation_date: date,
        universe: list[UniverseMember],
        signal_times: list[str],
    ) -> list[StockReturn]:
        rows: list[StockReturn] = []
        for member in universe:
            for signal_time in signal_times:
                seed = _stable_seed(simulation_date.isoformat(), member.symbol, signal_time)
                return_pct = round(((seed % 801) - 300) / 1000, 3)
                price = round(50_000 * (1 + (seed % 1000) / 5000), 2)
                rows.append(
                    StockReturn(
                        symbol=member.symbol,
                        name=member.name,
                        signal_time=signal_time,
                        return_pct=return_pct,
                        price=price,
                    )
                )
        return rows

    def get_futures_prices(self, simulation_date: date, symbol: str, times: list[str]) -> list[FuturesPrice]:
        rows: list[FuturesPrice] = []
        base = 350 + (_stable_seed(simulation_date.isoformat(), symbol) % 900) / 100
        day_bias = ((_stable_seed("daily_bias", simulation_date.isoformat(), symbol) % 401) - 200) / 1000
        amplitude = 0.35 + (_stable_seed("amplitude", simulation_date.isoformat(), symbol) % 250) / 1000
        phase = (_stable_seed("phase", simulation_date.isoformat(), symbol) % 1000) / 1000
        previous_noise = 0.0
        for index, time_value in enumerate(times):
            seed = _stable_seed(simulation_date.isoformat(), symbol, time_value)
            noise = (((seed % 201) - 100) / 1000) * 0.45 + previous_noise * 0.55
            previous_noise = noise
            intraday_wave = amplitude * sin(tau * (index / max(len(times), 1) + phase))
            rows.append(FuturesPrice(symbol=symbol, time=time_value, price=round(base + day_bias + intraday_wave + noise, 3)))
        return rows


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)
