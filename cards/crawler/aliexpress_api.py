"""AliExpress Portals API 클라이언트 — Ali쪽 데이터 자동 수집 (V1 보조).

⚠️ UNTESTED — AliExpress Portals(Admitad) 승인 후 실응답으로 검증·수정 필요.
   승인 전에는 키가 없어 호출 시 RuntimeError. 가격 발명은 절대 하지 않음(원칙1).

용도: 승인 후 shopping_comparisons 의 Ali쪽(가격·평점·딥링크)을 자동으로 채운다.
Amazon쪽은 수동 입력(또는 추후 PA-API).

서명: AliExpress Open Platform 은 appkey + appsecret + HMAC-MD5(또는 SHA256) 서명.
     실제 파라미터/엔드포인트는 승인 후 포털 문서로 확정한다.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time

from cards.config import get_card_secrets

log = logging.getLogger(__name__)

# 승인 후 포털 문서로 확정할 값 (placeholder)
_GATEWAY = "https://api-sg.aliexpress.com/sync"
_METHOD_PRODUCT_QUERY = "aliexpress.affiliate.product.query"


def _sign(params: dict, app_secret: str) -> str:
    """HMAC-SHA256 서명 (AliExpress 표준). 승인 후 실제 방식과 대조 검증 필요."""
    base = "".join(f"{k}{params[k]}" for k in sorted(params))
    return hmac.new(app_secret.encode(), base.encode(), hashlib.sha256).hexdigest().upper()


def is_configured() -> bool:
    s = get_card_secrets()
    return bool(s.aliexpress_app_key and s.aliexpress_app_secret)


def search_products(keyword: str, *, page_size: int = 10) -> list[dict]:
    """키워드로 AliExpress 인기 제품 조회.

    ⚠️ 승인 전에는 RuntimeError. 승인 후 실응답 구조에 맞게 파싱 보강.
    """
    s = get_card_secrets()
    if not is_configured():
        raise RuntimeError(
            "AliExpress Portals 키 미설정 — 승인 후 ALIEXPRESS_APP_KEY/SECRET 입력 필요. "
            "(승인 전 V1은 shopping_comparisons 수동 큐레이션으로 동작)")

    params = {
        "app_key": s.aliexpress_app_key,
        "method": _METHOD_PRODUCT_QUERY,
        "timestamp": str(int(time.time() * 1000)),
        "sign_method": "sha256",
        "keywords": keyword,
        "page_size": str(page_size),
        "tracking_id": s.aliexpress_tracking_id or "",
    }
    params["sign"] = _sign(params, s.aliexpress_app_secret)

    # 실제 HTTP 호출은 승인 후 응답 구조 확인하여 구현/검증한다.
    raise NotImplementedError(
        "AliExpress Portals 승인 후 실응답으로 구현 예정. "
        "현재는 수동 큐레이션(add_comparison) 경로를 사용하세요.")
