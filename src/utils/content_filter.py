"""콘텐츠 필터 (FR-2.5).

차단 키워드 파일을 읽어 텍스트의 위반 여부를 판정하고, 필요 시 마스킹한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class FilterResult:
    """필터링 결과."""
    allowed: bool                # 통과 여부 (모드별 의미: drop=차단/통과, mask=항상 True)
    masked_text: str             # 마스킹 적용된 텍스트 (mask 모드에서만 의미)
    matched_keywords: list[str]  # 적중한 키워드 (있으면 위반 발생)


class ContentFilter:
    """차단 키워드 기반 텍스트 필터.

    Modes
    -----
    - "drop": 키워드 적중 시 allowed=False, masked_text는 원문 그대로
    - "mask": 키워드 적중 부분을 ***로 치환, allowed=True
    """

    def __init__(self, keywords: list[str], *, mode: str = "drop", mask_token: str = "***") -> None:
        self.keywords = [k.strip() for k in keywords if k.strip()]
        if mode not in ("drop", "mask"):
            raise ValueError(f"unsupported mode: {mode}")
        self.mode = mode
        self.mask_token = mask_token

    @classmethod
    def from_file(cls, path: str | Path, *, mode: str = "drop") -> "ContentFilter":
        """`#` 주석 + 빈 줄을 무시하고 키워드 한 줄당 하나로 파싱."""
        p = Path(path)
        if not p.exists():
            return cls([], mode=mode)
        keywords: list[str] = []
        for line in p.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            keywords.append(stripped)
        return cls(keywords, mode=mode)

    def check(self, text: str) -> FilterResult:
        if not text:
            return FilterResult(allowed=True, masked_text=text, matched_keywords=[])
        matched: list[str] = []
        masked = text
        for kw in self.keywords:
            if not kw:
                continue
            if kw in text:
                matched.append(kw)
                if self.mode == "mask":
                    masked = masked.replace(kw, self.mask_token)
        if self.mode == "drop":
            return FilterResult(allowed=not matched, masked_text=text, matched_keywords=matched)
        return FilterResult(allowed=True, masked_text=masked, matched_keywords=matched)
