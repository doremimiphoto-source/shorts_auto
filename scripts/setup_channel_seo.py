"""채널 키워드(SEO) 및 채널 설명 업데이트.

YouTube 검색 알고리즘이 채널 정체성을 파악하는 핵심 신호 설정.
채널 키워드는 YouTube Studio > 채널 > 기본 정보 > 키워드와 동일.

실행:
    python -m scripts.setup_channel_seo
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.uploader.youtube import YouTubeUploader

# ── 채널 키워드 (최대 500자 합산) ────────────────────────────────
# 검색 의도 기반: 중학생이 실제로 검색하는 쿼리 중심으로 구성
CHANNEL_KEYWORDS = [
    "중학생 공부법",
    "공부법",
    "내신 공부",
    "성적 올리는 법",
    "공부 루틴",
    "기말고사 공부법",
    "중간고사 공부",
    "수행평가 꿀팁",
    "공부 집중력",
    "오답 노트",
    "공부 동기부여",
    "시험 전략",
    "공부 치트키",
    "중학생 성적",
    "암기법",
    "공부 Shorts",
]

# ── 채널 설명 ──────────────────────────────────────────────────
CHANNEL_DESCRIPTION = """\
📚 중학생 공부치트키 — 매일 공부법 Shorts

중학생이 오늘 당장 써먹을 수 있는
과목별 공부법 · 시험 전략 · 수행평가 꿀팁을
매일 짧고 강렬하게 전달합니다.

✅ 이런 분께 추천합니다
- 성적을 올리고 싶은 중학생
- 공부법을 찾고 있는 학부모님
- 기말·중간고사를 앞둔 수험생

🔔 구독하면 매일 새 공부 치트키가 올라옵니다!

※ 음성·영상은 AI 도구를 활용해 제작합니다.
"""


def main() -> None:
    settings = get_settings()
    uploader_cfg = settings.section("uploader")
    oauth_clients = uploader_cfg.get("oauth_clients", []) or [{"name": "default"}]
    oauth_client = oauth_clients[0]

    client_secret_env = oauth_client.get("client_secret_env", "YOUTUBE_CLIENT_SECRET_PATH")
    token_env = oauth_client.get("token_env", "YOUTUBE_TOKEN_PATH")
    client_secret_path = PROJECT_ROOT / getattr(settings.secrets, client_secret_env.lower(), client_secret_env)
    token_path = PROJECT_ROOT / getattr(settings.secrets, token_env.lower(), token_env)

    uploader = YouTubeUploader(
        client_secret_path=client_secret_path,
        token_path=token_path,
    )
    uploader._ensure_service()
    service = uploader._service

    # 내 채널 ID 조회
    me = service.channels().list(part="id,snippet,brandingSettings", mine=True).execute()
    if not me.get("items"):
        print("[ERROR] 채널을 찾을 수 없습니다. OAuth 인증을 확인하세요.")
        return

    channel = me["items"][0]
    channel_id = channel["id"]
    channel_title = channel["snippet"].get("title", "")
    print(f"채널: {channel_title}  ({channel_id})")

    # 현재 키워드 출력
    cur_keywords = channel.get("brandingSettings", {}).get("channel", {}).get("keywords", "")
    print(f"현재 키워드: {cur_keywords[:80]}{'...' if len(cur_keywords) > 80 else ''}")

    # 키워드 문자열 구성 — YouTube는 공백 포함 키워드를 따옴표로 감쌈
    kw_parts = []
    for kw in CHANNEL_KEYWORDS:
        kw_parts.append(f'"{kw}"' if " " in kw else kw)
    keywords_str = " ".join(kw_parts)
    print(f"새 키워드 ({len(keywords_str)}자): {keywords_str[:120]}")

    # 채널 업데이트
    body = {
        "id": channel_id,
        "brandingSettings": {
            "channel": {
                "keywords": keywords_str,
                "description": CHANNEL_DESCRIPTION,
            }
        },
    }
    service.channels().update(part="brandingSettings", body=body).execute()
    print("\n✅ 채널 키워드 및 설명 업데이트 완료!")
    print(f"   확인: https://studio.youtube.com/channel/{channel_id}/editing/details")


if __name__ == "__main__":
    main()
