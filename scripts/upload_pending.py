"""업로드 실패 영상 재업로드 스크립트.

렌더 완료(video_path 존재)됐지만 업로드 실패한 영상을 재업로드한다.

사용:
    python -m scripts.upload_pending              # 최근 실패 영상 전체
    python -m scripts.upload_pending --ids 66 67  # 특정 video_id 지정
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.stdout is None:
    sys.stdout = open("nul", "w", encoding="utf-8")
else:
    sys.stdout.reconfigure(encoding="utf-8")

from src.config import get_settings
from src.db import open_database
from src.notify.discord_webhook import DiscordNotifier
from src.pipeline import PipelineContext
from src.pipeline.upload_stage import run as run_upload
from src.repository import Repositories
from src.utils.concept_log import append_concept
from src.utils.logging import get_logger, setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", type=int, nargs="*", help="업로드할 video_id 목록")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(
        log_dir=settings.section("observability").get("log_dir", "logs"),
        level=settings.secrets.log_level,
        project_root=PROJECT_ROOT,
    )
    log = get_logger("upload_pending")
    run_id = uuid.uuid4().hex[:12]

    db_path = settings.project_path(settings.section("database").get("path", "data/shorts.db"))
    db = open_database(db_path, init=True)
    repos = Repositories(db)

    ctx = PipelineContext(
        settings=settings,
        repos=repos,
        run_id=run_id,
        log=log,
        project_root=PROJECT_ROOT,
    )

    notifier = DiscordNotifier(webhook_url=settings.secrets.discord_webhook_url)
    concept_log_path = settings.project_path("data/concept_log.jsonl")

    # 업로드 대상 video_id 목록 결정
    if args.ids:
        video_ids = args.ids
    else:
        # 렌더 완료됐지만 최신 업로드 상태가 failed인 영상
        rows = db.fetchall("""
            SELECT v.id
            FROM videos v
            WHERE v.video_path IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM uploads u WHERE u.video_id = v.id
              )
              AND (
                  SELECT status FROM uploads u WHERE u.video_id = v.id ORDER BY u.id DESC LIMIT 1
              ) = 'failed'
            ORDER BY v.id DESC
            LIMIT 10
        """)
        video_ids = [r["id"] for r in rows]

    if not video_ids:
        print("[upload_pending] 재업로드 대상 영상 없음")
        db.close()
        return

    print(f"[upload_pending] 재업로드 대상: video_ids={video_ids}  run_id={run_id}")

    notifier.send(
        title=f"재업로드 시작 — {len(video_ids)}개",
        level="INFO",
        content=f"video_ids: {video_ids}\nrun_id: `{run_id}`",
    )

    success, failed = 0, 0
    for vid in video_ids:
        try:
            upload_id = run_upload(ctx, video_id=vid)
            upload_rec = repos.db.fetchone(
                "SELECT youtube_video_id FROM uploads WHERE id = ?", (upload_id,)
            )
            yt_id = (upload_rec or {}).get("youtube_video_id", "")
            yt_url = f"https://youtu.be/{yt_id}" if yt_id else "업로드 완료(ID 확인 중)"

            video_rec = repos.videos.get(vid)
            script_id = (video_rec or {}).get("script_id")
            script_rec = repos.scripts.get(script_id) if script_id else None
            title = (script_rec or {}).get("title", "?")
            hook_pattern = (script_rec or {}).get("hook_pattern", "?")
            duration = round(float((video_rec or {}).get("duration_sec") or 0), 1)

            print(f"  [OK] video_id={vid}  {yt_url}")

            append_concept(
                concept_log_path,
                video_id=vid,
                script_id=script_id,
                title=title,
                hook_pattern=hook_pattern,
                hook_preview=(script_rec or {}).get("hook", "")[:80],
                yt_url=yt_url,
                sim_uploaded=(script_rec or {}).get("similarity_uploaded"),
            )

            notifier.send(
                title=f"재업로드 완료 — video_id={vid}",
                level="SUCCESS",
                content=f"**제목:** {title}\n**길이:** {duration}초\n**URL:** {yt_url}",
                extra={"video_id": str(vid), "run_id": run_id},
            )
            success += 1

        except Exception as e:
            msg = f"video_id={vid}: {type(e).__name__}: {e}"
            print(f"  [ERROR] {msg}")
            log.error("upload_pending_failed", video_id=vid, error=repr(e))
            notifier.send(
                title=f"재업로드 실패 — video_id={vid}",
                level="ERROR",
                content=f"```\n{msg[:300]}\n```",
                extra={"run_id": run_id},
            )
            failed += 1

    print(f"\n[upload_pending] 완료: {success}개 성공, {failed}개 실패")
    db.close()


if __name__ == "__main__":
    main()
