"""파이프라인 오케스트레이터 (Entry point).

사용 예:
    python -m src.main --dry-run             # 의존성 검증만
    python -m src.main                        # 1회 실행 (영상 1개 생성·업로드)
    python -m src.main --skip-upload          # 업로드 단계 건너뛰기
    python -m src.main --resume               # Kill-Switch 해제 (§12.2)

Windows 작업 스케줄러가 일 3회 본 모듈을 호출한다 (FR-7.1).
"""

from __future__ import annotations

import argparse
import sys
import uuid

from .config import PROJECT_ROOT, get_settings
from .db import open_database
from .notify.discord_webhook import DiscordNotifier
from .pipeline import (
    PipelineContext,
    StageError,
    StageSkipped,
    run_crawl,
    run_rewrite,
)
from .pipeline.render_stage import run as run_render
from .pipeline.subtitle_stage import run as run_subtitle
from .pipeline.tts_stage import run as run_tts
from .pipeline.upload_stage import run as run_upload
from .repository import Repositories
from .utils.killswitch import KillSwitchEvaluator
from .utils.lock import LockBusy, killswitch_active, pipeline_lock
from .utils.logging import get_logger, setup_logging


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="shorts-auto", description="Shorts Auto Pipeline")
    p.add_argument("--dry-run", action="store_true", help="의존성·설정만 검증")
    p.add_argument("--resume", action="store_true", help="Kill-Switch 플래그 제거")
    p.add_argument("--skip-upload", action="store_true", help="업로드 단계 건너뛰기 (영상 생성까지만)")
    p.add_argument("--config", default=None, help="config.yaml 경로")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings(args.config)

    setup_logging(
        log_dir=settings.section("observability").get("log_dir", "logs"),
        level=settings.secrets.log_level,
        project_root=PROJECT_ROOT,
    )
    log = get_logger("main")

    run_id = uuid.uuid4().hex[:12]
    log.info("pipeline_start",
             run_id=run_id,
             app_env=settings.secrets.app_env,
             version=settings.app.version,
             skip_upload=args.skip_upload,
             dry_run=args.dry_run)

    # Resume: Kill-Switch 해제
    killswitch_path = settings.project_path(settings.pipeline.killswitch_file)
    if args.resume:
        if killswitch_path.exists():
            killswitch_path.unlink()
            log.warning("killswitch_cleared", path=str(killswitch_path))
        return 0

    # Kill-Switch 검사 (§12.2)
    if killswitch_active(killswitch_path):
        log.critical("killswitch_active_abort", path=str(killswitch_path))
        return 2

    # DB 초기화
    db_cfg = settings.section("database")
    db_path = settings.project_path(db_cfg.get("path", "data/shorts.db"))
    db = open_database(db_path, init=True)
    log.info("db_ready", path=str(db_path))

    repos = Repositories(db)
    ctx = PipelineContext(
        settings=settings,
        repos=repos,
        run_id=run_id,
        log=log,
        project_root=PROJECT_ROOT,
    )

    if args.dry_run:
        return _dry_run(ctx)

    # 정상 실행: Lock 보호
    lock_path = settings.project_path(settings.pipeline.lock_file)
    notifier = _build_notifier(settings)

    try:
        with pipeline_lock(lock_path):
            log.info("lock_acquired", path=str(lock_path))
            return _run_pipeline(ctx, skip_upload=args.skip_upload, notifier=notifier)
    except LockBusy as e:
        log.warning("lock_busy", error=str(e))
        return 0
    finally:
        db.close()


def _run_pipeline(ctx: PipelineContext, *, skip_upload: bool, notifier: DiscordNotifier | None) -> int:
    """단계별 실행. 단계 실패는 다음 영상까지 영향 없이 로그·알림 후 중단."""
    import time
    from datetime import datetime
    started_at = time.time()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    _notify(notifier, "INFO", f"⚙️ 파이프라인 시작 — {now_str}", {"run_id": ctx.run_id})

    try:
        source_id = run_crawl(ctx)
        ctx.log.info("crawl_done", source_id=source_id)

        script_id = run_rewrite(ctx, source_id=source_id)
        ctx.log.info("rewrite_done", script_id=script_id)

        # 스크립트 정보 미리 조회 (알림에 활용)
        script_row = ctx.repos.scripts.get(script_id) or {}
        hook_pattern = script_row.get("hook_pattern", "-")

        video_id = run_tts(ctx, script_id=script_id)
        ctx.log.info("tts_done", video_id=video_id)

        video_row = ctx.repos.videos.get(video_id) or {}
        speaker = video_row.get("speaker_id", "-")
        duration = video_row.get("duration_sec") or 0

        run_subtitle(ctx, video_id=video_id)
        ctx.log.info("subtitle_done", video_id=video_id)

        final_path = run_render(ctx, video_id=video_id)
        ctx.log.info("render_done", video_id=video_id, path=str(final_path))

        if skip_upload:
            ctx.log.info("upload_skipped_by_flag")
            elapsed = int(time.time() - started_at)
            _notify(notifier, "SUCCESS", "✅ 렌더 완료 (업로드 건너뜀)", {
                "video_id": str(video_id),
                "hook": hook_pattern,
                "소요시간": f"{elapsed}초",
            })
            return 0

        upload_id = run_upload(ctx, video_id=video_id)
        ctx.log.info("upload_done", upload_id=upload_id)

        upload_row = ctx.repos.db.fetchone(
            "SELECT youtube_video_id, title FROM uploads WHERE id = ?", (upload_id,)
        )
        yt_id = (upload_row or {}).get("youtube_video_id", "")
        yt_title = (upload_row or {}).get("title", "")
        elapsed = int(time.time() - started_at)

        yt_url = f"https://www.youtube.com/watch?v={yt_id}" if yt_id else ""
        thumb_url = f"https://img.youtube.com/vi/{yt_id}/mqdefault.jpg" if yt_id else None

        description = (
            f"**[▶ 유튜브에서 보기]({yt_url})**\n\n"
            f"**{yt_title}**"
        ) if yt_url else "업로드 완료"

        _notify(
            notifier, "SUCCESS",
            title="✅ 업로드 완료!",
            content=description,
            extra={
                "🎬 hook": hook_pattern,
                "🎙️ 화자": speaker,
                "⏱️ 길이": f"{duration:.0f}초",
                "🕐 소요": f"{elapsed}초",
                "🆔 run_id": ctx.run_id,
            },
            image_url=thumb_url,
            url=yt_url or None,
        )

        # Kill-Switch 자동 평가 (§12)
        ks_cfg = ctx.settings.section("killswitch") or {}
        _ks_path = ctx.settings.project_path(ctx.settings.pipeline.killswitch_file)
        evaluator = KillSwitchEvaluator(_ks_path, config=ks_cfg)
        ks = evaluator.evaluate(ctx.repos)
        if ks:
            ctx.log.critical("killswitch_armed", reasons=ks.reasons)
            _notify(notifier, "CRITICAL", "🚨 Kill-Switch 활성화!", {"사유": "\n".join(ks.reasons)})

        return 0

    except StageSkipped as e:
        ctx.log.warning("pipeline_skipped", reason=str(e))
        _notify(notifier, "WARNING", "⏭️ 파이프라인 건너뜀", {
            "사유": str(e),
            "run_id": ctx.run_id,
        })
        return 0
    except StageError as e:
        ctx.log.error("pipeline_failed", error=str(e))
        _notify(notifier, "ERROR", "❌ 파이프라인 실패", {
            "오류": str(e)[:500],
            "run_id": ctx.run_id,
            "시각": datetime.now().strftime("%H:%M:%S"),
        })
        return 1
    except Exception as e:
        ctx.log.critical("pipeline_unexpected", error=repr(e), exc_info=True)
        _notify(notifier, "CRITICAL", "💥 예상치 못한 오류", {
            "오류": repr(e)[:500],
            "run_id": ctx.run_id,
        })
        return 1


def _dry_run(ctx: PipelineContext) -> int:
    """의존성·설정 점검."""
    settings = ctx.settings
    log = ctx.log
    log.info("dry_run_start", run_id=ctx.run_id)
    issues: list[str] = []

    if not settings.secrets.gemini_api_key:
        issues.append("GEMINI_API_KEY 미설정")
    if not settings.secrets.groq_api_key:
        issues.append("GROQ_API_KEY 미설정 (폴백 비활성)")
    if not settings.secrets.pexels_api_key:
        issues.append("PEXELS_API_KEY 미설정 (배경영상 자동 수집 불가)")
    if not settings.secrets.pixabay_api_key:
        issues.append("PIXABAY_API_KEY 미설정 (BGM 자동 수집 불가)")

    import shutil
    if not shutil.which("ffmpeg"):
        issues.append("FFmpeg 미설치 또는 PATH 미등록")

    # 한국어 주력 TTS는 MeloTTS — melo.api import 가능 여부로 검증
    try:
        import importlib
        importlib.import_module("melo.api")
    except Exception as e:
        issues.append(f"MeloTTS(melo.api) 미설치: {e!r}")

    # Piper는 영어 voiceover용으로만 보관 (한국어는 미지원). enabled=false 면 검사 생략
    tts_cfg = settings.section("tts")
    piper_cfg = tts_cfg.get("piper", {}) if isinstance(tts_cfg, dict) else {}
    if piper_cfg.get("enabled", False):
        if not shutil.which(settings.secrets.piper_bin_path):
            issues.append(f"Piper 바이너리 미발견: {settings.secrets.piper_bin_path}")

    counts = ctx.repos.db.fetchone("SELECT COUNT(*) AS c FROM sources") or {"c": 0}
    log.info("db_sources_count", count=counts["c"])

    # 에셋 풀 체크
    bg_dir = ctx.project_root / settings.section("renderer").get("background", {}).get("pool_dir", "assets/bg_video")
    bgm_dir = ctx.project_root / settings.section("renderer").get("bgm", {}).get("pool_dir", "assets/bgm")
    bg_count = sum(1 for _ in bg_dir.rglob("*") if _.is_file() and _.suffix.lower() in (".mp4", ".mov", ".webm"))
    bgm_count = sum(1 for _ in bgm_dir.rglob("*") if _.is_file() and _.suffix.lower() in (".mp3", ".m4a", ".ogg", ".wav"))
    log.info("asset_pool_count", bg_video=bg_count, bgm=bgm_count)
    if bg_count == 0:
        issues.append(f"배경영상 풀 비어 있음: {bg_dir}")
    if bgm_count == 0:
        issues.append(f"BGM 풀 비어 있음: {bgm_dir}")

    for msg in issues:
        log.warning("dry_run_issue", message=msg)
    log.info("dry_run_complete", run_id=ctx.run_id, ok=not issues, issue_count=len(issues))
    return 0 if not issues else 1


def _build_notifier(settings) -> DiscordNotifier | None:
    url = settings.secrets.discord_webhook_url
    if not url:
        return None
    return DiscordNotifier(webhook_url=url)


def _notify(
    notifier: DiscordNotifier | None,
    level: str,
    content: str,
    extra: dict | None = None,
    *,
    title: str | None = None,
    image_url: str | None = None,
    url: str | None = None,
) -> None:
    if notifier is None or not notifier.is_available():
        return
    notifier.send(
        content=content,
        title=title or f"[{level}] shorts-auto",
        level=level,
        extra=extra or {},
        image_url=image_url,
        url=url,
    )


if __name__ == "__main__":
    sys.exit(main())
