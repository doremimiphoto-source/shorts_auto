"""자막 생성 단계 (FR-4).

keyword_mode=True (기본): 나레이션 전문 대신 핵심 키워드만 표시.
keyword_mode=False: faster-whisper 전문 자막 (레거시).
"""

from __future__ import annotations

from pathlib import Path

from ..subtitle.whisper_engine import WhisperSubtitleEngine, make_styled_subtitles
from .context import PipelineContext, StageError, stage_timer


def run(ctx: PipelineContext, *, video_id: int) -> Path:
    """자막 생성. SRT 경로 반환."""
    with stage_timer(ctx, "subtitle") as state:
        video = ctx.repos.videos.get(video_id)
        if video is None:
            raise StageError(f"video_id={video_id} 미존재")
        audio_path = Path(video["audio_path"])
        if not audio_path.exists():
            raise StageError(f"audio_path 미존재: {audio_path}")

        sub_cfg = ctx.section("subtitle")
        format_cfg = sub_cfg.get("format", {})
        keyword_mode = bool(format_cfg.get("keyword_mode", True))

        out_dir = ctx.project_root / sub_cfg.get("output_dir", "output/subtitle")

        if keyword_mode:
            out_ass = out_dir / f"video_{video_id}.ass"
            script = ctx.repos.scripts.get(video["script_id"])
            if script is None:
                raise StageError(f"script_id={video['script_id']} 미존재")
            audio_duration = float(video.get("duration_sec") or 20.0)
            result = make_styled_subtitles(
                script=script,
                audio_duration=audio_duration,
                out_ass=out_ass,
            )
            out_srt = out_ass
        else:
            whisper_cfg = sub_cfg.get("whisper", {})
            engine = WhisperSubtitleEngine(
                model_size=whisper_cfg.get("model_size", "small"),
                compute_type=whisper_cfg.get("compute_type", "int8"),
                language=whisper_cfg.get("language", "ko"),
                beam_size=int(whisper_cfg.get("beam_size", 5)),
                vad_filter=bool(whisper_cfg.get("vad_filter", True)),
            )
            result = engine.transcribe(
                audio_path=audio_path,
                out_srt=out_srt,
                max_chars_per_line=int(format_cfg.get("max_chars_per_line", 10)),
                max_lines=int(format_cfg.get("max_lines", 1)),
            )

        ctx.repos.db.execute(
            "UPDATE videos SET subtitle_path = ? WHERE id = ?",
            (str(out_srt), video_id),
        )
        state["message"] = f"segments={len(result.segments)}, srt={out_srt}, mode={'keyword' if keyword_mode else 'whisper'}"
        return out_srt
