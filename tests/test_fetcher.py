from datetime import date

import pytest

from kosim.data.providers.kis_parsers import extract_futures_price_at_or_before
from kosim.data.providers.kis_rest import KisMarketDataProvider
from kosim.data.models import UniverseMember


def test_extract_futures_price_picks_nearest_row_at_or_before_target():
    rows = [
        {"futs_cntg_hour": "091000", "futs_prpr": "351.0"},
        {"futs_cntg_hour": "085000", "futs_prpr": "350.0"},
        {"futs_cntg_hour": "093000", "futs_prpr": "353.0"},
        {"futs_cntg_hour": "092000", "futs_prpr": "352.0"},
    ]

    assert extract_futures_price_at_or_before(rows, "09:25") == 352.0


def test_extract_futures_price_returns_none_when_no_prior_row_exists():
    rows = [{"futs_cntg_hour": "091000", "futs_prpr": "351.0"}]

    assert extract_futures_price_at_or_before(rows, "09:00") is None


def test_kis_provider_rejects_multi_time_nxt_signal_replication():
    provider = KisMarketDataProvider(
        {
            "kis": {
                "is_paper": True,
                "paper_base_url": "https://example.test",
                "base_url": "https://example.test",
                "app_key": "key",
                "app_secret": "secret",
            }
        }
    )

    with pytest.raises(ValueError, match="cannot create historical multi-time NXT snapshots"):
        provider.get_nxt_stock_returns(
            date(2026, 5, 7),
            [UniverseMember("005930", "Samsung", 1.0, 1)],
            ["08:00", "08:50"],
        )
