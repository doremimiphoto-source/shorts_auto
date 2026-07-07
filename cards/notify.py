"""Telegram 알림 (카드 시스템 전용).

무인 자동 게시의 성공/실패를 텔레그램으로 통지한다.
분리 원칙: src/ 미import. 봇 API 직접 호출. 쇼츠와 동일 봇 토큰 재사용(읽기).
키/알림 대상 미설정 시 조용히 무시(자동화 중단 방지).
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

from cards.config import get_card_secrets

log = logging.getLogger(__name__)


def _chat_ids() -> list[str]:
    raw = get_card_secrets().telegram_allowed_users or ""
    return [c.strip() for c in raw.split(",") if c.strip()]


def send(text: str) -> bool:
    """텔레그램 메시지 전송. 미설정/실패 시 False (예외 안 던짐)."""
    s = get_card_secrets()
    token = s.telegram_bot_token
    ids = _chat_ids()
    if not token or not ids:
        return False
    ok = False
    for chat_id in ids:
        try:
            data = urllib.parse.urlencode({
                "chat_id": chat_id, "text": text, "disable_web_page_preview": "true",
            }).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage", data=data)
            with urllib.request.urlopen(req, timeout=15) as resp:
                json.loads(resp.read().decode())
            ok = True
        except Exception as e:
            log.debug("telegram_send_failed err=%s", repr(e)[:120])
    return ok


# ── 편의 메시지 ────────────────────────────────────────────────────────────────
def notify_success(*, vertical: str, platform: str, title: str, post_id: str) -> None:
    send(f"✅ HiddenFindsDaily [{vertical}] {platform} 게시 성공\n"
         f"제목: {title}\npost_id: {post_id}")


def notify_failed(*, vertical: str, platform: str, error: str) -> None:
    send(f"❌ HiddenFindsDaily [{vertical}] {platform} 게시 실패\n{error[:300]}")


def notify_error(*, context: str, error: str) -> None:
    send(f"🔴 HiddenFindsDaily 오류 ({context})\n{error[:300]}")
