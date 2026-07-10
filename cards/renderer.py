"""멀티슬라이드 카드 캐러셀 렌더러 — @HiddenFindsDaily (영어 전용).

IMPL_AUDIT_v2.0 반영:
  - 슬라이드 4종: HOOK / REVEAL / COMPARE / CTA (CONTEXT 제거)
  - 3비율 독립 렌더링: pinterest(1000×1500) / instagram(1080×1080) / tiktok(1080×1920)
  - card_renderer.py와 격리 (쇼츠 LIVE 파이프라인 보호) — 프리미티브 자체 보유, size-파라미터화
  - 폰트: Poppins(헤드라인) / Inter(본문) — 영어 전용

배경 정책 (IMPL_AUDIT_v2.0 N-01):
  HOOK    → AI 배경 이미지 (image_path 지정 시)
  REVEAL  → 실제 사진/상품 이미지 (image_path)
  COMPARE → 단색 그라디언트
  CTA     → 단색 그라디언트 + 채널 브랜딩
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageFilter

# ── 폰트 ──────────────────────────────────────────────────────────────────────
# cards/renderer.py → parent(cards/) → parent(프로젝트 루트) / assets / fonts
_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FC: dict[tuple, ImageFont.FreeTypeFont] = {}


def _fnt(name: str, size: int) -> ImageFont.FreeTypeFont:
    key = (name, size)
    if key not in _FC:
        _FC[key] = ImageFont.truetype(str(_FONT_DIR / name), size)
    return _FC[key]


def _f_black(s):  return _fnt("Poppins-Black.ttf", s)
def _f_bold(s):   return _fnt("Poppins-Bold.ttf", s)
def _f_semi(s):   return _fnt("Poppins-SemiBold.ttf", s)
def _f_med(s):    return _fnt("Poppins-Medium.ttf", s)
def _f_reg(s):    return _fnt("Poppins-Regular.ttf", s)
def _f_emoji(s):  return _fnt("NotoEmoji-Bold.ttf", s)


# ── 이모지 폴백 렌더링 (F-01 해결) ─────────────────────────────────────────────
# Poppins/Inter 에 이모지·화살표 글리프가 없어 두부박스(☐)로 깨짐 →
# 이모지 구간만 Noto Emoji(흑백)로 분리 렌더링한다.
def _is_emoji_cp(cp: int) -> bool:
    return (
        0x1F300 <= cp <= 0x1FAFF or   # 기호·이모티콘·교통·보조
        0x2600 <= cp <= 0x27BF or     # 잡기호·딩뱃
        0x2190 <= cp <= 0x21FF or     # 화살표 (→)
        0x2B00 <= cp <= 0x2BFF or     # 잡기호·화살표 (⭐)
        0x2300 <= cp <= 0x23FF or     # 기술기호 (⏰)
        cp in (0x203C, 0x2049, 0x20E3, 0xFE0F, 0x200D)
    )


def _segment(text: str) -> list[tuple[str, bool]]:
    """텍스트 → [(run, is_emoji)] 구간 분리. VS16/ZWJ는 이모지 구간에 흡수."""
    runs: list[tuple[str, bool]] = []
    for ch in text:
        emo = _is_emoji_cp(ord(ch))
        # 변이선택자(FE0F)/ZWJ는 직전 이모지 구간에 붙임
        if ch in ("️", "‍") and runs and runs[-1][1]:
            runs[-1] = (runs[-1][0] + ch, True)
        elif runs and runs[-1][1] == emo:
            runs[-1] = (runs[-1][0] + ch, emo)
        else:
            runs.append((ch, emo))
    return runs


def _emoji_font_for(base_font, ratio: float = 0.86):
    return _f_emoji(max(12, int(base_font.size * ratio)))


def _measure_rich(text: str, base_font) -> int:
    ef = _emoji_font_for(base_font)
    w = 0
    for run, is_emo in _segment(text):
        f = ef if is_emo else base_font
        w += f.getbbox(run)[2] - f.getbbox(run)[0] if run.strip() else _tw(f, run)
    return w


def _draw_rich(base: Image.Image, xy, text: str, base_font, fill, *, center_w: int | None = None) -> None:
    """이모지 폴백 혼합 렌더. center_w 지정 시 그 폭 기준 가로 중앙정렬."""
    draw = ImageDraw.Draw(base)
    ef = _emoji_font_for(base_font)
    x, y = xy
    if center_w is not None:
        total = _measure_rich(text, base_font)
        x = (center_w - total) // 2
    # 이모지를 텍스트 캡높이에 맞춰 살짝 내려 정렬
    emo_dy = int(base_font.size * 0.08)
    for run, is_emo in _segment(text):
        if is_emo:
            draw.text((x, y + emo_dy), run, font=ef, fill=fill)
            x += _tw(ef, run)
        else:
            draw.text((x, y), run, font=base_font, fill=fill)
            x += _tw(base_font, run)


# ── 팔레트 ────────────────────────────────────────────────────────────────────
PALETTE = {
    "bg_top":    (10, 18, 38),
    "bg_mid":    (16, 28, 56),
    "bg_bot":    (5, 10, 22),
    "accent":    (64, 220, 180),    # 민트
    "highlight": (255, 214, 48),    # 옐로우
    "main":      (255, 255, 255),
    "sub":       (165, 192, 220),
    "card":      (255, 255, 255),
    "card_dark": (22, 32, 54),
}


# ── 슬라이드 데이터 ────────────────────────────────────────────────────────────
SlideType = Literal["hook", "reveal", "compare", "cta"]


@dataclass
class Slide:
    type: SlideType
    title: str = ""
    subtitle: str = ""
    body_lines: list[str] = field(default_factory=list)
    image_path: Path | None = None     # 배경 또는 상품 이미지
    image_mode: str = "cover"          # "cover"(풀블리드 배경) | "contain"(상단 썸네일)
    badge: str = ""                    # 번호("01"), 가격, 라벨
    # COMPARE 전용
    left: dict | None = None           # {"label","price","note","image_path"}
    right: dict | None = None


# ── 텍스트 유틸 (size-독립) ───────────────────────────────────────────────────
def _tw(font, text: str) -> int:
    b = font.getbbox(text)
    return b[2] - b[0]


def _th(font, text: str) -> int:
    b = font.getbbox(text)
    return b[3] - b[1]


def _wrap(text: str, font, max_w: int) -> list[str]:
    """단어 단위 줄바꿈 (영어)."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        if _tw(font, test) > max_w and cur:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines or [""]


# ── 그라디언트 (size-파라미터) ────────────────────────────────────────────────
def _gradient(W: int, H: int, pal: dict) -> Image.Image:
    img = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(img)
    c1, c2, c3 = pal["bg_top"], pal["bg_mid"], pal["bg_bot"]
    split = int(H * 0.55)
    for y in range(H):
        if y <= split:
            t = y / max(split, 1)
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
        else:
            t = (y - split) / max(H - split, 1)
            r = int(c2[0] + (c3[0] - c2[0]) * t)
            g = int(c2[1] + (c3[1] - c2[1]) * t)
            b = int(c2[2] + (c3[2] - c2[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    return img


def _grain(img: Image.Image, seed: int, intensity: int = 7) -> Image.Image:
    if not _HAS_NUMPY:
        return img
    rng = np.random.default_rng(seed)
    arr = np.array(img, dtype=np.int16)
    noise = rng.integers(-intensity, intensity + 1, arr.shape, dtype=np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _cover_image(path: Path, W: int, H: int, darken: float = 0.45) -> Image.Image:
    """이미지를 캔버스에 cover-fit + 어둡게 (텍스트 가독성)."""
    src = Image.open(path).convert("RGB")
    sw, sh = src.size
    scale = max(W / sw, H / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    src = src.resize((nw, nh), Image.LANCZOS)
    left = (nw - W) // 2
    top = (nh - H) // 2
    src = src.crop((left, top, left + W, top + H))
    if darken > 0:
        src = ImageEnhance.Brightness(src).enhance(1.0 - darken)
    return src


def _rounded_box(base: Image.Image, x1, y1, x2, y2, fill_rgba, radius=24) -> None:
    W, H = base.size
    ol = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ol).rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill_rgba)
    merged = Image.alpha_composite(base.convert("RGBA"), ol)
    base.paste(merged.convert("RGB"))


def _highlighter(base: Image.Image, x1, y1, x2, y2, color_rgb, alpha=110) -> None:
    W, H = base.size
    ol = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(ol).rectangle([x1 - 8, y1, x2 + 8, y2], fill=(*color_rgb, alpha))
    merged = Image.alpha_composite(base.convert("RGBA"), ol)
    base.paste(merged.convert("RGB"))


def _bottom_fade(base: Image.Image, start_y: int, color_rgb: tuple, height: int = 360) -> None:
    W, H = base.size
    ol = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ol)
    for i in range(height):
        y = start_y + i
        if y >= H:
            break
        a = int(235 * (i / height))
        od.line([(0, y), (W, y)], fill=(*color_rgb, a))
    merged = Image.alpha_composite(base.convert("RGBA"), ol)
    base.paste(merged.convert("RGB"))


# ── 렌더러 ────────────────────────────────────────────────────────────────────
CANVAS = {
    "pinterest": (1000, 1500),
    "instagram": (1080, 1350),   # 4:5 — 2026 IG 최적(화면 최대 활용)
    "tiktok":    (1080, 1920),
}


class CarouselRenderer:
    def __init__(self, *, channel_tag: str = "@HiddenFindsDaily",
                 linktree: str = "linktr.ee/HiddenFindsDaily_",
                 pal: dict | None = None) -> None:
        self.channel_tag = channel_tag
        self.linktree = linktree
        self.pal = pal or PALETTE

    # ── public ────────────────────────────────────────────────────────────────
    def render(self, slides: list[Slide], ratio: str, output_dir: Path,
               *, prefix: str = "slide") -> list[Path]:
        if ratio not in CANVAS:
            raise ValueError(f"unknown ratio: {ratio}")
        W, H = CANVAS[ratio]
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        total = len(slides)
        for i, slide in enumerate(slides, start=1):
            img = self._render_slide(slide, W, H, seed=i, index=i, total=total)
            out = output_dir / f"{prefix}_{i:02d}.jpg"
            img.save(str(out), "JPEG", quality=90, optimize=True)
            paths.append(out)
        return paths

    # ── 캐러셀 진행 도트 (상단, "더 있다" 신호 → 완주 유도) ──────────────────────
    def _draw_progress(self, base: Image.Image, W: int, H: int, index: int, total: int) -> None:
        if total < 2:
            return
        draw = ImageDraw.Draw(base)
        r = max(4, W // 150)
        gap = r * 3
        span = (total - 1) * gap
        x0 = (W - span) // 2
        y = int(H * 0.045)
        for k in range(total):
            cx = x0 + k * gap
            on = (k + 1) == index
            col = self.pal["accent"] if on else (255, 255, 255)
            rr = r + 1 if on else r
            draw.ellipse([cx - rr, y - rr, cx + rr, y + rr],
                         fill=col if on else None,
                         outline=(255, 255, 255) if not on else None,
                         width=0 if on else 2)

    # ── per-slide dispatch ──────────────────────────────────────────────────────
    def _render_slide(self, slide: Slide, W: int, H: int, seed: int,
                      index: int = 1, total: int = 1) -> Image.Image:
        # 배경: cover 모드 이미지만 풀블리드. contain(상품 썸네일)은 그라디언트 유지.
        has_cover = (slide.type in ("hook", "reveal") and slide.image_mode == "cover"
                     and slide.image_path and Path(slide.image_path).exists())
        if has_cover:
            base = _cover_image(Path(slide.image_path), W, H,
                                darken=0.5 if slide.type == "hook" else 0.35)
        else:
            base = _gradient(W, H, self.pal)
            base = _grain(base, seed=seed)

        if slide.type == "hook":
            self._draw_hook(base, slide, W, H)
        elif slide.type == "reveal":
            self._draw_reveal(base, slide, W, H)
        elif slide.type == "compare":
            self._draw_compare(base, slide, W, H)
        elif slide.type == "cta":
            self._draw_cta(base, slide, W, H)
        self._draw_progress(base, W, H, index, total)
        self._draw_watermark(base, W, H)
        return base

    # ── 상품 썸네일 (contain) — 상단 중앙 둥근 카드 ──────────────────────────────
    def _paste_thumb(self, base: Image.Image, path: Path, W: int, H: int) -> None:
        try:
            src = Image.open(path).convert("RGB")
        except Exception:
            return
        box = int(W * 0.52)                       # 정사각 썸네일 변
        # cover-fit into square
        sw, sh = src.size
        scale = max(box / sw, box / sh)
        src = src.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
        nx, ny = src.size
        src = src.crop(((nx - box) // 2, (ny - box) // 2,
                        (nx - box) // 2 + box, (ny - box) // 2 + box))
        # 둥근 마스크
        mask = Image.new("L", (box, box), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, box, box], radius=box // 12, fill=255)
        px = (W - box) // 2
        py = int(H * 0.12)
        base.paste(src, (px, py), mask)

    # ── 공통 워터마크 ────────────────────────────────────────────────────────────
    def _draw_watermark(self, base: Image.Image, W: int, H: int) -> None:
        draw = ImageDraw.Draw(base)
        f = _f_med(max(20, W // 50))
        tw = _tw(f, self.channel_tag)
        draw.text((W - tw - W // 28, H - H // 22), self.channel_tag,
                  font=f, fill=self.pal["sub"])

    # ── HOOK ──────────────────────────────────────────────────────────────────
    def _draw_hook(self, base: Image.Image, slide: Slide, W: int, H: int) -> None:
        pad = W // 14
        text_w = W - pad * 2
        _bottom_fade(base, int(H * 0.42), self.pal["bg_bot"], height=int(H * 0.6))
        draw = ImageDraw.Draw(base)

        # 상단 배지 (예: "HIDDEN TRAVEL")
        if slide.badge:
            fb = _f_bold(max(22, W // 42))
            bw = _tw(fb, slide.badge)
            bh = _th(fb, slide.badge)
            _rounded_box(base, pad, int(H * 0.30), pad + bw + 44, int(H * 0.30) + bh + 28,
                         fill_rgba=(*self.pal["accent"], 230), radius=(bh + 28) // 2)
            draw = ImageDraw.Draw(base)
            draw.text((pad + 22, int(H * 0.30) + 14), slide.badge,
                      font=fb, fill=self.pal["bg_bot"])

        # 메인 훅 타이틀 (하단 정렬, 길이 적응)
        size = max(40, W // 11)
        f_title = _f_black(size)
        lines = _wrap(slide.title, f_title, text_w)
        while len(lines) > 4 and size > 32:
            size -= 4
            f_title = _f_black(size)
            lines = _wrap(slide.title, f_title, text_w)
        lh = int(size * 1.16)
        total_h = lh * len(lines)
        y = int(H * 0.74) - total_h
        for idx, line in enumerate(lines):
            bb = f_title.getbbox(line)
            lw = bb[2] - bb[0]
            # 형광펜: 모든 줄 일관, 글자 몸통(x-height)에 정확히 위치
            _highlighter(base, pad - 4, y + int(size * 0.30),
                         pad + lw + 4, y + int(size * 0.96),
                         color_rgb=self.pal["highlight"], alpha=82)
            draw = ImageDraw.Draw(base)
            draw.text((pad, y), line, font=f_title, fill=self.pal["main"])
            y += lh

        # 서브타이틀 + 스와이프 유도 (이모지 폴백 — 💾 등 두부박스 방지)
        if slide.subtitle:
            fs = _f_med(max(26, W // 32))
            sy = y + 18
            for line in _wrap(slide.subtitle, fs, text_w)[:2]:
                _draw_rich(base, (pad, sy), line, fs, self.pal["sub"])
                sy += int(fs.size * 1.35)
        fa = _f_semi(max(24, W // 36))
        _draw_rich(base, (pad, int(H * 0.80)), "Swipe to see them 👉", fa, self.pal["accent"])

    # ── REVEAL ──────────────────────────────────────────────────────────────────
    def _draw_reveal(self, base: Image.Image, slide: Slide, W: int, H: int) -> None:
        pad = W // 16
        text_w = W - pad * 2
        has_cover = slide.image_mode == "cover" and slide.image_path and Path(slide.image_path).exists()

        # ── 상단 여백 채우기 (cover 배경이 없을 때) ──────────────────────────
        if not has_cover:
            # 상품 썸네일(contain) 있으면 상단 중앙에 둥근 이미지로 배치
            if (slide.image_mode == "contain" and slide.image_path
                    and Path(slide.image_path).exists()):
                self._paste_thumb(base, Path(slide.image_path), W, H)
            # 큰 반투명 번호 — 빈 상단을 에디토리얼하게 채움
            if slide.badge:
                fbig = _f_black(int(W * 0.30))
                num = ImageDraw.Draw(base)
                num.text((pad - W // 40, int(H * 0.06)), slide.badge,
                         font=fbig, fill=self.pal["bg_mid"])

        # 하단 정보 카드 영역
        card_top = int(H * 0.58)
        _rounded_box(base, pad, card_top, W - pad, H - int(H * 0.07),
                     fill_rgba=(*self.pal["card_dark"], 235), radius=28)
        draw = ImageDraw.Draw(base)

        x = pad + W // 22
        y = card_top + H // 28

        # 번호 배지
        if slide.badge:
            fbz = _f_black(max(30, W // 24))
            draw.text((x, y), slide.badge, font=fbz, fill=self.pal["accent"])
            x_title = x + _tw(fbz, slide.badge) + W // 30
        else:
            x_title = x

        # 제목 (장소명/상품명)
        ft = _f_bold(max(32, W // 20))
        title_lines = _wrap(slide.title, ft, (W - pad) - x_title)[:2]
        ty = y
        for line in title_lines:
            draw.text((x_title, ty), line, font=ft, fill=self.pal["main"])
            ty += int(ft.size * 1.15)

        # 서브타이틀 (위치/브랜드)
        yy = max(ty, y + int(ft.size * 1.2)) + 6
        if slide.subtitle:
            fs = _f_med(max(24, W // 34))
            draw.text((x, yy), slide.subtitle, font=fs, fill=self.pal["accent"])
            yy += int(fs.size * 1.5)

        # 본문 라인 (가격·팁·시기)
        fb = _f_reg(max(23, W // 36))
        for line in slide.body_lines[:4]:
            for wline in _wrap(line, fb, text_w - W // 22)[:1]:
                draw.text((x, yy), f"• {wline}", font=fb, fill=self.pal["sub"])
                yy += int(fb.size * 1.45)

    # ── COMPARE (V1 전용) ────────────────────────────────────────────────────────
    def _draw_compare(self, base: Image.Image, slide: Slide, W: int, H: int) -> None:
        draw = ImageDraw.Draw(base)
        pad = W // 18
        mid = W // 2
        top = int(H * 0.22)
        bot = int(H * 0.80)

        # 제목
        if slide.title:
            ft = _f_bold(max(30, W // 22))
            for i, line in enumerate(_wrap(slide.title, ft, W - pad * 2)[:2]):
                tw = _tw(ft, line)
                draw.text(((W - tw) // 2, int(H * 0.08) + i * int(ft.size * 1.15)),
                          line, font=ft, fill=self.pal["main"])

        def _col(side: dict | None, x1: int, x2: int, accent: tuple) -> None:
            if not side:
                return
            _rounded_box(base, x1, top, x2, bot, fill_rgba=(*self.pal["card_dark"], 235), radius=24)
            d = ImageDraw.Draw(base)
            cx = (x1 + x2) // 2
            # 라벨
            fl = _f_bold(max(26, W // 30))
            lbl = side.get("label", "")
            d.text((cx - _tw(fl, lbl) // 2, top + H // 30), lbl, font=fl, fill=accent)
            # 가격 (대형)
            fp = _f_black(max(48, W // 13))
            price = side.get("price", "")
            d.text((cx - _tw(fp, price) // 2, top + H // 12), price, font=fp, fill=self.pal["main"])
            # 노트
            fn = _f_reg(max(22, W // 38))
            note = side.get("note", "")
            for i, line in enumerate(_wrap(note, fn, (x2 - x1) - W // 20)[:3]):
                d.text((cx - _tw(fn, line) // 2, bot - H // 8 + i * int(fn.size * 1.3)),
                       line, font=fn, fill=self.pal["sub"])

        _col(slide.left, pad, mid - W // 40, self.pal["highlight"])
        _col(slide.right, mid + W // 40, W - pad, self.pal["accent"])

        # VS
        fv = _f_black(max(34, W // 20))
        draw = ImageDraw.Draw(base)
        draw.text((mid - _tw(fv, "VS") // 2, (top + bot) // 2 - fv.size // 2),
                  "VS", font=fv, fill=self.pal["highlight"])

    # ── CTA ──────────────────────────────────────────────────────────────────────
    def _draw_cta(self, base: Image.Image, slide: Slide, W: int, H: int) -> None:
        pad = W // 12
        title = slide.title or "Save this for later 💾"
        ft = _f_black(max(44, W // 13))
        fa = _f_med(max(28, W // 28))
        fl = _f_bold(max(26, W // 30))
        actions = (slide.body_lines or [
            "💾  Save this for later",
            "📤  Send to a friend who'd love this",
            "➕  Follow for a hidden gem every day",
        ])[:4]

        title_lines = _wrap(title, ft, W - pad * 2)[:3]
        lh_t = int(ft.size * 1.18)
        lh_a = int(fa.size * 1.55)
        gap1, gap2 = H // 28, H // 26
        link_h = fl.size + 36
        # 전체 블록 높이 → 세로 중앙 정렬 (하단 여백 해소)
        block_h = len(title_lines) * lh_t + gap1 + len(actions) * lh_a + gap2 + link_h
        cy = max(int(H * 0.10), (H - block_h) // 2)

        for line in title_lines:
            _draw_rich(base, (0, cy), line, ft, self.pal["main"], center_w=W)
            cy += lh_t
        cy += gap1
        for line in actions:
            _draw_rich(base, (0, cy), line, fa, self.pal["sub"], center_w=W)
            cy += lh_a
        cy += gap2

        # 링크 박스
        link = f"🔗 {self.linktree}"
        lw = _measure_rich(link, fl)
        bx1, bx2 = (W - lw) // 2 - 30, (W + lw) // 2 + 30
        _rounded_box(base, bx1, cy - 12, bx2, cy + fl.size + 24,
                     fill_rgba=(*self.pal["accent"], 235), radius=(fl.size + 36) // 2)
        _draw_rich(base, (0, cy), link, fl, self.pal["bg_bot"], center_w=W)


# ── 데모 (키 없이 검증용) ────────────────────────────────────────────────────────
def render_demo(ratio: str = "instagram", output_dir: Path | None = None) -> list[Path]:
    """샘플 여행 콘텐츠로 8슬라이드 생성 (배경 이미지 없이 그라디언트)."""
    out = output_dir or (Path(__file__).resolve().parent.parent
                         / "output" / "cards" / "demo" / ratio)
    slides = [
        Slide(type="hook", badge="HIDDEN TRAVEL",
              title="5 Secret Beaches in Asia No One Talks About",
              subtitle="Crystal water. Zero tourists. Locals only."),
        Slide(type="reveal", badge="01", title="Nacpan Beach",
              subtitle="El Nido, Philippines",
              body_lines=["Best time: Nov–May", "Budget: $25/night", "4km of empty white sand"]),
        Slide(type="reveal", badge="02", title="Koh Kradan",
              subtitle="Trang, Thailand",
              body_lines=["Best time: Dec–Apr", "Budget: $30/night", "Snorkeling paradise"]),
        Slide(type="reveal", badge="03", title="Ngapali Beach",
              subtitle="Rakhine, Myanmar",
              body_lines=["Best time: Oct–Mar", "Budget: $40/night", "Untouched fishing village"]),
        Slide(type="reveal", badge="04", title="Pink Beach",
              subtitle="Komodo, Indonesia",
              body_lines=["Best time: Apr–Dec", "Budget: $35/night", "Rare pink sand"]),
        Slide(type="reveal", badge="05", title="Long Beach",
              subtitle="Phu Quoc, Vietnam",
              body_lines=["Best time: Nov–Mar", "Budget: $20/night", "Sunset views"]),
        Slide(type="cta", title="Save this for your next trip ✈️",
              body_lines=["💾  Save before they get crowded",
                          "📤  Tag your travel buddy",
                          "💬  Which one is #1? Comment"]),
    ]
    r = CarouselRenderer()
    return r.render(slides, ratio, out)


if __name__ == "__main__":
    import sys
    ratio = sys.argv[1] if len(sys.argv) > 1 else "instagram"
    paths = render_demo(ratio)
    print(f"{len(paths)} slides → {paths[0].parent}")
