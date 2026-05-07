from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests


class KisApiError(RuntimeError):
    pass


class KisRestClient:
    def __init__(self, config: dict):
        kis_cfg = config["kis"]
        self.is_paper = bool(kis_cfg.get("is_paper", True))
        self.base_url = (kis_cfg["paper_base_url"] if self.is_paper else kis_cfg["base_url"]).rstrip("/")
        self.app_key = kis_cfg["app_key"]
        self.app_secret = kis_cfg["app_secret"]
        self.account_no = kis_cfg.get("account_no", "")
        self.token_cache_path = Path(kis_cfg.get("token_cache_path", "data/kis_token.json"))

    def get_market_cap_top(self, top_n: int, market_input_code: str = "0001") -> list[dict[str, Any]]:
        payload = self.get(
            "/uapi/domestic-stock/v1/ranking/market-cap",
            tr_id="FHPST01740000",
            params={
                "fid_input_price_2": "",
                "fid_cond_mrkt_div_code": "J",
                "fid_cond_scr_div_code": "20174",
                "fid_div_cls_code": "1",
                "fid_input_iscd": market_input_code,
                "fid_trgt_cls_code": "0",
                "fid_trgt_exls_cls_code": "0",
                "fid_input_price_1": "",
                "fid_vol_cnt": "",
            },
        )
        return list(payload.get("output", []))[:top_n]

    def get_overtime_price(self, symbol: str) -> dict[str, Any]:
        return self.get(
            "/uapi/domestic-stock/v1/quotations/inquire-overtime-price",
            tr_id="FHPST02300000",
            params={"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol},
        ).get("output", {})

    def get_futures_price(self, futures_code: str, market_div_code: str = "F") -> dict[str, Any]:
        return self.get(
            "/uapi/domestic-futureoption/v1/quotations/inquire-price",
            tr_id="FHMIF10000000",
            params={"FID_COND_MRKT_DIV_CODE": market_div_code, "FID_INPUT_ISCD": futures_code},
        ).get("output1", {})

    def get_futures_minute_chart(
        self,
        futures_code: str,
        input_date_yyyymmdd: str,
        input_time_hhmmss: str,
        market_div_code: str = "F",
    ) -> list[dict[str, Any]]:
        payload = self.get(
            "/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice",
            tr_id="FHKIF03020200",
            params={
                "FID_COND_MRKT_DIV_CODE": market_div_code,
                "FID_INPUT_ISCD": futures_code,
                "FID_HOUR_CLS_CODE": "60",
                "FID_PW_DATA_INCU_YN": "Y",
                "FID_FAKE_TICK_INCU_YN": "N",
                "FID_INPUT_DATE_1": input_date_yyyymmdd,
                "FID_INPUT_HOUR_1": input_time_hhmmss,
            },
        )
        return list(payload.get("output1") or payload.get("Output1") or [])

    def get(self, path: str, tr_id: str, params: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}{path}",
            headers=self._headers(tr_id),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("rt_cd", "0")) != "0":
            raise KisApiError(f"KIS API failed: {payload.get('msg_cd')} {payload.get('msg1')}")
        return payload

    def access_token(self) -> str:
        cached = self._read_cached_token()
        if cached:
            return cached

        response = requests.post(
            f"{self.base_url}/oauth2/tokenP",
            json={"grant_type": "client_credentials", "appkey": self.app_key, "appsecret": self.app_secret},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 86400))
        self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_cache_path.write_text(
            json.dumps({"access_token": token, "expires_at": time.time() + max(expires_in - 300, 60)}),
            encoding="utf-8",
        )
        return token

    def _headers(self, tr_id: str) -> dict[str, str]:
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self.access_token()}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P",
        }

    def _read_cached_token(self) -> str | None:
        if not self.token_cache_path.exists():
            return None
        try:
            payload = json.loads(self.token_cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if float(payload.get("expires_at", 0)) <= time.time():
            return None
        return payload.get("access_token")
