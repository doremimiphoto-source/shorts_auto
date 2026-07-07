"""V1 쇼핑 비교 콘텐츠 — AliExpress vs Amazon (영어 전용).

원칙1(사실): 가격·평점은 shopping_comparisons DB의 **실제 큐레이션 값만** 사용.
LLM은 훅/코멘트 카피만 작성하고 가격을 발명하지 않는다.
데이터가 없으면 에러 → 가짜 가격 게시 원천 차단.

데이터 입력:
  - 수동: add_comparison(...) 또는 cards.crawler.shopping CLI
  - (나중) AliExpress Portals API 로 Ali쪽 자동 채움 (cards/crawler/aliexpress_api.py)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from cards.db import CardsDB
from cards.llm import generate_json
from cards.renderer import Slide

log = logging.getLogger(__name__)


@dataclass
class Comparison:
    product_name: str
    ali_price_usd: float
    amazon_price_usd: float
    ali_rating: float | None = None
    ali_orders: str = ""
    amazon_rating: float | None = None
    ali_url: str = ""
    amazon_url: str = ""
    note: str = ""       # LLM 1줄 코멘트 (가격 발명 금지)

    @property
    def multiple(self) -> float:
        if self.ali_price_usd <= 0:
            return 0.0
        return round(self.amazon_price_usd / self.ali_price_usd, 1)


@dataclass
class ShoppingContent:
    title: str
    subtitle: str
    cta: str
    items: list[Comparison] = field(default_factory=list)


# ── 데이터 입력 (수동 큐레이션) ────────────────────────────────────────────────
def add_comparison(db: CardsDB, *, product_name: str, ali_price_usd: float,
                   amazon_price_usd: float, category: str = "",
                   ali_rating: float | None = None, ali_orders: str = "",
                   ali_url: str = "", amazon_rating: float | None = None,
                   amazon_url: str = "", image_url: str = "") -> int:
    cur = db.execute(
        "INSERT INTO shopping_comparisons "
        "(product_name, category, ali_price_usd, ali_rating, ali_orders, ali_url, "
        " amazon_price_usd, amazon_rating, amazon_url, image_url, curated_date) "
        "VALUES (?,?,?,?,?,?,?,?,?,?, date('now'))",
        (product_name, category, ali_price_usd, ali_rating, ali_orders, ali_url,
         amazon_price_usd, amazon_rating, amazon_url, image_url),
    )
    return int(cur.lastrowid)


def fetch_comparisons(db: CardsDB, *, count: int) -> list[Comparison]:
    rows = db.fetchall(
        "SELECT * FROM shopping_comparisons WHERE is_active = 1 "
        "ORDER BY (amazon_price_usd / NULLIF(ali_price_usd,0)) DESC LIMIT ?",
        (count,),
    )
    return [Comparison(
        product_name=r["product_name"],
        ali_price_usd=r["ali_price_usd"], amazon_price_usd=r["amazon_price_usd"],
        ali_rating=r["ali_rating"], ali_orders=r["ali_orders"] or "",
        amazon_rating=r["amazon_rating"], ali_url=r["ali_url"] or "",
        amazon_url=r["amazon_url"] or "",
    ) for r in rows]


# ── 카피 작성 (LLM — 가격 발명 금지) ───────────────────────────────────────────
_COPY_PROMPT = """You write honest shopping-comparison cards for a global English audience.
These are REAL products with REAL prices we verified on AliExpress and Amazon.

Products (name | AliExpress price | Amazon price):
{block}

Write the copy. Do NOT change or invent any prices — they are fixed facts.

Return STRICT JSON only:
{{
  "title": "first-person hook, max 9 words, no emoji (e.g. 'I stopped overpaying on Amazon')",
  "subtitle": "one short honest line",
  "items": [
    {{"product_name": "<exact name given>",
      "note": "ONE honest first-person line about the value, max 11 words, no fake claims"}}
  ],
  "cta": "personal save/share line, max 8 words, no emoji"
}}
VOICE: honest, first person, casual. NO hype ("insane/crazy/must-buy"). Do not invent specs or prices."""


def generate_shopping(db: CardsDB, *, count: int = 4) -> ShoppingContent:
    comps = fetch_comparisons(db, count=count)
    if not comps:
        raise ValueError(
            "shopping_comparisons 가 비어있음 — 실제 비교 데이터를 먼저 입력하세요 "
            "(add_comparison). 가격은 발명하지 않습니다.")

    block = "\n".join(
        f"- {c.product_name} | AliExpress ${c.ali_price_usd} | Amazon ${c.amazon_price_usd}"
        for c in comps)
    data = generate_json(_COPY_PROMPT.format(block=block), temperature=0.85, max_tokens=1500)

    by_name = {str(i.get("product_name", "")).strip().lower(): i
               for i in (data.get("items") or [])}
    for c in comps:
        c.note = str((by_name.get(c.product_name.strip().lower()) or {}).get("note", "")).strip()

    return ShoppingContent(
        title=str(data.get("title", "")).strip() or "AliExpress vs Amazon, real prices",
        subtitle=str(data.get("subtitle", "")).strip(),
        cta=str(data.get("cta", "")).strip() or "Save before your next Amazon order",
        items=comps,
    )


def to_slides(content: ShoppingContent) -> list[Slide]:
    slides: list[Slide] = [
        Slide(type="hook", badge="PRICE CHECK",
              title=content.title, subtitle=content.subtitle),
    ]
    for c in content.items:
        save_pct = ""
        if c.amazon_price_usd > c.ali_price_usd and c.multiple >= 1.2:
            save_pct = f"{c.multiple}x cheaper on AliExpress"
        slides.append(Slide(
            type="compare",
            title=c.product_name,
            left={"label": "AliExpress",
                  "price": f"${c.ali_price_usd:g}",
                  "note": (c.ali_orders or (f"{c.ali_rating}/5" if c.ali_rating else ""))},
            right={"label": "Amazon",
                   "price": f"${c.amazon_price_usd:g}",
                   "note": (f"{c.amazon_rating}/5" if c.amazon_rating else "Same product")},
            body_lines=[save_pct] if save_pct else [],
            subtitle=c.note,
        ))
    slides.append(Slide(
        type="cta",
        title=f"{content.cta} 🛒",
        body_lines=[
            "💾  Save this before you overpay",
            "📤  Send to someone who shops Amazon",
            "💬  Want more comparisons? Comment",
        ],
    ))
    return slides


def slides_to_json(slides: list[Slide]) -> str:
    return json.dumps([
        {"slide_num": i + 1, "type": s.type, "title": s.title,
         "subtitle": s.subtitle, "body_lines": s.body_lines, "badge": s.badge}
        for i, s in enumerate(slides)
    ], ensure_ascii=False)
