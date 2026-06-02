"""퀄리티 데모 영상 생성 v3 (독립 실행, 파이프라인 수정 없음).

적용 효과:
  1. Ken Burns — BG 110% 확대 + 천천히 패닝 (3분할 레이아웃 유지)
  2. 색보정 LUT — 따뜻한 시네마틱 톤 (curves 필터)
  3. Calm BGM — 학습 분위기 차분한 배경음 (-22dB)
  4. 한국어 숫자 수사 정규화 (1시간→한 시간) 후 TTS 재생성
  5. 자막 정밀 싱크 — silencedetect 실제 발화 경계 감지 (window ±2s)
  6. 강조 전 시각적 공백 — 첫째/둘째/셋째 직전 0.38초, 결론 직전 0.65초
  7. 첫째/둘째/셋째 Dialogue 분리 + 줄바꿈

실행:
    python -m scripts.make_demo_quality
"""
from __future__ import annotations

import asyncio
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from src.db import open_database
from src.renderer.composer import extract_pastel_bar_color

DEMO_DIR = PROJECT_ROOT / "output" / "demo"
DEMO_DIR.mkdir(parents=True, exist_ok=True)

# 3분할 레이아웃 상수 (composer.py 동일)
_TOP_H   = 480
_VIDEO_H = 1160
_BOT_H   = 280
_W       = 1080
_H       = 1920
_BOT_Y   = _TOP_H + _VIDEO_H  # 1640


# ── 자막 유틸 ─────────────────────────────────────────────────────────────────

def _ass_ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _parse_ts(ts: str) -> float:
    h, m, s = ts.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _rewrap(text: str, cpl: int = 19) -> str:
    """긴 텍스트에 \\N 삽입 (공백 기준, 줄당 최대 cpl 글자)."""
    words = text.replace("\\N", " ").split(" ")
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip() if cur else w
        if len(cand) <= cpl:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return "\\N".join(lines)


# ── 한국어 수사 정규화 ────────────────────────────────────────────────────────

_KO_NATIVE = {
    "1": "한", "2": "두", "3": "세", "4": "네", "5": "다섯",
    "6": "여섯", "7": "일곱", "8": "여덟", "9": "아홉",
}

def _normalize_ko_numbers(text: str) -> str:
    """숫자+단위(시간·개·번·가지) 패턴을 한국어 고유어 수사로 치환.

    예: 1시간→한 시간, 3개→세 개  (분·점은 Sino-Korean 유지)
    """
    def _sub(m: re.Match) -> str:
        return _KO_NATIVE.get(m.group(1), m.group(1)) + " " + m.group(2)

    # 고유어 수사를 쓰는 단위: 시간, 개, 번, 가지
    text = re.sub(r"([1-9])(시간|개|번|가지)", _sub, text)
    return text


def _regen_demo_audio(script: dict) -> Path:
    """한국어 숫자 정규화 후 Edge TTS(SunHiNeural)로 데모 오디오 재생성."""
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        raise RuntimeError("edge-tts 미설치: pip install edge-tts")

    hook  = (script.get("hook")  or "").strip()
    body  = (script.get("body")  or "").strip()
    twist = (script.get("twist") or "").strip()
    full  = _normalize_ko_numbers(" ".join([hook, body, twist]))

    # 수정된 텍스트 미리보기
    changed = [(m.group(0), _normalize_ko_numbers(m.group(0)))
               for m in re.finditer(r"[1-9](시간|개|번|가지)", hook + body + twist)]
    if changed:
        print(f"  숫자 수사 치환: {changed}")

    mp3_raw = DEMO_DIR / "audio_demo_raw.mp3"
    mp3_out = DEMO_DIR / "audio_demo.mp3"

    async def _gen() -> None:
        communicate = edge_tts.Communicate(full, "ko-KR-SunHiNeural", rate="+8%", pitch="+18Hz")
        await communicate.save(str(mp3_raw))

    asyncio.run(_gen())

    # loudnorm — silencedetect 신뢰도 향상
    subprocess.run([
        "ffmpeg", "-y", "-i", str(mp3_raw),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        str(mp3_out),
    ], capture_output=True, timeout=60, check=False)

    return mp3_out if (mp3_out.exists() and mp3_out.stat().st_size > 0) else mp3_raw


def _probe_duration(audio: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
        capture_output=True, timeout=10, check=False,
    )
    try:
        return float(r.stdout.decode().strip())
    except Exception:
        return 0.0


# ── 자막 후처리 ───────────────────────────────────────────────────────────────

def _fix_subtitle(src: Path, dst: Path) -> Path:
    """첫째/둘째/셋째가 한 Dialogue에 이어붙은 경우 분리 + 긴 줄 \\N."""
    SPLIT_RE = re.compile(r"\.\s+(첫째|둘째|셋째),")
    out = []
    for ln in src.read_text("utf-8").splitlines():
        if not ln.startswith("Dialogue:"):
            out.append(ln)
            continue
        fields = ln.split(",", 9)
        if len(fields) < 10:
            out.append(ln)
            continue

        text = fields[9]
        om = re.match(r"^(\{[^}]*\})", text)
        ovr, body = (om.group(1), text[om.end():]) if om else ("", text)

        sm = SPLIT_RE.search(body)
        if not sm:
            out.append(ln)
            continue

        before = body[: sm.start() + 1]   # "...말."
        after  = body[sm.start() + 2:]    # "셋째, ..."

        t0  = _parse_ts(fields[1])
        t1  = _parse_ts(fields[2])
        p0  = len(re.sub(r"\\N", "", before))
        p1  = len(re.sub(r"\\N", "", after))
        mid = t0 + (t1 - t0) * p0 / (p0 + p1)

        hd = fields[:9]

        def _row(s: float, e: float, body_text: str,
                 _hd: list = hd, _ovr: str = ovr) -> str:
            r = _hd[:]
            r[1] = _ass_ts(s)
            r[2] = _ass_ts(e)
            return ",".join(r) + "," + _ovr + body_text

        out.append(_row(t0, mid, before))
        out.append(_row(mid, t1, _rewrap(after)))

    dst.write_text("\n".join(out), "utf-8")
    return dst


def _detect_silences(audio: Path, noise_db: float = -35, min_dur: float = 0.15) -> list[tuple[float, float]]:
    """FFmpeg silencedetect로 무음 구간(start, end) 목록 반환."""
    r = subprocess.run(
        ["ffmpeg", "-i", str(audio),
         "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    silences, s = [], None
    for line in r.stderr.splitlines():
        ms = re.search(r"silence_start:\s*([\d.]+)", line)
        if ms:
            s = float(ms.group(1))
        me = re.search(r"silence_end:\s*([\d.]+)", line)
        if me and s is not None:
            silences.append((s, float(me.group(1))))
            s = None
    return silences


def _nearest(val: float, pool: list[float], window: float) -> float | None:
    """pool에서 val에 가장 가까운 값 반환 (window 초과 시 None)."""
    best, bd = None, window + 1
    for p in pool:
        d = abs(p - val)
        if d < bd:
            bd, best = d, p
    return best if bd <= window else None


def _enhance_subtitle(
    src: Path,
    dst: Path,
    silences: list[tuple[float, float]],
    emphasis_pause: float = 0.38,
    conclusion_pause: float = 0.65,
) -> Path:
    """
    1. 각 Dialogue 타이밍을 silencedetect 결과로 스냅 (window ±2.0s)
    2. 강조 구절(첫째/둘째/셋째) 직전 emphasis_pause 초 시각 공백
    3. 결론(이대로만) 직전 conclusion_pause 초 + 더 긴 공백
    """
    EMPH_RE = re.compile(r"^(첫째|둘째|셋째|이대로만)")

    s_ends   = [se for _, se in silences]   # 발화 시작점 (silence 끝)
    s_starts = [ss for ss, _ in silences]   # 발화 종료점 (silence 시작)

    raw_lines = src.read_text("utf-8").splitlines()
    header, dlgs = [], []
    in_events = False

    for ln in raw_lines:
        if ln.strip() == "[Events]":
            in_events = True
            header.append(ln)
            continue
        if not in_events or not ln.startswith("Dialogue:"):
            header.append(ln)
            continue

        f = ln.split(",", 9)
        if len(f) < 10:
            header.append(ln)
            continue

        layer = f[0].split(":")[-1].strip()
        t0, t1 = _parse_ts(f[1]), _parse_ts(f[2])
        om = re.match(r"^(\{[^}]*\})", f[9])
        ovr = om.group(1) if om else ""
        body = f[9][len(ovr):]
        dlgs.append({"layer": layer, "t0": t0, "t1": t1,
                     "hd": f[:9], "ovr": ovr, "body": body})

    # ① 타이밍 스냅 — window ±2.0s (Title 레이어 제외)
    for dlg in dlgs:
        if dlg["layer"] == "1":
            continue
        if s_ends:
            snapped = _nearest(dlg["t0"], s_ends, window=2.0)
            if snapped is not None:
                dlg["t0"] = snapped
        if s_starts:
            # t1 스냅: t0 이후에 있는 s_start 중 가장 가까운 것
            candidates = [(abs(ss - dlg["t1"]), ss)
                          for ss in s_starts if ss > dlg["t0"] + 0.3]
            if candidates:
                dlg["t1"] = max(min(candidates)[1], dlg["t0"] + 0.4)

    # ② 강조 구절 직전 시각 공백
    #    - 자연 pause ≥ target: 손대지 않음
    #    - 자연 pause < target: 이전 항목 t1을 앞당겨 gap 확보
    non_title = [d for d in dlgs if d["layer"] != "1"]
    for i, dlg in enumerate(non_title):
        if not EMPH_RE.match(dlg["body"]) or i == 0:
            continue
        prev  = non_title[i - 1]
        pause = conclusion_pause if dlg["body"].startswith("이대로만") else emphasis_pause
        natural_gap = dlg["t0"] - prev["t1"]
        if natural_gap < pause:
            new_t1 = dlg["t0"] - pause
            if new_t1 > prev["t0"] + 0.3:
                prev["t1"] = new_t1

    # ③ ASS 출력
    out = header[:]
    for dlg in dlgs:
        row = dlg["hd"][:]
        row[1] = _ass_ts(dlg["t0"])
        row[2] = _ass_ts(dlg["t1"])
        out.append(",".join(row) + "," + dlg["ovr"] + dlg["body"])

    dst.write_text("\n".join(out), "utf-8")
    return dst


# ── 렌더 ─────────────────────────────────────────────────────────────────────

def _render(
    bg_video: Path,
    audio: Path,
    subtitle_ass: Path,
    bgm: Path,
    logo: Path | None,
    bar_rgb: tuple[int, int, int],
    duration: float,
    fonts_dir: Path,
    out: Path,
    bgm_db: float = -22.0,
) -> Path:
    sub_arg   = str(subtitle_ass).replace("\\", "/").replace(":", r"\:")
    fonts_arg = str(fonts_dir).replace("\\", "/").replace(":", r"\:")
    dur       = duration

    r, g, b = bar_rgb
    bar_hex  = f"0x{r:02x}{g:02x}{b:02x}"

    # Ken Burns: BG를 110% 확대 후 가로 패닝
    pan_px  = 108
    cx_expr = f"({pan_px}*t/{dur:.1f})"
    cy_expr = f"(1276-{_VIDEO_H})/2"

    warm_lut = (
        "curves="
        "r='0/0 0.25/0.27 0.75/0.80 1/1.0':"
        "g='0/0 0.25/0.24 0.75/0.73 1/0.97':"
        "b='0/0.03 0.25/0.21 0.75/0.66 1/0.87'"
    )

    # ① BG → Ken Burns → 색보정
    bg_chain = (
        f"[0:v]setpts=PTS,"
        f"scale='if(gt(a\\,{_W}/{_VIDEO_H})\\,-2\\,{_W})':'if(gt(a\\,{_W}/{_VIDEO_H})\\,{_VIDEO_H}\\,-2)',"
        f"crop={_W}:{_VIDEO_H}:(iw-{_W})/2:(ih-{_VIDEO_H})/2,"
        f"scale=1188:1276:flags=lanczos,"
        f"crop={_W}:{_VIDEO_H}:x='{cx_expr}':y='{cy_expr}',"
        f"eq=contrast=1.12:saturation=1.20:brightness=-0.01,"
        f"{warm_lut},"
        f"vignette=angle=PI/5"
        f"[bg_crop]"
    )

    # ② 파스텔 캔버스 + BG 합성
    canvas_chain = (
        f"color=c={bar_hex}:s={_W}x{_H}:r=30[canvas];"
        f"[canvas][bg_crop]overlay=x=0:y={_TOP_H}[bg_full]"
    )

    # ③ 로고 (있으면) — 입력 순서: 0=BG, 1=TTS, [2=logo,] 2or3=BGM
    has_logo      = logo is not None and logo.exists()
    logo_idx      = 2 if has_logo else None
    bgm_input_idx = 3 if has_logo else 2

    if has_logo:
        logo_sz = 120
        logo_r  = logo_sz // 2
        logo_x  = (_W - logo_sz) // 2
        logo_y  = _BOT_Y + (_BOT_H - logo_sz) // 2
        circle  = f"255*lt((X-{logo_r})*(X-{logo_r})+(Y-{logo_r})*(Y-{logo_r}),{logo_r**2})"
        logo_chain = (
            f"[{logo_idx}:v]scale={logo_sz}:{logo_sz},format=rgba,"
            f"geq=r='r(X\\,Y)':g='g(X\\,Y)':b='b(X\\,Y)':a='{circle}'[logo];"
            f"[bg_full][logo]overlay=x={logo_x}:y={logo_y}[bg_logo]"
        )
        pre_sub = "bg_logo"
    else:
        logo_chain = ""
        pre_sub    = "bg_full"

    # ④ 자막
    sub_chain = f"[{pre_sub}]subtitles='{sub_arg}':fontsdir='{fonts_arg}'[v]"

    # ⑤ 오디오: TTS + Calm BGM
    audio_chain = (
        f"[1:a]volume=1.0[tts];"
        f"[{bgm_input_idx}:a]volume={bgm_db}dB[bgm_mix];"
        f"[tts][bgm_mix]amix=inputs=2:duration=first:dropout_transition=2[a]"
    )

    parts = [bg_chain, canvas_chain]
    if logo_chain:
        parts.append(logo_chain)
    parts += [sub_chain, audio_chain]
    filter_complex = ";".join(parts)

    cmd = [
        "ffmpeg", "-hide_banner", "-y",
        "-stream_loop", "-1", "-i", str(bg_video),   # 0: BG
        "-i", str(audio),                             # 1: TTS
    ]
    if has_logo:
        cmd += ["-loop", "1", "-i", str(logo)]        # 2: logo
    cmd += [
        "-stream_loop", "-1", "-i", str(bgm),         # 2 or 3: BGM
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "256k",
        "-t", str(min(duration + 0.5, 30)),
        str(out),
    ]

    print("  FFmpeg 렌더 시작...")
    result = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    _SIGTERM = 3221225786
    output_ok = out.exists() and out.stat().st_size > 0
    if result.returncode != 0 and not (result.returncode == _SIGTERM and output_ok):
        print(result.stderr.decode("utf-8", "replace")[-2000:])
        raise RuntimeError(f"FFmpeg exit={result.returncode}")
    return out


# ── Main ─────────────────────────────────────────────────────────────────────

def _select_calm_bgm(fallback: Path) -> Path:
    calm_dir = PROJECT_ROOT / "assets" / "bgm" / "calm"
    candidates = sorted(calm_dir.glob("*.mp3")) if calm_dir.exists() else []
    return candidates[0] if candidates else fallback


def main() -> None:
    db  = open_database(PROJECT_ROOT / "data" / "shorts.db")
    row = db.fetchone("""
        SELECT v.id, v.audio_path, v.subtitle_path, v.bg_video_path, v.bgm_path, v.duration_sec,
               s.title, s.hook, s.body, s.twist
        FROM videos v JOIN scripts s ON s.id = v.script_id
        WHERE v.audio_path IS NOT NULL AND v.bg_video_path IS NOT NULL
              AND v.subtitle_path IS NOT NULL
        ORDER BY v.id DESC LIMIT 1
    """)
    if not row:
        print("[ERROR] 영상 데이터 없음")
        return

    vid      = row["id"]
    subtitle = Path(row["subtitle_path"])
    bg_video = Path(row["bg_video_path"])
    fonts    = PROJECT_ROOT / "assets" / "fonts"
    logo     = PROJECT_ROOT / "assets" / "channel_logo.jpg"
    bgm      = _select_calm_bgm(Path(row["bgm_path"]))

    print(f"\n데모 생성: v{vid}  [{row['title']}]")
    print(f"  BG : {bg_video.name}")
    print(f"  BGM: {bgm.name}")

    # ── [1/5] 파스텔 바 색상 ─────────────────────────────────────────────────
    print("\n[1/5] 파스텔 바 색상 추출...")
    bar_rgb = extract_pastel_bar_color(bg_video)
    print(f"  bar_rgb: {bar_rgb}")

    # ── [2/5] 한국어 수사 정규화 + TTS 재생성 ────────────────────────────────
    print("\n[2/5] 한국어 수사 정규화 → TTS 재생성 (SunHiNeural)...")
    demo_audio = _regen_demo_audio(dict(row))
    duration   = _probe_duration(demo_audio)
    print(f"  출력: {demo_audio.name}  ({duration:.1f}초)")

    # ── [3/5] silencedetect 자막 싱크 ────────────────────────────────────────
    print("\n[3/5] TTS 무음 구간 분석...")
    silences = _detect_silences(demo_audio)
    print(f"  감지 {len(silences)}개: {[(round(a,2), round(b,2)) for a,b in silences]}")

    # ── [4/5] 자막 후처리 ────────────────────────────────────────────────────
    print("\n[4/5] 자막 후처리 (분리 → 싱크 스냅 → 강조 공백)...")
    split_sub    = _fix_subtitle(subtitle, DEMO_DIR / "subtitle_split.ass")
    enhanced_sub = _enhance_subtitle(
        split_sub, DEMO_DIR / "subtitle_enhanced.ass",
        silences,
        emphasis_pause=0.38,
        conclusion_pause=0.65,
    )
    print(f"  완료: {enhanced_sub.name}")

    # ── [5/5] 렌더 ───────────────────────────────────────────────────────────
    print("\n[5/5] 영상 합성 (Ken Burns + Warm LUT + Calm BGM + 3분할)...")
    out = DEMO_DIR / f"demo_quality_v{vid}.mp4"
    _render(bg_video, demo_audio, enhanced_sub, bgm,
            logo if logo.exists() else None,
            bar_rgb, duration, fonts, out)

    size_mb = round(out.stat().st_size / 1024 / 1024, 1)
    print(f"\n완료: {out.name}  ({size_mb} MB)")


if __name__ == "__main__":
    main()
