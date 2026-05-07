"""MusicGen 기반 BGM 생성 엔진 (Tier 1).

Hugging Face transformers의 MusicGen 모델로 무드별 BGM 클립을 생성한다.
Apache 2.0 라이센스, 결과물은 자유 사용 가능 + 매번 unique → Content ID 매칭 0%.

오프라인 풀 생성용으로 설계되어 있으며, 런타임 파이프라인에서는 호출하지 않는다.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# 무드별 프롬프트 템플릿 (사연 채널 톤)
MOOD_PROMPTS: dict[str, list[str]] = {
    "tension": [
        "dark ambient suspenseful cinematic soundtrack, slow heartbeat, anticipation, no drums",
        "minimalist tension drone, sub bass pulse, eerie pad, mysterious",
        "thriller cinematic underscore, gradually rising strings, suspense",
    ],
    "sad": [
        "melancholic solo piano slow tempo, emotional, introspective, korean drama",
        "lonely ambient pad, soft strings, sad reflective mood, no drums",
        "slow emotional cello and piano duet, mournful, cinematic",
    ],
    "calm": [
        "calm peaceful piano with soft strings, gentle, contemplative",
        "ambient meditation, soft pads, warm acoustic guitar, no drums, slow",
        "soft acoustic guitar fingerpicking, quiet evening atmosphere",
    ],
    "twist": [
        "cinematic reveal moment, rising orchestral swell, dramatic accent",
        "mystery resolved cinematic underscore, plucked strings, contemplative",
        "epic emotional twist moment, soaring strings building tension to release",
    ],
}


@dataclass
class GeneratedClip:
    path: Path
    mood: str
    prompt: str
    duration_sec: float
    sample_rate: int
    elapsed_sec: float
    metadata: dict[str, Any] = field(default_factory=dict)


class MusicGenEngine:
    """transformers' MusicGen wrapper.

    musicgen-small: ~2.2GB 다운로드, CPU에서 30초 클립 생성 ~2-4분.
    첫 호출 시 model cache 디렉토리에 자동 다운로드 (HF_HOME, 기본 ~/.cache/huggingface).
    """

    # MusicGen-small의 frame rate (50 audio tokens per second)
    AUDIO_FRAME_RATE = 50

    def __init__(
        self,
        *,
        model_id: str = "facebook/musicgen-small",
        device: str = "cpu",
        torch_dtype: str = "float32",
    ) -> None:
        self.model_id = model_id
        self.device = device
        self.torch_dtype = torch_dtype
        self._processor = None
        self._model = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        # 임포트는 지연 (의존성 미설치 시 모듈 임포트만으로 실패하지 않게)
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration

        dtype = getattr(torch, self.torch_dtype, torch.float32)
        self._processor = AutoProcessor.from_pretrained(self.model_id)
        self._model = MusicgenForConditionalGeneration.from_pretrained(
            self.model_id,
            torch_dtype=dtype,
        )
        if self.device != "cpu":
            self._model.to(self.device)

    def generate_to_wav(
        self,
        *,
        prompt: str,
        out_path: Path,
        duration_sec: int = 30,
        guidance_scale: float = 3.0,
        seed: int | None = None,
    ) -> GeneratedClip:
        """단일 프롬프트 → WAV 파일."""
        import torch

        self._ensure_loaded()
        assert self._processor is not None and self._model is not None
        out_path.parent.mkdir(parents=True, exist_ok=True)

        max_new_tokens = max(1, duration_sec * self.AUDIO_FRAME_RATE)
        inputs = self._processor(text=[prompt], padding=True, return_tensors="pt")
        if self.device != "cpu":
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

        if seed is not None:
            torch.manual_seed(seed)

        started = time.monotonic()
        with torch.no_grad():
            audio_values = self._model.generate(
                **inputs,
                do_sample=True,
                guidance_scale=guidance_scale,
                max_new_tokens=max_new_tokens,
            )
        elapsed = time.monotonic() - started

        sample_rate = int(self._model.config.audio_encoder.sampling_rate)
        # audio_values shape: (batch, channels, samples)
        audio_np = audio_values[0, 0].cpu().numpy()

        # WAV 저장 (scipy 사용 — 표준 라이브러리)
        from scipy.io import wavfile
        # int16 정규화
        import numpy as np
        peak = float(np.abs(audio_np).max() or 1.0)
        audio_int16 = (audio_np / peak * 32767).astype(np.int16)
        wavfile.write(str(out_path), sample_rate, audio_int16)

        actual_duration = audio_np.shape[-1] / sample_rate
        return GeneratedClip(
            path=out_path,
            mood="",
            prompt=prompt,
            duration_sec=actual_duration,
            sample_rate=sample_rate,
            elapsed_sec=elapsed,
        )

    def generate_pool(
        self,
        *,
        out_root: Path,
        moods: list[str] | None = None,
        per_mood: int = 5,
        duration_sec: int = 30,
        seed_base: int = 42,
        on_progress=None,
    ) -> list[GeneratedClip]:
        """무드별로 N개씩 풀 일괄 생성.

        Parameters
        ----------
        on_progress : callable(idx, total, GeneratedClip) | None
            진행 상황 콜백. 매 클립 생성 후 호출.
        """
        moods = moods or list(MOOD_PROMPTS.keys())
        prompts: list[tuple[str, str, int]] = []
        for m in moods:
            templates = MOOD_PROMPTS.get(m, [])
            if not templates:
                continue
            for i in range(per_mood):
                prompt = templates[i % len(templates)]
                prompts.append((m, prompt, seed_base + i + hash(m) % 1000))

        results: list[GeneratedClip] = []
        for idx, (mood, prompt, seed) in enumerate(prompts):
            mood_dir = out_root / mood
            mood_dir.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            out_path = mood_dir / f"musicgen_{mood}_{idx:03d}_{ts}.wav"
            clip = self.generate_to_wav(
                prompt=prompt,
                out_path=out_path,
                duration_sec=duration_sec,
                seed=seed,
            )
            clip.mood = mood
            results.append(clip)
            if on_progress:
                on_progress(idx + 1, len(prompts), clip)
        return results
