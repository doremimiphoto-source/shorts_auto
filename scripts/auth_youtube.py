"""YouTube OAuth 2.0 초기 인증 스크립트.

브라우저에서 Google 계정 로그인 → 권한 승인 → token.json 자동 저장.
저장된 token.json은 이후 파이프라인 자동 갱신(refresh_token)으로 재사용된다.

사용:
    python -m scripts.auth_youtube
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings  # noqa: E402

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def main() -> int:
    settings = get_settings()
    s = settings.secrets

    client_secret_path = PROJECT_ROOT / s.youtube_client_secret_path
    token_path = PROJECT_ROOT / s.youtube_token_path

    if not client_secret_path.exists():
        print(f"[ERROR] client_secret.json 없음: {client_secret_path}")
        print("  Google Cloud Console → API 및 서비스 → 사용자 인증 정보")
        print("  → OAuth 2.0 클라이언트 ID(데스크톱 앱) → JSON 다운로드")
        print(f"  → {client_secret_path} 에 저장")
        return 1

    from google_auth_oauthlib.flow import InstalledAppFlow

    print(f"[INFO] client_secret: {client_secret_path.name}")
    print("[INFO] 브라우저가 열립니다. Google 계정으로 로그인 후 채널 권한을 승인하세요.")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"[OK] 토큰 저장 완료: {token_path}")

    # 채널 정보 확인
    try:
        from googleapiclient.discovery import build

        service = build("youtube", "v3", credentials=creds, cache_discovery=False)
        resp = service.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if items:
            ch = items[0]["snippet"]
            print(f"[OK] 채널 확인: {ch['title']} (id={items[0]['id']})")
        else:
            print("[WARN] 채널 목록 비어있음 — YouTube 채널이 생성되어 있는지 확인")
    except Exception as e:
        print(f"[WARN] 채널 정보 조회 실패 (무시): {e}")

    print()
    print("이제 파이프라인을 --skip-upload 없이 실행할 수 있습니다:")
    print("  python -m src.main run")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
