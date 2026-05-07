"""Reddit 공식 API 기반 소재 수집 (FR-1.1 ②).

CC-BY 호환 서브레딧만 대상으로 하며, 원문은 24h 내 폐기 후 모티프만 보관 (FR-1.6).
구현 자체는 후속 단계에서 진행 (현재는 인터페이스 스켈레톤).
"""

from __future__ import annotations

from typing import Iterable

from .base import CrawlResult, SourceCrawler


class RedditCrawler(SourceCrawler):
    kind = "reddit"

    def __init__(self, *, subreddits: list[str], client_id: str = "", client_secret: str = "", user_agent: str = "") -> None:
        self.subreddits = subreddits
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent

    def is_available(self) -> bool:
        return bool(self.subreddits and self.client_id and self.client_secret)

    def fetch(self, *, limit: int = 10) -> Iterable[CrawlResult]:
        # TODO: PRAW 또는 httpx로 https://oauth.reddit.com/r/<sub>/top.json 호출
        # - rate limit 1 req / 3 sec 준수 (FR-1.4)
        # - 본문 → 모티프 추출 → CrawlResult 생성
        raise NotImplementedError("RedditCrawler는 후속 단계에서 구현 예정")
