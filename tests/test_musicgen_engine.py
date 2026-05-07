"""src.audio.musicgen_engine 단위 테스트.

실제 모델 로딩·생성은 mock으로 우회한다 (CI에서 수GB 모델 다운로드 회피).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.audio.musicgen_engine import MOOD_PROMPTS, MusicGenEngine


def test_mood_prompts_cover_required_moods() -> None:
    assert {"tension", "sad", "calm", "twist"}.issubset(MOOD_PROMPTS.keys())
    for moods in MOOD_PROMPTS.values():
        assert moods, "각 무드는 1개 이상의 프롬프트를 가져야 함"


def test_engine_lazy_load_not_triggered_on_init() -> None:
    eng = MusicGenEngine(model_id="facebook/musicgen-small")
    # 인스턴스 생성만으로는 모델/프로세서 로드되지 않음
    assert eng._model is None
    assert eng._processor is None


def _stub_engine(mocker, sample_rate: int = 32000, duration_sec: float = 1.0) -> MusicGenEngine:
    """모델/프로세서를 stub으로 갈아끼운 엔진 인스턴스."""
    eng = MusicGenEngine()
    eng._processor = mocker.Mock()
    fake_inputs = {"input_ids": mocker.Mock()}
    eng._processor.return_value = fake_inputs

    samples = int(sample_rate * duration_sec)
    fake_audio = np.linspace(-0.9, 0.9, samples, dtype=np.float32).reshape(1, 1, samples)

    fake_model = mocker.Mock()
    fake_model.generate.return_value = mocker.Mock()
    fake_model.generate.return_value.__getitem__ = lambda self, idx: _FakeTensor(fake_audio[idx])
    fake_model.config.audio_encoder.sampling_rate = sample_rate
    eng._model = fake_model
    return eng


class _FakeTensor:
    def __init__(self, arr: np.ndarray) -> None:
        self._arr = arr

    def __getitem__(self, idx):
        return _FakeTensor(self._arr[idx])

    def cpu(self):
        return self

    def numpy(self):
        return self._arr


def test_generate_to_wav_writes_file_and_returns_metadata(tmp_path: Path, mocker) -> None:
    # torch import는 함수 내부 → patch
    import torch
    mocker.patch.object(torch, "manual_seed")
    eng = _stub_engine(mocker, sample_rate=32000, duration_sec=2.0)
    out = tmp_path / "out.wav"

    clip = eng.generate_to_wav(prompt="ambient piano", out_path=out, duration_sec=2, seed=1)

    assert out.exists()
    assert out.stat().st_size > 0
    assert clip.path == out
    assert clip.sample_rate == 32000
    assert abs(clip.duration_sec - 2.0) < 0.01


def test_generate_pool_creates_per_mood_subdirs(tmp_path: Path, mocker) -> None:
    eng = _stub_engine(mocker, duration_sec=1.0)
    progress_calls: list[tuple[int, int]] = []

    def on_progress(idx: int, total: int, clip):
        progress_calls.append((idx, total))

    clips = eng.generate_pool(
        out_root=tmp_path,
        moods=["tension", "calm"],
        per_mood=2,
        duration_sec=1,
        on_progress=on_progress,
    )
    assert len(clips) == 4
    assert {c.mood for c in clips} == {"tension", "calm"}
    assert (tmp_path / "tension").is_dir()
    assert (tmp_path / "calm").is_dir()
    # 각 무드별 2개 파일
    assert len(list((tmp_path / "tension").glob("*.wav"))) == 2
    assert len(list((tmp_path / "calm").glob("*.wav"))) == 2
    # 프로그레스 콜백 호출 횟수
    assert len(progress_calls) == 4
    assert progress_calls[-1] == (4, 4)
