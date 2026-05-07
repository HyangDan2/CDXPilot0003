from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataPolicy:
    allow_current_price_fallback: bool = False
    allow_multi_signal_replication: bool = False
    require_complete_futures_times: bool = True

    @classmethod
    def for_mode(cls, mode: str) -> "DataPolicy":
        if mode == "mock":
            return cls(
                allow_current_price_fallback=False,
                allow_multi_signal_replication=True,
                require_complete_futures_times=True,
            )
        return cls(
            allow_current_price_fallback=False,
            allow_multi_signal_replication=False,
            require_complete_futures_times=True,
        )
