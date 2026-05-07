"""src.utils.content_filter 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.content_filter import ContentFilter


def test_drop_mode_blocks_match() -> None:
    cf = ContentFilter(["자살", "강간"], mode="drop")
    r = cf.check("그는 자살을 시도했다")
    assert r.allowed is False
    assert "자살" in r.matched_keywords


def test_drop_mode_passes_clean() -> None:
    cf = ContentFilter(["자살"], mode="drop")
    r = cf.check("평범한 일상 이야기")
    assert r.allowed is True
    assert r.matched_keywords == []


def test_mask_mode_replaces() -> None:
    cf = ContentFilter(["자살"], mode="mask", mask_token="[금지]")
    r = cf.check("그는 자살을 시도했다")
    assert r.allowed is True
    assert "자살" not in r.masked_text
    assert "[금지]" in r.masked_text


def test_invalid_mode_raises() -> None:
    with pytest.raises(ValueError):
        ContentFilter([], mode="unknown")


def test_from_file_skips_comments_and_blank(tmp_path: Path) -> None:
    p = tmp_path / "kw.txt"
    p.write_text("# 주석\n자살\n\n  \n# 다른 주석\n강간\n", encoding="utf-8")
    cf = ContentFilter.from_file(p)
    assert cf.keywords == ["자살", "강간"]


def test_from_file_missing_returns_empty(tmp_path: Path) -> None:
    cf = ContentFilter.from_file(tmp_path / "missing.txt")
    assert cf.keywords == []
    r = cf.check("anything")
    assert r.allowed is True


def test_empty_text() -> None:
    cf = ContentFilter(["x"])
    r = cf.check("")
    assert r.allowed is True


def test_multiple_matches_collected() -> None:
    cf = ContentFilter(["A", "B", "C"], mode="drop")
    r = cf.check("A and B but not C... wait, C too")
    assert set(r.matched_keywords) == {"A", "B", "C"}
