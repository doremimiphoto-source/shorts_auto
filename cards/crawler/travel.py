"""V2 여행 콘텐츠 생성 — 사실 검증 후 1인칭 작성 (CONTENT_PRINCIPLES_v1.0).

흐름 (원칙1 엄격 모드):
  1. LLM이 후보 여행지 제안 (장소명·국가만, 통계 발명 금지)
  2. cards.facts 로 무료 API 실존 검증 (미검증 폐기)
  3. LLM이 검증된 장소의 실제 위키 정보로 1인칭 여행자 카피 작성
     (사실은 위키 기반, 보이스는 여행자 경험담)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from cards.facts import VerifiedPlace, verify_many
from cards.llm import generate_json
from cards.renderer import Slide

log = logging.getLogger(__name__)

# ── 1단계: 후보 제안 (사실 발명 금지 — 이름·국가만) ──────────────────────────
_CANDIDATES_PROMPT = """You are a well-traveled person listing REAL but lesser-known destinations.
Region: {region}
Type: {theme}

List {n} REAL places you are confident actually exist (lesser-known, not the famous tourist spots).
Return STRICT JSON only:
{{"candidates": [{{"name": "exact place name as on a map", "country": "country"}}]}}
Rules: Only real, verifiable places. NO invented names. NO made-up resorts. {n} items."""

# ── 2단계: 검증된 사실로 1인칭 작성 ───────────────────────────────────────────
_WRITE_PROMPT = """You are a real traveler writing about places you personally visited.
Audience: global English speakers scrolling a travel carousel. Write in FIRST PERSON.

These places are VERIFIED real. The notes below are encyclopedic — use them ONLY to know
what KIND of place each is (a fishing town, a river mouth, a quiet beach). Then write like
a person who was THERE, about the feel of visiting.

{facts_block}

Return STRICT JSON only:
{{
  "title": "first-person hook, max 9 words, no emoji (e.g. 'I found Portugal's quietest beach towns')",
  "subtitle": "one short personal line",
  "places": [
    {{
      "name": "place name (keep exactly as given)",
      "location": "country (as given)",
      "note": "ONE first-person sentence about the EXPERIENCE of being there, max 13 words",
      "tip": "ONE natural, practical tip a friend would give, max 11 words"
    }}
  ],
  "cta": "personal save/share line, max 8 words, no emoji"
}}
HARD RULES:
- NEVER copy encyclopedic phrasing: no "urban area", "square kilometers", administrative dates,
  "became a city", population numbers, founding years. Those read robotic and fake.
- NEVER turn a date/number from the notes into a personal claim (no "I visited in 2001").
- DO write what a visitor actually experiences: the harbor, the old streets, the seafood,
  the empty sand, the light, the walk. Concrete and sensory.
- Casual, like texting a friend. NO ad-speak ("discover", "unveil", "nestled", "breathtaking", "gem").
- Tips must sound human, NOT start with "usually/often". Vary sentence length. Minimal emoji."""


@dataclass
class TravelContent:
    title: str
    subtitle: str
    cta: str
    region: str
    places: list[dict] = field(default_factory=list)   # name, location, note, tip
    sources: list[str] = field(default_factory=list)    # 검증 출처 URL


def _facts_block(verified: list[VerifiedPlace]) -> str:
    lines = []
    for vp in verified:
        loc = vp.country or "?"
        extract = vp.extract[:300]
        lines.append(f"- {vp.name} ({loc}): {extract}")
    return "\n".join(lines)


def generate_travel(region: str = "Southeast Asia",
                    theme: str = "secret beaches with few tourists",
                    count: int = 5) -> TravelContent:
    # 1. 후보 제안 (버퍼 포함 — 검증 탈락 대비 2배수)
    cand_data = generate_json(
        _CANDIDATES_PROMPT.format(region=region, theme=theme, n=count * 2),
        temperature=0.9, max_tokens=1024)
    candidates = list(cand_data.get("candidates") or [])
    if not candidates:
        raise ValueError("LLM이 후보를 반환하지 않음")
    log.info("후보 %d개 제안됨", len(candidates))

    # 2. 사실 검증 (미검증 폐기)
    verified = verify_many(candidates, need=count)
    if len(verified) < 1:
        raise ValueError("검증 통과 장소 0개 — 재시도 필요")
    log.info("검증 통과 %d/%d", len(verified), count)

    # 3. 검증된 사실로 1인칭 작성
    write_data = generate_json(
        _WRITE_PROMPT.format(facts_block=_facts_block(verified)),
        temperature=0.95, max_tokens=2048)

    # 작성 결과의 장소 순서를 검증된 장소에 맞춤 (이름 보존)
    written = {str(p.get("name", "")).strip().lower(): p
               for p in (write_data.get("places") or [])}
    places = []
    for vp in verified:
        w = written.get(vp.name.strip().lower(), {})
        note = str(w.get("note", "")).strip()
        if not note:
            # LLM이 진정성 있게 쓰지 못한 장소(빈 note)는 제외 — 빈 카드 방지
            log.info("빈 note 제외: %s", vp.name)
            continue
        places.append({
            "name": vp.name,
            "location": vp.country or w.get("location", ""),
            "note": note,
            "tip": str(w.get("tip", "")).strip(),
        })

    return TravelContent(
        title=str(write_data.get("title", "")).strip(),
        subtitle=str(write_data.get("subtitle", "")).strip(),
        cta=str(write_data.get("cta", "")).strip() or "Saving these for my next trip",
        region=region,
        places=places,
        sources=[vp.wiki_url for vp in verified if vp.wiki_url],
    )


def to_slides(content: TravelContent) -> list[Slide]:
    from cards.config import OUTPUT_DIR
    from cards.photos import fetch_photo
    cache = OUTPUT_DIR / "_placecache"

    # HOOK 배경: 첫 장소 사진 (없으면 그라디언트 폴백)
    hook_img = None
    if content.places:
        first = content.places[0]
        hook_img = fetch_photo(
            f"{first.get('name','')} {first.get('location','')}".strip(),
            cache, tag="hook")
    slides: list[Slide] = [
        Slide(type="hook", badge="HIDDEN TRAVEL",
              title=content.title, subtitle=content.subtitle,
              image_path=hook_img, image_mode="cover"),
    ]
    for i, p in enumerate(content.places, start=1):
        body = [x for x in (p.get("note"), p.get("tip")) if x]
        photo = fetch_photo(
            f"{str(p.get('name','')).strip()} {str(p.get('location','')).strip()}".strip(),
            cache, tag=f"{i:02d}")
        slides.append(Slide(
            type="reveal", badge=f"{i:02d}",
            title=str(p.get("name", "")).strip(),
            subtitle=str(p.get("location", "")).strip(),
            body_lines=body,
            image_path=photo, image_mode="cover",   # 실사진, 없으면 자동 폴백
        ))
    slides.append(Slide(
        type="cta",
        title=f"{content.cta} ✈️",
        body_lines=[
            "💾  Saving this for later",
            "📤  Send it to your travel buddy",
            "💬  Been to any of these? Tell me",
        ],
    ))
    return slides


def slides_to_json(slides: list[Slide]) -> str:
    return json.dumps([
        {"slide_num": i + 1, "type": s.type, "title": s.title,
         "subtitle": s.subtitle, "body_lines": s.body_lines, "badge": s.badge}
        for i, s in enumerate(slides)
    ], ensure_ascii=False)
