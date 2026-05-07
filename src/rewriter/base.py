"""대본 생성 추상 인터페이스 (FR-2)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RewriteResult:
    """대본 생성 결과 (FR-2.4 출력 구조)."""

    hook: str
    body: str
    twist: str
    title: str
    hashtags: list[str] = field(default_factory=list)
    hook_pattern_used: str = ""
    model_used: str = ""
    model_version: str = ""
    full_text: str = ""                       # hook + body + twist
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.full_text:
            self.full_text = " ".join(s for s in (self.hook, self.body, self.twist) if s).strip()


class Rewriter(ABC):
    """대본 생성기 베이스. 각 LLM 백엔드는 본 인터페이스를 구현."""

    name: str          # 'gemini' | 'groq' | 'ollama'
    model: str

    @abstractmethod
    def generate(
        self,
        *,
        theme: str,
        motif: str,
        hook_pattern: str,
        prompt_template: str,
    ) -> RewriteResult:
        """대본 생성. 실패 시 예외 발생 (호출자가 폴백 처리)."""

    def is_available(self) -> bool:
        """API 키 또는 로컬 서버가 사용 가능한지 검사."""
        return True
