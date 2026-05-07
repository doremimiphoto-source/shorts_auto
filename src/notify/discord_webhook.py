"""Discord Webhook 알림 (FR-8.4)."""

from __future__ import annotations

from typing import Any


class DiscordNotifier:
    """Discord Webhook으로 메시지 송출."""

    def __init__(self, *, webhook_url: str, timeout_seconds: float = 10.0) -> None:
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return bool(self.webhook_url)

    def send(
        self,
        *,
        content: str,
        title: str | None = None,
        level: str = "INFO",
        extra: dict[str, Any] | None = None,
        image_url: str | None = None,
        url: str | None = None,
    ) -> bool:
        """메시지 전송. 성공 시 True. 실패하면 False (예외 무시 — 알림 실패가 파이프라인을 중단시키지 않음)."""
        if not self.is_available():
            return False
        import httpx

        embed: dict[str, Any] = {
            "title": title or f"[{level}]",
            "description": content[:4000],
            "color": _color(level),
        }
        if url:
            embed["url"] = url
        if image_url:
            embed["image"] = {"url": image_url}
        if extra:
            embed["fields"] = [
                {"name": k[:256], "value": str(v)[:1024], "inline": True}
                for k, v in list(extra.items())[:10]
            ]
        payload = {"embeds": [embed]}
        try:
            r = httpx.post(self.webhook_url, json=payload, timeout=self.timeout_seconds)
            return 200 <= r.status_code < 300
        except Exception:
            return False


def _color(level: str) -> int:
    return {
        "INFO": 0x3498DB,
        "WARNING": 0xF39C12,
        "ERROR": 0xE74C3C,
        "CRITICAL": 0xC0392B,
        "SUCCESS": 0x2ECC71,
    }.get(level.upper(), 0x95A5A6)
