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
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import os

KST = timezone(timedelta(hours=9))

# launchd 레이블 → 표시 시각 매핑
LAUNCHD_LABELS = [
    ("com.shortsauto.batch_0700", "07:00"),
    ("com.shortsauto.batch_1530", "14:30"),
    ("com.shortsauto.batch_1800", "17:30"),
    ("com.shortsauto.batch_2000", "21:00"),
]


def _launchctl_info(label: str) -> dict:
    """launchctl list로 서비스 상태 조회."""
    try:
        out = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True, text=True, timeout=5,
        ).stdout
        info: dict = {}
        for line in out.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                info[k.strip().strip('"')] = v.strip().strip('";')
        return info
    except Exception:
        return {}


def _label_status(label: str) -> tuple[str, str]:
    """(icon, status_text) 반환."""
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] == label:
                pid, exit_code = parts[0], parts[1]
                if pid != "-":
                    return "🟢", f"실행 중 (PID {pid})"
                if exit_code == "0":
                    return "✅", "정상 완료"
                if exit_code == "-1":
                    return "⏳", "대기 중"
                return "❌", f"종료코드 {exit_code}"
        return "⚪", "미등록"
    except Exception:
        return "❓", "확인 불가"


def main() -> None:
    from src.config import get_settings
    from src.db import open_database
    from src.notify.discord_webhook import DiscordNotifier
    from src.repository import Repositories

    settings = get_settings()
    notifier = DiscordNotifier(webhook_url=settings.secrets.discord_webhook_url)

    now = datetime.now(KST)
    today_str = now.strftime("%Y-%m-%d (%a)")

    # ── launchd 서비스 현황 ────────────────────────────────────────
    schedule_lines = []
    for label, time_str in LAUNCHD_LABELS:
        icon, status = _label_status(label)
        schedule_lines.append(f"{icon} **{time_str}** `{label.split('.')[-1]}` — {status}")

    schedule_text = "\n".join(schedule_lines)

    # ── 전날 업로드 실적 ───────────────────────────────────────────
    db_path = settings.project_path(settings.section("database").get("path", "data/shorts.db"))
    db = open_database(db_path)
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
        perf_icon, perf_status = "✅", f"{yesterday_count}/{daily_target}개 (목표 달성)"
    elif yesterday_count > 0:
        perf_icon, perf_status = "⚠️", f"{yesterday_count}/{daily_target}개 (목표 미달)"
    else:
        perf_icon, perf_status = "❌", f"0/{daily_target}개 (업로드 없음)"

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
        daily_q = 10000
        cost = 1600
        margin = 1000
        remaining_uploads = max(0, (daily_q - used - margin) // cost)
        quota_text = f"오늘 quota: `{used:,}/{daily_q:,}` 사용 — 업로드 가능 **{remaining_uploads}개** 남음"
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
        extra={"예정 배치": f"{len(LAUNCHD_LABELS)}회", "알림 시각": now.strftime("%H:%M KST")},
    )
    print(f"[notify_schedule] 알림 발송 완료 {now.strftime('%H:%M')}")


if __name__ == "__main__":
    main()
