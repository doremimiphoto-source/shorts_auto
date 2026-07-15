"""브랜드 이미지 생성 — 노션 about 페이지 + 소셜 프로필 공용.

카드와 동일한 톤(다크 네이비 + 민트/옐로우, Poppins)으로:
  - avatar.jpg  (1080×1080) 프로필 사진
  - cover.jpg   (1500×500)  커버 배너

실행: .venv/bin/python -m cards.brand
출력: output/cards/brand/
"""

from __future__ import annotations

from pathlib import Path

from PIL import ImageDraw

from cards.renderer import (PALETTE, _draw_rich, _f_black, _f_bold, _f_med,
                            _gradient, _grain, _tw)

OUT = Path(__file__).resolve().parent.parent / "output" / "cards" / "brand"


def _center(draw, base, y, text, font, fill, W):
    _draw_rich(base, (0, y), text, font, fill, center_w=W)


def make_avatar() -> Path:
    W = H = 1080
    base = _grain(_gradient(W, H, PALETTE), seed=7)
    draw = ImageDraw.Draw(base)

    # 민트 링 (원형 강조)
    pad = 70
    draw.ellipse([pad, pad, W - pad, H - pad], outline=PALETTE["accent"], width=10)

    # 모노그램 "HF"
    f_mono = _f_black(360)
    mono = "HF"
    mw = _tw(f_mono, mono)
    draw.text(((W - mw) // 2, 250), mono, font=f_mono, fill=PALETTE["main"])
    # 옐로우 언더바
    bar_w = 240
    draw.rounded_rectangle([(W - bar_w) // 2, 660, (W + bar_w) // 2, 678],
                           radius=9, fill=PALETTE["highlight"])
    # 풀네임
    f_name = _f_bold(64)
    _center(draw, base, 710, "HiddenFindsDaily", f_name, PALETTE["main"], W)
    f_tag = _f_med(38)
    _center(draw, base, 800, "Korean Skincare · K-Beauty", f_tag, PALETTE["sub"], W)

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "avatar.jpg"
    base.save(str(p), "JPEG", quality=92)
    return p


def make_cover() -> Path:
    W, H = 1500, 500
    base = _grain(_gradient(W, H, PALETTE), seed=11)
    draw = ImageDraw.Draw(base)

    pad = 90
    # 좌측 민트 액센트 바
    draw.rounded_rectangle([pad, 150, pad + 12, 350], radius=6, fill=PALETTE["accent"])

    f_name = _f_black(110)
    draw.text((pad + 48, 150), "HiddenFindsDaily", font=f_name, fill=PALETTE["main"])
    f_tag = _f_med(46)
    _draw_rich(base, (pad + 52, 300),
               "💧 Korean Skincare  ·  💄 K-Beauty Finds Daily",
               f_tag, PALETTE["sub"])

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "cover.jpg"
    base.save(str(p), "JPEG", quality=92)
    return p


def make_all() -> list[Path]:
    return [make_avatar(), make_cover()]


if __name__ == "__main__":
    for p in make_all():
        print(f"  ✅ {p}")
