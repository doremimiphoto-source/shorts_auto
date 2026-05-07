"""src.utils.hook_pattern 테스트."""

from __future__ import annotations

import pytest

from src.utils.hook_pattern import select_hook_pattern


POOL = ["question", "shock", "number", "dialogue", "confession"]


def test_avoids_recent_window() -> None:
    recent = ["question", "shock", "number"]
    p = select_hook_pattern(pool=POOL, recent_used=recent, no_repeat_window=3)
    assert p not in recent


def test_seed_deterministic() -> None:
    p1 = select_hook_pattern(pool=POOL, recent_used=[], seed="abc")
    p2 = select_hook_pattern(pool=POOL, recent_used=[], seed="abc")
    assert p1 == p2


def test_round_robin_picks_oldest_unused() -> None:
    # 직전 사용 [question(가장 최신), shock, number] → "dialogue", "confession" 중 가장 오래됨 우선
    p = select_hook_pattern(pool=POOL, recent_used=["question", "shock", "number"], no_repeat_window=3)
    assert p in {"dialogue", "confession"}


def test_no_repeat_window_zero_allows_all() -> None:
    p = select_hook_pattern(pool=POOL, recent_used=["question"], no_repeat_window=0, seed="x")
    # 차단 없음 → 풀 전체에서 선택
    assert p in POOL


def test_all_blocked_falls_back_to_pool() -> None:
    p = select_hook_pattern(pool=POOL, recent_used=POOL, no_repeat_window=10, seed="x")
    assert p in POOL


def test_empty_pool_raises() -> None:
    with pytest.raises(ValueError):
        select_hook_pattern(pool=[], recent_used=[])
