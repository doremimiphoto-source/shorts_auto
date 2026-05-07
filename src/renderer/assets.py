"""에셋(배경영상·BGM) 선택 정책 (FR-5.4, FR-5.5)."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable


class AssetSelector:
    """배경영상·BGM 선택기.

    - 동일 배경영상 재사용 시 7일 간격 강제 (FR-5.4)
    - 블랙리스트(Content ID 매칭) 자동 제외 (FR-5.5, A10)
    """

    def __init__(
        self,
        *,
        bg_dir: Path,
        bgm_dir: Path,
        bg_reuse_min_days: int = 7,
        recent_usage_provider=None,    # callable: (kind, path) -> datetime | None
        blacklist_provider=None,       # callable: (kind, path) -> bool
        rng: random.Random | None = None,
    ) -> None:
        self.bg_dir = bg_dir
        self.bgm_dir = bgm_dir
        self.bg_reuse_min_days = bg_reuse_min_days
        self.recent_usage_provider = recent_usage_provider
        self.blacklist_provider = blacklist_provider
        self.rng = rng or random.Random()

    def list_files(self, root: Path, exts: tuple[str, ...]) -> list[Path]:
        return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in exts]

    def select_bg_video(self, *, mood: str | None = None) -> Path:
        candidates = self._candidates(self.bg_dir, exts=(".mp4", ".mov", ".webm"), mood=mood)
        candidates = list(self._filter_reuse(candidates, kind="bg_video"))
        candidates = list(self._filter_blacklist(candidates, kind="bg_video"))
        if not candidates:
            raise FileNotFoundError(f"사용 가능한 배경영상 없음 (mood={mood})")
        return self.rng.choice(candidates)

    def select_bgm(self, *, mood: str | None = None) -> Path:
        candidates = self._candidates(self.bgm_dir, exts=(".mp3", ".m4a", ".ogg", ".wav"), mood=mood)
        candidates = list(self._filter_blacklist(candidates, kind="bgm"))
        if not candidates:
            raise FileNotFoundError(f"사용 가능한 BGM 없음 (mood={mood})")
        return self.rng.choice(candidates)

    # ---------- 내부 ----------
    def _candidates(self, root: Path, *, exts: tuple[str, ...], mood: str | None) -> list[Path]:
        if mood:
            mood_dir = root / mood
            if mood_dir.exists():
                return self.list_files(mood_dir, exts)
        return self.list_files(root, exts)

    def _filter_reuse(self, candidates: Iterable[Path], *, kind: str) -> Iterable[Path]:
        if self.recent_usage_provider is None:
            yield from candidates
            return
        threshold = datetime.now() - timedelta(days=self.bg_reuse_min_days)
        for p in candidates:
            last_used = self.recent_usage_provider(kind, str(p))
            if last_used is None or last_used < threshold:
                yield p

    def _filter_blacklist(self, candidates: Iterable[Path], *, kind: str) -> Iterable[Path]:
        if self.blacklist_provider is None:
            yield from candidates
            return
        for p in candidates:
            if not self.blacklist_provider(kind, str(p)):
                yield p
