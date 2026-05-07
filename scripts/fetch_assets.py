"""에셋 자동 수집 스크립트 (FR-5.4, FR-5.5).

세 가지 BGM 전략을 지원한다 (3-Tier 하이브리드):

  Tier 1 - MusicGen (오프라인 AI 생성):  unique 클립 → Content ID 매칭 0%
  Tier 2 - Internet Archive API (PD):    Public Domain 곡 자동 다운로드
  Tier 3 - YouTube 오디오 라이브러리:    수동 1회 보강 (별도 가이드)

배경영상은 Pexels API로 자동 수집한다.

사용 예:
    python -m scripts.fetch_assets bg --per-keyword 5
    python -m scripts.fetch_assets bgm-musicgen --per-mood 3 --duration 30
    python -m scripts.fetch_assets bgm-ia --per-mood 5
    python -m scripts.fetch_assets all
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings  # noqa: E402
from src.utils.logging import get_logger, setup_logging  # noqa: E402


# ---------- 키워드 풀 (사연 분위기에 어울리는 추상 배경) ----------
BG_KEYWORDS_BY_CATEGORY = {
    "city": ["dark city night", "rainy street", "subway tunnel", "downtown traffic"],
    "nature": ["foggy forest", "sunset clouds", "ocean waves slow", "mountain mist"],
    "interior": ["empty room dim", "coffee shop ambient", "bedroom window", "old apartment"],
    "abstract": ["bokeh blur", "smoke slow motion", "ink in water", "particles dust"],
}

# Internet Archive Audio (Public Domain) 무드별 검색 키워드
IA_QUERIES_BY_MOOD = {
    "tension": ["suspense cinematic", "dramatic underscore"],
    "sad": ["melancholy piano", "elegy strings"],
    "calm": ["ambient quiet", "soft piano slow"],
    "twist": ["dramatic reveal", "cinematic orchestral"],
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_metadata(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "items": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_metadata(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _download(client: httpx.Client, url: str, out_path: Path, *, log) -> bool:
    try:
        with client.stream("GET", url) as r:
            r.raise_for_status()
            with out_path.open("wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        return True
    except httpx.HTTPError as e:
        log.warning("download_fail", url=url, error=repr(e))
        if out_path.exists():
            try:
                out_path.unlink()
            except OSError:
                pass
        return False


# ============================================================================
# 배경영상: Pexels Videos
# ============================================================================
def fetch_pexels_videos(
    *,
    api_key: str,
    out_root: Path,
    per_keyword: int = 5,
    min_width: int = 1080,
    log,
) -> list[dict[str, Any]]:
    if not api_key:
        log.error("pexels_api_key_missing")
        return []

    metadata_path = out_root / "_metadata.json"
    metadata = _load_metadata(metadata_path)
    existing_ids = {item.get("source_id") for item in metadata.get("items", [])}

    new_items: list[dict[str, Any]] = []
    headers = {"Authorization": api_key, "User-Agent": "ShortsAutoBot/1.0"}

    with httpx.Client(timeout=60.0, headers=headers) as client:
        for category, keywords in BG_KEYWORDS_BY_CATEGORY.items():
            cat_dir = out_root / category
            cat_dir.mkdir(parents=True, exist_ok=True)
            for kw in keywords:
                try:
                    r = client.get(
                        "https://api.pexels.com/videos/search",
                        params={"query": kw, "per_page": per_keyword, "size": "large"},
                    )
                    r.raise_for_status()
                except httpx.HTTPError as e:
                    log.warning("pexels_search_fail", keyword=kw, error=repr(e))
                    continue
                videos = r.json().get("videos", [])
                for v in videos:
                    vid_id = v.get("id")
                    if vid_id in existing_ids:
                        continue
                    files = v.get("video_files", [])
                    candidates = sorted(
                        [f for f in files if f.get("width", 0) >= min_width and f.get("file_type") == "video/mp4"],
                        key=lambda f: f.get("width", 0),
                    )
                    if not candidates:
                        continue
                    chosen = candidates[0]
                    url = chosen["link"]
                    safe_kw = kw.replace(" ", "_")
                    out_file = cat_dir / f"pexels_{vid_id}_{safe_kw}.mp4"
                    if out_file.exists():
                        continue
                    if not _download(client, url, out_file, log=log):
                        continue
                    item = {
                        "source": "Pexels",
                        "source_id": vid_id,
                        "category": category,
                        "keyword": kw,
                        "url": v.get("url"),
                        "license": "Pexels License (free, commercial OK, no attribution required)",
                        "width": chosen.get("width"),
                        "height": chosen.get("height"),
                        "duration_sec": v.get("duration"),
                        "path": str(out_file.relative_to(PROJECT_ROOT)),
                        "sha256": _sha256_file(out_file),
                        "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                    new_items.append(item)
                    existing_ids.add(vid_id)
                    log.info("pexels_downloaded", id=vid_id, keyword=kw, path=str(out_file.name))
                    time.sleep(1.0)

    metadata["items"] = (metadata.get("items") or []) + new_items
    _save_metadata(metadata_path, metadata)
    log.info("pexels_summary", added=len(new_items), total=len(metadata["items"]))
    return new_items


# ============================================================================
# Tier 1: BGM via MusicGen (Apache 2.0, 오프라인 AI 생성)
# ============================================================================
def fetch_bgm_musicgen(
    *,
    out_root: Path,
    per_mood: int = 3,
    duration_sec: int = 30,
    moods: list[str] | None = None,
    log,
) -> list[dict[str, Any]]:
    """MusicGen으로 무드별 BGM 클립 생성. 결과는 wav → 메타에 등록."""
    from src.audio.musicgen_engine import MOOD_PROMPTS, MusicGenEngine

    metadata_path = out_root / "_metadata.json"
    metadata = _load_metadata(metadata_path)

    selected_moods = moods or list(MOOD_PROMPTS.keys())
    log.info("musicgen_start",
             moods=selected_moods,
             per_mood=per_mood,
             duration=duration_sec,
             total=per_mood * len(selected_moods))

    engine = MusicGenEngine()

    new_items: list[dict[str, Any]] = []

    def on_progress(idx: int, total: int, clip):
        log.info("musicgen_progress",
                 idx=idx, total=total,
                 mood=clip.mood,
                 elapsed_sec=round(clip.elapsed_sec, 1),
                 path=clip.path.name)

    clips = engine.generate_pool(
        out_root=out_root,
        moods=selected_moods,
        per_mood=per_mood,
        duration_sec=duration_sec,
        on_progress=on_progress,
    )

    for clip in clips:
        item = {
            "source": "MusicGen",
            "source_id": f"musicgen_{clip.path.stem}",
            "mood": clip.mood,
            "prompt": clip.prompt,
            "license": "Apache 2.0 model; generated audio is free to use including commercial",
            "duration_sec": round(clip.duration_sec, 2),
            "sample_rate": clip.sample_rate,
            "elapsed_sec": round(clip.elapsed_sec, 1),
            "path": str(clip.path.relative_to(PROJECT_ROOT)),
            "sha256": _sha256_file(clip.path),
            "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        new_items.append(item)

    metadata["items"] = (metadata.get("items") or []) + new_items
    _save_metadata(metadata_path, metadata)
    total_elapsed = sum(c.elapsed_sec for c in clips)
    log.info("musicgen_summary",
             added=len(new_items),
             total=len(metadata["items"]),
             total_elapsed_sec=round(total_elapsed, 1))
    return new_items


# ============================================================================
# Tier 2: BGM via Internet Archive (Public Domain)
# ============================================================================
_IA_IDENTIFIER_BLACKLIST = (
    "librivox", "audiobook", "audio_book", "lecture", "sermon", "podcast",
    "tvquran", "quran", "_book_", "speech", "lectures", "interviews",
    "radio", "broadcast", "drama", "old-time-radio", "otr_",
)
_IA_TITLE_BLACKLIST = (
    "librivox", "audiobook", "audio book", "the adventures of",
    "podcast", "lecture", "sermon",
)
# BGM 1곡 기준 합리 상한 (60초 mp3 ≤ ~3MB, 길어도 10MB 이내)
_IA_MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024
# 음원 길이 상한 (초). 30초~5분 사이 곡만 BGM 재료로 적합
_IA_MAX_DURATION_SEC = 300
_IA_MIN_DURATION_SEC = 20


def _ia_is_audiobook_like(ident: str, title: str) -> bool:
    ident_l = (ident or "").lower()
    title_l = (title or "").lower()
    if any(p in ident_l for p in _IA_IDENTIFIER_BLACKLIST):
        return True
    if any(p in title_l for p in _IA_TITLE_BLACKLIST):
        return True
    return False


def fetch_bgm_internet_archive(
    *,
    out_root: Path,
    per_mood: int = 5,
    log,
) -> list[dict[str, Any]]:
    """Internet Archive에서 PD 음원 다운로드 (FR-5.5 풀 보강).

    오디오북·강연·낭독 컬렉션은 자동 제외하고, 30초~5분 사이의 음악 트랙만 받는다.
    """
    metadata_path = out_root / "_metadata.json"
    metadata = _load_metadata(metadata_path)
    existing_ids = {item.get("source_id") for item in metadata.get("items", [])}

    new_items: list[dict[str, Any]] = []

    # 검색·메타·다운로드 각 단계에 짧은 타임아웃을 걸어 hang 방지
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)
    with httpx.Client(timeout=timeout, headers={"User-Agent": "ShortsAutoBot/1.0"}, follow_redirects=True) as client:
        for mood, queries in IA_QUERIES_BY_MOOD.items():
            mood_dir = out_root / mood
            mood_dir.mkdir(parents=True, exist_ok=True)
            for q in queries:
                try:
                    r = client.get(
                        "https://archive.org/advancedsearch.php",
                        params={
                            "q": f'({q}) AND mediatype:(audio) AND licenseurl:(*creativecommons*publicdomain* OR *publicdomain*)',
                            "fl[]": ["identifier", "title", "creator", "licenseurl", "downloads"],
                            "rows": per_mood * 8,        # 필터링 여유
                            "page": 1,
                            "output": "json",
                            "sort[]": "downloads desc",
                        },
                    )
                    r.raise_for_status()
                except httpx.HTTPError as e:
                    log.warning("ia_search_fail", query=q, error=repr(e))
                    continue

                docs = r.json().get("response", {}).get("docs", [])
                added_in_query = 0
                for doc in docs:
                    if added_in_query >= per_mood:
                        break
                    ident = doc.get("identifier")
                    title = doc.get("title", "")
                    if not ident or ident in existing_ids:
                        continue
                    if _ia_is_audiobook_like(ident, title):
                        log.info("ia_skip_audiobook", id=ident, title=title[:60])
                        continue

                    picked = _ia_pick_audio_file(client, ident, log=log)
                    if picked is None:
                        continue
                    file_name, file_size_bytes, file_duration_sec = picked
                    if file_size_bytes > _IA_MAX_FILE_SIZE_BYTES:
                        log.info("ia_skip_oversize",
                                 id=ident, size_mb=round(file_size_bytes/1024/1024, 1))
                        continue
                    if file_duration_sec is not None and not (
                        _IA_MIN_DURATION_SEC <= file_duration_sec <= _IA_MAX_DURATION_SEC
                    ):
                        log.info("ia_skip_duration",
                                 id=ident, duration_sec=round(file_duration_sec, 1))
                        continue

                    audio_url = f"https://archive.org/download/{ident}/{file_name}"
                    safe_q = q.replace(" ", "_")
                    ext = Path(file_name).suffix.lower() or ".mp3"
                    if ext not in (".mp3", ".m4a", ".ogg", ".wav"):
                        ext = ".mp3"
                    out_file = mood_dir / f"ia_{ident}_{safe_q}{ext}"
                    if out_file.exists():
                        continue

                    if not _download_with_size_cap(
                        client, audio_url, out_file,
                        max_size_bytes=_IA_MAX_FILE_SIZE_BYTES,
                        log=log,
                    ):
                        continue

                    item = {
                        "source": "Internet Archive",
                        "source_id": ident,
                        "mood": mood,
                        "query": q,
                        "title": title,
                        "creator": doc.get("creator"),
                        "license_url": doc.get("licenseurl") or "https://archive.org/details/publicdomain",
                        "page_url": f"https://archive.org/details/{ident}",
                        "duration_sec": file_duration_sec,
                        "size_bytes": file_size_bytes,
                        "path": str(out_file.relative_to(PROJECT_ROOT)),
                        "sha256": _sha256_file(out_file),
                        "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                    new_items.append(item)
                    existing_ids.add(ident)
                    added_in_query += 1
                    log.info("ia_downloaded",
                             id=ident, query=q,
                             size_mb=round(file_size_bytes/1024/1024, 1),
                             duration_sec=file_duration_sec,
                             path=out_file.name)
                    time.sleep(1.0)         # rate limit etiquette

    metadata["items"] = (metadata.get("items") or []) + new_items
    _save_metadata(metadata_path, metadata)
    log.info("ia_summary", added=len(new_items), total=len(metadata["items"]))
    return new_items


def _ia_pick_audio_file(
    client: httpx.Client, identifier: str, *, log
) -> tuple[str, int, float | None] | None:
    """IA 메타데이터에서 적합한 음원 파일 1개 선택.

    Returns
    -------
    (filename, size_bytes, duration_sec) | None
    """
    try:
        r = client.get(f"https://archive.org/metadata/{identifier}")
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("ia_metadata_fail", id=identifier, error=repr(e))
        return None

    data = r.json()
    files = data.get("files", []) or []
    if not files:
        return None

    # mp3 → m4a → ogg → wav 우선순위로 가장 작은(=짧은) 곡 선택
    priority = (".mp3", ".m4a", ".ogg", ".wav")
    candidates: list[tuple[str, int, float | None]] = []
    for f in files:
        name = (f.get("name") or "")
        ext = Path(name).suffix.lower()
        if ext not in priority:
            continue
        # original 트랙만 (IA는 derive 파일도 함께 있음 — _spectrogram, _vbr 등)
        # 가장 단순한 휴리스틱: 파일명에 _spectrogram/_text 포함 시 제외
        if "spectrogram" in name.lower() or "text" in name.lower():
            continue
        try:
            size_b = int(f.get("size", 0))
        except (TypeError, ValueError):
            size_b = 0
        try:
            length_str = f.get("length")
            duration_sec = _parse_ia_length(length_str) if length_str else None
        except Exception:
            duration_sec = None
        candidates.append((name, size_b, duration_sec))

    if not candidates:
        return None
    # 가장 작은 파일 우선 (짧은 곡 가능성 ↑)
    candidates.sort(key=lambda t: (t[1] if t[1] > 0 else 10**12))
    return candidates[0]


def _parse_ia_length(length_str: str) -> float | None:
    """IA `length` 필드 파싱 (예: '143.45' 또는 '0:02:23')."""
    s = str(length_str).strip()
    if not s:
        return None
    if ":" in s:
        parts = s.split(":")
        try:
            parts_f = [float(p) for p in parts]
        except ValueError:
            return None
        sec = 0.0
        for p in parts_f:
            sec = sec * 60 + p
        return sec
    try:
        return float(s)
    except ValueError:
        return None


def _download_with_size_cap(
    client: httpx.Client, url: str, out_path: Path,
    *, max_size_bytes: int, log,
) -> bool:
    """다운로드 중 크기 상한을 초과하면 즉시 중단·삭제."""
    try:
        with client.stream("GET", url) as r:
            r.raise_for_status()
            total = 0
            with out_path.open("wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    total += len(chunk)
                    if total > max_size_bytes:
                        log.warning("ia_download_size_cap", url=url, downloaded=total)
                        f.close()
                        out_path.unlink(missing_ok=True)
                        return False
                    f.write(chunk)
        return True
    except httpx.HTTPError as e:
        log.warning("download_fail", url=url, error=repr(e))
        out_path.unlink(missing_ok=True)
        return False


# ============================================================================
# CLI
# ============================================================================
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch background videos / BGM")
    parser.add_argument(
        "kind",
        choices=["bg", "bgm-musicgen", "bgm-ia", "all"],
        help="bg(영상) / bgm-musicgen(AI 생성) / bgm-ia(Internet Archive) / all(셋 다)",
    )
    parser.add_argument("--per-keyword", type=int, default=5, help="bg: 키워드당 다운로드 개수")
    parser.add_argument("--per-mood", type=int, default=3, help="bgm: 무드당 곡 수")
    parser.add_argument("--duration", type=int, default=30, help="bgm-musicgen: 클립 길이(초)")
    args = parser.parse_args(argv)

    settings = get_settings()
    setup_logging(log_dir=PROJECT_ROOT / "logs", level="INFO", project_root=PROJECT_ROOT)
    log = get_logger("fetch_assets")

    if args.kind in ("bg", "all"):
        out_root = PROJECT_ROOT / "assets" / "bg_video"
        fetch_pexels_videos(
            api_key=settings.secrets.pexels_api_key,
            out_root=out_root,
            per_keyword=args.per_keyword,
            log=log,
        )

    if args.kind in ("bgm-musicgen", "all"):
        out_root = PROJECT_ROOT / "assets" / "bgm"
        fetch_bgm_musicgen(
            out_root=out_root,
            per_mood=args.per_mood,
            duration_sec=args.duration,
            log=log,
        )

    if args.kind in ("bgm-ia", "all"):
        out_root = PROJECT_ROOT / "assets" / "bgm"
        fetch_bgm_internet_archive(
            out_root=out_root,
            per_mood=args.per_mood,
            log=log,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
