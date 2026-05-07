"""Piper TTS 엔진 (FR-3 주력).

Piper 바이너리는 외부 도구로 호출 (subprocess). MIT, 완전 오프라인.
출력은 wav (Piper 기본). FFmpeg로 후속 mp3 변환·LUFS 정규화 (FR-3.4)는 renderer 단계에서 수행.
"""

from __future__ import annotations

import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from .base import SynthResult, TTSEngine


@dataclass
class PiperVoice:
    voice_id: str
    model_path: Path
    config_path: Path


class PiperEngine(TTSEngine):
    name = "piper"

    def __init__(self, *, voices: list[PiperVoice], bin_path: str = "piper") -> None:
        if not voices:
            raise ValueError("Piper 화자 풀이 비어 있습니다.")
        self.voices = {v.voice_id: v for v in voices}
        self.bin_path = bin_path

    def is_available(self) -> bool:
        # 바이너리 존재 확인 + 모델 파일 존재 확인
        if not shutil.which(self.bin_path):
            return False
        return all(v.model_path.exists() and v.config_path.exists() for v in self.voices.values())

    def list_speakers(self) -> list[str]:
        return list(self.voices.keys())

    def synthesize(
        self,
        *,
        text: str,
        out_path: Path,
        speaker_id: str | None = None,
    ) -> SynthResult:
        voice_id = speaker_id or next(iter(self.voices))
        if voice_id not in self.voices:
            raise KeyError(f"등록되지 않은 화자: {voice_id}")
        voice = self.voices[voice_id]
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # piper --model X.onnx --output_file out.wav < stdin
        cmd = [
            self.bin_path,
            "--model", str(voice.model_path),
            "--config", str(voice.config_path),
            "--output_file", str(out_path),
        ]
        result = subprocess.run(
            cmd,
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Piper 합성 실패 (exit={result.returncode}): {result.stderr.decode('utf-8', 'replace')}")
        if not out_path.exists():
            raise RuntimeError(f"Piper 출력 파일 누락: {out_path}")

        duration, sr = _wav_info(out_path)
        return SynthResult(
            audio_path=out_path,
            duration_seconds=duration,
            sample_rate=sr,
            speaker_id=voice_id,
            engine=self.name,
        )


def _wav_info(path: Path) -> tuple[float, int]:
    with wave.open(str(path), "rb") as w:
        frames = w.getnframes()
        sr = w.getframerate()
    duration = frames / float(sr) if sr else 0.0
    return duration, sr
