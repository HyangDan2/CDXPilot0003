from __future__ import annotations

from pathlib import Path

import requests


class TelegramClient:
    def __init__(self, config: dict):
        self.enabled = bool(config.get("enabled", False))
        self.bot_token = config.get("bot_token", "")
        self.chat_id = config.get("chat_id", "")

    def send_markdown(self, text: str) -> None:
        if not self.enabled:
            return
        self._validate()
        self._send_message(text[:4000], parse_mode="Markdown")

    def send_text(self, text: str) -> None:
        if not self.enabled:
            return
        self._validate()
        self._send_message(text[:4000], parse_mode=None)

    def send_text_chunks(self, text: str, chunk_size: int = 3500) -> None:
        if not self.enabled:
            return
        self._validate()
        chunk_size = max(500, min(chunk_size, 4000))
        for start in range(0, len(text), chunk_size):
            self._send_message(text[start : start + chunk_size], parse_mode=None)

    def _send_message(self, text: str, parse_mode: str | None) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        data = {"chat_id": self.chat_id, "text": text}
        if parse_mode:
            data["parse_mode"] = parse_mode
        response = requests.post(
            url,
            data=data,
            timeout=30,
        )
        response.raise_for_status()

    def send_file(self, path: str | Path, caption: str = "") -> None:
        if not self.enabled:
            return
        self._validate()
        file_path = Path(path)
        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        with file_path.open("rb") as handle:
            response = requests.post(
                url,
                data={"chat_id": self.chat_id, "caption": caption[:1024]},
                files={"document": handle},
                timeout=60,
            )
        response.raise_for_status()

    def send_photo(self, path: str | Path, caption: str = "") -> None:
        if not self.enabled:
            return
        self._validate()
        file_path = Path(path)
        url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        with file_path.open("rb") as handle:
            response = requests.post(
                url,
                data={"chat_id": self.chat_id, "caption": caption[:1024]},
                files={"photo": handle},
                timeout=60,
            )
        response.raise_for_status()

    def _validate(self) -> None:
        if not self.bot_token or self.bot_token.startswith("YOUR_"):
            raise ValueError("Telegram bot_token is not configured.")
        if not self.chat_id or self.chat_id.startswith("YOUR_"):
            raise ValueError("Telegram chat_id is not configured.")
