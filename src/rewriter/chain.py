"""LLM 폴백 체인 오케스트레이터 (FR-2.2, FR-2.3).

체인 순서대로 시도, 각 백엔드의 예외/한도 초과 시 다음으로 넘어간다.
"""

from __future__ import annotations

import logging

from .base import RewriteResult, Rewriter

_log = logging.getLogger(__name__)


class RewriterChain:
    """여러 Rewriter 백엔드를 순차 시도하는 폴백 체인."""

    def __init__(self, backends: list[Rewriter]) -> None:
        if not backends:
            raise ValueError("backends 리스트가 비어 있습니다.")
        self.backends = backends

    def generate(
        self,
        *,
        theme: str,
        motif: str,
        hook_pattern: str,
        prompt_template: str,
    ) -> RewriteResult:
        last_error: Exception | None = None
        for backend in self.backends:
            if not backend.is_available():
                continue
            try:
                return backend.generate(
                    theme=theme,
                    motif=motif,
                    hook_pattern=hook_pattern,
                    prompt_template=prompt_template,
                )
            except Exception as e:
                _log.warning("llm_backend_failed", extra={"backend": backend.name, "error": repr(e)[:200]})
                last_error = e
                continue
        raise RuntimeError(f"모든 LLM 백엔드 실패. last_error={last_error!r}")
