"""Ollama 로컬 LLM 클라이언트 (FR-2.3 2차 폴백, CPU 비상용).

인터넷 단절·전체 클라우드 한도 초과 시에만 사용. 모델: Gemma 2 2B (Apache 2.0).
"""

from __future__ import annotations

from .base import RewriteResult, Rewriter
from .gemini_client import _parse_response


class OllamaRewriter(Rewriter):
    name = "ollama"

    def __init__(self, *, model: str = "gemma2:2b", base_url: str = "http://127.0.0.1:11434", temperature: float = 0.85) -> None:
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self._client = None

    def is_available(self) -> bool:
        """Ollama 서버가 살아있고, 지정 모델이 다운로드되어 있을 때만 True."""
        try:
            import urllib.request
            import json as _json
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=2) as r:
                data = _json.loads(r.read())
            names = [m.get("name", "") for m in data.get("models", [])]
            base = self.model.split(":")[0]
            return any(n == self.model or n.startswith(base + ":") for n in names)
        except Exception:
            return False

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        import ollama

        self._client = ollama.Client(host=self.base_url)

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
        response = self._client.generate(
            model=self.model,
            prompt=prompt,
            format="json",
            options={"temperature": self.temperature},
        )
        text = response.get("response", "") if isinstance(response, dict) else getattr(response, "response", "")
        return _parse_response(text or "", model_used=self.name, model_version=self.model)
