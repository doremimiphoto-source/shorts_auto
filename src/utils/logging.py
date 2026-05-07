"""구조화 로깅 (JSON Lines + PII 마스킹).

FR-8.1: 모든 단계별 로그를 logs/YYYY-MM-DD.log에 JSON Lines 포맷으로 기록.
A5: 로그에 토큰/PII 노출 방지 (정규식 마스킹).
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog


# ---------- PII 마스킹 ----------
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # OAuth/Bearer 토큰
    (re.compile(r"(Bearer\s+)([A-Za-z0-9._\-]+)"), r"\1***REDACTED***"),
    # JSON 내 흔한 시크릿 키
    (re.compile(r'("(?:refresh_token|access_token|api_key|client_secret|authorization|password)"\s*:\s*")([^"]+)(")', re.IGNORECASE),
     r"\1***REDACTED***\3"),
    # 이메일 (외부 PII)
    (re.compile(r"\b([A-Za-z0-9._%+\-]+)@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b"),
     r"***EMAIL***@\2"),
    # AIza... (Google API key 패턴)
    (re.compile(r"\b(AIza[0-9A-Za-z_\-]{20,})\b"), "***GOOGLE_KEY***"),
    # gsk_... (Groq API key 패턴)
    (re.compile(r"\b(gsk_[0-9A-Za-z]{20,})\b"), "***GROQ_KEY***"),
]


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        masked = value
        for pat, repl in _PII_PATTERNS:
            masked = pat.sub(repl, masked)
        return masked
    if isinstance(value, dict):
        return {k: _mask_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_mask_value(v) for v in value)
    return value


def _pii_mask_processor(_logger: Any, _name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return {k: _mask_value(v) for k, v in event_dict.items()}


# ---------- 설정 ----------
def setup_logging(
    log_dir: str | Path = "logs",
    level: str = "INFO",
    *,
    project_root: Path | None = None,
    daily_rotation: bool = True,
) -> None:
    """structlog + 표준 logging을 초기화한다.

    - 콘솔: 사람이 읽기 쉬운 형식
    - 파일: JSON Lines, 일자별 (YYYY-MM-DD.log)
    """
    root = project_root or Path.cwd()
    log_path = Path(log_dir)
    if not log_path.is_absolute():
        log_path = root / log_path
    log_path.mkdir(parents=True, exist_ok=True)

    if daily_rotation:
        date_str = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
        log_file = log_path / f"{date_str}.log"
    else:
        log_file = log_path / "app.log"

    # 표준 logging: 파일은 JSON 한 줄, 콘솔은 사람이 읽기 좋게
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(level.upper())

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=False),
            _pii_mask_processor,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """모듈/단계용 logger.

    `name`은 일반적으로 모듈명 또는 파이프라인 stage("crawl", "rewrite", "tts" 등).
    """
    return structlog.get_logger(name) if name else structlog.get_logger()
