"""영상 합성 단계 (FR-5).

- AssetSelector로 배경영상·BGM 선택 (재사용 7일 / 블랙리스트 회피)
- VideoComposer로 FFmpeg 호출
- 길이/해상도/오디오 검증 (FR-5.8)
"""

from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path


def _resolve_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    winget = Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe"
    if winget.exists():
        return str(winget)
    return "ffmpeg"

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

            # 실사 풀 우선 → AI 폴백 (반복 방지: 동일 AI 프롬프트 캐시 문제)
            bg_video = _select_content_bg(bg_dir, script, au)
            if bg_video is not None:
                ctx.log.info("bg_source", source="pool_match", path=bg_video.name)
            else:
                # 랜덤 풀 선택 (study/school 폴더 우선)
                bg_video = _select_study_pool(bg_dir, au) or selector.select_bg_video()
                ctx.log.info("bg_source", source="pool_random", path=bg_video.name)

            # AI 배경은 풀이 완전히 비었을 때만 (폴백)
            if bg_video is None:
                ai_cache_dir = ctx.project_root / "output" / "aibg_cache"
                bg_video = _try_ai_bg(script, ai_cache_dir, ctx)
                if bg_video is None:
                    bg_video = selector.select_bg_video()
                ctx.log.info("bg_source", source="ai_fallback", path=bg_video.name)

            bgm = selector.select_bgm()
        except FileNotFoundError as e:
            raise StageSkipped(f"에셋 풀 비어 있음: {e}") from e

        # VideoComposer
        fonts_dir = ctx.project_root / renderer_cfg.get("subtitle_burn_in", {}).get("fonts_dir", "assets/fonts")
        cfg = RenderConfig(
            width=int(renderer_cfg.get("resolution", {}).get("width", 1080)),
            height=int(renderer_cfg.get("resolution", {}).get("height", 1920)),
            fps=int(renderer_cfg.get("fps", 30)),
            video_crf=int(renderer_cfg.get("video_crf", 18)),
            video_preset=str(renderer_cfg.get("video_preset", "fast")),
            audio_bitrate=str(renderer_cfg.get("audio_bitrate", "256k")),
            max_duration=int(renderer_cfg.get("max_duration_seconds", 58)),
            bgm_duck_db=float(renderer_cfg.get("bgm", {}).get("duck_db", -18.0)),
            speed_jitter=float(renderer_cfg.get("background", {}).get("randomize", {}).get("speed_jitter", 0.05)),
            fonts_dir=fonts_dir,
        )
        composer = VideoComposer(config=cfg, ffmpeg_bin=_resolve_ffmpeg())

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
        except subprocess.TimeoutExpired:
            # 타임아웃 → BG 파일 자동 블랙리스트 + 폴백 BG로 재시도 1회
            au.blacklist("bg_video", str(bg_video), reason="ffmpeg_timeout_90s")
            ctx.log.warning("bg_blacklisted_timeout", path=bg_video.name)
            fallback_bg = _select_study_pool(bg_dir, au) or selector.select_bg_video()
            bar_rgb = extract_pastel_bar_color(fallback_bg)
            try:
                composer.render(RenderInput(
                    bg_video=fallback_bg,
                    audio=audio_path,
                    subtitle_srt=srt_path,
                    bgm=bgm,
                    output=final,
                    logo=logo_path,
                    bar_rgb=bar_rgb,
                ))
                bg_video = fallback_bg
                ctx.log.info("render_fallback_ok", fallback=fallback_bg.name)
            except (RuntimeError, subprocess.TimeoutExpired) as e2:
                raise StageError(f"렌더 실패 (폴백 포함): {e2}") from e2
        except RuntimeError as e:
            err_msg = str(e)
            # SIGTERM + 출력 미생성: 동일 조건으로 1회 재시도 (배터리 전환 등 외부 종료 대응)
            if "exit=3221225786" in err_msg:
                ctx.log.warning("render_sigterm_retry", error=err_msg[:200])
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
                    ctx.log.info("render_sigterm_retry_ok")
                except (RuntimeError, subprocess.TimeoutExpired) as e2:
                    raise StageError(f"렌더 실패 (SIGTERM 재시도 포함): {e2}") from e2
            # geq 필터 오류(로고 관련)면 로고 없이 재시도 1회
            elif logo_path and ("geq" in err_msg or "Missing ')'" in err_msg or "filter" in err_msg.lower()):
                ctx.log.warning("render_logo_filter_err_retry", error=err_msg[:200])
                try:
                    composer.render(RenderInput(
                        bg_video=bg_video,
                        audio=audio_path,
                        subtitle_srt=srt_path,
                        bgm=bgm,
                        output=final,
                        logo=None,
                        bar_rgb=bar_rgb,
                    ))
                    ctx.log.info("render_no_logo_ok")
                except (RuntimeError, subprocess.TimeoutExpired) as e2:
                    raise StageError(f"렌더 실패 (로고 제거 재시도 포함): {e2}") from e2
            else:
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

        # 썸네일 생성 (실패해도 렌더 결과에 영향 없음)
        thumb_path = _generate_thumbnail(ctx, video_id, script, bg_video, fonts_dir, out_dir)
        if thumb_path:
            # 기존 DB에 thumbnail_path 컬럼이 없으면 자동 추가 (마이그레이션)
            try:
                ctx.repos.db.execute("ALTER TABLE videos ADD COLUMN thumbnail_path TEXT")
            except Exception:
                pass
            ctx.repos.db.execute(
                "UPDATE videos SET thumbnail_path = ? WHERE id = ?",
                (str(thumb_path), video_id),
            )
            ctx.log.info("thumbnail_generated", path=thumb_path.name)

        state["message"] = f"final={final.name}, bg={bg_video.name}, bgm={bgm.name}"
        return final


def _generate_thumbnail(ctx, video_id: int, script: dict | None,
                        bg_video: Path, fonts_dir: Path, out_dir: Path) -> Path | None:
    """썸네일 생성. 성공 시 Path, 실패 시 None."""
    if script is None:
        return None
    try:
        from ..renderer.thumbnail import ThumbnailInput, generate as gen_thumb
        inp = ThumbnailInput(
            title=script.get("title", ""),
            hook=script.get("hook", ""),
            twist=script.get("twist", ""),
            hook_pattern=script.get("hook_pattern", ""),
        )
        thumb_dir = out_dir.parent / "thumbnails"
        thumb_path = thumb_dir / f"thumb_{video_id}.jpg"
        return gen_thumb(inp, thumb_path, fonts_dir, bg_video=bg_video)
    except Exception as e:
        ctx.log.warning("thumbnail_gen_failed", error=repr(e))
        return None


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


def _collect_folder(bg_dir: Path, subfolder: str, au, *, tags: list[str] | None = None) -> list[Path]:
    """bg_dir/subfolder 내 mp4 파일 목록. tags 지정 시 파일명 필터. 블랙리스트 제외."""
    d = bg_dir / subfolder
    if not d.exists():
        return []
    files = list(d.glob("*.mp4"))
    if tags:
        files = [p for p in files if any(t in p.name.lower() for t in tags)]
    usable = [p for p in files if not au.is_blacklisted("bg_video", str(p))]
    return usable or files  # 블랙리스트 제외 후 비면 전체 허용


def _select_study_pool(bg_dir: Path, au) -> Path | None:
    """study → school → motivation 폴더에서 랜덤 선택. 없으면 None."""
    for sub in ("study", "school", "motivation"):
        pool = _collect_folder(bg_dir, sub, au)
        if pool:
            return random.choice(pool)
    return None


def _select_content_bg(bg_dir: Path, script: dict | None, au) -> Path | None:
    """스크립트 키워드 → 가장 어울리는 BG 영상 선택.

    우선순위: study/school 실사 → interior → abstract (폴백)
    study 키워드가 없으면 None 반환해 상위 로직에 위임.
    """
    if script is None:
        return None
    full = " ".join([
        script.get("hook", ""), script.get("body", ""), script.get("twist", ""),
        script.get("hook_pattern", ""),
    ])

    # 공부·학습 콘텐츠 → study/school 실사 영상 우선
    study_kw = [
        "공부", "시험", "집중", "기출", "암기", "포모도로", "오답", "수업", "학교",
        "학습", "복습", "필기", "플래너", "루틴", "성적", "수행평가",
    ]
    if any(kw in full for kw in study_kw):
        # 1순위: study 실사 풀 (학생 책상·도서관·노트 등)
        study_pool = _collect_folder(bg_dir, "study", au)
        if study_pool:
            return random.choice(study_pool)
        # 2순위: school 실사 풀 (교실·복도)
        school_pool = _collect_folder(bg_dir, "school", au)
        if school_pool:
            return random.choice(school_pool)
        # 3순위: interior (카페·침실·방)
        interior = _collect_folder(bg_dir, "interior", au,
                                   tags=["coffee", "bedroom", "room", "window"])
        if interior:
            return random.choice(interior)
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
