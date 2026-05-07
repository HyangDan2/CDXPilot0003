from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str


class OpenAICompatibleLLMClient:
    def __init__(self, config: dict):
        self.base_url = str(config.get("base_url", "")).rstrip("/")
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "nvidia/nemotron-120b")
        self.temperature = float(config.get("temperature", 0.5))
        self.timeout_seconds = int(config.get("timeout_seconds", 300))
        self.max_output_tokens = int(config.get("max_output_tokens", 12000))

    def analyze(self, prompt: str) -> LLMResponse:
        if not self.base_url or self.base_url.startswith("YOUR_"):
            raise ValueError("LLM base_url is not configured.")
        if not self.api_key or self.api_key.startswith("YOUR_"):
            raise ValueError("LLM api_key is not configured.")

        url = f"{self.base_url}/chat/completions"
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
                "max_tokens": self.max_output_tokens,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return LLMResponse(content=content, model=self.model)
