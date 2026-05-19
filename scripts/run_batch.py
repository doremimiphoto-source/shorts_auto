"""배치 영상 생성·업로드 스크립트.

crawl → rewrite → tts → subtitle → render → upload 전 단계 실행.
각 단계 및 영상별 Discord 알림 발송.

실행:
    python -m scripts.run_batch            # config daily_target_count 사용
    python -m scripts.run_batch --count 1  # 1개만 생성 (스케줄러용)
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from src.config import get_settings
from src.db import open_database
from src.notify.discord_webhook import DiscordNotifier
from src.pipeline import PipelineContext
from src.pipeline.context import StageSkipped, StageError
from src.pipeline.crawl_stage import run as run_crawl
from src.pipeline.render_stage import run as run_render
from src.pipeline.rewrite_stage import run as run_rewrite
from src.pipeline.subtitle_stage import run as run_subtitle
from src.pipeline.tts_stage import run as run_tts
from src.pipeline.upload_stage import run as run_upload
from src.repository import Repositories
from src.utils.logging import get_logger, setup_logging

_SIMILARITY_KEYWORDS = ("유사도", "similarity", "motif", "30일")


def _is_similarity_error(e: Exception) -> bool:
    return any(kw in str(e) for kw in _SIMILARITY_KEYWORDS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=0, help="생성할 영상 수 (0=config 값 사용)")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(
        log_dir=settings.section("observability").get("log_dir", "logs"),
        level=settings.secrets.log_level,
        project_root=PROJECT_ROOT,
    )
    log = get_logger("batch")
    run_id = uuid.uuid4().hex[:12]

    db_cfg = settings.section("database")
    db_path = settings.project_path(db_cfg.get("path", "data/shorts.db"))
    db = open_database(db_path, init=True)
    repos = Repositories(db)

    ctx = PipelineContext(
        settings=settings,
        repos=repos,
        run_id=run_id,
        log=log,
        project_root=PROJECT_ROOT,
    )

    target = args.count if args.count > 0 else int(settings.section("pipeline").get("daily_target_count", 3))
    notifier = DiscordNotifier(webhook_url=settings.secrets.discord_webhook_url)

    # ── 배치 시작 알림 ──────────────────────────────────────────
    notifier.send(
        title=f"배치 시작 — 영상 {target}개 제작",
        level="INFO",
        content=(
            f"run_id: `{run_id}`\n"
            f"목표: {target}개 영상 생성 → 유튜브 자동 업로드\n"
            f"단계: 소재수집 → 대본 → TTS → 자막 → 렌더 → 업로드"
        ),
        extra={"목표 영상 수": f"{target}개"},
    )
    print(f"[BATCH] 시작  run_id={run_id}  목표={target}개")

    results: list[dict] = []
    errors: list[str] = []

    for i in range(target):
        idx = i + 1
        print(f"\n[BATCH] {idx}/{target} 시작...")
        video_id: int | None = None
        script_id: int | None = None

        try:
            # 1+2. 소재 수집 + 대본 생성 (유사도 차단 시 최대 3회 재시도)
            source_id = script_id = None
            for attempt in range(1, 4):
                try:
                    source_id = run_crawl(ctx)
                    script_id = run_rewrite(ctx, source_id=source_id)
                    break
                except (StageSkipped, StageError) as e:
                    if _is_similarity_error(e) and attempt < 3:
                        print(f"  [1-2/6] 유사도 차단 → 재시도 {attempt}/3: {e}")
                        log.warning("crawl_rewrite_similarity_retry", attempt=attempt, error=str(e))
                        continue
                    raise
            if script_id is None:
                raise StageError("crawl+rewrite 3회 모두 유사도 차단됨")
            script = repos.scripts.get(script_id)
            title = (script or {}).get("title", "?")
            hook_pattern = (script or {}).get("hook_pattern", "?")
            print(f"  [1/6] 소재 수집 source_id={source_id}")
            print(f"  [2/6] 대본 생성 script_id={script_id}  [{hook_pattern}] {title}")

            # 3. TTS
            video_id = run_tts(ctx, script_id=script_id)
            video_rec = repos.videos.get(video_id)
            duration = round(float((video_rec or {}).get("duration_sec") or 0), 1)
            print(f"  [3/6] TTS 완료 video_id={video_id}  {duration}초")

            # 4. 자막
            srt_path = run_subtitle(ctx, video_id=video_id)
            print(f"  [4/6] 자막 완료 {srt_path.name}")

            # 5. 렌더
            final_path = run_render(ctx, video_id=video_id)
            size_mb = round(final_path.stat().st_size / 1024 / 1024, 1)
            print(f"  [5/6] 렌더 완료 {final_path.name}  {size_mb} MB")

            # 6. 유튜브 업로드
            upload_id = run_upload(ctx, video_id=video_id)
            upload_rec = repos.db.fetchone(
                "SELECT youtube_video_id FROM uploads WHERE id = ?", (upload_id,)
            )
            yt_id = (upload_rec or {}).get("youtube_video_id", "")
            yt_url = f"https://youtu.be/{yt_id}" if yt_id else "업로드 완료(ID 확인 중)"
            print(f"  [6/6] 업로드 완료  {yt_url}")

            results.append({
                "video_id": video_id,
                "title": title,
                "hook_pattern": hook_pattern,
                "duration": duration,
                "yt_url": yt_url,
            })

            # 영상별 완료 Discord 알림
            notifier.send(
                title=f"[{idx}/{target}] 영상 업로드 완료",
                level="SUCCESS",
                content=(
                    f"**제목:** {title}\n"
                    f"**패턴:** {hook_pattern}  |  **길이:** {duration}초\n"
                    f"**URL:** {yt_url}"
                ),
                extra={"video_id": str(video_id), "run_id": run_id},
            )

        except Exception as e:
            msg = f"영상 {idx}: {type(e).__name__}: {e}"
            print(f"  [ERROR] {msg}")
            errors.append(msg)
            log.error("batch_item_failed", index=idx, error=repr(e))

            notifier.send(
                title=f"[{idx}/{target}] 영상 생성 실패",
                level="ERROR",
                content=f"```\n{msg[:300]}\n```",
                extra={"run_id": run_id, "video_id": str(video_id) if video_id else "-"},
            )

    # ── 배치 완료 알림 ──────────────────────────────────────────
    if results:
        result_lines = [f"• [{r['hook_pattern']}] {r['title']}\n  → {r['yt_url']}" for r in results]
        content = "**업로드 완료 영상:**\n" + "\n".join(result_lines)
    else:
        content = "생성된 영상이 없습니다."
    if errors:
        content += "\n\n**오류:**\n" + "\n".join(f"• {e[:100]}" for e in errors)

    level = "SUCCESS" if not errors else ("WARNING" if results else "ERROR")
    notifier.send(
        title=f"배치 완료 — {len(results)}/{target}개 업로드",
        level=level,
        content=content,
        extra={"성공": f"{len(results)}개", "실패": f"{len(errors)}개", "run_id": run_id},
    )

    print(f"\n[BATCH] 완료: {len(results)}개 성공, {len(errors)}개 실패")
    db.close()


if __name__ == "__main__":
    main()
