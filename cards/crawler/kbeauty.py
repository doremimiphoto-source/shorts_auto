"""V3 K-뷰티 콘텐츠 생성 — 한국 제품을 외국인에게 (영어 전용).

원칙 (CONTENT_PRINCIPLES_v1.0 / REQUIREMENTS_ADDENDUM_v1.2):
  - 사실: 제품명·가격·브랜드는 Naver Shopping API 실데이터만 (발명 금지).
  - 소스: 올리브영/지그재그/에이블리는 레퍼런스, 데이터는 합법 Naver Shopping API.
  - 보이스: 솔직한 리뷰어 1인칭, 효능 과장 금지.
  - 구매: 외국인용 글로벌 배송 채널(YesStyle/StyleKorean)로 라우팅.
  - 무료: Naver Shopping API (일 25,000 무료) + Groq/Gemini.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from cards.config import get_card_secrets
from cards.llm import generate_json
from cards.renderer import Slide

log = logging.getLogger(__name__)

_NAVER_API = "https://openapi.naver.com/v1/search/shop.json"
_KRW_PER_USD = 1380  # 환산 추정치 (표기 시 'approx' 명시)

# 외국인에게 인기 있는 K-뷰티 카테고리 (영어 → 한국어 검색어)
_CATEGORY_QUERY = {
    "serum": "세럼",
    "sunscreen": "선크림",
    "toner": "토너",
    "cleanser": "클렌저",
    "sheet mask": "마스크팩",
    "cushion": "쿠션",
    "lip tint": "립틴트",
    "essence": "에센스",
}

# 유명 K-뷰티 브랜드 allowlist (한국어 검색어, 영어 표기) — 전부 실재 한국 브랜드,
# 글로벌 인지도 있고 YesStyle 등에서 해외 배송 가능.
K_BEAUTY_BRANDS: list[tuple[str, str]] = [
    ("코스알엑스", "Cosrx"), ("조선미녀", "Beauty of Joseon"), ("아누아", "Anua"),
    ("이니스프리", "Innisfree"), ("토리든", "Torriden"), ("메디큐브", "Medicube"),
    ("라운드랩", "Round Lab"), ("넘버즈인", "Numbuzin"), ("마녀공장", "Manyo Factory"),
    ("퓨리토", "Purito"), ("티르티르", "TIRTIR"), ("아비브", "Abib"),
    ("구달", "Goodal"), ("바닐라코", "Banila Co"), ("헤라", "Hera"),
    ("라네즈", "Laneige"), ("믹순", "Mixsoon"), ("닥터지", "Dr.G"),
    ("달바", "d'Alba"), ("스킨천사", "Skin1004"),
]


@dataclass
class KBeautyProduct:
    name_kr: str
    name_en: str
    brand: str            # 원본(한국어일 수 있음) — 카드엔 brand_en 사용
    price_krw: int
    price_usd: float
    image_url: str
    naver_link: str
    brand_en: str = ""    # 영어 브랜드명 (LLM 번역, 카드 표기용)
    note: str = ""        # 1인칭 영어 코멘트 (LLM, 과장 금지)


@dataclass
class KBeautyContent:
    title: str
    subtitle: str
    cta: str
    category: str
    products: list[KBeautyProduct] = field(default_factory=list)


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def _naver_search(query: str, *, display: int = 10, sort: str = "sim") -> list[dict]:
    """Naver Shopping 실제 제품 검색 (무료 API). 키 없으면 예외."""
    s = get_card_secrets()
    if not (s.naver_client_id and s.naver_client_secret):
        raise RuntimeError(
            "naver_client_id/secret 미설정 — Naver Shopping API 키 필요 "
            "(발급: https://developers.naver.com/apps/#/register)")
    url = f"{_NAVER_API}?{urllib.parse.urlencode({'query': query, 'display': display, 'sort': sort})}"
    req = urllib.request.Request(url, headers={
        "X-Naver-Client-Id": s.naver_client_id,
        "X-Naver-Client-Secret": s.naver_client_secret,
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return list(data.get("items") or [])


def _rotated_brands() -> list[tuple[str, str]]:
    """날짜 기반으로 브랜드 순서를 회전 (매일 다른 브랜드 조합)."""
    import datetime
    n = len(K_BEAUTY_BRANDS)
    off = datetime.datetime.utcnow().timetuple().tm_yday % n
    return K_BEAUTY_BRANDS[off:] + K_BEAUTY_BRANDS[:off]


def _fetch_products(category: str, *, count: int) -> list[KBeautyProduct]:
    """유명 K-뷰티 브랜드별로 '브랜드+카테고리' 검색 → 브랜드당 실제품 1개.

    allowlist 브랜드만 쓰므로 무명/외국 브랜드가 섞이지 않는다 (품질·신뢰도).
    """
    kquery = _CATEGORY_QUERY.get(category, category)
    products: list[KBeautyProduct] = []
    for kbrand, ebrand in _rotated_brands():
        if len(products) >= count:
            break
        try:
            items = _naver_search(f"{kbrand} {kquery}", display=3, sort="sim")
        except Exception:
            continue
        for it in items:
            name_kr = _strip_html(it.get("title", ""))
            # 검색 브랜드가 실제 제목에 있어야 그 브랜드 제품 (오매칭 방지)
            if kbrand not in name_kr:
                continue
            try:
                price_krw = int(it.get("lprice", 0))
            except (ValueError, TypeError):
                price_krw = 0
            if not name_kr or price_krw < 3000:   # 액세서리/오탐 제외
                continue
            products.append(KBeautyProduct(
                name_kr=name_kr, name_en="", brand=ebrand, brand_en=ebrand,
                price_krw=price_krw, price_usd=round(price_krw / _KRW_PER_USD, 1),
                image_url=it.get("image", ""), naver_link=it.get("link", ""),
            ))
            break   # 이 브랜드는 1개만
    return products


_TRANSLATE_PROMPT = """You write K-beauty product cards for a global English audience.
These are REAL products from well-known Korean brands (real names & prices from Naver).

Products (Korean name | brand | approx USD):
{block}

For EACH product return a clean English name and a genuine one-line take.

Return STRICT JSON only:
{{
  "title": "first-person hook, max 9 words, no emoji (e.g. 'Korean skincare worth the hype')",
  "subtitle": "one short honest line",
  "items": [
    {{"name_kr": "<exact Korean name given>",
      "name_en": "clean readable English product name (keep the brand)",
      "note": "ONE appealing but honest line, max 12 words"}}
  ],
  "cta": "personal save/share line, max 8 words, no emoji"
}}
NOTE RULES (important):
- Say why a K-beauty fan would like it: texture, finish, what it's good for, cult-favorite status.
- Be varied across items — do NOT make most notes about price being high.
- Honest, first person, casual. NO "miracle/holy grail/life-changing/glow up".
- Do NOT invent specific ingredients or clinical claims not implied by the name."""


def generate_kbeauty(category: str = "serum", count: int = 5) -> KBeautyContent:
    # LLM 미스(빈 note) 대비 소폭 버퍼로 수집
    products = _fetch_products(category, count=count + 3)
    if not products:
        raise ValueError(f"Naver에서 '{category}' 제품을 찾지 못함")

    block = "\n".join(
        f"- {p.name_kr} | {p.brand_en} | ~${p.price_usd}" for p in products)
    data = generate_json(_TRANSLATE_PROMPT.format(block=block),
                         temperature=0.85, max_tokens=2500)

    by_kr = {str(i.get("name_kr", "")).strip(): i for i in (data.get("items") or [])}
    picked: list[KBeautyProduct] = []
    for p in products:
        if len(picked) >= count:
            break
        match = by_kr.get(p.name_kr) or {}
        name_en = str(match.get("name_en", "")).strip()
        note = str(match.get("note", "")).strip()
        if not name_en or not note:      # LLM이 깔끔히 못 만든 항목은 제외
            continue
        p.name_en, p.note = name_en, note
        picked.append(p)

    if not picked:
        raise ValueError(f"'{category}' 콘텐츠 생성 실패 — 재시도 필요")

    return KBeautyContent(
        title=str(data.get("title", "")).strip() or "Korean skincare worth trying",
        subtitle=str(data.get("subtitle", "")).strip(),
        cta=str(data.get("cta", "")).strip() or "Saving these for my next haul",
        category=category,
        products=picked,
    )


def _ascii_safe(text: str, fallback: str) -> str:
    """영어 폰트(Poppins)가 못 그리는 비라틴 문자(한국어 등) 방지."""
    if text and text.isascii():
        return text
    # 비ASCII 문자 제거 후 남는 게 충분하면 사용, 아니면 fallback
    cleaned = "".join(ch for ch in text if ch.isascii()).strip()
    return cleaned if len(cleaned) >= 2 else fallback


def _download_image(url: str, dest_dir: Path, tag: str) -> Path | None:
    """Naver 상품 이미지 다운로드 → 로컬 경로. 실패 시 None."""
    if not url:
        return None
    import hashlib
    import urllib.request
    dest_dir.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(url.encode()).hexdigest()[:12]
    p = dest_dir / f"prod_{tag}_{h}.jpg"
    if p.exists() and p.stat().st_size > 3000:
        return p
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HiddenFindsDaily/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        if len(data) < 3000:
            return None
        p.write_bytes(data)
        return p
    except Exception:
        return None


def to_slides(content: KBeautyContent) -> list[Slide]:
    from cards.config import OUTPUT_DIR
    cache = OUTPUT_DIR / "_prodcache"
    slides: list[Slide] = [
        Slide(type="hook", badge="K-BEAUTY",
              title=content.title, subtitle=content.subtitle),
    ]
    for i, p in enumerate(content.products, start=1):
        body = [f"≈ ${p.price_usd} (approx)"]
        if p.note:
            body.append(p.note)
        body.append("Ships worldwide via YesStyle")
        img = _download_image(p.image_url, cache, tag=f"{i:02d}")   # 실제 상품 사진
        slides.append(Slide(
            type="reveal", badge=f"{i:02d}",
            title=_ascii_safe(p.name_en, "Korean Serum"),
            subtitle=_ascii_safe(p.brand_en or p.brand, "Korean beauty"),
            body_lines=body,
            image_path=img,
            image_mode="contain",   # 상품 사진은 상단 썸네일로
        ))
    slides.append(Slide(
        type="cta",
        title=f"{content.cta} 💄",
        body_lines=[
            "💾  Save this for your next K-haul",
            "📤  Send to your skincare bestie",
            "💬  Which one should I review next?",
        ],
    ))
    return slides


def slides_to_json(slides: list[Slide]) -> str:
    return json.dumps([
        {"slide_num": i + 1, "type": s.type, "title": s.title,
         "subtitle": s.subtitle, "body_lines": s.body_lines, "badge": s.badge}
        for i, s in enumerate(slides)
    ], ensure_ascii=False)
