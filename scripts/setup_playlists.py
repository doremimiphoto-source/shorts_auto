"""카테고리별 YouTube 재생목록 자동 생성.

기존 재생목록과 중복 생성하지 않음 (title 기준 비교).
생성된 playlist_id는 data/playlists.json 에 저장.

실행:
    python -m scripts.setup_playlists
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.uploader.youtube import YouTubeUploader

# ── 생성할 재생목록 정의 ──────────────────────────────────────────
PLAYLISTS = [
    {
        "title": "📚 과목별 공부법 · 수행평가 꿀팁",
        "description": "국어·수학·영어·과학·사회 등 과목별 공부법과 수행평가 고득점 전략을 Shorts로 정리했습니다.",
        "tag": "교과별",
    },
    {
        "title": "📝 시험 전략 · 오답 관리",
        "description": "기말·중간고사 D-카운트다운별 최적 플랜, 오답 원인 분석, 시험장 전략을 담은 시리즈입니다.",
        "tag": "시험전략",
    },
    {
        "title": "🏫 학교생활 치트키",
        "description": "수업·발표·선생님·친구 등 학교 안 실전 상황에서 바로 써먹는 팁 모음입니다.",
        "tag": "학교생활",
    },
    {
        "title": "🔥 멘탈 · 동기부여",
        "description": "슬럼프 탈출, 집중력 회복, 공부 의욕 채우는 심리 기술을 짧게 전달합니다.",
        "tag": "멘탈동기",
    },
    {
        "title": "⏰ 생활습관 · 건강 루틴",
        "description": "수면·스마트폰·식단·운동 등 성적과 직결되는 일상 습관 개선 Shorts 모음입니다.",
        "tag": "생활습관",
    },
    {
        "title": "💬 친구 · 부모님과 소통하는 법",
        "description": "갈등 해결, 협상, 공감 대화법 등 실제로 쓸 수 있는 말투와 전략을 담았습니다.",
        "tag": "관계소통",
    },
    {
        "title": "🎯 진로 · 직업 탐색",
        "description": "구체적 직업 정보와 '중학교 때 이것만 했어도' 식 후회·기회 프레임 콘텐츠입니다.",
        "tag": "진로직업",
    },
    {
        "title": "💡 자기계발 · 독서 · 경제",
        "description": "습관의 복리 효과, 독서법, 용돈 관리 등 오늘 밤 바로 시작할 수 있는 콘텐츠입니다.",
        "tag": "자기계발",
    },
    {
        "title": "🍀 시험 행운 부적",
        "description": "기말·중간고사 시즌 시험 운을 올려주는 재미있는 부적 Shorts 시리즈입니다!",
        "tag": "행운부적",
    },
]


def _list_existing(service) -> dict[str, str]:
    """채널 내 기존 재생목록을 {title: playlist_id} 형태로 반환."""
    existing: dict[str, str] = {}
    next_page = None
    while True:
        req = service.playlists().list(
            part="snippet",
            mine=True,
            maxResults=50,
            pageToken=next_page,
        )
        res = req.execute()
        for item in res.get("items", []):
            existing[item["snippet"]["title"]] = item["id"]
        next_page = res.get("nextPageToken")
        if not next_page:
            break
    return existing


def _create_playlist(service, *, title: str, description: str) -> str:
    """재생목록 생성 후 playlist_id 반환."""
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "defaultLanguage": "ko",
        },
        "status": {"privacyStatus": "public"},
    }
    res = service.playlists().insert(part="snippet,status", body=body).execute()
    return res["id"]


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

    print("기존 재생목록 조회 중...")
    existing = _list_existing(service)
    print(f"  기존 재생목록 {len(existing)}개 발견")

    result: dict[str, str] = {}
    for pl in PLAYLISTS:
        title = pl["title"]
        if title in existing:
            pid = existing[title]
            print(f"  [SKIP] 이미 존재: {title}  ({pid})")
            result[pl["tag"]] = pid
        else:
            pid = _create_playlist(service, title=title, description=pl["description"])
            print(f"  [CREATE] {title}  → {pid}")
            result[pl["tag"]] = pid

    out_path = PROJECT_ROOT / "data" / "playlists.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n재생목록 ID 저장 완료: {out_path}")
    for tag, pid in result.items():
        print(f"  [{tag}] https://www.youtube.com/playlist?list={pid}")


if __name__ == "__main__":
    main()
