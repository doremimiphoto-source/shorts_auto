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
        "cute kawaii anime girl holding glowing Korean exam luck charm talisman amulet, "
        "golden sparkles and stars swirling around her, cheerful expression cheering fighting, "
        "red and gold magical glowing effects, soft dreamy dark bokeh background, "
        "adorable chibi art style, highly detailed, no text no watermark, vertical portrait 9:16",
    ),
    # ─ 체육 수행평가
    (
        ["멀리던지기", "멀리차기", "에어로빅", "줄넘기"],
        "dynamic energetic sports action silhouette in motion, "
        "colorful speed motion blur streaks, explosive energy burst particles, "
        "vibrant blue orange gradient background, athletic power movement, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 도덕 수행평가
    (
        ["도덕", "도덕적", "도덕적 행동", "도덕적 추론"],
        "golden glowing balance scales floating in soft light, "
        "peaceful compassionate warm rays, "
        "ethereal harmony concept art, gentle warm tones, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 역사 수행평가 — 청나라·중국
    (
        ["청나라", "한족", "중국 역사"],
        "ancient Chinese imperial palace at night, golden red lanterns glowing, "
        "silk dragon embroidery texture overlay, historical map parchment background, "
        "elegant sepia gold tones, cinematic, no text no watermark, vertical portrait 9:16",
    ),
    # ─ 역사 수행평가 — 일반
    (
        ["역사", "독후감", "마인드맵", "자기주도 학습지"],
        "ancient Korean historical scroll parchment texture, "
        "ink brush painting style background, warm aged sepia amber tones, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 수학 수행평가
    (
        ["일차부등식", "인생그래프", "수학"],
        "glowing neon blue mathematical equations floating in dark space, "
        "graph curves and geometric shapes, futuristic educational mathematics aesthetic, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 과학 수행평가
    (
        ["영양소", "광물", "광물 특성", "과학", "실험"],
        "colorful science laboratory glassware with glowing liquids, "
        "floating molecules DNA helix atoms bokeh, vibrant clean laboratory background, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 국어 수행평가
    (
        ["반어", "역설", "풍자", "국어", "문학", "서술형"],
        "elegant Korean ink brush calligraphy flowing strokes on parchment, "
        "classical literary poetry atmosphere, soft warm amber tones, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 음악 수행평가
    (
        ["칼림바", "음악신문", "음악"],
        "colorful musical notes and treble clefs floating in warm concert light, "
        "vibrant purple gold music atmosphere, kalimba thumb piano bokeh, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 영어 수행평가
    (
        ["영어 쓰기", "영어 듣기", "영어"],
        "global communication concept speech bubbles bokeh, soft world map background, "
        "clean modern blue white educational gradient, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 한문 수행평가
    (
        ["창의 한자", "성어", "한문", "공익 광고"],
        "traditional Chinese calligraphy ink brush on rice paper texture, "
        "elegant red seal stamp accent, scholarly warm ambient, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 중국어 수행평가
    (
        ["한어병음", "국적", "중국어"],
        "colorful Chinese red paper lanterns bokeh warm glow, "
        "cultural education aesthetic, orange red gradient night sky, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 암기 비법
    (
        ["암기", "기억", "망각 곡선", "두문자법", "연상법"],
        "glowing human brain neurons network visualization, "
        "bioluminescent blue purple memory connections web, futuristic dark background, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 시간 관리 / 포모도로
    (
        ["포모도로", "시간표", "플래너", "시간 관리", "시간 배분"],
        "minimalist aesthetic glowing clock floating in soft bokeh, "
        "pastel study planner desk organized notebook pencil, calm productive atmosphere, "
        "no text no watermark, vertical portrait 9:16",
    ),
    # ─ 시험 대비 / 기출 / 기말 (범용)
    (
        ["기출", "기말", "시험 대비", "수행평가", "중간고사", "오답", "공부"],
        "Korean student studying at cozy night desk, "
        "warm amber desk lamp glow, open textbooks and notebooks, "
        "determined focused atmosphere, soft bokeh background, "
        "no text no watermark, vertical portrait 9:16",
    ),
]

_DEFAULT_PROMPT = (
    "cozy Korean student study room at night, warm glowing desk lamp, "
    "open textbooks and notebooks soft bokeh background, "
    "motivational peaceful atmosphere, "
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
            f"?width=1080&height=1920&nologo=true&enhance=true&model=flux"
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

    # ── Ken Burns: scale 1.30× → crop 이동 (pan 애니메이션)
    # 1.30× 스케일로 1080×1920 주변에 pan 여유 확보
    sw = 1404   # 1080 * 1.30 (짝수)
    sh = 2496   # 1920 * 1.30 (짝수)
    xp = sw - 1080   # 324px pan 폭
    yp = sh - 1920   # 576px pan 높이
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
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        str(vid_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    if result.returncode != 0 or not vid_path.exists() or vid_path.stat().st_size < 100_000:
        return None

    return vid_path
