"""재시도 정책 (FR-1.8, §3.2).

지수 백오프 + 최대 재시도 횟수. tenacity 래퍼.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


T = TypeVar("T")


def retry_call(
    fn: Callable[[], T],
    *,
    max_attempts: int = 3,
    backoff_base: float = 2.0,
    backoff_max: float = 30.0,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """`fn`을 지수 백오프로 재시도. 성공 시 결과 반환, 모두 실패 시 마지막 예외 raise."""
    for attempt in Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=backoff_base, max=backoff_max),
        retry=retry_if_exception_type(retry_on),
        reraise=True,
    ):
        with attempt:
            return fn()
    raise RuntimeError("unreachable")  # pragma: no cover
