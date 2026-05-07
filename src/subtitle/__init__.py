"""자막 생성 (FR-4).

faster-whisper small (CPU int8)로 음성 → SRT 변환.
"""

from .whisper_engine import WhisperSubtitleEngine

__all__ = ["WhisperSubtitleEngine"]
