"""Telegram 봇 진입점.

실행: python -m bot.main
launchd com.shortsauto.bot 서비스로 상주 실행된다.

슬래시 커맨드 (빠른 접근):
  /status   — 파이프라인 현황
  /logs     — 오늘 에러 로그
  /run      — 배치 즉시 실행 (1건)
  /stop     — 킬스위치 ON
  /go       — 킬스위치 OFF
  /clear    — 대화 히스토리 초기화
  /help     — 커맨드 목록

자연어 메시지는 Claude API를 통해 처리된다.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가 (python -m bot.main 실행 시 필요)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# .env 로드 (launchd 환경에는 환경변수가 없으므로)
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .agent import Agent
from .security import is_allowed

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bot")

_agent: Agent | None = None


def _get_agent() -> Agent:
    global _agent
    if _agent is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY 환경변수가 설정되지 않았습니다.")
        _agent = Agent(api_key=api_key)
    return _agent


# ──────────────────────────────────────────────
# 공통 유틸
# ──────────────────────────────────────────────

def _chunks(text: str, size: int = 4000) -> list[str]:
    """Telegram 메시지 최대 길이(4096)에 맞게 분할."""
    parts = []
    while text:
        parts.append(text[:size])
        text = text[size:]
    return parts


async def _guard(update: Update) -> bool:
    """허용된 사용자가 아니면 거부 메시지 전송 후 False 반환."""
    user = update.effective_user
    if not user or not is_allowed(user.id):
        if update.message:
            await update.message.reply_text("⛔ 접근 권한이 없습니다.")
        log.warning("unauthorized user_id=%s", user.id if user else "unknown")
        return False
    return True


async def _run_agent(update: Update, text: str) -> None:
    """Agent.process를 별도 스레드에서 실행하고 결과를 Telegram으로 전송."""
    user_id = update.effective_user.id
    await update.message.chat.send_action("typing")
    try:
        response = await asyncio.to_thread(_get_agent().process, text, user_id)
    except Exception as exc:
        log.exception("agent error")
        response = f"❌ 오류: {exc}"
    for chunk in _chunks(response):
        await update.message.reply_text(chunk)


# ──────────────────────────────────────────────
# 슬래시 커맨드 핸들러
# ──────────────────────────────────────────────

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await update.message.reply_text(
        "📋 *shorts\\_auto 봇 커맨드*\n\n"
        "/status — 파이프라인 현황 조회\n"
        "/logs   — 오늘 에러 로그\n"
        "/run    — 배치 즉시 실행 (1건)\n"
        "/stop   — 킬스위치 ON (배치 중단)\n"
        "/go     — 킬스위치 OFF (배치 재개)\n"
        "/clear  — 대화 히스토리 초기화\n"
        "/help   — 이 도움말\n\n"
        "자연어로도 말씀하세요 — Claude가 알아서 처리합니다.",
        parse_mode="MarkdownV2",
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await _run_agent(update, "지금 파이프라인 현황 알려줘. get_status 도구로 확인해.")


async def cmd_logs(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await _run_agent(update, "오늘 에러 로그만 보여줘. 원인 분석도 해줘.")


async def cmd_run(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await _run_agent(update, "현황 먼저 확인하고, 실행해도 괜찮으면 배치 1건 바로 실행해줘.")


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await _run_agent(update, "킬스위치 활성화해줘. 배치 중단이 필요해.")


async def cmd_go(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await _run_agent(update, "킬스위치 해제해줘. 배치 재개할게.")


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    user_id = update.effective_user.id
    _get_agent().clear_history(user_id)
    await update.message.reply_text("대화 히스토리를 초기화했습니다.")


# ──────────────────────────────────────────────
# 자연어 메시지 핸들러
# ──────────────────────────────────────────────

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not await _guard(update):
        return
    await _run_agent(update, update.message.text)


# ──────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────

def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 환경변수가 설정되지 않았습니다.")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("logs",   cmd_logs))
    app.add_handler(CommandHandler("run",    cmd_run))
    app.add_handler(CommandHandler("stop",   cmd_stop))
    app.add_handler(CommandHandler("go",     cmd_go))
    app.add_handler(CommandHandler("clear",  cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    log.info("Telegram Bot 시작 (polling)...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
