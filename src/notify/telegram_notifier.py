"""Telegram Bot API 직접 호출 알림 유틸리티.

python-telegram-bot 패키지 없이 urllib만으로 동작 (배치 스크립트에서 직접 호출).
TELEGRAM_BOT_TOKEN / TELEGRAM_ALLOWED_USERS 환경변수를 읽어 허용 사용자에게 메시지 전송.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class TelegramNotifier:
    """Telegram Bot API를 통한 푸시 알림."""

    API_BASE = "https://api.telegram.org"
    TIMEOUT = 10

    def __init__(
        self,
        *,
        bot_token: str = "",
        allowed_users: str = "",
    ) -> None:
        self._token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        raw_users = allowed_users or os.environ.get("TELEGRAM_ALLOWED_USERS", "")
        self._chat_ids: list[int] = [
            int(u.strip()) for u in raw_users.split(",") if u.strip().isdigit()
        ]

    def is_available(self) -> bool:
        return bool(self._token and self._chat_ids)

    def send(self, text: str, *, parse_mode: str = "HTML") -> bool:
        """허용된 모든 사용자에게 메시지 전송. 하나라도 성공하면 True."""
        if not self.is_available():
            return False

        url = f"{self.API_BASE}/bot{self._token}/sendMessage"
        success = False
        for chat_id in self._chat_ids:
            payload = json.dumps({
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }).encode()
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.TIMEOUT):
                    success = True
            except (urllib.error.URLError, Exception):
                pass
        return success

    def send_batch_failure(
        self,
        *,
        run_id: str,
        target: int,
        succeeded: int,
        errors: list[str],
    ) -> bool:
        """배치 전체 실패 전용 알림."""
        first_err = errors[0][:200] if errors else "알 수 없는 오류"
        text = (
            f"⚠️ <b>배치 실패</b>\n"
            f"결과: {succeeded}/{target}개 업로드\n"
            f"run_id: <code>{run_id}</code>\n\n"
            f"<b>첫 번째 오류:</b>\n<code>{_escape(first_err)}</code>"
        )
        if len(errors) > 1:
            text += f"\n\n총 {len(errors)}건 오류"
        return self.send(text)

    def send_llm_unavailable(self, *, run_id: str, backends: list[str]) -> bool:
        """LLM 백엔드 전체 불가 알림."""
        backend_str = " / ".join(backends) if backends else "gemini / groq"
        text = (
            f"🔴 <b>LLM 백엔드 불가</b>\n"
            f"실패 백엔드: {backend_str}\n"
            f"run_id: <code>{run_id}</code>\n\n"
            f"API 키·쿼터·네트워크를 확인하세요."
        )
        return self.send(text)


def _escape(text: str) -> str:
    """HTML 특수문자 이스케이프."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
