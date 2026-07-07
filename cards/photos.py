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


def fetch_photo(query: str, cache_dir: Path, *, tag: str) -> Path | None:
    """장소 사진 다운로드 → 로컬 경로. 실패/미설정 시 None (렌더러가 폴백)."""
    url = _search_url(query)
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
