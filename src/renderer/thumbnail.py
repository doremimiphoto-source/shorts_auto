"""썸네일 생성 — YouTube Shorts 1080×1920 (9:16).

설계 원칙 (v3 — 간결·모던):
  - 선(가로/세로) 없음: 계층은 크기·색·여백만으로 표현
  - 제목: ExtraBold 대형, 핵심 키워드 1개만 액센트 색
  - 후크: 첫 줄 ExtraBold + 액센트, 나머지 soft-white
  - 여백이 구분선 역할 — 장식 없이 공간으로 호흡
  - 상단 토픽 배지: 내용 기반 키워드 (패턴명 아님)
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ── 패턴별 컬러 테마 ──────────────────────────────────────────────
_THEMES: dict[str, tuple[str, str, str]] = {
    "comparison":    ("#0f0f0f", "#FF4757", "#2a2a2a"),
    "number":        ("#0d1b2a", "#F5A623", "#1a2d40"),
    "question":      ("#0a1628", "#00C2E0", "#0f2040"),
    "shock":         ("#1a0808", "#FF3333", "#2a1010"),
    "twist_preview": ("#0d1b2a", "#F5A623", "#1a2d40"),
    "timeline":      ("#081a0f", "#2ECC71", "#0f2a18"),
    "dialogue":      ("#150d28", "#A855F7", "#221040"),
    "confession":    ("#1a1008", "#E67E22", "#2a1c10"),
    "second_person": ("#081a1a", "#14B8A6", "#0f2828"),
    "lucky_charm":   ("#0a1a08", "#FFD700", "#152a10"),
}
_DEFAULT_THEME = ("#0d1b2a", "#F5A623", "#1a2d40")

# ── 캔버스 ────────────────────────────────────────────────────────
W, H      = 1080, 1920
X_LEFT    = 72          # 텍스트 왼쪽 여백
X_RIGHT   = W - 72      # 텍스트 오른쪽 한계
MAX_W     = X_RIGHT - X_LEFT  # 936px

# 그라디언트 (위→아래 — 텍스트 구역 보호)
_GY_DARK  = 880
_GY_FADE  = 1300
_GY_MIN   = 50

# ── 강조 키워드 우선순위 ──────────────────────────────────────────
_KW_T1 = {"비법", "꿀팁", "공식", "만점", "고득점", "비밀", "핵심"}
_KW_T2 = {"시험", "기말", "중간", "수행평가"}
_KW_T3 = {"루틴", "암기", "집중력", "포모도로", "역이용", "망각",
           "공부법", "성적", "올리는", "올리기"}


@dataclass
class ThumbnailInput:
    title: str
    hook: str
    twist: str
    hook_pattern: str
    channel_name: str = "도도레미"
    keywords: list[str] = field(default_factory=list)


# ── 공개 API ──────────────────────────────────────────────────────

def generate(
    inp: ThumbnailInput,
    output_path: Path,
    fonts_dir: Path,
    *,
    bg_video: Path | None = None,
    ffmpeg_bin: str = "ffmpeg",
) -> Path:
    bg_hex, accent_hex, _ = _THEMES.get(inp.hook_pattern, _DEFAULT_THEME)

    img: Image.Image
    if bg_video and bg_video.exists():
        frame = _extract_frame(bg_video, ffmpeg_bin=ffmpeg_bin)
        img = _build_image_bg(frame, bg_hex) if frame else _build_solid_bg(bg_hex)
    else:
        img = _build_solid_bg(bg_hex)

    draw = ImageDraw.Draw(img)
    accent = _rgb(accent_hex)

    _draw_header(draw, inp, accent, fonts_dir)
    _draw_body(draw, inp, accent, fonts_dir)
    _draw_footer(draw, inp, fonts_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "JPEG", quality=95)
    return output_path


def extract_frame(video_path: Path, *, time_sec: int = 3,
                  ffmpeg_bin: str = "ffmpeg") -> Path | None:
    return _extract_frame(video_path, time_sec=time_sec, ffmpeg_bin=ffmpeg_bin)


# ── 배경 ──────────────────────────────────────────────────────────

def _extract_frame(video_path: Path, *, time_sec: int = 3,
                   ffmpeg_bin: str = "ffmpeg") -> Image.Image | None:
    tmp = Path(tempfile.mktemp(suffix=".jpg"))
    try:
        res = subprocess.run(
            [ffmpeg_bin, "-ss", str(time_sec), "-i", str(video_path),
             "-vframes", "1", "-f", "image2", "-y", str(tmp)],
            capture_output=True, timeout=15, check=False,
        )
        if res.returncode == 0 and tmp.exists():
            return Image.open(tmp).copy()
    except Exception:
        pass
    finally:
        tmp.unlink(missing_ok=True) if tmp.exists() else None
    return None


def _build_image_bg(frame: Image.Image, bg_hex: str) -> Image.Image:
    fw, fh = frame.size
    scale = max(W / fw, H / fh)
    nw, nh = int(fw * scale), int(fh * scale)
    scaled = frame.resize((nw, nh), Image.LANCZOS)
    cx, cy = (nw - W) // 2, (nh - H) // 2
    cropped = scaled.crop((cx, cy, cx + W, cy + H)).convert("RGBA")

    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    r, g, b = _rgb(bg_hex)
    for y in range(H):
        if y <= _GY_DARK:
            a = 210
        elif y <= _GY_FADE:
            t = (y - _GY_DARK) / (_GY_FADE - _GY_DARK)
            a = int(210 - t * (210 - _GY_MIN))
        else:
            a = _GY_MIN
        gd.line([(0, y), (W, y)], fill=(r, g, b, a))

    return Image.alpha_composite(cropped, grad).convert("RGB")


def _build_solid_bg(bg_hex: str) -> Image.Image:
    img = Image.new("RGB", (W, H), _rgb(bg_hex))
    r, g, b = _rgb(bg_hex)
    lighter = (min(255, r + 22), min(255, g + 22), min(255, b + 22))
    ImageDraw.Draw(img).rectangle([(0, 80), (W, H - 80)], fill=lighter)
    return img


# ── 헤더 (상단 라벨 + 토픽 배지) ─────────────────────────────────

def _topic_label(inp: ThumbnailInput) -> str:
    full = " ".join(filter(None, [inp.title, inp.hook, inp.twist]))
    if any(k in full for k in ("기말", "기말고사")):   return "기말대비"
    if any(k in full for k in ("중간", "중간고사")):   return "중간대비"
    if "수행평가" in full:                             return "수행평가"
    if "포모도로" in full:                             return "포모도로"
    if any(k in full for k in ("D-day", "기출")):     return "시험대비"
    if "시험" in full:                                 return "시험대비"
    if any(k in full for k in ("집중", "집중력")):     return "집중력"
    if "루틴" in full:                                 return "시간관리"
    if any(k in full for k in ("암기", "망각")):       return "암기법"
    if "오답" in full:                                 return "오답노트"
    if any(k in full for k in ("효율",)):              return "효율성"
    if any(k in full for k in ("비법", "꿀팁", "공식")): return "공부비법"
    if "성적" in full:                                 return "성적향상"
    return "공부법"


def _draw_header(draw: ImageDraw.ImageDraw, inp: ThumbnailInput,
                 accent: tuple, fonts_dir: Path) -> None:
    # 좌측 채널 라벨
    fnt = _font(fonts_dir, "Pretendard-Bold.otf", 32)
    draw.text((X_LEFT, 68), "▶ 중학생 공부법", font=fnt, fill=accent)

    # 우측 토픽 배지 (내용 기반)
    label = _topic_label(inp)
    fnt_b = _font(fonts_dir, "Pretendard-Bold.otf", 27)
    bw = int(draw.textlength(label, font=fnt_b)) + 30
    bx = W - bw - 28
    draw.rounded_rectangle([(bx, 62), (bx + bw, 62 + 48)], radius=12, fill=accent)
    draw.text((bx + 15, 71), label, font=fnt_b, fill=(12, 12, 12))


# ── 본문 ──────────────────────────────────────────────────────────

def _draw_body(draw: ImageDraw.ImageDraw, inp: ThumbnailInput,
               accent: tuple, fonts_dir: Path) -> None:
    white     = (255, 255, 255)
    soft      = (205, 205, 205)
    fnt_xl    = _font(fonts_dir, "Pretendard-Black.otf",      130)
    fnt_hook1 = _font(fonts_dir, "Pretendard-ExtraBold.otf",   60)
    fnt_hook  = _font(fonts_dir, "Pretendard-Bold.otf",        54)

    title = _strip_emoji(inp.title)
    hook  = _strip_emoji(inp.hook)
    num   = _parse_number(hook)

    if inp.hook_pattern in ("number", "twist_preview") and num:
        _body_number(draw, title, hook, num, fnt_xl, fnt_hook, white, soft, accent, fonts_dir)
    elif inp.hook_pattern == "comparison":
        _body_comparison(draw, title, hook, fnt_xl, fnt_hook1, fnt_hook, white, soft, accent, fonts_dir)
    else:
        _body_default(draw, title, hook, fnt_hook1, fnt_hook, white, soft, accent, fonts_dir)


def _body_default(draw, title, hook, fnt_h1, fnt_h, white, soft, accent, fonts_dir):
    """제목 → 여백 → 후크 (선 없음, 여백이 구분)."""
    title_lines, fnt_t = _title_lines(draw, title, fonts_dir)
    kw = _pick_key_word(title)

    y = 195
    for line in title_lines:
        _ltext_mixed(draw, line, X_LEFT, y, fnt_t, white, accent, kw)
        y += draw.textbbox((0, 0), line, font=fnt_t)[3] + 16

    # 여백이 구분선 역할
    y += 90

    hook_lines = _wrap_ko(hook.rstrip("!"), max_ko=17)[:3]
    for i, line in enumerate(hook_lines):
        if i == 0:
            _ltext(draw, line, X_LEFT, y, fnt_h1, accent)
            y += draw.textbbox((0, 0), line, font=fnt_h1)[3] + 18
        else:
            _ltext(draw, line, X_LEFT, y, fnt_h, soft)
            y += draw.textbbox((0, 0), line, font=fnt_h)[3] + 14


def _body_number(draw, title, hook, num, fnt_xl, fnt_h, white, soft, accent, fonts_dir):
    """제목 → 여백 → 빅넘버(액센트) → 보조 텍스트."""
    rest_words = [w for w in hook.split() if w != num and w not in title.split()]
    rest = " ".join(rest_words).rstrip("!").strip() or "비법 공개"

    title_lines, fnt_t = _title_lines(draw, title, fonts_dir)
    kw = _pick_key_word(title)
    if kw and re.search(r"\d", kw):
        kw = None   # 숫자는 빅넘버에서 이미 강조

    y = 195
    for line in title_lines:
        _ltext_mixed(draw, line, X_LEFT, y, fnt_t, white, accent, kw)
        y += draw.textbbox((0, 0), line, font=fnt_t)[3] + 16

    y += 70
    _ltext(draw, num, X_LEFT, y, fnt_xl, accent)
    y += draw.textbbox((0, 0), num, font=fnt_xl)[3] + 14
    _ltext(draw, rest, X_LEFT, y, fnt_h, white)


def _body_comparison(draw, title, hook, fnt_xl, fnt_h1, fnt_h, white, soft, accent, fonts_dir):
    """A → 여백 → VS → 여백 → B (선 없음)."""
    m = re.search(r"(.+?)\s*vs\s*(.+?)(?:\s*[,?!]|$)", hook, re.IGNORECASE)
    if not m:
        _body_default(draw, title, hook, fnt_h1, fnt_h, white, soft, accent, fonts_dir)
        return
    a, b = m.group(1).strip(), m.group(2).strip()
    fnt_a = _fit_font(draw, a, fonts_dir, "Pretendard-ExtraBold.otf", 88, 44, MAX_W)
    fnt_b = _fit_font(draw, b, fonts_dir, "Pretendard-ExtraBold.otf", 88, 44, MAX_W)
    _ltext_mixed(draw, a, X_LEFT, 195, fnt_a, white, accent, _pick_key_word(a))
    _ltext(draw, "VS", X_LEFT, 340, fnt_xl, accent)
    _ltext_mixed(draw, b, X_LEFT, 510, fnt_b, white, accent, _pick_key_word(b))


# ── 푸터 ──────────────────────────────────────────────────────────

def _draw_footer(draw: ImageDraw.ImageDraw, inp: ThumbnailInput,
                 fonts_dir: Path) -> None:
    fnt = _font(fonts_dir, "Pretendard-Regular.otf", 30)
    draw.text((X_LEFT, H - 78), inp.channel_name, font=fnt, fill=(190, 190, 190))
    tag = "#중학생공부법  #공부팁"
    tw = draw.textlength(tag, font=fnt)
    draw.text((W - tw - X_LEFT, H - 78), tag, font=fnt, fill=(130, 130, 130))


# ── 텍스트 피팅 ───────────────────────────────────────────────────

def _title_lines(draw, title, fonts_dir):
    fn = "Pretendard-ExtraBold.otf"
    for size in range(96, 51, -4):
        fnt = _font(fonts_dir, fn, size)
        if draw.textbbox((0, 0), title, font=fnt)[2] <= MAX_W:
            return [title], fnt
    parts = _split_natural(title)
    for size in range(80, 43, -4):
        fnt = _font(fonts_dir, fn, size)
        if all(draw.textbbox((0, 0), p, font=fnt)[2] <= MAX_W for p in parts):
            return parts, fnt
    return parts, _font(fonts_dir, fn, 44)


def _split_natural(title: str) -> list[str]:
    for sep in ("—", ",", "-", "·"):
        if sep in title:
            idx = title.index(sep)
            a, b = title[:idx + 1].strip(), title[idx + 1:].strip()
            if a and b:
                return [a, b]
    words = title.split()
    mid = max(1, len(words) // 2)
    return [" ".join(words[:mid]), " ".join(words[mid:])]


def _fit_font(draw, text, fonts_dir, font_name, max_size, min_size, max_w):
    for size in range(max_size, min_size - 1, -2):
        fnt = _font(fonts_dir, font_name, size)
        if draw.textbbox((0, 0), text, font=fnt)[2] <= max_w:
            return fnt
    return _font(fonts_dir, font_name, min_size)


def _wrap_ko(text: str, max_ko: int) -> list[str]:
    words = text.split()
    lines, cur, cur_len = [], [], 0
    for w in words:
        wl = len(w)
        if cur and cur_len + wl > max_ko:
            lines.append(" ".join(cur))
            cur, cur_len = [w], wl
        else:
            cur.append(w)
            cur_len += wl
    if cur:
        lines.append(" ".join(cur))
    return lines


# ── 키워드 선택 ───────────────────────────────────────────────────

def _pick_key_word(title: str) -> str | None:
    words = title.split()
    for w in words:
        if re.search(r"\d", w):
            return w
    for tier in (_KW_T1, _KW_T2, _KW_T3):
        for w in words:
            clean = re.sub(r"[^가-힣a-zA-Z]", "", w)
            if clean in tier or any(kw in clean for kw in tier):
                return w
    return None


# ── 텍스트 렌더러 ────────────────────────────────────────────────

def _ltext(draw, text: str, x: int, y: int,
           font: ImageFont.FreeTypeFont, fill: tuple) -> None:
    """왼쪽 정렬 + 4방향 얇은 아웃라인."""
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=fill)


def _ltext_mixed(draw, text: str, x: int, y: int,
                 font: ImageFont.FreeTypeFont,
                 default_fill: tuple, accent: tuple,
                 key_word: str | None = None) -> None:
    """단 1개의 key_word만 액센트 색, 나머지는 default_fill."""
    kw_c = re.sub(r"[^가-힣a-zA-Z\d]", "", key_word) if key_word else ""
    cur_x = x
    for word in text.split():
        wc = re.sub(r"[^가-힣a-zA-Z\d]", "", word)
        fill = accent if (kw_c and wc == kw_c) else default_fill
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            draw.text((cur_x + dx, y + dy), word, font=font, fill=(0, 0, 0))
        draw.text((cur_x, y), word, font=font, fill=fill)
        cur_x += int(draw.textlength(word + " ", font=font))


# ── 유틸 ─────────────────────────────────────────────────────────

def _parse_number(text: str) -> str | None:
    m = re.search(r"\d+[+]?[배주분초점개회번할%]+", text)
    return m.group() if m else None


def _strip_emoji(text: str) -> str:
    return re.sub(
        r"[⌀-⯿⸀-⹿︀-️\U0001F000-\U0001FFFF\U00002702-\U000027B0]+",
        "", text,
    ).strip()


def _rgb(hex_color: str) -> tuple[int, int, int]:
    c = hex_color.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _font(fonts_dir: Path, name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(fonts_dir / name), size)
