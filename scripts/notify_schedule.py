"""매일 06:30 배치 스케줄 사전 알림.

당일 예정 배치 내역과 전날 실적, YouTube quota 잔여량을
Discord 웹훅으로 발송한다.

실행:
    python -m scripts.notify_schedule
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.stdout is None:
    sys.stdout = open("nul", "w", encoding="utf-8")
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

KST = timezone(timedelta(hours=9))
TASKS = [
    ("ShortsAuto_0700", "07:00"),
    ("ShortsAuto_1530", "15:30"),
    ("ShortsAuto_1800", "18:00"),
    ("ShortsAuto_2200", "22:00"),
]


def _task_info(task_name: str) -> dict:
    """schtasks로 태스크 최근 실행 결과 조회."""
    try:
        out = subprocess.run(
            ["schtasks", "/query", "/tn", f"\\{task_name}", "/fo", "LIST", "/v"],
            capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace",
        ).stdout
        result, last_run = "", ""
        for line in out.splitlines():
            if "Last Result" in line:
                result = line.split(":", 1)[-1].strip()
            if "Last Run Time" in line:
                last_run = line.split(":", 1)[-1].strip()
        return {"result": result, "last_run": last_run}
    except Exception:
        return {"result": "?", "last_run": "?"}


def _result_icon(code: str) -> str:
    if code == "0":
        return "✅"
    if code in ("267011", "267014"):
        return "⏳"
    return "❌"


def main() -> None:
    from src.config import get_settings
    from src.db import open_database
    from src.notify.discord_webhook import DiscordNotifier
    from src.repository import Repositories

    settings = get_settings()
    notifier = DiscordNotifier(webhook_url=settings.secrets.discord_webhook_url)

    now = datetime.now(KST)
    today_str = now.strftime("%Y-%m-%d (%a)")

    # ── 태스크 스케줄 현황 ─────────────────────────────────────────
    schedule_lines = []
    for task_name, time_str in TASKS:
        info = _task_info(task_name)
        icon = _result_icon(info["result"])
        last = info["last_run"]
        # 마지막 실행일이 오늘이면 "오늘 HH:MM", 아니면 날짜만
        try:
            dt = datetime.strptime(last[:10], "%Y-%m-%d")
            if dt.date() == now.date():
                last_label = f"오늘 {last[11:16]}"
            else:
                last_label = last[:10]
        except Exception:
            last_label = last[:16] if last else "-"
        schedule_lines.append(f"{icon} **{time_str}** `{task_name}` — 직전 실행: {last_label}")

    schedule_text = "\n".join(schedule_lines)

    # ── 전날 업로드 실적 ───────────────────────────────────────────
    db = open_database(settings.project_path(settings.section("database").get("path", "data/shorts.db")))
    repos = Repositories(db)

    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_uploads = db.fetchall("""
        SELECT u.youtube_video_id, s.title, u.uploaded_at
        FROM uploads u
        JOIN videos v ON v.id = u.video_id
        JOIN scripts s ON s.id = v.script_id
        WHERE u.status = 'success'
          AND date(u.uploaded_at) = ?
        ORDER BY u.id DESC
    """, (yesterday,))

    daily_target = int(settings.section("pipeline").get("daily_target_count", 4))
    yesterday_count = len(yesterday_uploads)
    if yesterday_count >= daily_target:
        perf_icon = "✅"
        perf_status = f"{yesterday_count}/{daily_target}개 (목표 달성)"
    elif yesterday_count > 0:
        perf_icon = "⚠️"
        perf_status = f"{yesterday_count}/{daily_target}개 (목표 미달)"
    else:
        perf_icon = "❌"
        perf_status = f"0/{daily_target}개 (업로드 없음)"

    if yesterday_uploads:
        perf_lines = []
        for r in yesterday_uploads:
            yt = r.get("youtube_video_id", "")
            title = str(r.get("title", ""))[:35]
            url = f"https://youtu.be/{yt}"
            perf_lines.append(f"• [{title}]({url})")
        perf_text = (
            f"{perf_icon} **어제({yesterday}) 실적: {perf_status}**\n"
            + "\n".join(perf_lines)
        )
    else:
        perf_text = f"{perf_icon} **어제({yesterday}) 실적: {perf_status}**"

    # ── YouTube quota 잔여 ─────────────────────────────────────────
    try:
        used = repos.uploads.quota_used_today(oauth_client_name="default")
        daily = 10000
        cost = 1600
        margin = 1000
        remaining_uploads = max(0, (daily - used - margin) // cost)
        quota_text = f"오늘 quota: `{used:,}/{daily:,}` 사용 — 업로드 가능 **{remaining_uploads}개** 남음"
    except Exception as e:
        quota_text = f"quota 조회 실패: {e}"

    db.close()

    # ── 발송 ──────────────────────────────────────────────────────
    content = (
        f"**오늘 배치 스케줄:**\n{schedule_text}\n\n"
        f"{perf_text}\n\n"
        f"{quota_text}"
    )

    notifier.send(
        title=f"📅 {today_str} 배치 스케줄",
        level="INFO",
        content=content,
        extra={"예정 배치": f"{len(TASKS)}회", "알림 시각": now.strftime("%H:%M KST")},
    )
    print(f"[notify_schedule] 알림 발송 완료 {now.strftime('%H:%M')}")


if __name__ == "__main__":
    main()
