"""TTS 단계 (FR-3).

- 콘텐츠 해시 + 직전 N개 영상과 다른 화자 강제 (FR-3.3)
- 한국어 주력: MeloTTS-Korean (MIT, FR-3 v1.0 갱신본)
- 폴백: Piper(영어용 보관) / edge(비공식)
- FFmpeg loudnorm으로 LUFS -16 정규화 + mp3 24kHz mono 변환 (FR-3.4)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..utils.ffmpeg_path import resolve_ffmpeg as _resolve_ffmpeg
from ..tts.base import TTSEngine
from ..tts.edge_engine import EdgeEngine
from ..tts.melo_engine import MeloEngine, MeloVoice
from ..tts.piper_engine import PiperEngine, PiperVoice
from ..tts.speaker_selector import select_speaker
from ..utils.similarity import text_sha256
from .context import PipelineContext, StageError, StageSkipped, stage_timer


def run(ctx: PipelineContext, *, script_id: int) -> int:
    """TTS 단계. 신규 video_id 반환 (audio_path만 채워진 상태)."""
    with stage_timer(ctx, "tts") as state:
        script = ctx.repos.scripts.get(script_id)
        if script is None:
            raise StageError(f"script_id={script_id} 미존재")

        tts_cfg = ctx.section("tts")
        engine = _build_engine(ctx, tts_cfg)

        # 화자 선택 (FR-3.3)
        speakers = engine.list_speakers()
        if not speakers:
            raise StageSkipped(f"{engine.name} 화자 풀이 비어 있습니다.")
        recent_used = ctx.repos.videos.list_recent_speakers(
            limit=int(tts_cfg.get("speaker_rotation", {}).get("min_distinct_in_recent_n", 3))
        )
        speaker_id = select_speaker(
            content_hash=text_sha256(script["full_text"]),
            available=speakers,
            recent_used=recent_used,
            min_distinct_in_recent=int(tts_cfg.get("speaker_rotation", {}).get("min_distinct_in_recent_n", 3)),
        )
        ctx.log.info("speaker_selected", engine=engine.name, speaker=speaker_id, recent=recent_used)

        # 합성: 엔진 → wav → mp3 (LUFS -16)
        audio_dir = ctx.project_root / "output" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        wav_path = audio_dir / f"script_{script_id}_{speaker_id}.wav"
        mp3_path = audio_dir / f"script_{script_id}_{speaker_id}.mp3"

        hook_text  = _sanitize_for_ko_tts(script.get("hook")  or "")
        body_text  = _sanitize_for_ko_tts(script.get("body")  or "")
        twist_text = _sanitize_for_ko_tts(script.get("twist") or "")
        raw_segs = [("hook", hook_text), ("body", body_text), ("twist", twist_text)]
        segments = [(n, t) for n, t in raw_segs if t.strip()]

        if len(segments) >= 2:
            synth = engine.synthesize_segmented(
                segments=segments,
                out_path=wav_path,
                speaker_id=speaker_id,
            )
        else:
            synth = engine.synthesize(
                text=_sanitize_for_ko_tts(script["full_text"]),
                out_path=wav_path,
                speaker_id=speaker_id,
            )
        ctx.log.info("tts_synth_ok",
                     engine=engine.name,
                     duration_seconds=round(synth.duration_seconds, 2),
                     path=str(wav_path))

        audio_cfg = tts_cfg.get("audio", {})
        target_lufs = float(audio_cfg.get("target_lufs", -16.0))
        sample_rate = int(audio_cfg.get("sample_rate", 24000))
        target_min = float(audio_cfg.get("target_duration_min", 50))
        target_max = float(audio_cfg.get("target_duration_max", 58))

        # edge-tts는 MP3를 직접 출력 → synth.audio_path가 실제 파일 경로
        _convert_with_loudnorm(
            input_path=synth.audio_path,
            output_path=mp3_path,
            target_lufs=target_lufs,
            sample_rate=sample_rate,
            ffmpeg_bin=_resolve_ffmpeg(),
        )

        # 세그먼트 타이밍 사이드카 저장
        segment_times = synth.metadata.get("segment_times", {})
        if segment_times:
            import json
            times_path = mp3_path.parent / (mp3_path.stem + "_times.json")
            times_path.write_text(json.dumps(segment_times, ensure_ascii=False), "utf-8")
        # 길이 검증 (FR-3.5)
        duration = synth.duration_seconds
        if not (target_min <= duration <= target_max):
            ctx.log.warning("tts_duration_out_of_range",
                            duration=duration, target_min=target_min, target_max=target_max)

        # 임시 원본 정리 (edge는 mp3_path와 다를 수 있음)
        src = synth.audio_path
        if src.exists() and src.resolve() != mp3_path.resolve():
            try:
                src.unlink()
            except OSError:
                pass

        video_id = ctx.repos.videos.insert(
            script_id=script_id,
            speaker_id=speaker_id,
            audio_path=str(mp3_path),
            audio_lufs=target_lufs,
            duration_sec=duration,
        )
        state["message"] = f"video_id={video_id}, speaker={speaker_id}, duration={duration:.1f}s"
        return video_id


def _build_engine(ctx: PipelineContext, tts_cfg: dict) -> TTSEngine:
    """primary 설정 + fallback_chain 순서대로 빌드 가능한 첫 엔진을 반환."""
    primary = tts_cfg.get("primary", "melo")
    chain = tts_cfg.get("fallback_chain", [primary])
    if primary not in chain:
        chain = [primary] + list(chain)

    last_error: str | None = None
    for name in chain:
        try:
            if name == "edge":
                return _build_edge_engine(ctx, tts_cfg.get("edge", {}))
            if name == "melo":
                return _build_melo_engine(ctx, tts_cfg.get("melo", {}))
            if name == "piper":
                return _build_piper_engine(ctx, tts_cfg.get("piper", {}))
            last_error = f"unsupported engine: {name}"
        except StageSkipped as e:
            last_error = f"{name}: {e}"
            ctx.log.warning("tts_engine_skip", engine=name, reason=str(e))
            continue
    raise StageSkipped(f"사용 가능한 TTS 엔진 없음. last={last_error}")


def _build_edge_engine(ctx: PipelineContext, edge_cfg: dict) -> EdgeEngine:
    if not edge_cfg.get("enabled", False):
        raise StageSkipped("edge 엔진 비활성화 (config.tts.edge.enabled=false)")
    voices = edge_cfg.get("voices") or []
    engine = EdgeEngine(voices=voices or None)
    if not engine.is_available():
        raise StageSkipped("edge-tts 라이브러리 미설치 (pip install edge-tts)")
    return engine


def _build_melo_engine(ctx: PipelineContext, melo_cfg: dict) -> MeloEngine:
    voices_cfg = melo_cfg.get("voices") or []
    if not voices_cfg:
        # 기본값 사용 (engine 자체가 _SPEED_PROFILES 내장)
        return MeloEngine(device=str(melo_cfg.get("device", "cpu")))
    voices = [MeloVoice(voice_id=str(v["id"]), speed=float(v.get("speed", 1.0))) for v in voices_cfg]
    engine = MeloEngine(voices=voices, device=str(melo_cfg.get("device", "cpu")))
    if not engine.is_available():
        raise StageSkipped("MeloTTS 라이브러리(melo.api) 미설치")
    return engine


def _build_piper_engine(ctx: PipelineContext, piper_cfg: dict) -> PiperEngine:
    if not piper_cfg.get("enabled", True):
        raise StageSkipped("piper 엔진 비활성화 (config.tts.piper.enabled=false)")

    bin_path = ctx.settings.secrets.piper_bin_path or piper_cfg.get("bin", "piper")
    # 절대/상대 경로 모두 지원: 상대 경로면 프로젝트 루트 기준
    bin_resolved = bin_path
    if bin_path and not Path(bin_path).is_absolute():
        cand = ctx.project_root / bin_path
        if cand.exists():
            bin_resolved = str(cand)

    voices_cfg = piper_cfg.get("voices", []) or []
    if not voices_cfg:
        raise StageSkipped("piper.voices 설정이 비어 있습니다.")

    voices: list[PiperVoice] = []
    for v in voices_cfg:
        model = ctx.project_root / v["model"]
        config = ctx.project_root / v["config"]
        if not model.exists() or not config.exists():
            ctx.log.warning("piper_voice_missing", voice=v.get("id"), model=str(model))
            continue
        voices.append(PiperVoice(voice_id=v["id"], model_path=model, config_path=config))

    if not voices:
        raise StageSkipped("사용 가능한 Piper 음성 모델이 없습니다.")

    engine = PiperEngine(voices=voices, bin_path=bin_resolved)
    if not shutil.which(bin_resolved):
        raise StageSkipped(f"Piper 바이너리 미발견: {bin_resolved}")
    return engine


# ── 순우리말 수 (사람·사물을 셀 때 사용하는 고유어 수사) ──────────────────
_NATIVE_ONES = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"]
_NATIVE_TENS = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]

# 순우리말 수를 쓰는 단위 (인원·사물·나이·종류·배수 등)
# 주의: 긴 단위어를 먼저 매칭하도록 정렬하므로 tuple 순서는 무관 (sorted 처리됨)
_KO_COUNTERS = (
    # 기존 단위어
    "명", "개", "권", "장", "마리", "살", "번", "대", "잔", "병",
    "켤레", "벌", "채", "칸", "층", "줄", "그루", "포기", "송이",
    "다발", "마디", "알", "방울", "조각", "통", "봉지", "봉", "쌍", "짝",
    # 추가: 종류·배수·가닥 계열 (순우리말 수 필요)
    "가지",   # 세 가지, 다섯 가지 방법
    "배",     # 두 배, 세 배 (배수)
    "차례",   # 세 차례 (횟수·회수)
    "가닥",   # 두 가닥
    "갈래",   # 두 갈래
    "사람",   # 두 사람 (명의 비격식 대안)
    "군데",   # 세 군데 (장소 수)
    "시간",   # 한 시간, 두 시간 (시간 단위 — 순우리말 수사)
)

# ── 한자어 수 (시간·점수·횟수 등 Sino-Korean 수사) ──────────────────────
_SINO_DIGIT = ["영", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]


def _to_sino_korean(n: int) -> str:
    """정수를 한자어 수사로 변환 (0~99999).

    10→십, 20→이십, 80→팔십, 100→백, 1000→천 (선행 '일' 생략 규칙 적용).
    """
    if n == 0:
        return "영"
    if n < 0 or n >= 100000:
        return str(n)
    parts: list[str] = []
    for unit, label in ((10000, "만"), (1000, "천"), (100, "백"), (10, "십")):
        k = n // unit
        if k:
            parts.append(("" if k == 1 else _SINO_DIGIT[k]) + label)
            n %= unit
    if n:
        parts.append(_SINO_DIGIT[n])
    return "".join(parts)


def _to_native(n: int) -> str:
    """1~99 정수를 순우리말 수로 변환. 범위 밖이면 str(n)."""
    if not (1 <= n <= 99):
        return str(n)
    tens, ones = divmod(n, 10)
    if tens == 0:
        return _NATIVE_ONES[ones]
    return _NATIVE_TENS[tens] + (_NATIVE_ONES[ones] if ones else "")


def _normalize_ko_numbers(text: str) -> str:
    """숫자+순우리말단위 → 순우리말 수 변환.

    10명 → 열 명 / 20명 → 스무 명 / 21명 → 스물한 명
    """
    import re
    counter_pat = "|".join(sorted(_KO_COUNTERS, key=len, reverse=True))
    pattern = re.compile(r"(\d+)\s*(" + counter_pat + r")")

    def _replace(m: re.Match) -> str:
        n = int(m.group(1))
        unit = m.group(2)
        if n < 1:
            return m.group(0)
        if n > 99:
            # 100 이상은 한자어 수 + 단위 (백 개, 백 명 등)
            return _to_sino_korean(n) + " " + unit
        native = _to_native(n)
        if n == 20:
            native = "스무"
        return native + " " + unit

    return pattern.sub(_replace, text)


def _normalize_sino_numbers(text: str) -> str:
    """남은 아라비아 숫자를 모두 한자어 수사로 변환.

    25분→이십오 분, 80→팔십, 3회→삼 회, 3단계→삼 단계, 20%→이십 퍼센트 등.
    순우리말 단위어와 결합된 숫자는 _normalize_ko_numbers에서 이미 처리됨.
    """
    import re
    # % 기호는 퍼센트로 치환
    text = text.replace("%", " 퍼센트")

    _src = text  # 원본 보존 (위치 참조용)

    def _replace(m: re.Match) -> str:
        try:
            converted = _to_sino_korean(int(m.group(0)))
        except ValueError:
            return m.group(0)
        # 바로 다음 문자가 한글이면 공백 삽입 (삼회→삼 회, 삼단계→삼 단계)
        end = m.end()
        if end < len(_src) and ("가" <= _src[end] <= "힣" or "ᄀ" <= _src[end] <= "ᇿ"):
            return converted + " "
        return converted

    return re.sub(r"\d+", _replace, text)


def _add_sentence_breaks(text: str) -> str:
    """문장 끝에 마침표를 보완하고 TTS 포즈 경계를 삽입한다.

    Edge TTS는 마침표(.)에서 자연스럽게 쉬므로, 마침표 누락 시 문장이 이어진다.
    1단계: 마침표 없이 이어지는 문장 경계에 마침표 삽입
    2단계: 구두점 뒤 공백 → 줄바꿈 (MeloTTS 포즈 마커 역할)
    """
    import re
    # ① 구두점 없는 문장 경계에 마침표 삽입: "읽는다 둘째" → "읽는다. 둘째"
    #   - 다/요 바로 뒤에 공백이 오고, 다음이 한글·숫자 (이미 .,!? 가 붙어있으면 스킵)
    text = re.sub(r"([다요])(?=[.,!?])", r"\1", text)   # 이미 구두점 있는 건 스킵 (no-op)
    text = re.sub(r"([다요])( +)(?=[가-힣0-9])", r"\1.\2", text)
    # ② 텍스트 끝이 다/요로 끝나면 마침표 추가
    text = re.sub(r"([다요])$", r"\1.", text)
    # ③ 구두점 뒤 공백 → 줄바꿈 (TTS 포즈 마커)
    text = re.sub(r"([다요]\.) +", r"\1\n", text)
    text = re.sub(r"([!?]) +", r"\1\n", text)
    # ④ 연속 줄바꿈 정리
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def _fix_ko_spacing(text: str) -> str:
    """기본 띄어쓰기 교정 — TTS 발음에 영향을 주는 공백 오류만 처리."""
    import re
    # 쉼표·마침표 뒤 공백 없는 경우 삽입 (소수점 숫자 제외)
    text = re.sub(r",([가-힣a-zA-Z0-9])", r", \1", text)
    text = re.sub(r"\.([가-힣a-zA-Z])", r". \1", text)
    # 구두점 앞 불필요한 공백 제거
    text = re.sub(r"\s+([.,!?])", r"\1", text)
    # 중복 공백 → 단일 공백
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _sanitize_for_ko_tts(text: str) -> str:
    """한국어 TTS 입력 정제.

    0) 한자·히라가나·카타카나 선제 제거 (rewrite 단계 누락분 안전망)
    1) 순우리말 단위 수 변환 (10명→열 명)
    2) 나머지 숫자 한자어 변환 (80→팔십, 25분→이십오 분)
    3) 기본 띄어쓰기 교정
    4) 문장 경계 줄바꿈 삽입으로 자연 쉬어가기 유도
    5) 비한국어 문자 제거
    """
    from ..utils.korean import strip_cjk
    text = strip_cjk(text)
    text = _normalize_ko_numbers(text)
    text = _normalize_sino_numbers(text)
    text = _fix_ko_spacing(text)
    text = _add_sentence_breaks(text)

    _ALLOWED = frozenset(range(0x0020, 0x007F))  # basic ASCII printable
    result = []
    for ch in text:
        cp = ord(ch)
        if (cp in _ALLOWED
                or ch in "\n\r\t"
                or 0xAC00 <= cp <= 0xD7A3   # Hangul syllables
                or 0x1100 <= cp <= 0x11FF   # Hangul Jamo
                or 0x3130 <= cp <= 0x318F): # Hangul Compat Jamo
            result.append(ch)
        else:
            result.append(" ")
    return "".join(result).strip()


def _convert_with_loudnorm(
    *,
    input_path: Path,
    output_path: Path,
    target_lufs: float,
    sample_rate: int,
    ffmpeg_bin: str = "ffmpeg",
) -> None:
    """FFmpeg loudnorm으로 LUFS 정규화 + 24kHz mono mp3 변환."""
    cmd = [
        ffmpeg_bin,
        "-hide_banner", "-y",
        "-i", str(input_path),
        "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-codec:a", "libmp3lame", "-q:a", "2",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=180, check=False)
    if result.returncode != 0 or not output_path.exists():
        raise StageError(
            f"FFmpeg loudnorm 변환 실패 (exit={result.returncode}): "
            f"{result.stderr.decode('utf-8', 'replace')[-1000:]}"
        )
