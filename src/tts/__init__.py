"""음성 합성 (FR-3).

폴백 체인: Piper → MeloTTS → edge-tts.
화자 다변화는 콘텐츠 ID 해시 기반 결정론적 선택 (FR-3.3).
"""

from .base import SynthResult, TTSEngine

__all__ = ["SynthResult", "TTSEngine"]
