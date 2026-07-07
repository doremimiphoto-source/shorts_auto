"""Pinterest API v5 핀 업로더 (단일 정적 핀, image_base64 방식).

IMPL_AUDIT H-02: Idea Pins(멀티페이지)는 파트너 승인 필요 →
MVP는 일반 정적 핀(이미지 1장)에 어필리에이트 직링크를 삽입한다.
Imgur 불필요 (Pinterest는 base64 직접 업로드 지원).
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

from cards.config import get_card_secrets

_API = "https://api.pinterest.com/v5/pins"


class PinterestError(RuntimeError):
    pass


def upload_pin(*, board_id: str, image_path: Path, title: str,
               description: str, link: str, alt_text: str = "") -> str:
    """정적 핀 1개 업로드 → pin_id 반환. 실패 시 PinterestError."""
    secrets = get_card_secrets()
    token = secrets.pinterest_access_token
    if not token:
        raise PinterestError("pinterest_access_token 미설정")
    if not board_id:
        raise PinterestError("board_id 미설정")

    img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    payload = {
        "board_id": board_id,
        "title": title[:100],
        "description": description[:800],
        "link": link,
        "alt_text": (alt_text or title)[:500],
        "media_source": {
            "source_type": "image_base64",
            "content_type": "image/jpeg",
            "data": img_b64,
        },
    }
    req = urllib.request.Request(
        _API,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return str(data.get("id", ""))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:300]
        raise PinterestError(f"HTTP {e.code}: {body}") from e
    except Exception as e:
        raise PinterestError(repr(e)[:200]) from e


def board_for_vertical(vertical: str) -> str:
    s = get_card_secrets()
    return {
        "v1_shopping": s.pinterest_board_v1,
        "v2_travel":   s.pinterest_board_v2,
        "v3_kbeauty":  s.pinterest_board_v3,
    }.get(vertical, "")
