"""src.tts.speaker_selector 단위 테스트."""

from __future__ import annotations

import pytest

from src.tts.speaker_selector import select_speaker


VOICES = ["v1", "v2", "v3", "v4", "v5"]


def test_deterministic_same_hash_same_speaker() -> None:
    h = "abc123"
    s1 = select_speaker(content_hash=h, available=VOICES, recent_used=[])
    s2 = select_speaker(content_hash=h, available=VOICES, recent_used=[])
    assert s1 == s2


def test_avoids_recent_used() -> None:
    h = "abc123"
    # base_idx의 결과를 우선 확보
    base = select_speaker(content_hash=h, available=VOICES, recent_used=[])
    # base 화자를 차단했을 때 다른 화자 반환
    result = select_speaker(content_hash=h, available=VOICES, recent_used=[base], min_distinct_in_recent=1)
    assert result != base


def test_avoids_top_n_recent() -> None:
    h = "xyz789"
    # 직전 3개를 차단하면 결과는 그 3개 중에 들어가지 않는다
    blocked = ["v1", "v2", "v3"]
    result = select_speaker(content_hash=h, available=VOICES, recent_used=blocked, min_distinct_in_recent=3)
    assert result not in blocked


def test_only_blocked_falls_back() -> None:
    # 가능 화자보다 많은 차단이면 base_idx 그대로 반환 (강제 폴백)
    h = "fallback"
    blocked = VOICES.copy()
    result = select_speaker(content_hash=h, available=VOICES, recent_used=blocked, min_distinct_in_recent=10)
    assert result in VOICES


def test_single_speaker() -> None:
    result = select_speaker(content_hash="anything", available=["only"], recent_used=["only"])
    assert result == "only"


def test_empty_available_raises() -> None:
    with pytest.raises(ValueError):
        select_speaker(content_hash="x", available=[], recent_used=[])
