"""한국어 텍스트 처리 유틸리티."""

from __future__ import annotations

import re

# 히라가나·카타카나·한자(CJK)를 제거하는 정규식
# 보존: 한글(AC00-D7A3), 영어, 숫자, 이모지, 일반 구두점
_CJK_STRIP = re.compile(
    r"[぀-ゟ"   # 히라가나
    r"゠-ヿ"    # 카타카나
    r"一-鿿"    # CJK 통합 한자
    r"㐀-䶿"    # CJK 확장 A
    r"豈-﫿]"   # CJK 호환 한자
)


def strip_cjk(text: str) -> str:
    """한자·히라가나·카타카나를 제거하고 공백을 정리한다.

    한글·영어·숫자·이모지·구두점은 유지된다.
    """
    cleaned = _CJK_STRIP.sub("", text)
    # 연속 공백 정리
    cleaned = re.sub(r" {2,}", " ", cleaned).strip()
    return cleaned
