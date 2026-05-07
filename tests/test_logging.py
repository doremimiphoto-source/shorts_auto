"""src.utils.logging PII 마스킹 테스트."""

from __future__ import annotations

from src.utils.logging import _mask_value


def test_masks_bearer_token() -> None:
    masked = _mask_value("Authorization: Bearer ya29.A0AfH6SMBxxxxxxx")
    assert "ya29.A0AfH6SMBxxxxxxx" not in masked
    assert "REDACTED" in masked


def test_masks_json_refresh_token() -> None:
    raw = '{"refresh_token": "1//04xyzabc123","other":"keep"}'
    masked = _mask_value(raw)
    assert "1//04xyzabc123" not in masked
    assert "keep" in masked


def test_masks_email() -> None:
    raw = "user contacted us at john.doe@example.com about issue"
    masked = _mask_value(raw)
    assert "john.doe" not in masked
    assert "@example.com" in masked


def test_masks_google_api_key() -> None:
    raw = "key=AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    masked = _mask_value(raw)
    assert "AIzaSyBxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" not in masked
    assert "GOOGLE_KEY" in masked


def test_masks_groq_api_key() -> None:
    raw = "Authorization: gsk_abcdefghijklmnopqrstuvwxyz1234"
    masked = _mask_value(raw)
    assert "gsk_abcdefghijklmnopqrstuvwxyz1234" not in masked


def test_recursive_dict_masking() -> None:
    raw = {
        "level1": {
            "api_key": "AIzaSyAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "safe": "preserved",
        }
    }
    masked = _mask_value(raw)
    assert masked["level1"]["safe"] == "preserved"
    # api_key 값이 마스킹 됐어야 함
    assert "AIzaSyAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in str(masked)


def test_list_masking() -> None:
    raw = ["AIzaSyAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "normal", "user@gmail.com"]
    masked = _mask_value(raw)
    assert "AIzaSyAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in masked
    assert "normal" in masked
    assert "user@gmail.com" not in str(masked)


def test_passthrough_non_string() -> None:
    assert _mask_value(123) == 123
    assert _mask_value(True) is True
    assert _mask_value(None) is None
