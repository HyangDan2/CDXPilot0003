from __future__ import annotations

import hashlib
from datetime import date
from typing import Protocol

from kosim.kis_client import KisRestClient
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
        for index, time_value in enumerate(times):
            seed = _stable_seed(simulation_date.isoformat(), symbol, time_value)
            drift = (index * 0.03) + (((seed % 201) - 100) / 1000)
            rows.append(FuturesPrice(symbol=symbol, time=time_value, price=round(base + drift, 3)))
        return rows


class KisMarketDataProvider:
    """KIS REST adapter for documented endpoints.

    NXT historical time snapshots are not available through the REST sheets
    inspected so far. This adapter can fetch current overtime/NXT-adjacent
    returns and futures prices, but historical multi-day sweep quality still
    depends on a persisted raw-data archive or a confirmed historical endpoint.
    """

    def __init__(self, config: dict):
        self.config = config
        self.client = KisRestClient(config)

    def get_market_cap_top(self, basis_date: date, market: str, top_n: int) -> list[UniverseMember]:
        rows = self.client.get_market_cap_top(top_n=top_n, market_input_code="0001")
        members: list[UniverseMember] = []
        for index, row in enumerate(rows, start=1):
            members.append(
                UniverseMember(
                    symbol=str(row.get("mksc_shrn_iscd", "")).zfill(6),
                    name=str(row.get("hts_kor_isnm", "")),
                    market_cap=_to_float(row.get("stck_avls") or row.get("market_cap") or 0.0),
                    rank=int(_to_float(row.get("data_rank") or index)),
                )
            )
        return members[:top_n]

    def get_nxt_stock_returns(
        self,
        simulation_date: date,
        universe: list[UniverseMember],
        signal_times: list[str],
    ) -> list[StockReturn]:
        rows: list[StockReturn] = []
        for member in universe:
            payload = self.client.get_overtime_price(member.symbol)
            return_pct = _to_float(payload.get("ovtm_untp_prdy_ctrt"))
            price = _to_float(payload.get("ovtm_untp_prpr"))
            for signal_time in signal_times:
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
        prices: list[FuturesPrice] = []
        for time_value in times:
            chart_rows = self.client.get_futures_minute_chart(
                futures_code=symbol,
                input_date_yyyymmdd=simulation_date.strftime("%Y%m%d"),
                input_time_hhmmss=time_value.replace(":", "") + "00",
            )
            price = _extract_futures_price_at_or_before(chart_rows, time_value)
            if price is None:
                current = self.client.get_futures_price(symbol)
                price = _to_float(current.get("futs_prpr"))
            prices.append(FuturesPrice(symbol=symbol, time=time_value, price=price))
        return prices


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _to_float(value) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _extract_futures_price_at_or_before(rows: list[dict], target_time: str) -> float | None:
    target = target_time.replace(":", "")
    for row in rows:
        row_time = str(
            row.get("stck_cntg_hour")
            or row.get("cntg_hour")
            or row.get("futs_cntg_hour")
            or row.get("hour")
            or ""
        )[:4]
        if row_time and row_time <= target:
            price = _to_float(row.get("futs_prpr") or row.get("stck_prpr") or row.get("prpr"))
            if price:
                return price
    return None
