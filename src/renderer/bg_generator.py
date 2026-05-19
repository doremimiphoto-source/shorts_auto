"""콘텐츠 매칭 AI 배경 생성 (Pollinations AI — 무료, API 키 불필요).

스크립트 hook/body/twist 내용 → 영문 이미지 프롬프트 → 1080×1920 배경 이미지 생성.
생성 이미지 → 3초 루프 MP4 변환 → 렌더 파이프라인에 전달 (-stream_loop -1 로 루프).
생성 실패(타임아웃·네트워크 오류) 시 None 반환 → 기존 풀 폴백.
"""

from __future__ import annotations

import hashlib
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path


# ── 콘텐츠 키워드 → 이미지 프롬프트 매핑 ───────────────────────────────────
_PROMPT_MAP: list[tuple[list[str], str]] = [
    # ─ 시험 행운 부적
    (
        ["부적", "lucky_charm", "행운", "만점 전설", "10명에게 공유"],
        "breathtaking anime girl holding radiant golden exam luck talisman, "
        "swirling magical stardust and sparkling aurora particles around her, "
        "cinematic volumetric light shafts, rich crimson and gold mystical glow, "
        "ultra-detailed anime illustration, professional digital art, dramatic dark background, "
        "award-winning artwork, no text no watermark, vertical portrait 9:16",
    ),
    # ─ 체육 수행평가
    (
        ["멀리던지기", "멀리차기", "에어로빅", "줄넘기"],
        "cinematic freeze-frame athlete in explosive peak action, "
        "dramatic motion blur speed streaks, shattered light prism energy burst, "
        "high-contrast deep blue orange cinematic color grade, "
        "professional sports photography, 8K ultra detail, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 도덕 수행평가
    (
        ["도덕", "도덕적", "도덕적 행동", "도덕적 추론"],
        "luminous golden scales of justice floating in ethereal divine light, "
        "soft glowing feathers drifting in sacred warm rays, "
        "cinematic god rays volumetric fog, dreamlike harmony concept art, "
        "professional CGI render, award-winning digital illustration, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 역사 수행평가 — 청나라·중국
    (
        ["청나라", "한족", "중국 역사"],
        "majestic Forbidden City at blue hour, ornate golden dragon pillars glowing, "
        "cinematic low-angle shot with dramatic sky, "
        "rich cinnabar red and imperial gold color palette, "
        "8K hyperrealistic professional photography, cinematic color grading, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 역사 수행평가 — 일반
    (
        ["역사", "독후감", "마인드맵", "자기주도 학습지"],
        "ancient Korean palace at golden hour, exquisite brush painting style, "
        "dramatic side lighting on aged scroll parchment texture, "
        "rich sepia and amber cinematic color grade, bokeh fireflies, "
        "award-winning fine art photography, no text no watermark, vertical portrait 9:16",
    ),
    # ─ 수학 수행평가
    (
        ["일차부등식", "인생그래프", "수학"],
        "mesmerizing neon blue-violet mathematical equations cascading in deep space, "
        "glowing parabola curves and 3D geometry floating holographically, "
        "cinematic lens flare, dark cosmic background with starfield, "
        "hyperrealistic CGI render, 8K ultra-sharp, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 과학 수행평가
    (
        ["영양소", "광물", "광물 특성", "과학", "실험"],
        "stunning science lab with glowing luminescent liquid-filled beakers, "
        "crystalline minerals sparkling under dramatic rim lighting, "
        "cinematic teal and orange color grade, floating DNA helix bokeh, "
        "professional scientific photography, 8K ultra detail, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 국어 수행평가
    (
        ["반어", "역설", "풍자", "국어", "문학", "서술형"],
        "magnificent Korean ink calligraphy brushstroke in dramatic black flow, "
        "aged golden parchment texture with bokeh soft light, "
        "cinematic side-lit classical atmosphere, ink droplets splashing artistically, "
        "award-winning fine art photography, no text no watermark, vertical portrait 9:16",
    ),
    # ─ 음악 수행평가
    (
        ["칼림바", "음악신문", "음악"],
        "enchanting concert hall filled with floating luminous musical notes, "
        "dramatic stage light beams cutting through smoke, "
        "rich purple and warm gold cinematic color grade, "
        "kalimba tines glinting in spotlight, bokeh string lights, "
        "professional concert photography, no text no watermark, vertical portrait 9:16",
    ),
    # ─ 영어 수행평가
    (
        ["영어 쓰기", "영어 듣기", "영어"],
        "sleek modern global education concept, glowing translucent speech bubbles, "
        "neon blue world map hologram floating in dark air, "
        "cinematic cool blue-white color grade, futuristic minimalist aesthetic, "
        "professional advertising photography, no text no watermark, vertical portrait 9:16",
    ),
    # ─ 한문 수행평가
    (
        ["창의 한자", "성어", "한문", "공익 광고"],
        "exquisite Chinese ink calligraphy brushstroke on luxurious rice paper, "
        "dramatic single beam spotlight on bold black strokes, "
        "elegant vermillion seal stamp accent, rich warm scholarly atmosphere, "
        "award-winning fine art, no text no watermark, vertical portrait 9:16",
    ),
    # ─ 중국어 수행평가
    (
        ["한어병음", "국적", "중국어"],
        "vibrant Chinese festival night scene, rows of glowing crimson paper lanterns, "
        "golden confetti bokeh falling gracefully, "
        "cinematic warm orange-red color grade, luxury cultural atmosphere, "
        "professional photography, 8K, no text no watermark, vertical portrait 9:16",
    ),
    # ─ 암기 비법
    (
        ["암기", "기억", "망각 곡선", "두문자법", "연상법"],
        "breathtaking human brain with bioluminescent neuron network glowing electric blue, "
        "synaptic sparks cascading like aurora through neural pathways, "
        "deep black cosmic background, cinematic volumetric light, "
        "hyperrealistic CGI render, 8K ultra-detail, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 시간 관리 / 포모도로
    (
        ["포모도로", "시간표", "플래너", "시간 관리", "시간 배분"],
        "ultra-premium minimal desk setup at golden hour, "
        "sleek white notebook and elegant pen bathed in warm window light, "
        "glowing brass hourglass with soft bokeh background, "
        "cinematic shallow depth-of-field, luxury editorial photography, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 시험 대비 / 기출 / 기말 (범용)
    (
        ["기출", "기말", "시험 대비", "수행평가", "중간고사", "오답", "공부"],
        "cinematic Korean student studying at premium night desk, "
        "warm amber desk lamp casting dramatic rim light on open textbook, "
        "blurred city night view through window bokeh, "
        "moody teal-orange cinematic color grade, award-winning editorial photography, "
        "no text no watermark, vertical portrait 9:16",
    ),
]

_DEFAULT_PROMPT = (
    "cinematic premium Korean study room at night, "
    "warm amber desk lamp with dramatic rim lighting, "
    "luxury stationery and open textbook in foreground, "
    "city bokeh through window in background, "
    "moody teal and warm gold cinematic color grade, "
    "award-winning editorial photography, "
    "no text no watermark, vertical portrait 9:16"
)


def _build_prompt(script: dict) -> str:
    """스크립트 내용 + hook_pattern으로 가장 맞는 이미지 프롬프트 선택."""
    hook_pattern = script.get("hook_pattern", "")
    full_text = " ".join([
        script.get("hook", ""),
        script.get("body", ""),
        script.get("twist", ""),
        hook_pattern,
    ])
    for keywords, prompt in _PROMPT_MAP:
        if any(kw in full_text for kw in keywords):
            return prompt
    return _DEFAULT_PROMPT


def generate_bg_video(
    script: dict,
    cache_dir: Path,
    *,
    timeout_sec: int = 45,
    duration: int = 35,
    ffmpeg_bin: str = "ffmpeg",
) -> Path | None:
    """AI 이미지 생성 → 풀 길이 Ken Burns 판/줌 영상. 실패 시 None 반환.

    - Pollinations AI(FLUX)로 1080×1920 이미지 생성
    - scale 1.30× → crop 이동으로 35초 무루프 판 애니메이션
    - 해시 마지막 자리로 이동 방향 다양화 (4방향)
    - cache_dir에 프롬프트 해시 기반 캐시 → 동일 콘텐츠 재생성 방지
    """
    prompt = _build_prompt(script)
    content_hash = hashlib.sha256(prompt.encode()).hexdigest()[:14]
    img_path = cache_dir / f"aibg_{content_hash}.jpg"
    vid_path = cache_dir / f"aibg_{content_hash}_full.mp4"

    # ── 캐시 히트 (풀 비디오 ≥ 200 KB)
    if vid_path.exists() and vid_path.stat().st_size > 200_000:
        return vid_path

    cache_dir.mkdir(parents=True, exist_ok=True)

    # ── Pollinations AI 이미지 생성
    if not (img_path.exists() and img_path.stat().st_size > 10_000):
        encoded = urllib.parse.quote(prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=1080&height=1920&nologo=true&enhance=true&model=flux-realism"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ShortsAuto/1.0"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                data = resp.read()
            if len(data) < 10_000:
                return None
            img_path.write_bytes(data)
        except Exception:
            return None

    if not img_path.exists() or img_path.stat().st_size < 10_000:
        return None

    # ── Ken Burns: scale 1.40× → crop 이동 (pan 애니메이션)
    # 1.40× 스케일로 1080×1920 주변에 더 넓은 pan 여유 확보 (더 역동적인 움직임)
    sw = 1512   # 1080 * 1.40 (짝수)
    sh = 2688   # 1920 * 1.40 (짝수)
    xp = sw - 1080   # 432px pan 폭
    yp = sh - 1920   # 768px pan 높이
    d  = duration

    # 해시 마지막 16진수로 4방향 중 선택 → 콘텐츠마다 다른 이동 패턴
    pan_dir = int(content_hash[-1], 16) % 4
    if pan_dir == 0:
        xe = f"min({xp}*t/{d},{xp})"        # 좌→우
        ye = f"min({yp}*t/{d},{yp})"        # 상→하 (대각)
    elif pan_dir == 1:
        xe = f"max({xp}-{xp}*t/{d},0)"      # 우→좌
        ye = f"max({yp}-{yp}*t/{d},0)"      # 하→상 (역대각)
    elif pan_dir == 2:
        xe = f"min({xp}*t/{d},{xp})"        # 좌→우
        ye = f"{yp // 2}"                   # 수평 이동 (중앙 Y 고정)
    else:
        xe = f"{xp // 2}"                   # 중앙 X 고정
        ye = f"min({yp}*t/{d},{yp})"        # 수직 이동 (상→하)

    vf = (
        f"scale={sw}:{sh}:flags=lanczos,"
        f"crop=1080:1920:x='{xe}':y='{ye}',"
        f"setsar=1"
    )

    cmd = [
        ffmpeg_bin, "-hide_banner", "-y",
        "-loop", "1", "-i", str(img_path),
        "-vf", vf,
        "-t", str(d),
        "-r", "30",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        str(vid_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    if result.returncode != 0 or not vid_path.exists() or vid_path.stat().st_size < 100_000:
        return None

    return vid_path
