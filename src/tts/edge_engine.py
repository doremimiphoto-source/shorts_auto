"""edge-tts 엔진 (감성 명언 채널 주력 TTS).

Microsoft Azure Neural TTS를 edge-tts 비공식 wrapper로 호출.
MeloTTS 대비 훨씬 자연스러운 한국어 발음 — 감성 콘텐츠에 최적.

- rate 설정으로 발화 속도 조절 (기본 -15%: 명언 여운 확보)
- 연속 실패 5회 → is_available() False (차단 감지, FR-3.7)
- edge-tts 설치: pip install edge-tts
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path

from .base import SynthResult, TTSEngine

# 실제 제공 한국어 음성: SunHiNeural(여), InJoonNeural(남), HyunsuMultilingualNeural(남)
# 공부 팁 채널: 여자 중학생 수준의 밝고 자연스러운 톤 — SunHiNeural 단독 사용
_VOICE_RATE: dict[str, str] = {
    "ko-KR-SunHiNeural":               "+8%",    # 활기차고 빠른 10대 중학생 발화 속도
    "ko-KR-InJoonNeural":              "-8%",    # 자연스러운 남성 (폴백용)
    "ko-KR-HyunsuMultilingualNeural":  "-5%",    # 다국어 남성 (폴백용)
}

# 피치 조정 — +18Hz: 중학생 여성의 맑고 높은 음역대 연출
_VOICE_PITCH: dict[str, str] = {
    "ko-KR-SunHiNeural":               "+18Hz",  # 중학생 여성 특유의 높고 또렷한 피치
    "ko-KR-InJoonNeural":              "-2Hz",
    "ko-KR-HyunsuMultilingualNeural":  "+0Hz",
}

_DEFAULT_VOICES = list(_VOICE_RATE.keys())
_FAIL_THRESHOLD = 5
_MAX_RETRIES = 3
_RETRY_BASE_WAIT = 2  # 초, 지수 백오프: 2s, 4s


class EdgeEngine(TTSEngine):
    name = "edge"

    def __init__(
        self,
        *,
        voices: list[str] | None = None,
        fail_threshold: int = _FAIL_THRESHOLD,
    ) -> None:
        self.voices = voices or _DEFAULT_VOICES
        self._fail_threshold = fail_threshold
        self._fail_count = 0

    def list_speakers(self) -> list[str]:
        return list(self.voices)

    def is_available(self) -> bool:
        if self._fail_count >= self._fail_threshold:
            return False
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def synthesize(
        self,
        *,
        text: str,
        out_path: Path,
        speaker_id: str | None = None,
    ) -> SynthResult:
        try:
            import edge_tts
        except ImportError as e:
            raise RuntimeError("edge-tts 미설치. pip install edge-tts") from e

        voice = speaker_id if (speaker_id and speaker_id in self.voices) else self.voices[0]
        rate  = _VOICE_RATE.get(voice, "-10%")
        pitch = _VOICE_PITCH.get(voice, "+0Hz")

        # edge-tts는 MP3 출력. tts_stage의 loudnorm 출력(mp3)과 충돌 방지를 위해
        # _raw 접미사 중간 파일에 저장 → loudnorm이 최종 mp3로 변환
        mp3_path = out_path.with_stem(out_path.stem + "_raw").with_suffix(".mp3")
        mp3_path.parent.mkdir(parents=True, exist_ok=True)

        async def _do() -> None:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await communicate.save(str(mp3_path))

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                asyncio.run(_do())
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_BASE_WAIT * (attempt + 1))
        if last_exc is not None:
            self._fail_count += 1
            raise RuntimeError(
                f"Edge TTS 합성 실패 ({voice}, {_MAX_RETRIES}회 시도): {last_exc}"
            ) from last_exc

        if not mp3_path.exists() or mp3_path.stat().st_size == 0:
            self._fail_count += 1
            raise RuntimeError(f"Edge TTS 결과 파일 누락: {mp3_path}")

        self._fail_count = 0
        duration = _probe_duration(mp3_path)
        return SynthResult(
            audio_path=mp3_path,
            duration_seconds=duration,
            sample_rate=24000,
            speaker_id=voice,
            engine=self.name,
            metadata={"voice": voice, "rate": rate},
        )


def _probe_duration(path: Path) -> float:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return float(result.stdout.decode().strip())
    except Exception:
        return 0.0
