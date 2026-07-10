"""여행지 실사진 수집 (Unsplash API — 무료).

V2 여행 카드에 실제 장소 사진을 넣는다.
안전장치: 키 없거나 결과 없으면 None 반환 → 렌더러가 큰번호 에디토리얼로 폴백.

분리 원칙: src/ 미import. 무료(Unsplash 50 req/h).
"""

from __future__ import annotations

import hashlib
import json
import logging
import urllib.parse
import urllib.request
from pathlib import Path

from cards.config import get_card_secrets

log = logging.getLogger(__name__)

_SEARCH = "https://api.unsplash.com/search/photos"


def is_configured() -> bool:
    return bool(get_card_secrets().unsplash_access_key)


def _search_url(query: str) -> str | None:
    """장소명으로 세로형 사진 1장 URL 조회. 실패 시 None."""
    key = get_card_secrets().unsplash_access_key
    if not key:
        return None
    q = urllib.parse.urlencode({
        "query": query, "per_page": 3, "orientation": "portrait",
        "content_filter": "high",
    })
    req = urllib.request.Request(f"{_SEARCH}?{q}",
                                 headers={"Authorization": f"Client-ID {key}",
                                          "Accept-Version": "v1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("results") or []
        if not results:
            return None
        return results[0].get("urls", {}).get("regular")
    except Exception as e:
        log.debug("unsplash_search_failed q=%s err=%s", query, repr(e)[:120])
        return None


def download_url(url: str, cache_dir: Path, *, tag: str) -> Path | None:
    """임의 이미지 URL을 캐시에 다운로드 → 로컬 경로 (위키 대표사진용). 실패 시 None."""
    if not url:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(url.encode()).hexdigest()[:12]
    p = cache_dir / f"place_{tag}_{h}.jpg"
    if p.exists() and p.stat().st_size > 5000:
        return p
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HiddenFindsDaily/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        if len(data) < 5000:
            return None
        p.write_bytes(data)
        return p
    except Exception:
        return None


def _commons_filename(image_url: str) -> str | None:
    """upload.wikimedia URL → Commons 파일명 (thumb/원본 모두 처리)."""
    if "upload.wikimedia.org" not in image_url:
        return None
    parts = [x for x in image_url.split("/") if x]
    if not parts:
        return None
    # thumb URL: .../thumb/a/ab/File.jpg/500px-File.jpg → 실제 파일은 뒤에서 2번째
    name = parts[-2] if "/thumb/" in image_url else parts[-1]
    return urllib.parse.unquote(name)


_COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def commons_attribution(image_url: str) -> str:
    """위키미디어 이미지의 저작자·라이선스 표기 (CC 준수). 실패 시 'Wikimedia Commons'."""
    import re
    fname = _commons_filename(image_url)
    if not fname:
        return "Wikimedia Commons"
    q = urllib.parse.urlencode({
        "action": "query", "titles": f"File:{fname}", "prop": "imageinfo",
        "iiprop": "extmetadata", "format": "json",
    })
    try:
        req = urllib.request.Request(f"{_COMMONS_API}?{q}",
                                     headers={"User-Agent": "HiddenFindsDaily/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        pages = (data.get("query") or {}).get("pages") or {}
        meta = next(iter(pages.values()), {}).get("imageinfo", [{}])[0].get("extmetadata", {})
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
        lic = (meta.get("LicenseShortName") or {}).get("value", "").strip()
        artist = re.sub(r"\s+", " ", artist)[:60]
        if artist and lic:
            return f"{artist} ({lic}) / Wikimedia"
        if lic:
            return f"Wikimedia Commons ({lic})"
        return "Wikimedia Commons"
    except Exception:
        return "Wikimedia Commons"


def fetch_photo(query: str, cache_dir: Path, *, tag: str,
                fallbacks: list[str] | None = None) -> Path | None:
    """장소 사진 다운로드 → 로컬 경로. 실패/미설정 시 None (렌더러가 폴백).

    fallbacks: 정확 검색 실패 시 시도할 대체 쿼리(예: 지역 대표사진). HOOK 등 일반
    슬라이드에만 사용 — 특정 장소(REVEAL)엔 오사진 혼입 방지 위해 미사용.
    """
    url = None
    for q in [query] + (fallbacks or []):
        if q and q.strip():
            url = _search_url(q.strip())
            if url:
                break
    if not url:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(f"{query}{url}".encode()).hexdigest()[:12]
    p = cache_dir / f"place_{tag}_{h}.jpg"
    if p.exists() and p.stat().st_size > 5000:
        return p
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HiddenFindsDaily/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        if len(data) < 5000:
            return None
        p.write_bytes(data)
        return p
    except Exception:
        return None
