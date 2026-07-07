"""어필리에이트 링크 + UTM 파라미터 생성.

승인된 파트너 ID는 CardSecrets 에서 읽는다. 미승인 상태(빈 ID)면
파트너 기본 URL + UTM 만 생성한다 (구조 선구현, ID는 발급 후 자동 주입).
"""

from __future__ import annotations

import urllib.parse

from cards.config import get_card_secrets

# 파트너 기본 URL (어필리에이트 ID 주입 위치는 {aid})
_PARTNER_BASE = {
    "booking":  "https://www.booking.com/index.html?aid={aid}",
    "tripcom":  "https://www.trip.com/?allianceid={aid}",
    "agoda":    "https://www.agoda.com/?cid={aid}",
    "klook":    "https://www.klook.com/?aid={aid}",
    "aliexpress": "https://s.click.aliexpress.com/e/{aid}",
    "amazon": "https://www.amazon.com/?tag={aid}",
    "yesstyle": "https://www.yesstyle.com/?rc={aid}",
}


def _partner_aid(partner: str) -> str:
    s = get_card_secrets()
    return {
        "booking":  s.booking_affiliate_id,
        "tripcom":  s.tripdotcom_affiliate_id,
        "klook":    s.klook_affiliate_id,
        "aliexpress": s.aliexpress_tracking_id,
        "amazon": s.amazon_associate_tag,
        "yesstyle": s.yesstyle_affiliate_id,
    }.get(partner, "")


def add_utm(url: str, *, platform: str, vertical: str, campaign: str) -> str:
    """기존 URL에 UTM 파라미터 추가 (기존 쿼리 보존)."""
    utm = {
        "utm_source": platform,
        "utm_medium": "carousel",
        "utm_campaign": f"{vertical}_{campaign}",
    }
    parts = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(parts.query))
    q.update(utm)
    new_q = urllib.parse.urlencode(q)
    return urllib.parse.urlunparse(parts._replace(query=new_q))


def build_link(partner: str, *, platform: str, vertical: str, campaign: str,
               product_url: str | None = None) -> str:
    """파트너 어필리에이트 링크 + UTM 생성.

    product_url 지정 시 그 URL 기준(딥링크), 없으면 파트너 기본 URL.
    """
    if product_url:
        base = product_url
    else:
        aid = _partner_aid(partner)
        tmpl = _PARTNER_BASE.get(partner, "https://example.com/?aid={aid}")
        base = tmpl.format(aid=aid or "PENDING")
    return add_utm(base, platform=platform, vertical=vertical, campaign=campaign)
