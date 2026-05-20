"""영상 합성 (FR-5).

FFmpeg `-filter_complex` 직접 호출.
- 3-존 레이아웃: 상단 파스텔 바(480px) / 영상 4:5→1:1(1080×1160) / 하단 파스텔 바(280px)
- 상하단 바 색상: BG 영상 대표색 → 파스텔 변환 (분위기 통일)
- 자막 번인 libass (FR-5.7)  BGM -18dB ducking (FR-5.3)
- 채널 프로필 이미지 원형 크롭 오버레이
"""

from __future__ import annotations

import random
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RenderInput:
    bg_video: Path
    audio: Path
    subtitle_srt: Path
    bgm: Path
    output: Path
    logo: Path | None = None
    bar_rgb: tuple[int, int, int] = (210, 205, 220)   # 파스텔 기본값 (연보라)


@dataclass
class RenderConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    video_crf: int = 18
    video_preset: str = "fast"
    audio_bitrate: str = "256k"
    max_duration: int = 58
    bgm_duck_db: float = -22.0   # -18 → -22: BGM을 더 낮춰 나레이션 명료도 향상
    speed_jitter: float = 0.05
    fonts_dir: Path = Path("assets/fonts")


# 3-존 레이아웃 (1080×1920 캔버스) — 구분선 없음
_LAYOUT_TOP_H   = 480   # 상단 파스텔 타이틀 바
_LAYOUT_VIDEO_H = 1160  # 중앙 영상 윈도우 (480~1640)
_LAYOUT_BOT_H   = 280   # 하단 파스텔 채널 바


def _probe_audio_duration(audio: Path) -> float:
    """ffprobe로 오디오 길이(초) 반환. 실패 시 30.0."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
            capture_output=True, timeout=10, check=False,
        )
        return float(r.stdout.decode().strip())
    except Exception:
        return 30.0


def extract_pastel_bar_color(bg_video: Path, ffmpeg_bin: str = "ffmpeg") -> tuple[int, int, int]:
    """BG 영상 대표 색상 추출 후 파스텔 변환. 실패 시 연보라 기본값 반환."""
    try:
        res = subprocess.run(
            [ffmpeg_bin, "-ss", "1", "-i", str(bg_video),
             "-vf", "scale=1:1", "-vframes", "1",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
            capture_output=True, timeout=10, check=False,
        )
        if res.returncode == 0 and len(res.stdout) >= 3:
            r, g, b = res.stdout[0], res.stdout[1], res.stdout[2]
        else:
            return (210, 205, 220)
    except Exception:
        return (210, 205, 220)

    # 파스텔 변환: 원색 35% + 밝은 중성 65% → 부드럽고 밝은 톤
    neutral = 200
    pr = min(255, int(r * 0.35 + neutral * 0.65))
    pg = min(255, int(g * 0.35 + neutral * 0.65))
    pb = min(255, int(b * 0.35 + neutral * 0.65))
    return (pr, pg, pb)


class VideoComposer:
    """FFmpeg 호출 단일 진입점."""

    def __init__(self, *, config: RenderConfig | None = None, ffmpeg_bin: str = "ffmpeg", rng: random.Random | None = None) -> None:
        self.cfg = config or RenderConfig()
        self.ffmpeg_bin = ffmpeg_bin
        self.rng = rng or random.Random()

    def render(self, inp: RenderInput) -> Path:
        """단일 영상 렌더링. 성공 시 출력 경로 반환, 실패 시 RuntimeError."""
        inp.output.parent.mkdir(parents=True, exist_ok=True)
        speed = 1.0 + self.rng.uniform(-self.cfg.speed_jitter, self.cfg.speed_jitter)
        has_logo = inp.logo is not None and inp.logo.exists()
        audio_dur = _probe_audio_duration(inp.audio)

        filter_complex = self._build_filter_complex(
            speed=speed, srt_path=inp.subtitle_srt,
            has_logo=has_logo, bar_rgb=inp.bar_rgb,
            audio_duration=audio_dur,
        )

        cmd = [
            self.ffmpeg_bin,
            "-hide_banner", "-y",
            "-stream_loop", "-1", "-i", str(inp.bg_video),
            "-i", str(inp.audio),
            "-stream_loop", "-1", "-i", str(inp.bgm),  # BGM도 루프 — TTS보다 짧아도 잘리지 않음
        ]
        if has_logo:
            cmd.extend(["-loop", "1", "-i", str(inp.logo)])

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264", "-preset", self.cfg.video_preset, "-crf", str(self.cfg.video_crf),
            "-pix_fmt", "yuv420p",
            "-r", str(self.cfg.fps),
            "-c:a", "aac", "-b:a", self.cfg.audio_bitrate,
            "-shortest",
            "-t", str(self.cfg.max_duration),
            str(inp.output),
        ])
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=90, check=False)
        except subprocess.TimeoutExpired:
            # 타임아웃 → 손상된 BG 파일 감지 신호로 상위에 전달
            raise subprocess.TimeoutExpired(cmd, 90)

        # 0xC000013A(3221225786) = Windows SIGTERM/창닫기로 인한 FFmpeg 종료.
        # 실제 렌더는 완료됐을 수 있으므로 출력 파일 크기로 최종 판단.
        _WINDOWS_SIGTERM = 3221225786
        output_ok = inp.output.exists() and inp.output.stat().st_size > 0
        if result.returncode != 0 and not (result.returncode == _WINDOWS_SIGTERM and output_ok):
            raise RuntimeError(
                f"FFmpeg 렌더 실패 (exit={result.returncode}): "
                f"{result.stderr.decode('utf-8', 'replace')[-2000:]}"
            )
        if not output_ok:
            raise RuntimeError(f"FFmpeg 렌더 실패: 출력 파일 없음 또는 빈 파일")
        return inp.output

    def _build_filter_complex(
        self, *, speed: float, srt_path: Path,
        has_logo: bool = False, bar_rgb: tuple[int, int, int] = (210, 205, 220),
        audio_duration: float = 30.0,
    ) -> str:
        sub_arg   = str(srt_path).replace("\\", "/").replace(":", r"\:")
        fonts_arg = str(self.cfg.fonts_dir).replace("\\", "/").replace(":", r"\:")
        w, h = self.cfg.width, self.cfg.height
        vid_h = _LAYOUT_VIDEO_H   # 1160
        top_y = _LAYOUT_TOP_H     # 480
        bot_y = top_y + vid_h     # 1640
        bot_h = _LAYOUT_BOT_H     # 280

        contrast   = round(self.rng.uniform(1.05, 1.20), 3)
        saturation = round(self.rng.uniform(1.10, 1.40), 3)
        brightness = round(self.rng.uniform(-0.02, 0.03), 3)
        crop_y_expr = f"(ih-{vid_h})*{round(self.rng.uniform(0.0, 1.0), 3)}"

        # Warm LUT (시네마틱 오렌지-틸 톤)
        warm_lut = (
            "curves="
            "r='0/0 0.25/0.27 0.75/0.80 1/1.0':"
            "g='0/0 0.25/0.24 0.75/0.73 1/0.97':"
            "b='0/0.03 0.25/0.21 0.75/0.66 1/0.87'"
        )
        eq_filter = (
            f"eq=contrast={contrast}:saturation={saturation}:brightness={brightness},"
            f"{warm_lut},"
            f"vignette=angle=PI/5"
        )

        # Ken Burns: 110% 확대 후 천천히 가로 패닝 (방향 랜덤)
        kb_w  = round(w * 1.1)       # 1188
        kb_h  = round(vid_h * 1.1)   # 1276
        kb_cy = (kb_h - vid_h) // 2  # 58 (수직 중앙)
        pan   = kb_w - w             # 108 px
        dur   = max(audio_duration, 1.0)
        if self.rng.random() < 0.5:  # left→right
            kb_cx = f"({pan}*t/{dur:.1f})"
        else:                        # right→left
            kb_cx = f"({pan}-{pan}*t/{dur:.1f})"

        # 파스텔 바 색상 (FFmpeg 0xRRGGBB 포맷)
        r, g, b = bar_rgb
        bar_hex = f"0x{r:02x}{g:02x}{b:02x}"

        # ① BG 영상 → 크롭 → Ken Burns(110%) → 색보정
        bg_chain = (
            f"[0:v]setpts={1.0/speed:.4f}*PTS,"
            f"scale='if(gt(a,{w}/{vid_h}),-2,{w})':'if(gt(a,{w}/{vid_h}),{vid_h},-2)',"
            f"crop={w}:{vid_h}:(iw-{w})/2:{crop_y_expr},"
            f"scale={kb_w}:{kb_h}:flags=lanczos,"
            f"crop={w}:{vid_h}:x='{kb_cx}':y={kb_cy},"
            f"{eq_filter}[bg_crop]"
        )

        # ② 파스텔 캔버스(1080×1920) + 영상 윈도우 합성 (구분선 없음)
        canvas_chain = (
            f"color=c={bar_hex}:s={w}x{h}:r={self.cfg.fps}[canvas];"
            f"[canvas][bg_crop]overlay=x=0:y={top_y}[bg_full]"
        )

        # ③ 채널 프로필 이미지 원형 크롭 (하단 바 중앙)
        if has_logo:
            logo_size = 120
            logo_r    = logo_size // 2
            logo_x    = (w - logo_size) // 2
            logo_y    = bot_y + (bot_h - logo_size) // 2
            circle_expr = f"255*lt((X-{logo_r})*(X-{logo_r})+(Y-{logo_r})*(Y-{logo_r}),{logo_r**2})"
            logo_chain = (
                f"[3:v]scale={logo_size}:{logo_size},format=rgba,"
                f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{circle_expr}'[logo];"
                f"[bg_full][logo]overlay=x={logo_x}:y={logo_y}[bg_logo]"
            )
            pre_sub = "bg_logo"
        else:
            logo_chain = ""
            pre_sub = "bg_full"

        # ④ 자막 번인
        sub_chain = f"[{pre_sub}]subtitles='{sub_arg}':fontsdir='{fonts_arg}'[v]"

        # ⑤ BGM 더킹 — duration=first: TTS 오디오([1:a]) 길이 기준으로 종료 (BGM이 짧아도 잘림 없음)
        audio_chain = (
            f"[2:a]volume={self.cfg.bgm_duck_db}dB[bgm];"
            f"[1:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[a]"
        )

        parts = [bg_chain, canvas_chain]
        if logo_chain:
            parts.append(logo_chain)
        parts.extend([sub_chain, audio_chain])
        return ";".join(parts)
