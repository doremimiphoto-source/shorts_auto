"""업로드 영상 컨셉 로그 관리.

data/concept_log.jsonl 에 영상당 한 줄씩 기록.
배치 시작 시 최근 컨셉 목록 조회, 업로드 완료 후 기록.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _console_print(text: str) -> None:
    """콘솔 인코딩으로 표현 불가한 문자를 '?' 로 치환해 출력 (CP949 등 Windows 환경 대응)."""
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    safe = text.encode(enc, errors="replace").decode(enc, errors="replace")
    print(safe)


_DEFAULT_LOG = Path("data/concept_log.jsonl")


def append_concept(
    log_path: Path | str = _DEFAULT_LOG,
    *,
    video_id: int,
    script_id: int,
    title: str,
    hook_pattern: str,
    hook_preview: str,
    yt_url: str,
    sim_uploaded: float | None = None,
) -> None:
    """업로드 완료된 영상의 컨셉을 로그에 한 줄 추가."""
    entry: dict[str, Any] = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "video_id": video_id,
        "script_id": script_id,
        "title": title,
        "hook_pattern": hook_pattern,
        "hook_preview": hook_preview[:80].replace("\n", " "),
        "yt_url": yt_url,
    }
    if sim_uploaded is not None:
        entry["sim_uploaded"] = round(sim_uploaded, 4)

    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_recent_concepts(
    log_path: Path | str = _DEFAULT_LOG,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """최근 컨셉 목록 반환 (최신순)."""
    path = Path(log_path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    entries: list[dict] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
        if len(entries) >= limit:
            break
    return entries


def print_recent_concepts(log_path: Path | str = _DEFAULT_LOG, *, limit: int = 15) -> None:
    """배치 시작 전 최근 컨셉 목록 콘솔 출력."""
    entries = load_recent_concepts(log_path, limit=limit)
    if not entries:
        print("[CONCEPT] 기존 컨셉 로그 없음 — 첫 배치")
        return
    _console_print(f"[CONCEPT] 최근 업로드 컨셉 {len(entries)}개 (중복 방지 대상):")
    for e in entries:
        date = e.get("date", "")[:10]
        pat = e.get("hook_pattern", "?")
        title = e.get("title", "?")[:40]
        url = e.get("yt_url", "")
        _console_print(f"  {date} [{pat:14s}] {title}  {url}")
