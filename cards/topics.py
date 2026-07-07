"""콘텐츠 주제 로테이션 — 매일 다른 주제로 자동 게시 (반복 방지).

날짜(연중 일수) 기반으로 큐레이션 리스트를 순환 선택한다.
외부 상태 없이 결정적(deterministic)으로 동작 → launchd 자동화에 적합.
"""

from __future__ import annotations

import datetime


# ── V2 여행: (지역, 테마) — 전부 실재하는 지역 ──────────────────────────────────
V2_TOPICS: list[tuple[str, str]] = [
    ("Southeast Asia", "secret beaches with few tourists"),
    ("Portugal", "underrated coastal towns"),
    ("Japan", "quiet towns most tourists skip"),
    ("Italy", "hidden villages off the tourist trail"),
    ("Greece", "islands beyond Santorini and Mykonos"),
    ("Mexico", "lesser-known beach towns"),
    ("Vietnam", "underrated towns and beaches"),
    ("Spain", "hidden coastal and mountain towns"),
    ("Indonesia", "islands beyond Bali"),
    ("Croatia", "quiet alternatives to Dubrovnik"),
    ("Philippines", "hidden islands and beaches"),
    ("Thailand", "quiet islands beyond Phuket"),
    ("Turkey", "underrated coastal spots"),
    ("Morocco", "lesser-known towns worth visiting"),
    ("Colombia", "underrated towns and coast"),
    ("Albania", "hidden Mediterranean coast"),
]

# ── V3 K-뷰티: 카테고리 (kbeauty._CATEGORY_QUERY 키와 일치) ────────────────────
V3_CATEGORIES: list[str] = [
    "serum", "sunscreen", "toner", "cleanser",
    "sheet mask", "essence", "cushion", "lip tint",
]


def _day_index() -> int:
    """연중 일수 (1~366). 날짜 기반 결정적 순환용."""
    return datetime.datetime.utcnow().timetuple().tm_yday


def pick_v2(offset: int = 0) -> tuple[str, str]:
    """오늘의 여행 (지역, 테마)."""
    return V2_TOPICS[(_day_index() + offset) % len(V2_TOPICS)]


def pick_v3(offset: int = 0) -> str:
    """오늘의 K-뷰티 카테고리."""
    return V3_CATEGORIES[(_day_index() + offset) % len(V3_CATEGORIES)]
