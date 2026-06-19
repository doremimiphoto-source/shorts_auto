"""Gemini 2.0 Flash 클라이언트 (FR-2 주력).

무료 한도: RPM 15 / RPD 1,500. 자율 제한은 별도 토큰 버킷에서 관리한다.
"""

from __future__ import annotations

import json
import logging
import re
import time

from .base import RewriteResult, Rewriter

log = logging.getLogger(__name__)


def _parse_retry_after(exc: Exception) -> float:
    """429 에러 메시지에서 retry 대기 시간(초) 파싱. 없으면 60초 기본값."""
    match = re.search(r'retry in ([\d.]+)s', str(exc), re.IGNORECASE)
    return float(match.group(1)) + 2.0 if match else 60.0


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "resource_exhausted" in msg or "rate" in msg


class GeminiRewriter(Rewriter):
    name = "gemini"

    def __init__(self, *, api_key: str, model: str = "gemini-2.0-flash", temperature: float = 0.85, max_output_tokens: int = 8192, timeout_sec: int = 120) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.timeout_sec = timeout_sec
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        import os
        import google.genai as genai

        # SSL_CERT_FILE(edge-tts용 certifi 경로)이 google-genai httpx 핸드셰이크를 방해.
        # 클라이언트 초기화 중에만 제거하고 복원한다.
        _ssl = os.environ.pop("SSL_CERT_FILE", None)
        _ca  = os.environ.pop("REQUESTS_CA_BUNDLE", None)
        try:
            self._client = genai.Client(
                api_key=self.api_key,
                http_options={"timeout": self.timeout_sec},
            )
        finally:
            if _ssl is not None:
                os.environ["SSL_CERT_FILE"] = _ssl
            if _ca is not None:
                os.environ["REQUESTS_CA_BUNDLE"] = _ca

    def generate(
        self,
        *,
        theme: str,
        motif: str,
        hook_pattern: str,
        prompt_template: str,
    ) -> RewriteResult:
        self._ensure_client()
        prompt = (
            prompt_template
            .replace("{{theme}}", theme)
            .replace("{{motif}}", motif)
            .replace("{{hook_pattern}}", hook_pattern)
        )
        assert self._client is not None
        from google.genai import types as genai_types

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        temperature=self.temperature,
                        max_output_tokens=self.max_output_tokens,
                        response_mime_type="application/json",
                    ),
                )
                break
            except Exception as exc:
                if attempt >= max_retries or not _is_rate_limit(exc):
                    raise
                wait = _parse_retry_after(exc)
                log.warning("gemini_rate_limit_retry", extra={"attempt": attempt + 1, "wait_sec": wait})
                time.sleep(wait)

        text = response.text or ""
        return _parse_response(text, model_used=self.name, model_version=self.model)


def _parse_response(raw: str, *, model_used: str, model_version: str) -> RewriteResult:
    """LLM 응답(JSON 문자열) → RewriteResult."""
    if not raw:
        raise ValueError("LLM이 빈 응답을 반환했습니다.")
    # 코드펜스/잡문 제거: 첫 JSON 객체만 추출
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError(f"응답에서 JSON을 찾을 수 없습니다: {raw[:200]}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 파싱 실패: {e}") from e

    return RewriteResult(
        hook=str(data.get("hook", "")).strip(),
        body=str(data.get("body", "")).strip(),
        twist=str(data.get("twist", "")).strip(),
        title=str(data.get("title", "")).strip(),
        hashtags=list(data.get("hashtags") or []),
        hook_pattern_used=str(data.get("hook_pattern_used", "")).strip(),
        warnings=list(data.get("warnings") or []),
        model_used=model_used,
        model_version=model_version,
    )
