"""TTS 엔진 추상 인터페이스 (FR-3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SynthResult:
    audio_path: Path
    duration_seconds: float
    sample_rate: int
    speaker_id: str
    engine: str
    lufs: float | None = None
    metadata: dict = field(default_factory=dict)


class TTSEngine(ABC):
    """TTS 엔진 베이스. 각 백엔드(piper/melo/edge)는 본 인터페이스를 구현."""

    name: str           # 'piper' | 'melo' | 'edge'

    @abstractmethod
    def synthesize(
        self,
        *,
        text: str,
        out_path: Path,
        speaker_id: str | None = None,
    ) -> SynthResult:
        """텍스트 → 오디오 파일. out_path 디렉토리는 호출자가 보장."""

    @abstractmethod
    def list_speakers(self) -> list[str]:
        """등록된 화자 ID 목록."""

    def is_available(self) -> bool:
        return True
