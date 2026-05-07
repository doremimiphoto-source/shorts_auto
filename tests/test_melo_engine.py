"""src.tts.melo_engine 단위 테스트 (실제 모델 로딩은 mock)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.tts.melo_engine import _SPEED_PROFILES, MeloEngine, MeloVoice


def test_default_voices_match_speed_profiles() -> None:
    eng = MeloEngine()
    assert set(eng.list_speakers()) == set(_SPEED_PROFILES.keys())
    for vid, voice in eng.voices.items():
        assert voice.speed == _SPEED_PROFILES[vid]
        assert voice.melo_speaker_key == "KR"


def test_custom_voices() -> None:
    eng = MeloEngine(voices=[
        MeloVoice(voice_id="custom_a", speed=0.8),
        MeloVoice(voice_id="custom_b", speed=1.1),
    ])
    assert eng.list_speakers() == ["custom_a", "custom_b"]


def test_engine_lazy_load_not_triggered_on_init() -> None:
    eng = MeloEngine()
    assert eng._model is None


class _FakeSpk2Id:
    """MeloTTS HParams 모방. vars() 로 키 조회 가능."""
    def __init__(self, mapping: dict[str, int]) -> None:
        for k, v in mapping.items():
            setattr(self, k, v)


def _stub_engine(mocker, *, with_kr: bool = True, sample_rate: int = 44100):
    eng = MeloEngine()
    spk2id = _FakeSpk2Id({"KR": 0} if with_kr else {"OTHER": 5})
    fake_model = mocker.Mock()
    fake_model.hps.data.spk2id = spk2id

    def fake_tts_to_file(*, text, speaker_id, output_path, speed, quiet=False):
        # 단순 wav 헤더 + 짧은 데이터로 출력 파일 생성
        import wave

        with wave.open(output_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            # 1초 무음
            w.writeframes(b"\x00\x00" * sample_rate)

    fake_model.tts_to_file.side_effect = fake_tts_to_file
    eng._model = fake_model
    return eng, fake_model


def test_synthesize_uses_KR_speaker(tmp_path: Path, mocker) -> None:
    eng, fake_model = _stub_engine(mocker)
    out = tmp_path / "out.wav"
    result = eng.synthesize(text="안녕하세요.", out_path=out, speaker_id="kr_soft_default")
    assert out.exists()
    assert result.engine == "melo"
    assert result.speaker_id == "kr_soft_default"
    assert result.metadata["melo_speaker_key"] == "KR"
    assert result.metadata["speed"] == _SPEED_PROFILES["kr_soft_default"]
    fake_model.tts_to_file.assert_called_once()
    # speaker_id 인자가 한국어 화자 인덱스 0인지 확인
    kwargs = fake_model.tts_to_file.call_args.kwargs
    assert kwargs["speaker_id"] == 0
    assert abs(kwargs["speed"] - 0.95) < 1e-6


def test_synthesize_falls_back_to_first_speaker_if_kr_missing(tmp_path: Path, mocker) -> None:
    eng, fake_model = _stub_engine(mocker, with_kr=False)
    out = tmp_path / "out.wav"
    result = eng.synthesize(text="x", out_path=out, speaker_id="kr_soft_default")
    assert result.metadata["melo_speaker_key"] == "OTHER"
    kwargs = fake_model.tts_to_file.call_args.kwargs
    assert kwargs["speaker_id"] == 5


def test_synthesize_empty_text_raises() -> None:
    eng = MeloEngine()
    with pytest.raises(ValueError):
        eng.synthesize(text="", out_path=Path("x.wav"))


def test_synthesize_unknown_speaker_raises(tmp_path: Path, mocker) -> None:
    eng, _ = _stub_engine(mocker)
    with pytest.raises(KeyError):
        eng.synthesize(text="hi", out_path=tmp_path / "out.wav", speaker_id="not_registered")


def test_synthesize_missing_output_raises(tmp_path: Path, mocker) -> None:
    eng = MeloEngine()
    spk2id = _FakeSpk2Id({"KR": 0})
    fake_model = mocker.Mock()
    fake_model.hps.data.spk2id = spk2id
    # tts_to_file 가 파일을 생성하지 않는 시나리오
    fake_model.tts_to_file.side_effect = lambda **kw: None
    eng._model = fake_model
    with pytest.raises(RuntimeError, match="합성 결과 누락"):
        eng.synthesize(text="hi", out_path=tmp_path / "missing.wav")
