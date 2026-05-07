"""Hook 패턴 순환 (FR-2.7).

직전 N개 대본과 동일 패턴을 금지하며, 풀 안에서 결정론적/순환적으로 다음 패턴을 선택한다.
"""

from __future__ import annotations

import hashlib


def select_hook_pattern(
    *,
    pool: list[str],
    recent_used: list[str],
    no_repeat_window: int = 5,
    seed: str | None = None,
) -> str:
    """Hook 패턴 선택.

    Parameters
    ----------
    pool : list[str]
        가용 패턴 풀.
    recent_used : list[str]
        직전 사용된 패턴 (최신순).
    no_repeat_window : int
        직전 N개 패턴 차단.
    seed : str | None
        결정론적 선택용 시드 (예: 모티프 해시). None이면 round-robin.
    """
    if not pool:
        raise ValueError("pool이 비어 있습니다.")
    blocked = set(recent_used[:no_repeat_window])
    candidates = [p for p in pool if p not in blocked]
    if not candidates:
        # 차단이 너무 많아 모두 막힌 경우 — 가장 오래된 사용 패턴부터 선택
        candidates = pool

    if seed is None:
        # round-robin: 가장 오래된 미사용 패턴 우선
        used_index = {p: i for i, p in enumerate(recent_used)}
        candidates.sort(key=lambda p: used_index.get(p, 10**9))
        return candidates[0]

    h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    return candidates[h % len(candidates)]
