from __future__ import annotations

from datetime import date

from kosim.data.models import FuturesPrice, StockReturn, UniverseMember
from kosim.data.providers.kis_parsers import extract_futures_price_at_or_before, to_float
from kosim.data.providers.policy import DataPolicy
from kosim.kis_client import KisRestClient


class KisMarketDataProvider:
    """KIS REST adapter for documented endpoints."""

    def __init__(self, config: dict, policy: DataPolicy | None = None):
        self.config = config
        self.policy = policy or DataPolicy.for_mode("kis_rest")
        self.client = KisRestClient(config)

    def get_market_cap_top(self, basis_date: date, market: str, top_n: int) -> list[UniverseMember]:
        rows = self.client.get_market_cap_top(top_n=top_n, market_input_code="0001")
        members: list[UniverseMember] = []
        for index, row in enumerate(rows, start=1):
            members.append(
                UniverseMember(
                    symbol=str(row.get("mksc_shrn_iscd", "")).zfill(6),
                    name=str(row.get("hts_kor_isnm", "")),
                    market_cap=to_float(row.get("stck_avls") or row.get("market_cap") or 0.0),
                    rank=int(to_float(row.get("data_rank") or index)),
                )
            )
        return members[:top_n]

    def get_nxt_stock_returns(
        self,
        simulation_date: date,
        universe: list[UniverseMember],
        signal_times: list[str],
    ) -> list[StockReturn]:
        if len(signal_times) != 1 and not self.policy.allow_multi_signal_replication:
            raise ValueError(
                "KIS REST mode cannot create historical multi-time NXT snapshots. "
                "Use exactly one signal time from a real fetch, or import stored snapshots."
            )
        rows: list[StockReturn] = []
        for member in universe:
            payload = self.client.get_overtime_price(member.symbol)
            return_pct = to_float(payload.get("ovtm_untp_prdy_ctrt"))
            price = to_float(payload.get("ovtm_untp_prpr"))
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
            price = extract_futures_price_at_or_before(chart_rows, time_value)
            if price is None:
                raise ValueError(
                    f"KIS futures minute price missing for {simulation_date.isoformat()} {time_value}. "
                    "Current-price fallback is disabled for historical simulation."
                )
            prices.append(FuturesPrice(symbol=symbol, time=time_value, price=price))
        return prices
