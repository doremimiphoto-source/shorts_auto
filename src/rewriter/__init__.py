"""대본 생성 (FR-2).

폴백 체인: Gemini Flash → Groq Llama 3.1 8B → Ollama Gemma 2 2B (CPU).
GPU 미보유 환경에서 클라우드 무료 API를 1순위로 사용한다.
"""

from .base import RewriteResult, Rewriter

__all__ = ["RewriteResult", "Rewriter"]
