"""Pinterest API v5 액세스 토큰 발급 헬퍼 (OAuth 2.0 자동 처리).

사전 준비:
  1. https://developers.pinterest.com 에서 앱 생성 → App ID / App secret 확보
  2. 앱의 Redirect URI 에 정확히 등록:  http://localhost:8085/callback
  3. .env 에 PINTEREST_APP_ID / PINTEREST_APP_SECRET 입력

실행:
  .venv/bin/python -m cards.auth_pinterest

동작:
  - 인증 URL 을 브라우저로 열고
  - localhost:8085 로 돌아온 code 를 자동 수신
  - code 를 access_token + refresh_token 으로 교환
  - .env 에 붙여넣을 값을 출력

분리 원칙: src/ 미import.
"""

from __future__ import annotations

import base64
import json
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from cards.config import get_card_secrets

REDIRECT_URI = "http://localhost:8085/callback"
SCOPES = "boards:read,boards:write,pins:read,pins:write"
AUTH_URL = "https://www.pinterest.com/oauth/"
TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"

_received: dict[str, str] = {}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        q = urllib.parse.urlparse(self.path)
        if not q.path.startswith("/callback"):
            self.send_response(404); self.end_headers(); return
        params = dict(urllib.parse.parse_qsl(q.query))
        _received.update(params)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = ("✅ 인증 완료. 터미널로 돌아가세요."
               if "code" in params else f"❌ 오류: {params}")
        self.wfile.write(f"<html><body><h2>{msg}</h2></body></html>".encode("utf-8"))

    def log_message(self, *a):  # 서버 로그 억제
        pass


def _exchange_code(code: str, app_id: str, app_secret: str) -> dict:
    basic = base64.b64encode(f"{app_id}:{app_secret}".encode()).decode()
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST", headers={
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    s = get_card_secrets()
    if not (s.pinterest_app_id and s.pinterest_app_secret):
        print("❌ .env 에 PINTEREST_APP_ID / PINTEREST_APP_SECRET 를 먼저 입력하세요.")
        print("   앱 생성: https://developers.pinterest.com (My apps → Connect app)")
        print(f"   앱의 Redirect URI 에 정확히 등록: {REDIRECT_URI}")
        return 1

    auth = f"{AUTH_URL}?" + urllib.parse.urlencode({
        "client_id": s.pinterest_app_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": "hfd",
    })

    print("=" * 60)
    print("1) 아래 URL 이 브라우저에서 열립니다. Pinterest 로그인 후 'Allow' 클릭.")
    print("   (안 열리면 직접 복사해서 여세요)")
    print(auth)
    print("=" * 60)

    server = HTTPServer(("localhost", 8085), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        webbrowser.open(auth)
    except Exception:
        pass

    print("2) 브라우저 인증 대기 중... (localhost:8085 수신)")
    while "code" not in _received and "error" not in _received:
        pass
    server.shutdown()

    if "error" in _received:
        print(f"❌ 인증 실패: {_received}")
        return 1

    print("3) code 수신 → 토큰 교환 중...")
    try:
        tok = _exchange_code(_received["code"], s.pinterest_app_id, s.pinterest_app_secret)
    except Exception as e:
        print(f"❌ 토큰 교환 실패: {e!r}")
        print("   (Redirect URI 가 앱 설정과 정확히 일치하는지 확인하세요)")
        return 1

    access = tok.get("access_token", "")
    refresh = tok.get("refresh_token", "")
    print()
    print("=" * 60)
    print("✅ 발급 성공! 아래 줄을 .env 에 붙여넣으세요:")
    print("=" * 60)
    print(f"PINTEREST_ACCESS_TOKEN={access}")
    if refresh:
        print(f"PINTEREST_REFRESH_TOKEN={refresh}")
    print("=" * 60)
    print("다음: 보드 ID 확인 →")
    print(f'  curl -H "Authorization: Bearer {access[:12]}..." '
          'https://api.pinterest.com/v5/boards')
    return 0


if __name__ == "__main__":
    sys.exit(main())
