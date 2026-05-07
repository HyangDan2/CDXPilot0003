from __future__ import annotations

from kosim.data.providers.base import MarketDataProvider
from kosim.data.providers.kis_rest import KisMarketDataProvider
from kosim.data.providers.mock import MockMarketDataProvider
from kosim.data.providers.policy import DataPolicy


def create_market_data_provider(config: dict) -> MarketDataProvider:
    mode = config.get("app", {}).get("mode", "mock")
    if mode == "live":
        mode = "kis_rest"
    if mode == "kis_rest":
        return KisMarketDataProvider(config, DataPolicy.for_mode(mode))
    return MockMarketDataProvider()
