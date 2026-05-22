"""자막 생성 단계 (FR-4).

keyword_mode=True (기본): 나레이션 전문 대신 핵심 키워드만 표시.
keyword_mode=False: faster-whisper 전문 자막 (레거시).

후처리 (keyword_mode=True):
  - 첫째/둘째/셋째 이어붙은 Dialogue 분리
  - silencedetect 실제 발화 경계로 타이밍 스냅 (±2s)
  - 강조 구절(첫째/둘째/셋째) 직전 0.38초, 결론(이대로만) 직전 0.65초 시각 공백
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def _resolve_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    winget = Path.home() / "AppData/Local/Microsoft/WinGet/Links/ffmpeg.exe"
    if winget.exists():
        return str(winget)
    return "ffmpeg"

from ..subtitle.whisper_engine import WhisperSubtitleEngine, make_styled_subtitles
from .context import PipelineContext, StageError, stage_timer

# ── 자막 싱크 후처리 헬퍼 ─────────────────────────────────────────────────────

_EMPH_RE  = re.compile(r"^(첫째|둘째|셋째|이대로만)")
_SPLIT_RE = re.compile(r"\.\s+(첫째|둘째|셋째),")


def _ass_ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _parse_ts(ts: str) -> float:
    h, m, s = ts.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def _rewrap(text: str, cpl: int = 19) -> str:
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


def _detect_silences(audio: Path) -> list[tuple[float, float]]:
    """FFmpeg silencedetect로 무음 구간 반환."""
    r = subprocess.run(
        [_resolve_ffmpeg(), "-i", str(audio),
         "-af", "silencedetect=noise=-35dB:d=0.15",
         "-f", "null", "-"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    silences: list[tuple[float, float]] = []
    s: float | None = None
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
    best, bd = None, window + 1.0
    for p in pool:
        d = abs(p - val)
        if d < bd:
            bd, best = d, p
    return best if bd <= window else None


def _fix_subtitle_splits(path: Path) -> None:
    """첫째/둘째/셋째가 한 Dialogue에 이어붙은 경우 in-place 분리."""
    lines = path.read_text("utf-8").splitlines()
    out: list[str] = []
    changed = False
    for ln in lines:
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
        sm = _SPLIT_RE.search(body)
        if not sm:
            out.append(ln)
            continue
        before = body[: sm.start() + 1]
        after  = body[sm.start() + 2:]
        t0 = _parse_ts(fields[1])
        t1 = _parse_ts(fields[2])
        p0 = len(re.sub(r"\\N", "", before))
        p1 = len(re.sub(r"\\N", "", after))
        mid = t0 + (t1 - t0) * p0 / (p0 + p1)
        hd = fields[:9]

        def _row(s: float, e: float, bt: str,
                 _hd: list = hd, _ovr: str = ovr) -> str:
            r = _hd[:]
            r[1] = _ass_ts(s)
            r[2] = _ass_ts(e)
            return ",".join(r) + "," + _ovr + bt

        out.append(_row(t0, mid, before))
        out.append(_row(mid, t1, _rewrap(after)))
        changed = True
    if changed:
        path.write_text("\n".join(out), "utf-8")


def _enhance_subtitle_timing(
    path: Path,
    silences: list[tuple[float, float]],
    emphasis_pause: float = 0.38,
    conclusion_pause: float = 0.65,
) -> None:
    """실제 발화 경계로 자막 타이밍 스냅 + 강조 전 시각 공백 (in-place).

    ① t0 스냅: 각 세그먼트 시작 → 가장 가까운 silence_end (발화 재개점)
    ② t0 순서 강제: 스냅 후 역전·겹침 방지 (이전 t0 + 0.5s 이상)
    ③ t1 스냅: 현재 t0+0.3s 이후이고 **다음 t0 이전**인 silence_start만 사용
    ④ 강조 구절 직전 시각 공백
    """
    s_ends   = [se for _, se in silences]
    s_starts = [ss for ss, _ in silences]

    raw = path.read_text("utf-8").splitlines()
    header: list[str] = []
    dlgs: list[dict] = []
    in_events = False

    for ln in raw:
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

    non_title = [d for d in dlgs if d["layer"] != "1"]

    # ① t0 스냅: silence_end(발화 재개) 중 ±2.0s 이내 가장 가까운 것으로
    for dlg in non_title:
        if s_ends:
            snapped = _nearest(dlg["t0"], s_ends, 2.0)
            if snapped is not None:
                dlg["t0"] = snapped

    # ② t0 순서 강제: 스냅 결과 역전되면 이전 t0 + 0.5s로 밀어내기
    for i in range(1, len(non_title)):
        min_t0 = non_title[i - 1]["t0"] + 0.5
        if non_title[i]["t0"] < min_t0:
            non_title[i]["t0"] = min_t0

    # ③ t1 스냅: silence_start 중 (t0+0.3s, next_t0) 범위 내 것만 사용
    #    다음 t0 이후 silence_start는 절대 사용 안 해 겹침을 원천 차단
    for i, dlg in enumerate(non_title):
        next_t0 = non_title[i + 1]["t0"] if i + 1 < len(non_title) else float("inf")
        cands = [(abs(ss - dlg["t1"]), ss)
                 for ss in s_starts
                 if dlg["t0"] + 0.3 < ss < next_t0 - 0.05]
        if cands:
            dlg["t1"] = min(cands)[1]
        else:
            # 범위 내 silence 없으면 다음 t0 - 0.15s 로 끊기
            cap = (next_t0 - 0.15) if next_t0 < float("inf") else dlg["t1"]
            dlg["t1"] = max(cap, dlg["t0"] + 0.4)

    # ④ 강조 구절 직전 시각 공백
    for i, dlg in enumerate(non_title):
        if not _EMPH_RE.match(dlg["body"]) or i == 0:
            continue
        prev  = non_title[i - 1]
        pause = conclusion_pause if dlg["body"].startswith("이대로만") else emphasis_pause
        if dlg["t0"] - prev["t1"] < pause:
            new_t1 = dlg["t0"] - pause
            if new_t1 > prev["t0"] + 0.3:
                prev["t1"] = new_t1

    # ⑤ 출력
    out = header[:]
    for dlg in dlgs:
        row = dlg["hd"][:]
        row[1] = _ass_ts(dlg["t0"])
        row[2] = _ass_ts(dlg["t1"])
        out.append(",".join(row) + "," + dlg["ovr"] + dlg["body"])
    path.write_text("\n".join(out), "utf-8")


def _apply_segment_timing(
    path: Path,
    segment_times: dict[str, dict[str, float]],
    silences: list[tuple[float, float]],
) -> None:
    """세그먼트 타이밍 사이드카가 있을 때 정확한 구간으로 ASS 타임라인 덮어쓰기.

    body는 내부 silence를 찾아 body_part1/body_part2로 분리.
    """
    raw = path.read_text("utf-8").splitlines()
    header: list[str] = []
    dlgs: list[dict] = []
    in_events = False

    for ln in raw:
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
        body_text = f[9][len(ovr):]
        dlgs.append({"layer": layer, "t0": t0, "t1": t1,
                     "hd": f[:9], "ovr": ovr, "body": body_text})

    non_title = [d for d in dlgs if d["layer"] != "1"]
    # segment order inferred from position: hook(1), body_pt1(1+), body_pt2(opt), twist(last)
    # count body segments = total non_title - (1 if hook in times) - (1 if twist in times)
    n_hook  = 1 if "hook"  in segment_times else 0
    n_twist = 1 if "twist" in segment_times else 0
    n_body  = max(0, len(non_title) - n_hook - n_twist)

    seg_names: list[str] = []
    if n_hook:  seg_names.append("hook")
    for _ in range(n_body): seg_names.append("body")
    if n_twist: seg_names.append("twist")

    body_idx = 0  # which body sub-segment we're on

    for i, dlg in enumerate(non_title):
        if i >= len(seg_names):
            break
        seg = seg_names[i]
        times = segment_times.get(seg, {})
        if not times:
            continue

        if seg == "body":
            body_start = times["start"]
            body_end   = times["end"]
            if n_body == 1:
                dlg["t0"] = body_start
                dlg["t1"] = body_end
            else:
                # Split body by finding a silence within body range
                body_sils = [(ss, se) for ss, se in silences
                             if body_start < ss < body_end - 0.1]
                if body_sils and n_body == 2:
                    mid_sil = min(body_sils, key=lambda s: abs(s[0] - (body_start + body_end) / 2))
                    if body_idx == 0:
                        dlg["t0"] = body_start
                        dlg["t1"] = round(mid_sil[0], 3)
                    else:
                        dlg["t0"] = round(mid_sil[1], 3)
                        dlg["t1"] = body_end
                else:
                    # fallback: split evenly
                    step = (body_end - body_start) / n_body
                    dlg["t0"] = round(body_start + body_idx * step, 3)
                    dlg["t1"] = round(body_start + (body_idx + 1) * step - 0.1, 3)
            body_idx += 1
        else:
            dlg["t0"] = round(times["start"], 3)
            dlg["t1"] = round(times["end"],   3)

    out = header[:]
    for dlg in dlgs:
        row = dlg["hd"][:]
        row[1] = _ass_ts(dlg["t0"])
        row[2] = _ass_ts(dlg["t1"])
        out.append(",".join(row) + "," + dlg["ovr"] + dlg["body"])
    path.write_text("\n".join(out), "utf-8")


def run(ctx: PipelineContext, *, video_id: int) -> Path:
    """자막 생성. SRT 경로 반환."""
    with stage_timer(ctx, "subtitle") as state:
        video = ctx.repos.videos.get(video_id)
        if video is None:
            raise StageError(f"video_id={video_id} 미존재")
        audio_path = Path(video["audio_path"])
        if not audio_path.exists():
            raise StageError(f"audio_path 미존재: {audio_path}")

        sub_cfg = ctx.section("subtitle")
        format_cfg = sub_cfg.get("format", {})
        keyword_mode = bool(format_cfg.get("keyword_mode", True))

        out_dir = ctx.project_root / sub_cfg.get("output_dir", "output/subtitle")

        if keyword_mode:
            out_ass = out_dir / f"video_{video_id}.ass"
            script = ctx.repos.scripts.get(video["script_id"])
            if script is None:
                raise StageError(f"script_id={video['script_id']} 미존재")
            audio_duration = float(video.get("duration_sec") or 20.0)
            result = make_styled_subtitles(
                script=script,
                audio_duration=audio_duration,
                out_ass=out_ass,
            )
            out_srt = out_ass

            # 세그먼트 타이밍 사이드카 확인
            import json
            times_path = audio_path.parent / (audio_path.stem + "_times.json")
            segment_times: dict = {}
            if times_path.exists():
                try:
                    segment_times = json.loads(times_path.read_text("utf-8"))
                except Exception:
                    pass

            try:
                silences = _detect_silences(audio_path)
                if segment_times:
                    # 정확한 세그먼트 타이밍 적용
                    _apply_segment_timing(out_ass, segment_times, silences)
                    ctx.log.info("subtitle_segment_timing",
                                 segments=list(segment_times.keys()), path=out_ass.name)
                elif silences:
                    # 폴백: silence 기반 스냅
                    _fix_subtitle_splits(out_ass)
                    _enhance_subtitle_timing(out_ass, silences)
                    ctx.log.info("subtitle_enhanced",
                                 silences=len(silences), path=out_ass.name)
            except Exception as e:
                ctx.log.warning("subtitle_enhance_failed", error=repr(e))
        else:
            out_srt = out_dir / f"video_{video_id}.srt"
            whisper_cfg = sub_cfg.get("whisper", {})
            engine = WhisperSubtitleEngine(
                model_size=whisper_cfg.get("model_size", "small"),
                compute_type=whisper_cfg.get("compute_type", "int8"),
                language=whisper_cfg.get("language", "ko"),
                beam_size=int(whisper_cfg.get("beam_size", 5)),
                vad_filter=bool(whisper_cfg.get("vad_filter", True)),
            )
            result = engine.transcribe(
                audio_path=audio_path,
                out_srt=out_srt,
                max_chars_per_line=int(format_cfg.get("max_chars_per_line", 10)),
                max_lines=int(format_cfg.get("max_lines", 1)),
            )

        ctx.repos.db.execute(
            "UPDATE videos SET subtitle_path = ? WHERE id = ?",
            (str(out_srt), video_id),
        )
        state["message"] = f"segments={len(result.segments)}, srt={out_srt}, mode={'keyword' if keyword_mode else 'whisper'}"
        return out_srt
