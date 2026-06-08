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

from .base import SynthResult, TTSEngine, _concat_audio_with_gaps

# 실제 제공 한국어 음성: SunHiNeural(여), InJoonNeural(남), HyunsuMultilingualNeural(남)
# 공부 팁 채널: 여자 중학생 수준의 밝고 자연스러운 톤 — SunHiNeural 단독 사용
_VOICE_RATE: dict[str, str] = {
    "ko-KR-SunHiNeural":               "+8%",    # 활기차고 빠른 10대 중학생 발화 속도
    "ko-KR-InJoonNeural":              "-8%",    # 자연스러운 남성 (폴백용)
    "ko-KR-HyunsuMultilingualNeural":  "-5%",    # 다국어 남성 (폴백용)
}

# 피치 조정 — cheerful 스타일과 함께 사용: +14Hz로 자연스러운 중학생 여성 음역대 유지
_VOICE_PITCH: dict[str, str] = {
    "ko-KR-SunHiNeural":               "+14Hz",  # cheerful 스타일이 에너지 추가 → 과잉 방지
    "ko-KR-InJoonNeural":              "-2Hz",
    "ko-KR-HyunsuMultilingualNeural":  "+0Hz",
}

# SSML mstts:express-as 스타일 — SunHiNeural: cheerful(밝고 에너지), sad 지원
# cheerful: 중학생 여성 특유의 친근하고 활기찬 톤 연출
_VOICE_STYLE: dict[str, str] = {
    "ko-KR-SunHiNeural": "cheerful",
}

_DEFAULT_VOICES = list(_VOICE_RATE.keys())
_FAIL_THRESHOLD = 5


def _to_ssml(text: str, voice: str, rate: str, pitch: str) -> str:
    """SSML 래퍼 — mstts:express-as style + prosody rate/pitch.

    _VOICE_STYLE에 등록된 voice만 SSML로 변환; 나머지는 plain text 그대로 반환.
    HTML 특수문자(<>&"')는 escape 처리.
    """
    import html
    style = _VOICE_STYLE.get(voice)
    if not style:
        return text
    return (
        "<speak version='1.0' "
        "xmlns='http://www.w3.org/2001/10/synthesis' "
        "xmlns:mstts='http://www.w3.org/2001/mstts' "
        "xml:lang='ko-KR'>"
        f"<voice name='{voice}'>"
        f"<mstts:express-as style='{style}'>"
        f"<prosody rate='{rate}' pitch='{pitch}'>"
        f"{html.escape(text)}"
        "</prosody>"
        "</mstts:express-as>"
        "</voice>"
        "</speak>"
    )
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

        async def _do() -> list[dict]:
            ssml = _to_ssml(text, voice, rate, pitch)
            is_ssml = ssml.startswith("<speak")
            # SSML 사용 시 rate/pitch는 <prosody> 안에 포함 → Communicate 생성자에 미전달
            communicate = edge_tts.Communicate(
                ssml, voice, boundary="WordBoundary",
                **({} if is_ssml else {"rate": rate, "pitch": pitch}),
            )
            boundaries: list[dict] = []
            audio_chunks: list[bytes] = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    # edge-tts 7.x: offset/duration은 100ns 단위, text는 문자열
                    boundaries.append({
                        "text": chunk["text"],
                        "offset_sec": round(chunk["offset"] / 10_000_000, 3),
                        "duration_sec": round(chunk.get("duration", 0) / 10_000_000, 3),
                    })
            mp3_path.write_bytes(b"".join(audio_chunks))
            return boundaries

        last_exc: Exception | None = None
        word_boundaries: list[dict] = []
        for attempt in range(_MAX_RETRIES):
            try:
                word_boundaries = asyncio.run(_do())
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
            metadata={"voice": voice, "rate": rate, "word_boundaries": word_boundaries},
        )

    def synthesize_segmented(
        self,
        *,
        segments: list[tuple[str, str]],
        out_path: Path,
        speaker_id: str | None = None,
        gaps: tuple[float, ...] = (0.35, 0.50),
    ) -> SynthResult:
        """MP3 출력 엔진(edge_tts) 전용: 세그먼트별 합성 후 묵음 갭 삽입 연결."""
        try:
            import edge_tts
        except ImportError as e:
            raise RuntimeError("edge-tts 미설치") from e

        voice = speaker_id if (speaker_id and speaker_id in self.voices) else self.voices[0]
        rate = _VOICE_RATE.get(voice, "-10%")
        pitch = _VOICE_PITCH.get(voice, "+0Hz")
        gaps_list = list(gaps)
        temp_mp3s = []
        durations = []

        all_word_boundaries: list[dict] = []  # 전체 타임라인 누적
        cumulative_offset = 0.0

        for i, (name, text) in enumerate(segments):
            seg_mp3 = out_path.with_stem(f"_seg{i}_{out_path.stem}").with_suffix(".mp3")

            async def _stream_seg(t=text, p=seg_mp3):
                ssml = _to_ssml(t, voice, rate, pitch)
                is_ssml = ssml.startswith("<speak")
                communicate = edge_tts.Communicate(
                    ssml, voice, boundary="WordBoundary",
                    **({} if is_ssml else {"rate": rate, "pitch": pitch}),
                )
                boundaries: list[dict] = []
                chunks: list[bytes] = []
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        chunks.append(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        boundaries.append({
                            "text": chunk["text"],
                            "offset_sec": round(chunk["offset"] / 10_000_000, 3),
                            "duration_sec": round(chunk.get("duration", 0) / 10_000_000, 3),
                        })
                p.write_bytes(b"".join(chunks))
                return boundaries

            last_exc = None
            seg_boundaries: list[dict] = []
            for attempt in range(_MAX_RETRIES):
                try:
                    seg_boundaries = asyncio.run(_stream_seg())
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(_RETRY_BASE_WAIT * (attempt + 1))
            if last_exc is not None:
                self._fail_count += 1
                raise RuntimeError(f"Edge TTS 세그먼트 합성 실패 ({name}): {last_exc}")

            dur = _probe_duration(seg_mp3)
            temp_mp3s.append(seg_mp3)
            durations.append(dur)

            # 세그먼트 오프셋을 누적해 전체 타임라인 기준으로 변환
            for wb in seg_boundaries:
                all_word_boundaries.append({
                    "segment": name,
                    "text": wb["text"],
                    "offset_sec": round(wb["offset_sec"] + cumulative_offset, 3),
                    "duration_sec": wb["duration_sec"],
                })
            cumulative_offset += dur + (gaps_list[i] if i < len(segments) - 1 and i < len(gaps_list) else 0)

        # Compute exact times
        t = 0.0
        segment_times = {}
        for i, (name, _) in enumerate(segments):
            segment_times[name] = {"start": round(t, 3), "end": round(t + durations[i], 3)}
            t += durations[i]
            if i < len(segments) - 1 and i < len(gaps_list):
                t += gaps_list[i]

        # Concatenate MP3s with silence gaps
        combined_raw = out_path.with_stem(out_path.stem + "_raw").with_suffix(".mp3")
        _concat_audio_with_gaps(temp_mp3s, gaps_list[:len(segments) - 1], combined_raw)

        for f in temp_mp3s:
            try:
                f.unlink()
            except OSError:
                pass

        self._fail_count = 0
        total_dur = _probe_duration(combined_raw)
        return SynthResult(
            audio_path=combined_raw,
            duration_seconds=total_dur,
            sample_rate=24000,
            speaker_id=voice,
            engine=self.name,
            metadata={
                "voice": voice,
                "rate": rate,
                "segment_times": segment_times,
                "word_boundaries": all_word_boundaries,
            },
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
