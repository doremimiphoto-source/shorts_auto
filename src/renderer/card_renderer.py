"""한국 중학생 공부 콘텐츠용 카드 이미지 생성기.

Pillow 기반. 사람이 Canva/Slides로 직접 만든 듯한 느낌 목표:
  - 완벽 중앙 정렬 대신 왼쪽 정렬 + 여백 리듬
  - 형광펜 마킹 (반투명, 약간 기울어짐)
  - 왼쪽 액센트 바 (blockquote 스타일)
  - 점선 구분선 (딱딱한 직선 아님)
  - 필름 그레인 텍스처 (numpy 있을 때만)

레이아웃:
  shock_fact  — 기본. 다크 네이비 배경, 반전 훅 + 불릿 + CTA
  number_stat — 숫자 초대형 강조 (number 패턴)
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

from PIL import Image, ImageDraw, ImageFont

# ── 캔버스 ────────────────────────────────────────────────────────────────
W, H = 1080, 1920

_FONT_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"

# ── 팔레트 ────────────────────────────────────────────────────────────────
# Dark navy (기본)
_D = {
    "bg_top":   (12, 22, 44),
    "bg_mid":   (19, 34, 70),
    "bg_bot":   (7,  13, 30),
    "accent":   (64, 255, 200),     # 민트 형광
    "hl":       (255, 228, 48),     # 노랑 형광펜
    "main":     (255, 255, 255),
    "sub":      (148, 180, 218),
    "div":      (255, 255, 255),
}

# ── 폰트 캐시 ─────────────────────────────────────────────────────────────
_FC: dict[tuple, ImageFont.FreeTypeFont] = {}

def _fnt(name: str, size: int) -> ImageFont.FreeTypeFont:
    key = (name, size)
    if key not in _FC:
        _FC[key] = ImageFont.truetype(str(_FONT_DIR / name), size)
    return _FC[key]

def _fb(sz):   return _fnt("Pretendard-Black.otf", sz)
def _fxb(sz):  return _fnt("Pretendard-ExtraBold.otf", sz)
def _fbd(sz):  return _fnt("Pretendard-Bold.otf", sz)
def _fm(sz):   return _fnt("Pretendard-Medium.otf", sz)
def _fr(sz):   return _fnt("Pretendard-Regular.otf", sz)

def _tw(font: ImageFont.FreeTypeFont, text: str) -> int:
    b = font.getbbox(text)
    return b[2] - b[0]

def _th(font: ImageFont.FreeTypeFont, text: str) -> int:
    b = font.getbbox(text)
    return b[3] - b[1]


# ── 텍스트 줄바꿈 ──────────────────────────────────────────────────────────
def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for ch in text:
        test = cur + ch
        if _tw(font, test) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines or [""]


# ── 그라디언트 배경 ────────────────────────────────────────────────────────
def _gradient(pal: dict) -> Image.Image:
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    c1, c2, c3 = pal["bg_top"], pal["bg_mid"], pal["bg_bot"]
    split = int(H * 0.58)
    for y in range(H):
        if y <= split:
            t = y / split
        else:
            # bottom: ease-in (더 빠르게 어두워짐)
            raw = (y - split) / (H - split)
            t = 1.0 - (1.0 - raw) ** 2   # ease-in toward dark
        if y <= split:
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
        else:
            t2 = (y - split) / (H - split)
            r = int(c2[0] + (c3[0] - c2[0]) * t2)
            g = int(c2[1] + (c3[1] - c2[1]) * t2)
            b = int(c2[2] + (c3[2] - c2[2]) * t2)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return img


# ── 필름 그레인 (인간적 질감) ─────────────────────────────────────────────
def _grain(img: Image.Image, intensity: int = 9) -> Image.Image:
    if not _HAS_NUMPY:
        return img
    rng = np.random.default_rng(37)          # 고정 seed: 일관된 질감
    arr = np.array(img, dtype=np.int16)
    noise = rng.integers(-intensity, intensity + 1, arr.shape, dtype=np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


# ── 형광펜 마킹 (RGBA overlay) ────────────────────────────────────────────
def _highlighter(base: Image.Image, x1: int, y1: int, x2: int, y2: int,
                 color_rgb: tuple, alpha: int = 115, angle: float = 1.4) -> None:
    """텍스트 bbox에 살짝 기울어진 형광펜 마킹."""
    pad_x, pad_bot = 10, 8
    rx1, ry1, rx2, ry2 = x1 - pad_x, y1 - 2, x2 + pad_x, y2 + pad_bot

    ol = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ol)
    od.rectangle([rx1, ry1, rx2, ry2], fill=(*color_rgb, alpha))
    # 약간 기울임 — 손으로 친 느낌
    cx, cy = (rx1 + rx2) // 2, (ry1 + ry2) // 2
    ol = ol.rotate(angle, center=(cx, cy), resample=Image.BICUBIC)
    base_rgba = base.convert("RGBA")
    base_rgba = Image.alpha_composite(base_rgba, ol)
    base.paste(base_rgba.convert("RGB"))


# ── 왼쪽 액센트 바 ────────────────────────────────────────────────────────
def _accent_bar(base: Image.Image, y_top: int, y_bot: int, color_rgb: tuple) -> None:
    ol = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ol)
    od.rectangle([50, y_top, 62, y_bot], fill=(*color_rgb, 195))
    base_rgba = base.convert("RGBA")
    base_rgba = Image.alpha_composite(base_rgba, ol)
    base.paste(base_rgba.convert("RGB"))


# ── 반투명 둥근 박스 ──────────────────────────────────────────────────────
def _rounded_box(base: Image.Image, x1: int, y1: int, x2: int, y2: int,
                 fill_rgba: tuple, radius: int = 20) -> None:
    ol = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ol)
    od.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill_rgba)
    base_rgba = base.convert("RGBA")
    base_rgba = Image.alpha_composite(base_rgba, ol)
    base.paste(base_rgba.convert("RGB"))


# ── 점선 구분선 ────────────────────────────────────────────────────────────
def _dashed_sep(draw: ImageDraw.ImageDraw, y: int, pal: dict) -> None:
    x, dash_w, gap = 76, 16, 10
    color_rgb = pal["div"]
    while x < W - 76:
        draw.rectangle([x, y, min(x + dash_w, W - 76), y + 2],
                       fill=(*color_rgb, 50))
        x += dash_w + gap


# ── 상단 카테고리 태그 pill ────────────────────────────────────────────────
def _tag_pill(base: Image.Image, label: str, pal: dict) -> None:
    font = _fm(26)
    tw = _tw(font, label)
    th = _th(font, label)
    px, py = 22, 12
    rx = W - 76 - tw - px * 2
    ry = 96
    _rounded_box(base, rx, ry, rx + tw + px * 2, ry + th + py * 2,
                 fill_rgba=(255, 255, 255, 26), radius=22)
    draw = ImageDraw.Draw(base)
    draw.text((rx + px, ry + py), label, font=font, fill=pal["sub"])


# ── 바디 → 불릿 파싱 ──────────────────────────────────────────────────────
def _bullets(body: str) -> list[str]:
    """body → 최대 3개 불릿. 첫째/둘째/셋째 우선, 없으면 문장 분리."""
    parts = re.split(r'(첫째[,，]\s*|둘째[,，]\s*|셋째[,，]\s*|넷째[,，]\s*)', body.strip())
    if len(parts) >= 3:
        pts = []
        for i in range(1, len(parts), 2):
            # "첫째, " → strip → rstrip(',') → "첫째"
            label = parts[i].strip().rstrip(',，').strip()
            after = (parts[i + 1].strip() if i + 1 < len(parts) else "").rstrip('.')
            pts.append(f"{label}: {after}" if after else label)
        return pts[:3]
    sents = [s.strip().rstrip('.') for s in re.split(r'[.。\n]+', body) if s.strip()]
    return [s[:46] + ("…" if len(s) > 46 else "") for s in sents[:3]]


# ── 핵심 수치 추출 ─────────────────────────────────────────────────────────
def _stat(text: str) -> tuple[str, str] | None:
    m = re.search(r'(\d+(?:\.\d+)?)(%|배|시간|분|일|점|개|명)', text)
    if m:
        return m.group(1), m.group(2)
    return None


# ── 하단 그라디언트 오버레이 (텍스트 가독성↑) ────────────────────────────
def _bottom_fade(base: Image.Image, start_y: int, pal: dict) -> None:
    fade_h = 160
    ol = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ol)
    c = pal["bg_bot"]
    for fy in range(fade_h):
        a = int(220 * (fy / fade_h))
        od.line([(0, start_y + fy), (W, start_y + fy)], fill=(*c, a))
    base_rgba = base.convert("RGBA")
    base_rgba = Image.alpha_composite(base_rgba, ol)
    base.paste(base_rgba.convert("RGB"))


# ─────────────────────────────────────────────────────────────────────────────
# 레이아웃: shock_fact
# ─────────────────────────────────────────────────────────────────────────────
def _layout_shock_fact(
    base: Image.Image,
    hook: str, body: str, twist: str, emph: list[str],
    pal: dict,
) -> None:
    draw = ImageDraw.Draw(base)
    PAD_L = 76
    TEXT_W = W - PAD_L - 64

    # ── 훅 폰트 크기: 길이에 따라 자동 조정 ─────────────────────────────
    hook_sz = 72 if len(hook) <= 18 else (62 if len(hook) <= 26 else 54)
    f_hook = _fxb(hook_sz)
    hook_lines = _wrap(hook, f_hook, TEXT_W)[:3]   # 최대 3줄

    y = 200
    lh = int(hook_sz * 1.38)

    # 왼쪽 액센트 바 범위
    bar_top = y - 6
    for idx, line in enumerate(hook_lines):
        # 첫 번째 줄 전체 or emphasis 단어 포함 줄 → 형광펜
        if idx == 0 or any(ew in line for ew in emph):
            bb = f_hook.getbbox(line)
            lw = bb[2] - bb[0]
            lht = bb[3] - bb[1]
            # 형광펜은 텍스트 아래쪽 1/3 영역에만 (더 자연스러움)
            hl_y1 = y + lht // 2
            hl_y2 = y + lht + 6
            _highlighter(base, PAD_L, hl_y1, PAD_L + lw, hl_y2,
                         color_rgb=pal["hl"], alpha=100, angle=1.2)
        draw = ImageDraw.Draw(base)
        draw.text((PAD_L, y), line, font=f_hook, fill=pal["main"])
        y += lh

    bar_bot = y - 10
    _accent_bar(base, bar_top, bar_bot, pal["accent"])
    draw = ImageDraw.Draw(base)

    y += 28

    # ── 핵심 수치 하이라이트 박스 ────────────────────────────────────────
    sv = _stat(hook + " " + body)
    if sv:
        num_s, unit_s = sv
        box_h = 170
        _rounded_box(base, PAD_L, y, W - 64, y + box_h,
                     fill_rgba=(*pal["accent"], 18), radius=18)
        draw = ImageDraw.Draw(base)

        f_num  = _fb(108)
        f_unit = _fbd(52)
        nw = _tw(f_num, num_s)
        uw = _tw(f_unit, unit_s)
        total = nw + 10 + uw
        nx = (W - total) // 2
        draw.text((nx, y + 20), num_s, font=f_num, fill=pal["accent"])
        draw.text((nx + nw + 10, y + 62), unit_s, font=f_unit, fill=pal["accent"])
        y += box_h + 28

    # ── 점선 구분선 ──────────────────────────────────────────────────────
    _dashed_sep(draw, y, pal)
    y += 38

    # ── 바디 불릿 ────────────────────────────────────────────────────────
    bullet_pts = _bullets(body)
    f_body = _fr(38)
    symbols = ["①", "②", "③"]
    for i, pt in enumerate(bullet_pts):
        sym = symbols[i] if i < 3 else "▸"
        draw.text((PAD_L, y + 4), sym, font=_fbd(36), fill=pal["accent"])
        lines = _wrap(pt, f_body, TEXT_W - 50)
        for j, line in enumerate(lines):
            draw.text((PAD_L + 50, y + j * 52), line, font=f_body, fill=pal["main"])
        y += 52 * max(len(lines), 1) + 20

    # ── 하단 페이드 ──────────────────────────────────────────────────────
    cta_y = max(y + 40, 1500)
    _bottom_fade(base, cta_y - 80, pal)
    draw = ImageDraw.Draw(base)

    # ── CTA ──────────────────────────────────────────────────────────────
    f_cta = _fbd(44)
    cta_lines = _wrap(twist, f_cta, TEXT_W)[:2]
    for line in cta_lines:
        lw = _tw(f_cta, line)
        draw.text(((W - lw) // 2, cta_y), line, font=f_cta, fill=pal["hl"])
        cta_y += 62

    # ── 채널 태그 ─────────────────────────────────────────────────────────
    ch = "@중학생공부치트키"
    f_ch = _fr(28)
    cw = _tw(f_ch, ch)
    draw.text(((W - cw) // 2, cta_y + 22), ch, font=f_ch, fill=pal["sub"])


# ─────────────────────────────────────────────────────────────────────────────
# 레이아웃: number_stat (숫자 초대형 강조)
# ─────────────────────────────────────────────────────────────────────────────
def _layout_number_stat(
    base: Image.Image,
    hook: str, body: str, twist: str, emph: list[str],
    pal: dict,
) -> None:
    sv = _stat(hook + " " + body)
    if not sv:
        # 수치 없으면 shock_fact 폴백
        _layout_shock_fact(base, hook, body, twist, emph, pal)
        return

    draw = ImageDraw.Draw(base)
    PAD_L = 76
    TEXT_W = W - PAD_L - 64
    num_s, unit_s = sv

    # ── 초대형 숫자 ──────────────────────────────────────────────────────
    y = 300
    f_huge = _fb(190)
    f_unit = _fxb(78)
    nw = _tw(f_huge, num_s)
    uw = _tw(f_unit, unit_s)
    total = nw + 14 + uw
    nx = (W - total) // 2
    draw.text((nx, y), num_s, font=f_huge, fill=pal["accent"])
    draw.text((nx + nw + 14, y + 102), unit_s, font=f_unit, fill=pal["accent"])
    y += 260

    # 수치 설명 (출처/맥락)
    src_m = re.search(r'(UC버클리|연구|실험|조사|연구팀|과학|뇌과학|심리)[^.。\n]{0,30}', hook + " " + body)
    if src_m:
        f_src = _fm(32)
        src = src_m.group(0)[:34] + ("…" if len(src_m.group(0)) > 34 else "")
        sw = _tw(f_src, src)
        draw.text(((W - sw) // 2, y), src, font=f_src, fill=pal["sub"])
        y += 52

    _dashed_sep(draw, y + 16, pal)
    y += 56

    # ── 훅 텍스트 (중간 크기) ────────────────────────────────────────────
    f_h = _fxb(56)
    h_lines = _wrap(hook, f_h, TEXT_W)[:3]
    bar_top = y - 4
    for idx, line in enumerate(h_lines):
        if idx == 0:
            bb = f_h.getbbox(line)
            _highlighter(base, PAD_L, y + (bb[3] - bb[1]) // 2,
                         PAD_L + bb[2] - bb[0], y + bb[3] - bb[1] + 6,
                         color_rgb=pal["hl"], alpha=95, angle=1.0)
        draw = ImageDraw.Draw(base)
        draw.text((PAD_L, y), line, font=f_h, fill=pal["main"])
        y += 76
    _accent_bar(base, bar_top, y - 8, pal["accent"])
    draw = ImageDraw.Draw(base)
    y += 22

    # ── 불릿 ─────────────────────────────────────────────────────────────
    bullet_pts = _bullets(body)
    f_body = _fr(38)
    for i, pt in enumerate(bullet_pts):
        sym = ["①", "②", "③"][i] if i < 3 else "▸"
        draw.text((PAD_L, y + 4), sym, font=_fbd(36), fill=pal["accent"])
        lines = _wrap(pt, f_body, TEXT_W - 50)
        for j, line in enumerate(lines):
            draw.text((PAD_L + 50, y + j * 52), line, font=f_body, fill=pal["main"])
        y += 52 * max(len(lines), 1) + 20

    cta_y = max(y + 40, 1520)
    _bottom_fade(base, cta_y - 80, pal)
    draw = ImageDraw.Draw(base)

    f_cta = _fbd(44)
    cta_lines = _wrap(twist, f_cta, TEXT_W)[:2]
    for line in cta_lines:
        lw = _tw(f_cta, line)
        draw.text(((W - lw) // 2, cta_y), line, font=f_cta, fill=pal["hl"])
        cta_y += 62

    ch = "@중학생공부치트키"
    f_ch = _fr(28)
    cw = _tw(f_ch, ch)
    draw.text(((W - cw) // 2, cta_y + 22), ch, font=f_ch, fill=pal["sub"])


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def render_card(script: dict, output_path: Path, *, layout: str = "auto") -> Path:
    """script dict → PNG 카드 이미지 저장 후 경로 반환.

    script keys: hook, body, twist, title, hook_pattern, emphasis_words
    layout: 'auto' | 'shock_fact' | 'number_stat'
    """
    hook    = str(script.get("hook", "")).strip()
    body    = str(script.get("body", "")).strip()
    twist   = str(script.get("twist", "")).strip()
    title   = str(script.get("title", "")).strip()
    pattern = str(script.get("hook_pattern", "")).strip()
    emph    = [str(e) for e in (script.get("emphasis_words") or [])]

    if layout == "auto":
        layout = "number_stat" if pattern == "number" else "shock_fact"

    pal = _D

    base = _gradient(pal)
    base = _grain(base, intensity=9)

    # 카테고리 태그 pill (제목 앞 12자)
    tag = (title[:12] if title else "📚 공부꿀팁")
    _tag_pill(base, tag, pal)

    if layout == "number_stat":
        _layout_number_stat(base, hook, body, twist, emph, pal)
    else:
        _layout_shock_fact(base, hook, body, twist, emph, pal)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    base.save(str(output_path), "PNG", optimize=True)
    return output_path
