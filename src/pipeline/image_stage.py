"""카드 이미지 생성 스테이지 (FR-Image).

script → card_renderer → PNG 저장 → DB card_image_path 업데이트.
image_stage는 run_batch에서 render_stage 직후 호출된다.
실패해도 배치 전체를 중단하지 않는다 (soft-fail).
"""

from __future__ import annotations

from pathlib import Path

from ..pipeline.context import PipelineContext


def run(ctx: PipelineContext, *, video_id: int) -> Path | None:
    """카드 이미지 생성 후 저장 경로 반환. 실패 시 None 반환."""
    cfg = ctx.settings.section("image_stage") if hasattr(ctx.settings, "section") else {}
    if not cfg.get("enabled", True):
        return None

    video = ctx.repos.videos.get(video_id)
    if not video:
        ctx.log.warning("image_stage_no_video", video_id=video_id)
        return None

    script_id = video.get("script_id")
    if not script_id:
        return None

    script = ctx.repos.scripts.get(script_id)
    if not script:
        return None

    try:
        from ..renderer.card_renderer import render_card

        out_dir = ctx.project_root / cfg.get("output_dir", "output/cards")
        out_path = out_dir / f"card_{video_id}_{script_id}.png"

        layout = cfg.get("layout", "auto")
        render_card(script, out_path, layout=layout)

        # DB 업데이트 (card_image_path 컬럼)
        ctx.repos.db.execute(
            "UPDATE videos SET card_image_path = ? WHERE id = ?",
            (str(out_path), video_id),
        )

        ctx.log.info("image_stage_ok", video_id=video_id,
                     path=out_path.name, size_kb=round(out_path.stat().st_size / 1024))
        return out_path

    except Exception as exc:
        ctx.log.warning("image_stage_failed", video_id=video_id, error=repr(exc))
        return None
