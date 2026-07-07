"""카드 배경 이미지 생성 (Pollinations AI — 무료, API 키 불필요).

분리 원칙:
  - 쇼츠 src/renderer/bg_generator.py 를 import 하지 않는다 (별도 서비스).
  - 카드 전용 영어 프롬프트 + 정적 이미지(JPG)만 반환 (MP4 변환 없음).

배경 정책 (IMPL_AUDIT_v2.0 N-01):
  HOOK 슬라이드만 AI 배경을 쓴다. REVEAL 제품/장소 슬라이드는
  실제 상품/여행지 이미지를 별도로 사용한다 (본 모듈 미사용).
"""

from __future__ import annotations

import hashlib
import urllib.parse
import urllib.request
from pathlib import Path

from cards.config import BG_CACHE_DIR

# ── 버티컬별 영어 프롬프트 ────────────────────────────────────────────────────
_VERTICAL_PROMPT = {
    "v1_shopping": (
        "ultra-clean product flat lay on white marble surface, "
        "minimalist commercial photography, dramatic studio side lighting, "
        "premium products aesthetically arranged, shallow depth of field bokeh, "
        "cinematic teal and warm white color grade, luxury advertising photography, "
        "no text no watermark"
    ),
    "v2_travel": (
        "breathtaking hidden tropical beach with crystal turquoise water and white sand, "
        "dramatic aerial drone perspective, untouched paradise no tourists, "
        "cinematic golden hour lighting, lush green cliffs and jungle, "
        "professional travel photography award-winning, 8K ultra detail, "
        "no text no watermark"
    ),
    "v3_kbeauty": (
        "elegant Korean skincare products on minimalist white marble surface, "
        "soft luxury beauty photography with gentle diffused natural light, "
        "glass skin aesthetic, premium cosmetics flat lay artistically styled, "
        "cinematic cool pastel color grade, professional commercial beauty photography, "
        "no text no watermark"
    ),
}


def generate_card_bg(
    vertical: str,
    *,
    width: int,
    height: int,
    prompt_extra: str = "",
    cache_dir: Path | None = None,
    timeout_sec: int = 45,
) -> Path | None:
    """버티컬에 맞는 AI 배경 이미지 생성 → JPG 캐시 후 경로 반환. 실패 시 None."""
    base_prompt = _VERTICAL_PROMPT.get(vertical, _VERTICAL_PROMPT["v2_travel"])
    prompt = f"{prompt_extra + ', ' if prompt_extra else ''}{base_prompt}"

    cdir = cache_dir or BG_CACHE_DIR
    cdir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(f"{prompt}{width}x{height}".encode()).hexdigest()[:14]
    img_path = cdir / f"bg_{vertical}_{h}.jpg"

    if img_path.exists() and img_path.stat().st_size > 10_000:
        return img_path

    encoded = urllib.parse.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&nologo=true&enhance=true&model=flux-realism"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HiddenFindsDaily/1.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = resp.read()
        if len(data) < 10_000:
            return None
        img_path.write_bytes(data)
        return img_path
    except Exception:
        return None
