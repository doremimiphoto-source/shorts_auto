"""소재 수집 (FR-1).

저작권 안전성 우선:
1. LLM 완전 창작 (`llm_creator`)
2. Reddit 공식 API CC-BY 호환 서브레딧 (`reddit`)
3. 공공 도메인 (`public_domain`)
4. 일반 게시판 (모티프만 추출, 원문 즉시 폐기)
"""

from .base import CrawlResult, SourceCrawler

__all__ = ["CrawlResult", "SourceCrawler"]
