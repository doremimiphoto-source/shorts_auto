"""src.config 설정 로더 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Settings, _load_yaml, get_settings


def test_load_yaml_returns_dict(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text("app:\n  name: test\n  version: 0.1.0\n", encoding="utf-8")
    data = _load_yaml(p)
    assert data == {"app": {"name": "test", "version": "0.1.0"}}


def test_load_yaml_missing_returns_empty(tmp_path: Path) -> None:
    assert _load_yaml(tmp_path / "missing.yaml") == {}


def test_load_yaml_rejects_non_mapping(tmp_path: Path) -> None:
    p = tmp_path / "list.yaml"
    p.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ValueError):
        _load_yaml(p)


def test_settings_section_returns_dict() -> None:
    from src.config import Secrets

    s = Settings(secrets=Secrets(), raw={"crawler": {"limit": 10}})
    assert s.section("crawler") == {"limit": 10}
    assert s.section("missing") == {}


def test_get_settings_uses_example_when_no_yaml() -> None:
    # config.yaml.example 가 존재해야 한다 (스켈레톤 단계)
    get_settings.cache_clear()
    s = get_settings()
    assert s.app.name == "shorts-auto"
    # cache reset for other tests
    get_settings.cache_clear()


def test_project_path_relative() -> None:
    from src.config import PROJECT_ROOT, Secrets

    s = Settings(secrets=Secrets(), raw={})
    assert s.project_path("data/x.db") == PROJECT_ROOT / "data" / "x.db"


def test_project_path_absolute_unchanged(tmp_path: Path) -> None:
    from src.config import Secrets

    s = Settings(secrets=Secrets(), raw={})
    assert s.project_path(str(tmp_path / "abs.db")) == tmp_path / "abs.db"
