"""TTS 단계 (FR-3).

- 콘텐츠 해시 + 직전 N개 영상과 다른 화자 강제 (FR-3.3)
- 한국어 주력: MeloTTS-Korean (MIT, FR-3 v1.0 갱신본)
- 폴백: Piper(영어용 보관) / edge(비공식)
- FFmpeg loudnorm으로 LUFS -16 정규화 + mp3 24kHz mono 변환 (FR-3.4)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

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
        )
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

# 순우리말 수를 쓰는 단위 (인원·사물·나이 등)
_KO_COUNTERS = (
    "명", "개", "권", "장", "마리", "살", "번", "대", "잔", "병",
    "켤레", "벌", "채", "칸", "층", "줄", "그루", "포기", "송이",
    "다발", "마디", "알", "방울", "조각", "통", "봉지", "봉", "쌍", "짝",
)


def _to_native(n: int) -> str:
    """1~99 정수를 순우리말 수로 변환. 범위 밖이면 str(n)."""
    if not (1 <= n <= 99):
        return str(n)
    tens, ones = divmod(n, 10)
    if tens == 0:
        return _NATIVE_ONES[ones]
    return _NATIVE_TENS[tens] + (_NATIVE_ONES[ones] if ones else "")


def _normalize_ko_numbers(text: str) -> str:
    """숫자+단위어 → 순우리말 수 변환.

    10명 → 열 명 / 20명 → 스무 명 / 21명 → 스물한 명
    20은 단독으로 명사 앞에 오면 '스무'로 변환 (스물 + 명사 → 스무 명사).
    """
    import re
    counter_pat = "|".join(sorted(_KO_COUNTERS, key=len, reverse=True))
    pattern = re.compile(r"(\d+)\s*(" + counter_pat + r")")

    def _replace(m: re.Match) -> str:
        n = int(m.group(1))
        unit = m.group(2)
        if not (1 <= n <= 99):
            return m.group(0)
        native = _to_native(n)
        # 20, 30, ... 처럼 십단위로 끝날 때 + 바로 명사 → 스물→스무 등
        # 실제로 스물만 해당 (다른 십단위는 변형 없음)
        if n == 20:
            native = "스무"
        return native + " " + unit

    return pattern.sub(_replace, text)


def _sanitize_for_ko_tts(text: str) -> str:
    """한국어 TTS 입력 정제.

    1) 숫자+단위어를 순우리말 수로 변환 (10명→열 명, 20명→스무 명 등)
    2) 비한국어 문자(중국어·일본어 등) 제거
    """
    text = _normalize_ko_numbers(text)
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
