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
import re
from dataclasses import dataclass, field
from pathlib import Path

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
_WRITE_PROMPT = """You write a SAVE-WORTHY travel guide card for a global English audience.
Accuracy matters more than vibes — people save this to actually use it, so every fact must be true.

These places are VERIFIED real. Below are encyclopedic notes about each. Pull the concrete FACTS
(what it's known for, its nickname, where it is, what's nearby, its size, how you reach it) and
rephrase them into short natural lines. The TITLE/SUBTITLE/CTA carry a light personal voice;
the per-place lines are FACTS from the notes.

{facts_block}

Return STRICT JSON only:
{{
  "title": "first-person hook, max 9 words, no emoji (e.g. 'I found Portugal's quietest beach towns')",
  "subtitle": "one short personal line",
  "places": [
    {{
      "name": "place name (keep exactly as given)",
      "location": "country (as given)",
      "why": "what it's KNOWN FOR or its nickname — a REAL fact from the notes, max 7 words",
      "detail": "WHERE it is / what's nearby / its size or setting — a REAL fact from the notes, max 7 words",
      "tip": "a practical tip that FOLLOWS from those facts (getting there, season, bring cash, gear), max 7 words"
    }}
  ],
  "cta": "personal save/share line, max 8 words, no emoji"
}}
HARD RULES — FACTS ONLY:
- "why" and "detail" MUST be real facts taken from the notes. If the notes say "4.5 km off
  Sihanoukville, nicknamed Bamboo Island", good lines are "Nicknamed Bamboo Island" and
  "4.5km off Sihanoukville". Do NOT invent anything absent from the notes.
- NEVER invent sensory/personal color. BANNED: "seaweed wrapped around legs", "loud bird calls",
  "I loved it here", "so peaceful", "quiet evenings", "amazing views", "bring a good book".
- NEVER just restate the category (a beach / an island / a park) — give a distinguishing fact.
- Only use numbers that appear in the notes (e.g. a distance). No invented population/date/price.
- "tip" is the only line that may be advice; keep it plausible and derived from the facts
  (remote island → "bring cash, few ATMs"; marine park → "pack snorkel gear"). No fake specifics.
- If a place lacks a real fact for a field, write a SHORTER true one — never pad with fluff."""


@dataclass
class TravelContent:
    title: str
    subtitle: str
    cta: str
    region: str
    places: list[dict] = field(default_factory=list)   # name, location, why, detail, tip, wiki_image
    sources: list[str] = field(default_factory=list)    # 검증 출처 URL
    photo_credits: list[str] = field(default_factory=list)  # 위키미디어 사진 저작자표시


def _nums(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text or ""))


def _numbers_grounded(line: str, extract: str) -> bool:
    """line의 모든 숫자가 위키 추출문에 실재하면 True (없는 숫자=발명 → False)."""
    ln = _nums(line)
    return ln.issubset(_nums(extract)) if ln else True


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
        why = str(w.get("why", "")).strip()           # 위키 근거 사실 1
        detail = str(w.get("detail", "")).strip()     # 위키 근거 사실 2
        tip = str(w.get("tip", "")).strip()
        # 숫자 자동검증: 위키 추출문에 없는 숫자를 담은 줄 제거 (LLM 숫자 발명 차단)
        if why and not _numbers_grounded(why, vp.extract):
            log.info("숫자 미검증 제거 why: %s | %s", vp.name, why); why = ""
        if detail and not _numbers_grounded(detail, vp.extract):
            log.info("숫자 미검증 제거 detail: %s | %s", vp.name, detail); detail = ""
        if tip and not _numbers_grounded(tip, vp.extract):
            log.info("숫자 미검증 제거 tip: %s | %s", vp.name, tip); tip = ""
        if not (why or detail):
            # 사실을 못 뽑은 장소는 제외 — 빈/막연 카드 방지
            log.info("사실 부족 제외: %s", vp.name)
            continue
        places.append({
            "name": vp.name,
            "location": vp.country or w.get("location", ""),
            "why": why,
            "detail": detail,
            "tip": tip,
            "wiki_image": vp.image_url,               # 위키백과 그 장소 실제 사진
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
    from cards.photos import fetch_photo, download_url, commons_attribution
    cache = OUTPUT_DIR / "_placecache"

    import hashlib
    region = str(content.region or "").strip()
    n = len(content.places)
    loc0 = str(content.places[0].get("location", "")).strip() if content.places else ""

    seen: set[str] = set()
    def _uniq(photo):
        """이미 쓴 이미지와 동일하면 None — 같은 사진/스톡 재사용 중복 방지."""
        if not photo:
            return None
        try:
            h = hashlib.md5(Path(photo).read_bytes()).hexdigest()
        except Exception:
            return photo
        if h in seen:
            return None
        seen.add(h)
        return photo

    # 1) 리빌 사진 — 위키백과 '그 장소 실제 사진' 우선(정확성), 없으면 Unsplash 폴백.
    #    특정 장소에 우선권을 줘서 훅이 스톡사진을 가로채 리빌이 비는 것 방지.
    reveal_imgs = []
    for i, p in enumerate(content.places, start=1):
        name = str(p.get("name", "")).strip()
        loc = str(p.get("location", "")).strip()
        wiki = str(p.get("wiki_image", "")).strip()
        img = None
        if wiki:
            img = _uniq(download_url(wiki, cache, tag=f"{i:02d}w"))
            if img:
                content.photo_credits.append(f"{name}: {commons_attribution(wiki)}")
        if img is None:      # 위키사진 없음/중복 → Unsplash 키워드 (정확도 낮음)
            img = _uniq(fetch_photo(f"{name} {loc}".strip(), cache, tag=f"{i:02d}"))
        reveal_imgs.append(img)

    # 2) 훅·티저는 '지역' 풍경 (특정 장소 아님 → 리빌과 의미상·이미지상 안 겹침). 중복이면 None
    hook_img = _uniq(fetch_photo(
        f"{region} beach landscape", cache, tag="hook",
        fallbacks=[f"{region} coast", f"{region} tropical", f"{loc0} coastline"]))
    teaser_img = _uniq(fetch_photo(
        f"{loc0} village", cache, tag="teaser",
        fallbacks=[f"{loc0} coast aerial", f"{region} scenery", f"{region} nature"]))

    slides: list[Slide] = [
        Slide(type="hook", badge=f"{n} HIDDEN GEMS" if n else "HIDDEN TRAVEL",
              title=content.title, subtitle=content.subtitle,
              image_path=hook_img, image_mode="cover"),
    ]
    # 슬라이드 2도 훅 (IG는 안 넘기면 2번 재노출 → 여기서 저장 유도로 낚아챔)
    teasers = ["You won't find these on Google",
               "Most tourists never make it here",
               "Save these before the crowds find them"]
    slides.append(Slide(
        type="hook", badge="",
        title=teasers[n % len(teasers)],
        subtitle="Save this for your next trip 💾",
        image_path=teaser_img, image_mode="cover"))
    for i, p in enumerate(content.places, start=1):
        # 저장가치(#11): 사실 2줄(위키근거) + 실용팁 1줄 — 발명 금지
        body = [x for x in (p.get("why"), p.get("detail"), p.get("tip")) if x]
        slides.append(Slide(
            type="reveal", badge=f"{i:02d}",
            title=str(p.get("name", "")).strip(),
            subtitle=str(p.get("location", "")).strip(),
            body_lines=body,
            image_path=reveal_imgs[i - 1], image_mode="cover",   # 실사진, 없으면 그라디언트
        ))
    slides.append(Slide(
        type="cta",
        title=f"{content.cta} ✈️",
        body_lines=[
            "💾  Save this for your next trip",
            "📤  Send it to your travel buddy",
            "➕  Follow for a hidden gem daily",
            "💬  Which one first? Comment 👇",
        ],
    ))
    return slides


def slides_to_json(slides: list[Slide]) -> str:
    return json.dumps([
        {"slide_num": i + 1, "type": s.type, "title": s.title,
         "subtitle": s.subtitle, "body_lines": s.body_lines, "badge": s.badge}
        for i, s in enumerate(slides)
    ], ensure_ascii=False)
