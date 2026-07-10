"""사실 검증 엔진 (무료 API) — 원칙1 (CONTENT_PRINCIPLES_v1.0).

장소 실존을 무료 API로 검증하고 실제 정보를 반환한다.
LLM이 지어낸 장소는 여기서 걸러진다.

소스 (전부 무료, 키 불필요):
  - Wikipedia REST API   : 실존·요약·좌표·국가
  - OSM Nominatim        : 지리적 실존·국가 (보조)
"""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

log = logging.getLogger(__name__)

_UA = "HiddenFindsDaily/1.0 (travel content; contact: hiddenfindsdaily@example.com)"
_WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
_NOMINATIM = "https://nominatim.openstreetmap.org/search"


@dataclass
class VerifiedPlace:
    name: str            # 정규 명칭
    country: str
    extract: str         # 위키 실제 설명
    lat: float | None
    lon: float | None
    wiki_url: str
    source: str          # 'wikipedia' | 'nominatim'
    image_url: str = ""  # 위키백과 그 장소의 실제 대표사진 (정확성 — Unsplash보다 우선)
    description: str = "" # 위키 짧은 설명 ("Island in Cambodia" 등) — 방문가능 장소 판별용


def _get_json(url: str, *, timeout: int = 15) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA,
                                                    "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.debug("facts_get_failed url=%s err=%s", url[:80], repr(e)[:120])
        return None


def _wiki_summary_one(title: str) -> dict | None:
    url = _WIKI_SUMMARY + urllib.parse.quote(title.replace(" ", "_"))
    data = _get_json(url)
    if not isinstance(data, dict):
        return None
    if data.get("type") == "disambiguation" or "extract" not in data:
        return None
    if len((data.get("extract") or "").strip()) < 40:
        return None
    return data


def _wikipedia(name: str, expected_country: str = "") -> VerifiedPlace | None:
    """이름(+국가 변형)으로 Wikipedia 실존 검증. 동음이의어는 '이름, 국가'로 재시도."""
    titles = [name]
    if expected_country:
        # 동음이의어 회피: 'Nazaré' → 'Nazaré, Portugal'
        titles += [f"{name}, {expected_country}", f"{name} ({expected_country})"]
    data = None
    for t in titles:
        data = _wiki_summary_one(t)
        if data:
            break
    if not data:
        return None
    extract = (data.get("extract") or "").strip()
    desc = (data.get("description") or "").strip()
    coord = data.get("coordinates") or {}
    # 위키 대표사진(그 장소 실제 이미지) — 원본 우선, 없으면 썸네일
    img = ((data.get("originalimage") or {}).get("source")
           or (data.get("thumbnail") or {}).get("source") or "")
    return VerifiedPlace(
        name=data.get("title", name),
        country="",
        extract=extract,
        lat=coord.get("lat"), lon=coord.get("lon"),
        wiki_url=(data.get("content_urls", {}).get("desktop", {}).get("page", "")),
        source="wikipedia",
        image_url=img,
        description=desc,
    )


def _nominatim(name: str) -> tuple[float, float, str] | None:
    url = (f"{_NOMINATIM}?q={urllib.parse.quote(name)}"
           f"&format=json&limit=1&addressdetails=1&accept-language=en")
    data = _get_json(url)
    if not isinstance(data, list) or not data:
        return None
    top = data[0]
    country = (top.get("address") or {}).get("country", "")
    try:
        return float(top["lat"]), float(top["lon"]), country
    except (KeyError, ValueError):
        return None


def verify_place(name: str, *, expected_country: str = "",
                 nominatim_delay: float = 1.1) -> VerifiedPlace | None:
    """장소 실존 검증 + 실제 정보 반환. 미검증 시 None.

    1순위: Wikipedia 실존 + 추출문에서 국가 직접 확인 (Nominatim 호출 회피).
    2순위: 추출문에 국가 없으면 Nominatim 으로 국가 확인 (호출 최소화 → throttling 방지).
    """
    place = _wikipedia(name, expected_country)
    if place is None:
        return None

    if not expected_country:
        return place

    # (a) Wikipedia 추출문/제목에 기대 국가가 직접 언급 → 확인 완료 (API 추가호출 없음)
    haystack = f"{place.extract} {place.name}".lower()
    if expected_country.lower() in haystack:
        place.country = expected_country
        return place

    # (b) 추출문에 없으면 Nominatim 으로 국가 확인 (1회만)
    time.sleep(nominatim_delay)
    geo = _nominatim(name)
    if geo:
        lat, lon, country = geo
        place.lat = place.lat or lat
        place.lon = place.lon or lon
        place.country = country
        if country and (expected_country.lower() in country.lower()
                        or country.lower() in expected_country.lower()):
            return place
        if country:
            log.info("국가 불일치 폐기: %s (기대=%s, 실제=%s)",
                     place.name, expected_country, country)
            return None

    # (c) 어느 쪽으로도 기대 국가를 확인 못 함 → 잘못된 지역 혼입 방지 위해 폐기
    log.info("국가 미확인 폐기(엄격): %s", place.name)
    return None


def verify_many(candidates: list[dict], *, need: int) -> list[VerifiedPlace]:
    """후보 리스트 [{name, country}] → 검증 통과 장소 (최대 need개)."""
    verified: list[VerifiedPlace] = []
    for c in candidates:
        if len(verified) >= need:
            break
        name = str(c.get("name", "")).strip()
        if not name:
            continue
        vp = verify_place(name, expected_country=str(c.get("country", "")).strip())
        if vp:
            verified.append(vp)
            log.info("✅ 검증: %s (%s)", vp.name, vp.country or "?")
        else:
            log.info("❌ 폐기(미검증): %s", name)
    return verified
