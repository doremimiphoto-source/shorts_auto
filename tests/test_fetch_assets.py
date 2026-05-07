"""scripts.fetch_assets 헬퍼 함수 테스트."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.fetch_assets import (
    _ia_is_audiobook_like,
    _ia_pick_audio_file,
    _load_metadata,
    _parse_ia_length,
    _save_metadata,
)


def test_metadata_load_missing_returns_template(tmp_path: Path) -> None:
    data = _load_metadata(tmp_path / "missing.json")
    assert data == {"schema_version": 1, "items": []}


def test_metadata_save_and_load_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "m.json"
    payload = {"schema_version": 1, "items": [{"id": 1, "name": "한글"}]}
    _save_metadata(p, payload)
    loaded = _load_metadata(p)
    assert loaded == payload
    # UTF-8로 저장되어 한글 보존
    assert "한글" in p.read_text(encoding="utf-8")


def test_ia_pick_audio_file_prefers_smallest_mp3(mocker) -> None:
    fake_response = mocker.Mock()
    fake_response.json.return_value = {
        "files": [
            {"name": "track_long.mp3", "size": "5000000", "length": "120.0"},
            {"name": "track_short.mp3", "size": "1500000", "length": "60.0"},
            {"name": "cover.jpg", "size": "500"},
        ]
    }
    fake_response.raise_for_status.return_value = None
    client = mocker.Mock()
    client.get.return_value = fake_response

    log = mocker.Mock()
    result = _ia_pick_audio_file(client, "id1", log=log)
    assert result is not None
    name, size, duration = result
    assert name == "track_short.mp3"
    assert size == 1_500_000
    assert duration == 60.0


def test_ia_pick_audio_file_skips_spectrogram_and_text(mocker) -> None:
    fake_response = mocker.Mock()
    fake_response.json.return_value = {
        "files": [
            {"name": "track_spectrogram.mp3", "size": "100"},
            {"name": "track_text.mp3", "size": "100"},
            {"name": "track_real.mp3", "size": "200000"},
        ]
    }
    fake_response.raise_for_status.return_value = None
    client = mocker.Mock()
    client.get.return_value = fake_response

    result = _ia_pick_audio_file(client, "id", log=mocker.Mock())
    assert result is not None
    assert result[0] == "track_real.mp3"


def test_ia_pick_audio_file_returns_none_when_no_audio(mocker) -> None:
    fake_response = mocker.Mock()
    fake_response.json.return_value = {"files": [{"name": "image.jpg"}]}
    fake_response.raise_for_status.return_value = None
    client = mocker.Mock()
    client.get.return_value = fake_response

    assert _ia_pick_audio_file(client, "abc", log=mocker.Mock()) is None


def test_ia_pick_audio_file_handles_http_error(mocker) -> None:
    import httpx

    client = mocker.Mock()
    client.get.side_effect = httpx.HTTPError("network down")

    log = mocker.Mock()
    assert _ia_pick_audio_file(client, "abc", log=log) is None
    log.warning.assert_called_once()


def test_ia_audiobook_blacklist() -> None:
    assert _ia_is_audiobook_like("the_art_of_war_librivox", "The Art of War")
    assert _ia_is_audiobook_like("OTRR_drama_singles", "Old Time Radio")
    assert _ia_is_audiobook_like("any_id", "The Adventures of Sherlock Holmes")
    assert not _ia_is_audiobook_like("indie_ambient_pack", "Ambient Drone Collection")
    assert not _ia_is_audiobook_like("musicgen_calm_001", "calm piano")


def test_parse_ia_length_decimal() -> None:
    assert _parse_ia_length("60.5") == 60.5


def test_parse_ia_length_hms() -> None:
    assert _parse_ia_length("0:02:23") == 143.0
    assert _parse_ia_length("1:30") == 90.0


def test_parse_ia_length_invalid() -> None:
    assert _parse_ia_length("") is None
    assert _parse_ia_length("abc") is None
