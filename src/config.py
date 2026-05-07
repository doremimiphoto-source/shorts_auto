"""설정 로더.

`config.yaml`과 `.env`를 통합하여 단일 `Settings` 객체로 노출한다.
- 비밀 정보(API 키)는 환경변수에서만 로드한다.
- 운영 파라미터는 `config.yaml`에서 로드한다.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Secrets(BaseSettings):
    """`.env`에서만 로드되는 비밀 정보."""

    gemini_api_key: str = ""
    groq_api_key: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "gemma2:2b"

    piper_bin_path: str = "piper"
    piper_voice_model: str = "models/piper/ko_KR-kss-medium.onnx"
    piper_voice_config: str = "models/piper/ko_KR-kss-medium.onnx.json"

    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    youtube_client_secret_path: str = "credentials/client_secret.json"
    youtube_token_path: str = "credentials/token.json"
    youtube_channel_id: str = ""

    discord_webhook_url: str = ""

    log_level: str = "INFO"
    timezone: str = "Asia/Seoul"
    app_env: str = "development"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class AppConfig(BaseModel):
    name: str = "shorts-auto"
    version: str = "1.0.0"
    timezone: str = "Asia/Seoul"


class PipelineConfig(BaseModel):
    daily_target_count: int = 3
    schedule_times: list[str] = ["09:00", "15:00", "21:00"]
    upload_jitter_minutes: int = 20
    lock_file: str = "data/pipeline.lock"
    killswitch_file: str = "data/killswitch.flag"


class Settings(BaseModel):
    """통합 설정."""

    secrets: Secrets
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def app(self) -> AppConfig:
        return AppConfig(**self.raw.get("app", {}))

    @property
    def pipeline(self) -> PipelineConfig:
        return PipelineConfig(**self.raw.get("pipeline", {}))

    def section(self, key: str) -> dict[str, Any]:
        """`config.yaml`의 임의 섹션을 dict로 반환.

        구체 모델로 매핑되지 않은 섹션(crawler/rewriter/tts/...)은 본 메서드로 접근한다.
        """
        return dict(self.raw.get(key, {}))

    def project_path(self, relative: str | Path) -> Path:
        """프로젝트 루트 기준 상대 경로를 절대 경로로 변환."""
        p = Path(relative)
        if p.is_absolute():
            return p
        return PROJECT_ROOT / p


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config.yaml 최상위는 mapping 이어야 합니다: {path}")
    return data


@lru_cache(maxsize=1)
def get_settings(config_path: str | Path | None = None) -> Settings:
    """전역 설정 인스턴스 (캐시).

    Parameters
    ----------
    config_path : str | Path | None
        명시 경로. None이면 `<project_root>/config.yaml` → `config.yaml.example` 순으로 탐색.
    """
    if config_path is None:
        candidate = PROJECT_ROOT / "config.yaml"
        if not candidate.exists():
            candidate = PROJECT_ROOT / "config.yaml.example"
        config_path = candidate
    raw = _load_yaml(Path(config_path))
    secrets = Secrets()
    return Settings(secrets=secrets, raw=raw)
