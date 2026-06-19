"""Telegram 봇 보안 — 사용자 화이트리스트."""

from __future__ import annotations

import os


def allowed_users() -> set[int]:
    """허용된 Telegram user_id 집합. .env의 TELEGRAM_ALLOWED_USERS 파싱."""
    raw = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def is_allowed(user_id: int) -> bool:
    users = allowed_users()
    if not users:
        return False  # 화이트리스트 미설정 시 전면 차단
    return user_id in users
