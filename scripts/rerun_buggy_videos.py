"""SSML 버그 기간 영상 재처리 스크립트.

bad audio(too long) → 삭제 → TTS 재합성 → 자막 → 렌더 → 업로드

사용:
    python -m scripts.rerun_buggy_videos
    python -m scripts.rerun_buggy_videos --script-ids 131,132,133,134,135
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.db import open_database
from src.repository import Repositories
from src.utils.logging import get_logger, setup_logging
from src.pipeline.context import PipelineContext, StageSkipped
from src.pipeline.tts_stage import run as run_tts
from src.pipeline.subtitle_stage import run as run_subtitle
from src.pipeline.render_stage import run as run_render
from src.pipeline.upload_stage import run as run_upload
from structlog import get_logger


def _delete_audio_cache(script_id: int, audio_dir: Path) -> None:
    """script_<id>_*.mp3/json 캐시 전부 삭제해 TTS 재합성 유도."""
    deleted = []
    for p in audio_dir.glob(f"script_{script_id}_*"):
        p.unlink(missing_ok=True)
        deleted.append(p.name)
    if deleted:
        print(f"  [cache] 삭제: {', '.join(deleted)}")


def _reset_video_row(repos: Repositories, video_id: int, audio_dir: Path, final_dir: Path) -> None:
    """videos 행을 초기 상태로 리셋해 render 단계 재실행 허용."""
    video = repos.videos.get(video_id)
    if video is None:
        return

    # 기존 렌더 결과물 삭제
    if video.get("video_path"):
        Path(video["video_path"]).unlink(missing_ok=True)
    if video.get("audio_path"):
        Path(video["audio_path"]).unlink(missing_ok=True)
    if video.get("subtitle_path"):
        Path(video["subtitle_path"]).unlink(missing_ok=True)

    # DB 초기화 (valid=0, 경로 전부 NULL) — tts_stage가 새 행을 INSERT하므로 기존 행 삭제
    repos.db.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    repos.db.execute("DELETE FROM uploads WHERE video_id = ?", (video_id,))
    print(f"  [db] video_id={video_id} 행 삭제 완료")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--script-ids",
        default="131,132,133,134,135",
        help="재처리할 script_id 목록 (콤마 구분)",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="업로드 단계 건너뜀 (로컬 렌더만)",
    )
    args = parser.parse_args()

    script_ids = [int(x.strip()) for x in args.script_ids.split(",") if x.strip()]
    settings = get_settings()
    setup_logging(
        log_dir=settings.section("observability").get("log_dir", "logs"),
        level="INFO",
        project_root=PROJECT_ROOT,
    )
    log = get_logger("rerun")
    run_id = uuid.uuid4().hex[:12]

    db_path = settings.project_path(
        settings.section("database").get("path", "data/shorts.db")
    )
    db = open_database(db_path, init=True)
    repos = Repositories(db)

    ctx = PipelineContext(
        settings=settings,
        repos=repos,
        run_id=run_id,
        log=log,
        project_root=PROJECT_ROOT,
    )

    audio_dir = PROJECT_ROOT / "output" / "audio"
    final_dir = PROJECT_ROOT / "output" / "final"

    print(f"\n[RERUN] script_ids={script_ids}  run_id={run_id}")

    for script_id in script_ids:
        print(f"\n{'='*50}")
        print(f"[RERUN] script_id={script_id} 재처리 시작")

        # 기존 video 행 찾기
        existing_video = repos.db.fetchone(
            "SELECT id FROM videos WHERE script_id = ? ORDER BY id DESC LIMIT 1",
            (script_id,),
        )

        # 캐시 삭제
        _delete_audio_cache(script_id, audio_dir)

        # 기존 비디오 행 리셋
        if existing_video:
            _reset_video_row(repos, existing_video["id"], audio_dir, final_dir)

        try:
            # TTS 재합성
            video_id = run_tts(ctx, script_id=script_id)
            video_rec = repos.videos.get(video_id)
            duration = round(float((video_rec or {}).get("duration_sec") or 0), 1)
            print(f"  [TTS] video_id={video_id}  {duration}초")

            if duration > 60:
                print(f"  [ERROR] TTS 여전히 비정상 ({duration}s > 60s) — 건너뜀")
                continue

            # 자막
            srt_path = run_subtitle(ctx, video_id=video_id)
            print(f"  [자막] {srt_path.name}")

            # 렌더
            final_path = run_render(ctx, video_id=video_id)
            size_mb = round(final_path.stat().st_size / 1024 / 1024, 1)
            print(f"  [렌더] {final_path.name}  {size_mb} MB")

            # 업로드
            if not args.skip_upload:
                try:
                    upload_id = run_upload(ctx, video_id=video_id)
                    upload_rec = repos.db.fetchone(
                        "SELECT youtube_video_id, status FROM uploads WHERE id = ?",
                        (upload_id,),
                    )
                    yt_id = (upload_rec or {}).get("youtube_video_id", "")
                    status = (upload_rec or {}).get("status", "?")
                    yt_url = f"https://youtu.be/{yt_id}" if yt_id else f"status={status}"
                    print(f"  [업로드] {yt_url}")
                except StageSkipped as e:
                    # 일일 상한 도달 — queued 레코드 삽입해 upload_pending이 내일 처리하도록
                    repos.db.execute(
                        "INSERT INTO uploads (video_id, status, error_msg) VALUES (?, 'queued', ?)",
                        (video_id, str(e)),
                    )
                    print(f"  [업로드] 일일 상한 — queued 등록, upload_pending으로 내일 처리")
            else:
                print("  [업로드] --skip-upload 로 건너뜀")

        except Exception as e:
            print(f"  [ERROR] script_id={script_id}: {e}")
            import traceback; traceback.print_exc()

    print(f"\n[RERUN] 완료")
    db.close()


if __name__ == "__main__":
    main()
