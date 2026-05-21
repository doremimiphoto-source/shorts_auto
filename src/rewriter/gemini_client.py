"""Gemini 2.5 Flash 클라이언트 (FR-2 주력).

무료 한도: RPM 15 / RPD 1,500. 자율 제한은 별도 토큰 버킷에서 관리한다.
"""

from __future__ import annotations

import json
import re

from .base import RewriteResult, Rewriter


class GeminiRewriter(Rewriter):
    name = "gemini"

    def __init__(self, *, api_key: str, model: str = "gemini-2.5-flash", temperature: float = 0.85, max_output_tokens: int = 8192, timeout_sec: int = 90) -> None:
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
        import google.genai as genai

        self._client = genai.Client(
            api_key=self.api_key,
            http_options={"timeout": self.timeout_sec},
        )

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

        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
                response_mime_type="application/json",
            ),
        )
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
