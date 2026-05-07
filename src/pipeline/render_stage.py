"""영상 합성 단계 (FR-5).

- AssetSelector로 배경영상·BGM 선택 (재사용 7일 / 블랙리스트 회피)
- VideoComposer로 FFmpeg 호출
- 길이/해상도/오디오 검증 (FR-5.8)
"""

from __future__ import annotations

import random
import subprocess
from pathlib import Path

from ..renderer.assets import AssetSelector
from ..renderer.composer import RenderConfig, RenderInput, VideoComposer, extract_pastel_bar_color
from .context import PipelineContext, StageError, StageSkipped, stage_timer


def run(ctx: PipelineContext, *, video_id: int) -> Path:
    """영상 합성. 최종 mp4 경로 반환."""
    with stage_timer(ctx, "render") as state:
        video = ctx.repos.videos.get(video_id)
        if video is None:
            raise StageError(f"video_id={video_id} 미존재")
        audio_path = Path(video["audio_path"])
        srt_path = Path(video["subtitle_path"]) if video["subtitle_path"] else None
        if not audio_path.exists() or srt_path is None or not srt_path.exists():
            raise StageError(f"필수 입력 미존재: audio={audio_path}, srt={srt_path}")

        renderer_cfg = ctx.section("renderer")
        bg_dir = ctx.project_root / renderer_cfg.get("background", {}).get("pool_dir", "assets/bg_video")
        bgm_dir = ctx.project_root / renderer_cfg.get("bgm", {}).get("pool_dir", "assets/bgm")

        # AssetSelector
        au = ctx.repos.asset_usage
        selector = AssetSelector(
            bg_dir=bg_dir,
            bgm_dir=bgm_dir,
            bg_reuse_min_days=int(renderer_cfg.get("background", {}).get("reuse_min_interval_days", 7)),
            recent_usage_provider=lambda kind, p: au.last_used_at(kind, p),
            blacklist_provider=lambda kind, p: au.is_blacklisted(kind, p),
            rng=random.Random(),
        )
        try:
            script = ctx.repos.scripts.get(video["script_id"])

            # AI 콘텐츠 매칭 배경 생성 시도 (실패 시 기존 풀 폴백)
            ai_cache_dir = ctx.project_root / "output" / "aibg_cache"
            bg_video = _try_ai_bg(script, ai_cache_dir, ctx)
            if bg_video is None:
                bg_video = _select_content_bg(bg_dir, script, au) or selector.select_bg_video()
                ctx.log.info("bg_source", source="pool", path=bg_video.name)
            else:
                ctx.log.info("bg_source", source="ai_generated", path=bg_video.name)

            bgm = selector.select_bgm()
        except FileNotFoundError as e:
            raise StageSkipped(f"에셋 풀 비어 있음: {e}") from e

        # VideoComposer
        fonts_dir = ctx.project_root / renderer_cfg.get("subtitle_burn_in", {}).get("fonts_dir", "assets/fonts")
        cfg = RenderConfig(
            width=int(renderer_cfg.get("resolution", {}).get("width", 1080)),
            height=int(renderer_cfg.get("resolution", {}).get("height", 1920)),
            fps=int(renderer_cfg.get("fps", 30)),
            video_crf=int(renderer_cfg.get("video_crf", 23)),
            audio_bitrate=str(renderer_cfg.get("audio_bitrate", "192k")),
            max_duration=int(renderer_cfg.get("max_duration_seconds", 58)),
            bgm_duck_db=float(renderer_cfg.get("bgm", {}).get("duck_db", -18.0)),
            speed_jitter=float(renderer_cfg.get("background", {}).get("randomize", {}).get("speed_jitter", 0.05)),
            fonts_dir=fonts_dir,
        )
        composer = VideoComposer(config=cfg)

        out_dir = ctx.project_root / renderer_cfg.get("output", {}).get("final_dir", "output/final")
        out_dir.mkdir(parents=True, exist_ok=True)
        final = out_dir / f"video_{video_id}.mp4"

        logo_rel = renderer_cfg.get("channel_logo", "assets/channel_logo.jpg")
        logo_path: Path | None = ctx.project_root / logo_rel
        if not logo_path.exists():
            logo_path = None

        bar_rgb = extract_pastel_bar_color(bg_video)

        try:
            composer.render(RenderInput(
                bg_video=bg_video,
                audio=audio_path,
                subtitle_srt=srt_path,
                bgm=bgm,
                output=final,
                logo=logo_path,
                bar_rgb=bar_rgb,
            ))
        except RuntimeError as e:
            raise StageError(f"렌더 실패: {e}") from e

        # 검증 (FR-5.8)
        valid = _validate_video(final, expected=(cfg.width, cfg.height), max_duration=cfg.max_duration)
        if not valid:
            raise StageError("영상 검증 실패 (해상도/길이/오디오)")

        # DB 갱신 + 에셋 사용 기록
        ctx.repos.db.execute(
            "UPDATE videos SET bg_video_path = ?, bgm_path = ?, video_path = ?, width = ?, height = ?, valid = 1 WHERE id = ?",
            (str(bg_video), str(bgm), str(final), cfg.width, cfg.height, video_id),
        )
        au.record(asset_kind="bg_video", asset_path=str(bg_video), video_id=video_id)
        au.record(asset_kind="bgm", asset_path=str(bgm), video_id=video_id)
        state["message"] = f"final={final.name}, bg={bg_video.name}, bgm={bgm.name}"
        return final


def _try_ai_bg(script: dict | None, cache_dir: Path, ctx) -> Path | None:
    """AI 콘텐츠 매칭 배경 생성 시도. 실패 시 None 반환."""
    if script is None:
        return None
    try:
        from ..renderer.bg_generator import generate_bg_video
        return generate_bg_video(script, cache_dir)
    except Exception as e:
        ctx.log.warning("ai_bg_failed", error=repr(e))
        return None


def _select_content_bg(bg_dir: Path, script: dict | None, au) -> Path | None:
    """스크립트 키워드로 분위기 맞는 BG 영상 선택. 없으면 None 반환."""
    if script is None:
        return None
    full = " ".join([
        script.get("hook", ""), script.get("body", ""), script.get("twist", ""),
    ])
    # 공부/기출 콘텐츠 → 인테리어 우선(카페·침실·조용한 방), 폴백 bokeh
    study_kw = ["공부", "시험", "집중", "기출", "암기", "포모도로", "오답", "수업", "학교", "학습"]
    if any(kw in full for kw in study_kw):
        def _collect(sub: str, tags: list[str]) -> list[Path]:
            d = bg_dir / sub
            if not d.exists():
                return []
            return [p for p in d.glob("*.mp4") if any(t in p.name.lower() for t in tags)]

        # 1순위: 카페·침실·빈 방·아파트 (실내 분위기)
        interior = _collect("interior", ["coffee", "bedroom", "room", "apartment", "window"])
        # 2순위: abstract bokeh (폴백)
        bokeh = _collect("abstract", ["bokeh"])

        for pool in (interior, bokeh):
            if not pool:
                continue
            usable = [p for p in pool if not au.is_blacklisted("bg_video", str(p))]
            return random.choice(usable or pool)
    return None


def _validate_video(path: Path, *, expected: tuple[int, int], max_duration: int, ffprobe_bin: str = "ffprobe") -> bool:
    """ffprobe로 해상도·길이·오디오 트랙 검증."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        result = subprocess.run(
            [
                ffprobe_bin, "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height:format=duration",
                "-of", "default=noprint_wrappers=1:nokey=0",
                str(path),
            ],
            capture_output=True, timeout=30, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0:
        return False
    info = result.stdout.decode("utf-8", "replace")
    width = _parse_kv(info, "width")
    height = _parse_kv(info, "height")
    duration = _parse_kv(info, "duration", as_float=True)
    if width != expected[0] or height != expected[1]:
        return False
    if duration is None or duration > max_duration + 2 or duration < 1:
        return False
    return True


def _parse_kv(text: str, key: str, *, as_float: bool = False):
    for line in text.splitlines():
        if line.startswith(f"{key}="):
            v = line.split("=", 1)[1].strip()
            try:
                return float(v) if as_float else int(v)
            except ValueError:
                return None
    return None
