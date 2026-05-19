"""자막 생성 (FR-4.1).

keyword_mode=True (기본):
  - 나레이션 전문 대신 hook/body/twist에서 핵심 구절만 추출
  - Whisper 불필요 → 빠름
  - 4~5개 임팩트 텍스트를 시간 비례 배치

keyword_mode=False:
  - faster-whisper 음성 인식으로 전문 자막 생성 (레거시)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SubtitleSegment:
    start: float
    end: float
    text: str


@dataclass
class SubtitleResult:
    srt_path: Path
    segments: list[SubtitleSegment] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 스타일드 ASS 자막 (keyword_mode 기본)
# 가이드: hook=Pretendard ExtraBold 92px / body=Pretendard Bold 70px /
#         twist=Pretendard Black 88px 노랑 / 페이드 인/아웃
# ---------------------------------------------------------------------------

_ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 1
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Pretendard,76,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,3,8,80,80,120,1
Style: Title,Pretendard,80,&H00FFFFFF,&H000000FF,&H001E78FF,&H00000000,-1,0,0,0,100,100,2,0,1,18,0,8,80,80,300,1


[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# ─── 타이틀 (상단 파스텔 바, \an2 Y=450 기준) ───
# 96px 웜 골드 | 위→아래 12px 플로트인 + 페이드 | 아웃라인 5px
_TITLE_ANIM = (
    r"{\an2\move(540,438,540,450,0,450)"
    r"\fad(300,200)"
    r"\fnGowun Dodum\fs96\fsp1"
    r"\c&H0066E0FF&\3c&H00000000&\bord5\shad4\blur0}"
)

# ─── 영상 윈도우 자막 (480px~1640px, 중앙 Y=1060) ─ Gowun Dodum ───
# hook : 슬라이드업 20px (1080→1060) + 페이드인 / 92px 흰 글자
# body : 슬라이드업 55px (1115→1060) + 페이드인 / 70px 흰 글자
# twist: 바운스 탄성 팝인 (0→108→97→101→100%) / 88px 웜 골드
_TAG_HOOK  = r"{\an5\move(540,1080,540,1060,0,350)\fnGowun Dodum\fs92\c&H00FFFFFF&\3c&H00000000&\bord5\shad2\fad(300,200)}"
_TAG_BODY  = r"{\an5\move(540,1115,540,1060,0,320)\fnGowun Dodum\fs70\c&H00FFFFFF&\3c&H00000000&\bord4\shad2\fad(220,200)}"
_TAG_TWIST = r"{\an5\pos(540,1060)\fnGowun Dodum\fs88\c&H0066E0FF&\3c&H00000000&\bord5\shad2\fscx0\fscy0\t(0,180,\fscx108\fscy108)\t(180,290,\fscx97\fscy97)\t(290,390,\fscx101\fscy101)\t(390,430,\fscx100\fscy100)\fad(0,300)}"

# 강조 태그 (웜 골드 &H0066E0FF& = RGB 255·224·102, video_15 스타일)
_EMPH_HOOK  = (r"{\c&H0066E0FF&\fs102\blur0}", r"{\c&H00FFFFFF&\fs92\blur0}")
_EMPH_BODY  = (r"{\c&H0066E0FF&\fs80\blur0}",  r"{\c&H00FFFFFF&\fs70\blur0}")
_EMPH_TWIST = (r"{\c&H00FFFFFF&\fs98\blur0}",  r"{\c&H0066E0FF&\fs88\blur0}")

# Gowun Dodum 880px 실질 안전폭 기준 최대 한글 수/줄 (fontSize × 0.85 ≈ charWidth, 이모지 포함 여유)
_MAX_KO_HOOK  = 10   # 92px → 880/(92×0.85) ≈ 11.2
_MAX_KO_BODY  = 12   # 70px → 880/(70×0.85) ≈ 14.8
_MAX_KO_TWIST = 10   # 88px → 880/(88×0.85) ≈ 11.8


import re as _re

_CJK_STRIP = _re.compile(
    r"[぀-ゟ"   # 히라가나
    r"゠-ヿ"    # 카타카나
    r"一-鿿"    # CJK 통합 한자
    r"㐀-䶿"    # CJK 확장 A
    r"豈-﫿]"   # CJK 호환 한자
)


def _strip_cjk(text: str) -> str:
    """한자·히라가나·카타카나 제거 — 한글·영어·이모지·숫자·구두점 보존."""
    return _CJK_STRIP.sub("", text).strip()


def _ko_len(text: str) -> int:
    """한글 음절(가-힣) 수만 반환."""
    return sum(1 for c in text if "가" <= c <= "힣")


# 한글 조사 음절 — 단어 끝에 오면 자연스러운 분리 우선 지점
# '서'(에서), '로'(으로), '을/를', '은/는', '이/가', '와/과', '도', '의', '등', '만'
_KO_PARTICLES = frozenset("로을를은는가와과도의등")  # 이/서는 어간에도 흔해 제외


def _word_ko_len(word: str) -> int:
    """단어 내 한글 음절 수."""
    return sum(1 for c in word if "가" <= c <= "힣")


def _wrap_text_lines(text: str, max_ko_per_line: int, max_lines: int = 3) -> str:
    r"""한국어 단어 단위 자연스러운 줄바꿈 (최대 max_lines줄).

    분리 우선순위:
    1. 문장 부호(다/요/!?.) 뒤 → 자연 문장 분리
    2. 단어 그리디 묶기: max_ko_per_line 이내 최대한 채우되
       현재 줄의 마지막 단어가 조사 끝이면 거기서 분리 우선
    3. 공백 없으면 강제 mid 분할
    """
    import re
    text = text.strip()
    if not text or _ko_len(text) <= max_ko_per_line or max_lines <= 1:
        return text

    # 1순위: 문장 부호 뒤 자연 분리
    for m in re.finditer(r"(?<=[다요!?.])\s+", text):
        line1 = text[: m.start()].strip()
        rest  = text[m.end():].strip()
        if line1 and rest and _ko_len(line1) <= max_ko_per_line:
            return line1 + r"\N" + _wrap_text_lines(rest, max_ko_per_line, max_lines - 1)

    # 2순위: 단어 그리디 묶기
    words = text.split()
    if len(words) <= 1:
        mid = len(text) // 2
        return text[:mid] + r"\N" + text[mid:]

    lines: list[str] = []
    current: list[str] = []
    current_ko = 0

    for idx, word in enumerate(words):
        wko = _word_ko_len(word)

        if current and current_ko + wko > max_ko_per_line:
            lines.append(" ".join(current))
            current = [word]
            current_ko = wko

            if len(lines) >= max_lines - 1:
                remaining = " ".join(words[idx + 1:])
                if remaining:
                    current.append(remaining)
                break
        else:
            current.append(word)
            current_ko += wko

    if current:
        lines.append(" ".join(current))

    return r"\N".join(lines) if lines else text


def _apply_word_emphasis(text: str, words: list[str], emph_open: str, emph_close: str) -> str:
    """지정 단어를 ASS 인라인 태그로 강조. 단어당 첫 번째 등장만 변환."""
    for word in words:
        if not word:
            continue
        idx = text.find(word)
        if idx == -1:
            continue
        text = text[:idx] + emph_open + word + emph_close + text[idx + len(word):]
    return text


def _wrap_line(text: str, max_ko: int) -> str:
    r"""레거시 SRT용: 한글 글자 수가 max_ko 초과 시 중간 공백에서 \N 줄바꿈."""
    if _ko_len(text) <= max_ko:
        return text
    mid = len(text) // 2
    for offset in range(0, min(7, mid)):
        for pos in (mid - offset, mid + offset):
            if 0 < pos < len(text) and text[pos] == " ":
                return text[:pos] + r"\N" + text[pos + 1:]
    return text[:mid] + r"\N" + text[mid:]


def make_styled_subtitles(
    *,
    script: dict,
    audio_duration: float,
    out_ass: Path,
    style_overrides: dict | None = None,
) -> SubtitleResult:
    """hook/body/twist 전문을 스타일드 ASS 자막으로 생성.

    style_overrides 키: title_anim / tag_hook / tag_body / tag_twist /
                        emph_hook / emph_body / emph_twist (각각 (open, close) 튜플)
    """
    hook  = _strip_cjk((script.get("hook")  or "").strip())
    body  = _strip_cjk((script.get("body")  or "").strip())
    twist = _strip_cjk((script.get("twist") or "").strip())
    emph_words = [w.strip() for w in (script.get("emphasis_words") or []) if w.strip()]

    _so = style_overrides or {}
    ta = _so.get("title_anim", _TITLE_ANIM)
    th = _so.get("tag_hook",   _TAG_HOOK)
    tb = _so.get("tag_body",   _TAG_BODY)
    tt = _so.get("tag_twist",  _TAG_TWIST)
    eh_o, eh_c = _so.get("emph_hook",  _EMPH_HOOK)
    eb_o, eb_c = _so.get("emph_body",  _EMPH_BODY)
    et_o, et_c = _so.get("emph_twist", _EMPH_TWIST)

    entries: list[tuple[str, str, float]] = []

    kw_hook = _wrap_text_lines(hook, _MAX_KO_HOOK)
    if kw_hook:
        kw_hook = _apply_word_emphasis(kw_hook, emph_words, eh_o, eh_c)
        entries.append((th, kw_hook, len(hook)))

    if body:
        b1, b2 = _split_body_sentences(body)
        kw_b1 = _wrap_text_lines(b1, _MAX_KO_BODY)
        kw_b2 = _wrap_text_lines(b2, _MAX_KO_BODY)
        half_w = len(body) * 0.5
        if kw_b1:
            kw_b1 = _apply_word_emphasis(kw_b1, emph_words, eb_o, eb_c)
            entries.append((tb, kw_b1, half_w))
        if kw_b2:
            kw_b2 = _apply_word_emphasis(kw_b2, emph_words, eb_o, eb_c)
            entries.append((tb, kw_b2, half_w))

    kw_twist = _wrap_text_lines(twist, _MAX_KO_TWIST)
    if kw_twist:
        kw_twist = _apply_word_emphasis(kw_twist, emph_words, et_o, et_c)
        entries.append((tt, kw_twist, len(twist)))

    out_ass.parent.mkdir(parents=True, exist_ok=True)
    if not entries:
        out_ass.write_text("", encoding="utf-8")
        return SubtitleResult(srt_path=out_ass)

    total_weight = sum(w for _, _, w in entries) or 1.0
    segments: list[SubtitleSegment] = []
    t = 0.0
    for tag, text, weight in entries:
        duration = audio_duration * (weight / total_weight)
        end = min(t + duration - 0.15, audio_duration)
        segments.append(SubtitleSegment(
            start=round(t, 3),
            end=round(end, 3),
            text=tag + text,
        ))
        t += duration

    extra: list[str] = []
    full_end = _ass_time(audio_duration)
    title_text = _strip_cjk((script.get("title") or "").strip())
    if title_text:
        wrapped_title = _wrap_text_lines(title_text, max_ko_per_line=9)
        extra.append(f"Dialogue: 1,0:00:00.00,{full_end},Title,,0,0,0,,{ta}{wrapped_title}\n")

    _write_ass(out_ass, segments, extra_lines=extra)
    return SubtitleResult(srt_path=out_ass, segments=segments)


def _split_body_sentences(body: str) -> tuple[str, str]:
    """body를 문장 단위로 전반/후반 2그룹으로 분리."""
    import re
    sentences = re.split(r"(?<=[다요!?.])\s+", body.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 1:
        mid = len(body) // 2
        return body[:mid].strip(), body[mid:].strip()
    mid = max(1, len(sentences) // 2)
    return " ".join(sentences[:mid]), " ".join(sentences[mid:])


def _key_phrase(text: str, max_chars: int) -> str:
    """텍스트에서 핵심 구절 추출 (문장 부호 > 공백 > 글자 수 순 우선)."""
    text = text.strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text

    # 1. 문장 부호 (다/요/!/?/./,) 에서 끊기
    for i, ch in enumerate(text[: max_chars + 5]):
        if ch in "다요!?.," and i >= 4:
            return text[: i + 1].strip()

    # 2. 공백에서 끊기 (max_chars ~ max_chars-5 범위)
    for i in range(min(max_chars, len(text) - 1), max(3, max_chars - 5), -1):
        if text[i] == " ":
            return text[:i].strip()

    return text[:max_chars].strip()


# ---------------------------------------------------------------------------
# 기존 SRT 자막 (keyword_mode=False Whisper 또는 레거시 호환)
# ---------------------------------------------------------------------------

def make_keyword_subtitles(
    *,
    script: dict,
    audio_duration: float,
    out_srt: Path,
    max_chars: int = 10,
) -> SubtitleResult:
    """레거시 SRT 방식 (Whisper 폴백용)."""
    hook  = (script.get("hook")  or "").strip()
    body  = (script.get("body")  or "").strip()
    twist = (script.get("twist") or "").strip()

    entries: list[tuple[str, float]] = []

    kw_hook = _key_phrase(hook, max_chars + 8)
    if kw_hook:
        entries.append((kw_hook, len(hook)))

    if body:
        b1, b2 = _split_body_sentences(body)
        kw_b1 = _key_phrase(b1, max_chars + 4)
        kw_b2 = _key_phrase(b2, max_chars + 4)
        half_w = len(body) * 0.5
        if kw_b1:
            entries.append((kw_b1, half_w))
        if kw_b2:
            entries.append((kw_b2, half_w))

    kw_twist = _key_phrase(twist, max_chars + 10)
    if kw_twist:
        entries.append((kw_twist, len(twist)))

    if not entries:
        out_srt.parent.mkdir(parents=True, exist_ok=True)
        out_srt.write_text("", encoding="utf-8")
        return SubtitleResult(srt_path=out_srt)

    total_weight = sum(w for _, w in entries) or 1.0
    segments: list[SubtitleSegment] = []
    t = 0.0
    for text, weight in entries:
        duration = audio_duration * (weight / total_weight)
        end = min(t + duration - 0.15, audio_duration)
        segments.append(SubtitleSegment(start=round(t, 3), end=round(end, 3), text=text))
        t += duration

    out_srt.parent.mkdir(parents=True, exist_ok=True)
    _write_srt(out_srt, segments)
    return SubtitleResult(srt_path=out_srt, segments=segments)


# ---------------------------------------------------------------------------
# Whisper 전문 자막 (레거시, keyword_mode=False 시 사용)
# ---------------------------------------------------------------------------

class WhisperSubtitleEngine:
    def __init__(
        self,
        *,
        model_size: str = "small",
        compute_type: str = "int8",
        language: str = "ko",
        beam_size: int = 5,
        vad_filter: bool = True,
    ) -> None:
        self.model_size = model_size
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel
        self._model = WhisperModel(self.model_size, compute_type=self.compute_type)

    def transcribe(
        self,
        *,
        audio_path: Path,
        out_srt: Path,
        max_chars_per_line: int = 10,
        max_lines: int = 1,
    ) -> SubtitleResult:
        self._ensure_model()
        out_srt.parent.mkdir(parents=True, exist_ok=True)
        assert self._model is not None

        segments_iter, _info = self._model.transcribe(
            str(audio_path),
            language=self.language,
            beam_size=self.beam_size,
            vad_filter=self.vad_filter,
        )
        segments: list[SubtitleSegment] = []
        for seg in segments_iter:
            text = _wrap_korean(seg.text.strip(), max_chars_per_line, max_lines)
            segments.append(SubtitleSegment(start=float(seg.start), end=float(seg.end), text=text))

        _write_srt(out_srt, segments)
        return SubtitleResult(srt_path=out_srt, segments=segments)


# ---------------------------------------------------------------------------
# SRT 직렬화
# ---------------------------------------------------------------------------

def _format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _write_ass(path: Path, segments: list[SubtitleSegment], *, extra_lines: list[str] | None = None) -> None:
    lines = [_ASS_HEADER]
    for line in (extra_lines or []):
        lines.append(line)
    for seg in segments:
        start = _ass_time(seg.start)
        end   = _ass_time(seg.end)
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{seg.text}\n")
    path.write_text("".join(lines), encoding="utf-8")


def _write_srt(path: Path, segments: list[SubtitleSegment]) -> None:
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{_format_timestamp(seg.start)} --> {_format_timestamp(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _wrap_korean(text: str, max_chars: int, max_lines: int) -> str:
    """한국어 자막 줄바꿈 (Whisper 전문 자막용)."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    if " " in text:
        result = _split_by_spaces(text, max_chars, max_lines)
        if result:
            return result
    return _split_by_korean_boundary(text, max_chars, max_lines)


def _split_by_spaces(text: str, max_chars: int, max_lines: int) -> str:
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = (cur + " " + w).strip() if cur else w
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
                if len(lines) >= max_lines:
                    break
            cur = w[:max_chars]
    if cur and len(lines) < max_lines:
        lines.append(cur[:max_chars])
    return "\n".join(lines[:max_lines]) if lines else ""


_KO_BREAK_ENDINGS = frozenset("고서며니데죠요에서으로부터까지했는")


def _split_by_korean_boundary(text: str, max_chars: int, max_lines: int) -> str:
    if len(text) <= max_chars:
        return text
    mid = len(text) // 2
    best = mid
    for offset in range(0, min(4, mid)):
        for pos in (mid + offset, mid - offset):
            if 0 < pos < len(text) and text[pos - 1] in _KO_BREAK_ENDINGS:
                best = pos
                break
        else:
            continue
        break
    line1 = text[:best].strip()[:max_chars]
    line2 = text[best:].strip()[:max_chars]
    if max_lines == 1 or not line2:
        return line1
    return f"{line1}\n{line2}"
