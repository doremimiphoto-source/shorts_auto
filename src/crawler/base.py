"""소재 수집 추상 인터페이스 (FR-1)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class CrawlResult:
    """단일 소재 수집 결과.

    `raw_text`는 24시간 후 DB에서 자동 삭제 (FR-1.6).
    `motif`는 영구 보관.
    """

    source_kind: str                     # 'llm_creator' | 'reddit' | 'public_domain'
    motif: str                           # 200~1500자 (FR-1.7)
    raw_text: str | None = None          # 1차 수집 시점에만 보유
    source_site: str | None = None
    url: str | None = None
    title: str | None = None
    metadata: dict = field(default_factory=dict)


class SourceCrawler(ABC):
    """소재 수집기 베이스. 각 소스(reddit, llm_creator 등)는 본 인터페이스를 구현."""

    kind: str  # 'reddit' 등 식별자

    @abstractmethod
    def fetch(self, *, limit: int = 10) -> Iterable[CrawlResult]:
        """결과를 yield. 실패 시 예외 발생 (호출자가 재시도/폴백 처리)."""

    def is_available(self) -> bool:
        """API 키나 의존성 등 사전조건이 충족되는지 검사."""
        return True
