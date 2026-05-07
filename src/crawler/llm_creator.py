"""LLM 완전 창작 소재 (FR-1.1 ① 1순위).

테마·키워드만 입력해 LLM이 모티프(주제·전개·반전 키워드)를 생성한다.
저작권 리스크가 가장 낮은 1순위 소스.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Iterable

from .base import CrawlResult, SourceCrawler

LLMCallable = callable  # type: ignore[assignment]


_MOTIF_PROMPT = """너는 한국어 YouTube Shorts 채널의 콘텐츠 기획자다.
주제 "{theme}"에 대해 15~25초 분량 한국어 쇼츠로 풀어낼 수 있는 소재를 생성한다.

[규칙]
- 욕설·혐오·실명·정치/종교/의료/법률/금융 자문 금지.
- 한국어 한글로만 작성한다. 영어·한자(漢字)·중국어·일본어 문자 사용 금지.
- 중·고등학생이 공감할 수 있는 구체적인 내용을 소재로 한다.

[테마별 처리]
- 공부법·암기·시간관리: 구체적인 수치(시간, 횟수, 효과) 포함. 바로 실천 가능한 팁.
- 수행평가 꿀팁 (체육·국어·도덕·역사·수학·과학·음악·영어·한문·중국어):
  해당 과목·종목의 핵심 기술·개념 팁 위주로 구체적으로 서술.
- 행운 부적: 시험 기간 학생들의 설렘·재미를 담은 오락 콘텐츠.
  "이 영상을 10명에게 공유하면 모든 시험 만점을 받는다는 전설이 있다"는 바이럴 메시지 소재.
  재미·공유 유도 목적이며, 허구적 설정임을 내포한 유머 포맷으로 작성.

[출력 형식 - JSON만]
{{
  "theme": "{theme}",
  "motif_summary": "80~150자 사이의 한국어 소재 개요 (구체적인 방법과 기대 효과 포함)",
  "key_tip": "핵심 포인트 키워드 1개",
  "tone_keywords": ["실용적", "..."],
  "warnings": []
}}
"""


def _in_exam_season(periods: list[dict], lead_days: int = 7) -> bool:
    """오늘 날짜가 시험 기간(start - lead_days ~ end) 이내인지 확인."""
    today = date.today()
    for p in periods:
        try:
            sm, sd = p["start"].split("-")
            em, ed = p["end"].split("-")
            start = date(today.year, int(sm), int(sd)) - timedelta(days=lead_days)
            end   = date(today.year, int(em), int(ed))
            if start <= today <= end:
                return True
        except (KeyError, ValueError):
            continue
    return False


class LLMCreatorCrawler(SourceCrawler):
    """LLM이 모티프를 직접 생성한다."""

    kind = "llm_creator"

    def __init__(
        self,
        *,
        themes: list[str],
        llm_call: LLMCallable,
        seed: int | None = None,
        lucky_charm_themes: list[str] | None = None,
        exam_periods: list[dict] | None = None,
        lucky_charm_lead_days: int = 7,
        lucky_charm_ratio: float = 0.30,
    ) -> None:
        if not themes:
            raise ValueError("themes 리스트가 비어 있습니다.")
        self.themes = themes
        self.llm_call = llm_call
        self._rng = random.Random(seed)
        self.lucky_charm_themes = lucky_charm_themes or []
        self.exam_periods = exam_periods or []
        self.lucky_charm_lead_days = lucky_charm_lead_days
        self.lucky_charm_ratio = lucky_charm_ratio

    def is_available(self) -> bool:
        return self.llm_call is not None and bool(self.themes)

    def _effective_themes(self) -> list[str]:
        """시험 기간이면 행운 부적 테마를 lucky_charm_ratio 비율로 풀에 추가."""
        if (
            self.lucky_charm_themes
            and self.exam_periods
            and _in_exam_season(self.exam_periods, self.lucky_charm_lead_days)
        ):
            # 비율 계산: normal_n : lucky_n ≈ (1-ratio) : ratio
            normal_n = len(self.themes)
            lucky_n = max(1, round(normal_n * self.lucky_charm_ratio / (1 - self.lucky_charm_ratio)))
            repeats = max(1, lucky_n // len(self.lucky_charm_themes))
            return self.themes + self.lucky_charm_themes * repeats
        return self.themes

    def fetch(self, *, limit: int = 10) -> Iterable[CrawlResult]:
        pool = self._effective_themes()
        for _ in range(limit):
            theme = self._rng.choice(pool)
            prompt = _MOTIF_PROMPT.format(theme=theme)
            response = self.llm_call(prompt)
            motif = self._extract_motif(response)
            if motif is None:
                continue
            yield CrawlResult(
                source_kind=self.kind,
                motif=motif,
                raw_text=None,
                source_site=None,
                url=None,
                title=theme,
                metadata={"theme": theme},
            )

    @staticmethod
    def _extract_motif(response: str) -> str | None:
        import json
        import re

        if not response:
            return None
        match = re.search(r"\{[\s\S]*\}", response)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        motif = data.get("motif_summary")
        if not isinstance(motif, str):
            return None
        motif = motif.strip()
        if not (50 <= len(motif) <= 400):
            return None
        return motif
