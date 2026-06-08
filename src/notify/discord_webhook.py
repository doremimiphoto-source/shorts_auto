"""Discord Webhook 알림 (FR-8.4)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DiscordNotifier:
    """Discord Webhook으로 메시지 송출."""

    def __init__(
        self,
        *,
        webhook_url: str,
        timeout_seconds: float = 10.0,
        queue_path: "Path | str | None" = None,
    ) -> None:
        self.webhook_url = webhook_url
        self.timeout_seconds = timeout_seconds
        self._queue_path = Path(queue_path) if queue_path else None

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
        """메시지 전송. 성공 시 True. 실패하면 False (예외 무시 — 알림 실패가 파이프라인을 중단시키지 않음).
        queue_path 설정 시 실패한 알림을 파일에 저장해 다음 실행 시 재발송한다."""
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
            self._enqueue(
                content=content, title=title, level=level,
                extra=extra, image_url=image_url, url=url,
            )
            return False

    def _enqueue(self, **kwargs: Any) -> None:
        """발송 실패 알림을 큐 파일에 저장."""
        if not self._queue_path:
            return
        try:
            self._queue_path.parent.mkdir(parents=True, exist_ok=True)
            with self._queue_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(kwargs, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def flush_queue(self) -> int:
        """큐에 쌓인 미발송 알림을 재발송. 발송 성공 수 반환."""
        if not self._queue_path or not self._queue_path.exists():
            return 0
        try:
            lines = self._queue_path.read_text(encoding="utf-8").splitlines()
            self._queue_path.unlink()
        except Exception:
            return 0

        sent, failed = 0, []
        for line in lines:
            if not line.strip():
                continue
            try:
                kwargs = json.loads(line)
                # flush 중에는 큐 저장 비활성화 (무한 재귀 방지)
                orig_qp, self._queue_path = self._queue_path, None
                ok = self.send(**kwargs)
                self._queue_path = orig_qp
                if ok:
                    sent += 1
                else:
                    failed.append(line)
            except Exception:
                failed.append(line)

        if failed:
            try:
                with self._queue_path.open("w", encoding="utf-8") as f:  # type: ignore[union-attr]
                    f.write("\n".join(failed) + "\n")
            except Exception:
                pass
        return sent


def _color(level: str) -> int:
    return {
        "INFO": 0x3498DB,
        "WARNING": 0xF39C12,
        "ERROR": 0xE74C3C,
        "CRITICAL": 0xC0392B,
        "SUCCESS": 0x2ECC71,
    }.get(level.upper(), 0x95A5A6)
