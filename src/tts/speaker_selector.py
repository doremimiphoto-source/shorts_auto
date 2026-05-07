"""화자 선택 정책 (FR-3.3).

- 콘텐츠 ID 해시 기반 결정론적 선택 (동일 대본 재생성 시 동일 화자)
- 채널 단위 직전 N개 영상과 다른 화자 강제
"""

from __future__ import annotations

import hashlib


def select_speaker(
    *,
    content_hash: str,
    available: list[str],
    recent_used: list[str],
    min_distinct_in_recent: int = 3,
) -> str:
    """결정론적 화자 선택.

    Parameters
    ----------
    content_hash : str
        대본 콘텐츠의 SHA-256 등 안정적 해시.
    available : list[str]
        선택 가능한 화자 ID 목록.
    recent_used : list[str]
        직전 N개 영상에 사용된 화자 ID (최신순).
    min_distinct_in_recent : int
        직전 N개와 다른 화자 강제 (FR-3.3).
    """
    if not available:
        raise ValueError("available 화자 목록이 비어 있습니다.")
    if len(available) == 1:
        return available[0]

    # 1. 콘텐츠 해시를 정수로 변환
    h = int(hashlib.sha256(content_hash.encode("utf-8")).hexdigest(), 16)
    base_idx = h % len(available)

    # 2. 직전 N개와 다른 화자 강제
    blocked = set(recent_used[:min_distinct_in_recent])
    if available[base_idx] not in blocked:
        return available[base_idx]

    # 3. 차단된 경우, 해시 기준 순환 탐색
    for offset in range(1, len(available)):
        cand = available[(base_idx + offset) % len(available)]
        if cand not in blocked:
            return cand

    # 4. 모두 차단된 경우 (가능 화자 < 차단 수): 가장 오래된 사용 화자
    return available[base_idx]
