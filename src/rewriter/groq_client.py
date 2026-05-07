"""Groq Llama 3.1 8B-Instant 클라이언트 (FR-2.3 1차 폴백).

무료 한도: RPM 30.
"""

from __future__ import annotations

from .base import RewriteResult, Rewriter
from .gemini_client import _parse_response


class GroqRewriter(Rewriter):
    name = "groq"

    def __init__(self, *, api_key: str, model: str = "llama-3.1-8b-instant", temperature: float = 0.85, max_tokens: int = 1024) -> None:
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        from groq import Groq

        self._client = Groq(api_key=self.api_key)

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
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"},
        )
        text = completion.choices[0].message.content or ""
        return _parse_response(text, model_used=self.name, model_version=self.model)
