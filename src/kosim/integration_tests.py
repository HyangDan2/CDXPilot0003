from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from kosim.kis_client import KisRestClient
from kosim.reports.llm_client import OpenAICompatibleLLMClient
from kosim.reports.telegram import TelegramClient


@dataclass(frozen=True)
class IntegrationTestResult:
    name: str
    ok: bool
    message: str


def test_kis_rest(config: dict) -> IntegrationTestResult:
    try:
        client = KisRestClient(config)
        token = client.access_token()
        token_msg = f"token ok, length={len(token)}"
        try:
            rows = client.get_market_cap_top(top_n=1)
            return IntegrationTestResult("KIS REST", True, f"{token_msg}; market-cap rows={len(rows)}")
        except Exception as exc:
            return IntegrationTestResult(
                "KIS REST",
                True,
                f"{token_msg}; token works, market-cap endpoint check failed separately: {exc}",
            )
    except Exception as exc:
        return IntegrationTestResult("KIS REST", False, str(exc))


def test_telegram(config: dict) -> IntegrationTestResult:
    try:
        client = TelegramClient(config.get("telegram", {}))
        if not client.enabled:
            return IntegrationTestResult("Telegram", False, "telegram.enabled is false")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        client.send_text(f"KOSIM Telegram connection test: {stamp}")
        return IntegrationTestResult("Telegram", True, "test message sent")
    except Exception as exc:
        return IntegrationTestResult("Telegram", False, str(exc))


def test_llm(config: dict) -> IntegrationTestResult:
    try:
        llm_cfg = dict(config.get("llm", {}))
        if not llm_cfg.get("enabled", False):
            return IntegrationTestResult("LLM", False, "llm.enabled is false")
        llm_cfg["max_output_tokens"] = min(int(llm_cfg.get("max_output_tokens", 12000)), 128)
        client = OpenAICompatibleLLMClient(llm_cfg)
        response = client.analyze(
            'Use only this prompt. Return only this Korean sentence: "LLM 연결 테스트 성공"'
        )
        return IntegrationTestResult("LLM", True, response.content[:500])
    except Exception as exc:
        return IntegrationTestResult("LLM", False, str(exc))
