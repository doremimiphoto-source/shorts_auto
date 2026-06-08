"""한국어 텍스트 처리 유틸리티."""

from __future__ import annotations

import re

# 허용 문자: 한글·영문·숫자·공백·기본구두점·이모지만 통과
# 제거 대상: 아랍어·베트남 특수문자·히라가나·카타카나·한자 등 모든 기타 외국 문자
_ALLOWED_ONLY = re.compile(
    "["
    "^가-힣"          # 한글 완성형
    "ㄱ-ㆎ"            # 한글 자모 (ㄱ~ㅣ)
    "ᄀ-ᇿ"            # 한글 자모 확장
    "A-Za-z0-9"                # 영문·숫자
    " \t\r\n"                  # 공백
    r"!?,.\-:;\"'()\[\]#%&*+/@_~^"  # 기본 ASCII 구두점
    "\U0001F300-\U0001FAFF"   # 이모지 (Misc Symbols ~ Extended-A)
    "☀-➿"            # 기타기호·화살표
    "️‍⃣"      # 이모지 수식자 (VS16, ZWJ, keycap)
    "]"
)


def strip_cjk(text: str) -> str:
    """한글·영문·숫자·이모지·기본구두점만 남기고 나머지를 제거한다.

    제거 대상: 한자·히라가나·카타카나·아랍어·베트남 특수문자 등 모든 비허용 문자.
    기존 함수명(strip_cjk) 유지 — 호출부 변경 없음.
    """
    cleaned = _ALLOWED_ONLY.sub("", text)
    cleaned = re.sub(r" {2,}", " ", cleaned).strip()
    return cleaned
