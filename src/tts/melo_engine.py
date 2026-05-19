"""MeloTTS 기반 한국어 TTS 엔진 (FR-3 주력 — Day 5 전환).

Piper의 한국어 모델이 상업 사용 가능한 형태로 존재하지 않아 (CC-BY-NC-SA만 가용)
MIT 라이센스의 MeloTTS-Korean으로 주력 전환.

특성:
- 한국어 단일 화자 (KR), 여성·부드러운 톤
- 다변화는 speed (0.85~1.05) + 피치(FFmpeg post)로 가상 다중 화자 구성
- CPU 동작 (60초 텍스트 ~30~90초 합성)
- 첫 호출 시 myshell-ai/MeloTTS-Korean 모델 자동 다운로드 (~150MB)
"""

from __future__ import annotations

import time
import wave
from dataclasses import dataclass
from pathlib import Path

from .base import SynthResult, TTSEngine


# 자연스러운 한국어 TTS 속도 — 0.93~1.03 범위 (너무 느리면 로봇 느낌)
_SPEED_PROFILES: dict[str, float] = {
    "kr_soft_default": 0.97,
    "kr_soft_slow":    0.94,
    "kr_soft_normal":  1.00,
    "kr_soft_brisk":   1.03,
    "kr_soft_calm":    0.96,
}


@dataclass
class MeloVoice:
    """MeloTTS 화자 프로필.

    동일 모델·화자에 speed 변형으로 인지적 다양성을 제공한다 (FR-3.2 우회).
    추후 MeloTTS가 다중 한국어 화자를 추가하거나, 별도 한국어 TTS 합류 시 확장.
    """
    voice_id: str
    speed: float = 1.0
    melo_speaker_key: str = "KR"     # MeloTTS 한국어는 단일 화자 'KR'


class MeloEngine(TTSEngine):
    name = "melo"

    # MeloTTS 한국어 출력 샘플레이트 (모델 hps에 의존, 통상 44100)
    DEFAULT_SAMPLE_RATE = 44100

    def __init__(
        self,
        *,
        voices: list[MeloVoice] | None = None,
        device: str = "cpu",
    ) -> None:
        # 단일 모델·단일 화자에 speed 변형 5종을 가상 화자로 노출 → FR-3.2 충족
        if voices is None:
            voices = [MeloVoice(voice_id=k, speed=v) for k, v in _SPEED_PROFILES.items()]
        self.voices = {v.voice_id: v for v in voices}
        self.device = device
        self._model = None

    def is_available(self) -> bool:
        try:
            import importlib

            importlib.import_module("melo.api")
            return True
        except Exception:
            return False

    def list_speakers(self) -> list[str]:
        return list(self.voices.keys())

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        # Windows: g2pkk가 eunjeon을 요구하지만 빌드가 어려우므로 no-op stub으로 대체
        _patch_g2pkk_for_windows()

        # 임포트 지연 (의존성 미설치 환경에서 모듈 임포트만으로 실패 회피)
        from melo.api import TTS

        # MeloTTS는 첫 호출 시 myshell-ai/MeloTTS-Korean을 자동 다운로드
        self._model = TTS(language="KR", device=self.device)

    def synthesize(
        self,
        *,
        text: str,
        out_path: Path,
        speaker_id: str | None = None,
    ) -> SynthResult:
        if not text:
            raise ValueError("빈 텍스트는 합성할 수 없습니다.")
        self._ensure_model()
        assert self._model is not None

        voice_id = speaker_id or next(iter(self.voices))
        if voice_id not in self.voices:
            raise KeyError(f"등록되지 않은 화자: {voice_id}")
        voice = self.voices[voice_id]
        out_path.parent.mkdir(parents=True, exist_ok=True)

        spk2id = self._model.hps.data.spk2id  # type: ignore[union-attr]
        # MeloTTS의 spk2id는 HParams (속성 접근). hasattr 로 키 존재 여부 확인.
        try:
            if hasattr(spk2id, voice.melo_speaker_key):
                melo_key = voice.melo_speaker_key
                melo_speaker_id = getattr(spk2id, melo_key)
            else:
                # 첫 속성으로 fallback (HParams.__dict__ 사용)
                attrs = [k for k in vars(spk2id).keys() if not k.startswith("_")]
                if not attrs:
                    raise RuntimeError("MeloTTS 모델에 등록된 화자가 없습니다.")
                melo_key = attrs[0]
                melo_speaker_id = getattr(spk2id, melo_key)
        except (AttributeError, TypeError) as e:
            raise RuntimeError(f"MeloTTS 화자 키 조회 실패: {e}") from e

        started = time.monotonic()
        # MeloTTS는 wav를 out_path에 직접 저장
        self._model.tts_to_file(  # type: ignore[union-attr]
            text=text,
            speaker_id=melo_speaker_id,
            output_path=str(out_path),
            speed=voice.speed,
            quiet=True,  # Windows CP949 콘솔 인코딩 오류 방지
        )
        elapsed = time.monotonic() - started

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise RuntimeError(f"MeloTTS 합성 결과 누락: {out_path}")
        duration, sr = _wav_info(out_path)
        return SynthResult(
            audio_path=out_path,
            duration_seconds=duration,
            sample_rate=sr,
            speaker_id=voice_id,
            engine=self.name,
            metadata={
                "melo_speaker_key": melo_key,
                "speed": voice.speed,
                "synthesis_elapsed_sec": round(elapsed, 2),
            },
        )


def _patch_g2pkk_for_windows() -> None:
    """g2pkk가 Windows에서 `eunjeon`(Korean MeCab)을 요구하지만 빌드 어렵고
    `python-mecab-ko`는 `mecab-python3`(MeloTTS Japanese 의존성)와 동일 폴더
    충돌 (대소문자 구분 안 됨). 따라서 안전한 stub을 등록한다.

    g2pkk의 `annotate()`는 mecab.pos()가 빈 리스트를 반환하면 입력 문자열을
    그대로 반환 — 일부 phoneme 규칙(의/J, 받침 변환)이 빠지지만 대부분의
    사연 문장에서는 청각 차이가 크지 않다. 향후 필요 시 mecab-ko-dic을 별도
    설치하여 진짜 분석기로 교체 가능.
    """
    import platform
    if platform.system() != "Windows":
        return
    import sys

    if "eunjeon" in sys.modules:
        return

    import types

    stub = types.ModuleType("eunjeon")

    class Mecab:
        """eunjeon.Mecab no-op 스텁. pos/morphs/nouns 모두 빈 결과."""

        def pos(self, text: str) -> list[tuple[str, str]]:
            return []

        def morphs(self, text: str) -> list[str]:
            return []

        def nouns(self, text: str) -> list[str]:
            return []

    stub.Mecab = Mecab  # type: ignore[attr-defined]
    # importlib.util.find_spec("eunjeon") raises ValueError if __spec__ is None
    import importlib.machinery
    stub.__spec__ = importlib.machinery.ModuleSpec("eunjeon", loader=None, origin="stub")
    sys.modules["eunjeon"] = stub


def _wav_info(path: Path) -> tuple[float, int]:
    try:
        with wave.open(str(path), "rb") as w:
            frames = w.getnframes()
            sr = w.getframerate()
        return frames / float(sr) if sr else 0.0, sr
    except wave.Error:
        return 0.0, MeloEngine.DEFAULT_SAMPLE_RATE
