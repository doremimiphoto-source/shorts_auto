"""채널 설명(한글 유지+영문 추가)·키워드를 YouTube Data API v3로 업데이트한다.

사용법:
    python -m scripts.update_channel [--dry-run]

--dry-run: API 호출 없이 최종 합산 텍스트만 출력.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.stdout is None:
    sys.stdout = open("nul", "w", encoding="utf-8")
else:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── 영문 추가 섹션 (한글 설명 뒤에 붙임) ────────────────────────────────────

_SEP = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ENGLISH_SECTION = f"""\
{_SEP}
📚 Do Re Mi(ful) Tension — Korean middle school study hacks, delivered daily!

✅ 4 uploads a day — bite-sized 10–25 sec tips you can use RIGHT NOW
✅ Final exam & midterm crunch-time routines
✅ Subject-specific high-score strategies:
   Korean · English · Math · Science · History · Ethics · PE · Music · Hanja · Chinese
✅ Memorization tricks · Time management · Focus boosters · Wrong-answer review

🎯 Every video = one actionable tip. No fluff. Just results.
📌 Subscribe for a fresh study hack every single day!

#KoreanStudy #StudyTips #MiddleSchool #ExamPrep #StudyWithMe #StudyHacks"""

CHANNEL_KEYWORDS = (
    "Korean study tips, middle school study hacks, exam prep, study motivation, "
    "study with me, study routine, memorization tricks, focus study, "
    "중학생 공부법, 내신 공부법, 수행평가 꿀팁, 기말고사 대비, 공부 루틴, "
    "성적 올리는 법, 암기법, 집중력 향상, 시험 공부법, 서술형 고득점"
)

# ─────────────────────────────────────────────────────────────────────────────


def _build_combined(korean_desc: str) -> str:
    """한글 설명에서 기존 영문 블록을 제거하고 최신 영문 블록을 뒤에 붙인다."""
    korean_part = korean_desc.strip()
    if _SEP in korean_part:
        korean_part = korean_part[: korean_part.index(_SEP)].strip()
    return korean_part + "\n\n" + ENGLISH_SECTION


def main() -> None:
    parser = argparse.ArgumentParser(description="YouTube 채널 설명·키워드 업데이트")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 내용만 출력")
    args = parser.parse_args()

    from src.config import get_settings
    from src.uploader.youtube import YouTubeUploader

    settings = get_settings()
    uploader_cfg = settings.section("uploader")
    oauth_clients = uploader_cfg.get("oauth_clients", []) or [{"name": "default"}]
    oauth_client = oauth_clients[0]

    client_secret_env = oauth_client.get("client_secret_env", "YOUTUBE_CLIENT_SECRET_PATH")
    token_env = oauth_client.get("token_env", "YOUTUBE_TOKEN_PATH")
    secrets = settings.secrets
    client_secret_path = PROJECT_ROOT / getattr(secrets, client_secret_env.lower(), "")
    token_path = PROJECT_ROOT / getattr(secrets, token_env.lower(), "")

    uploader = YouTubeUploader(client_secret_path=client_secret_path, token_path=token_path)
    uploader._ensure_service()
    svc = uploader._service
    assert svc is not None

    # 현재 채널 정보 조회
    ch_resp = svc.channels().list(part="id,snippet,brandingSettings", mine=True).execute()
    items = ch_resp.get("items", [])
    if not items:
        print("[오류] 채널을 찾을 수 없습니다.")
        return

    ch = items[0]
    channel_id = ch["id"]
    current_desc = ch.get("snippet", {}).get("description", "").strip()

    combined = _build_combined(current_desc)

    print(f"채널 ID : {channel_id}")
    print(f"현재 한글 설명 ({len(current_desc)}자):")
    print("-" * 60)
    print(current_desc)
    print("-" * 60)
    print(f"\n[최종 합산 설명 ({len(combined)}자) — YouTube Studio에 붙여넣기]")
    print("=" * 60)
    print(combined)
    print("=" * 60)
    print(f"\n[채널 키워드]\n{CHANNEL_KEYWORDS}")

    if args.dry_run:
        print("\n[dry-run] API 호출 생략.")
        return

    # brandingSettings.keywords 업데이트 (API로 가능한 유일한 채널 메타 항목)
    branding = ch.get("brandingSettings", {})
    ch_branding = branding.get("channel", {})
    ch_branding["keywords"] = CHANNEL_KEYWORDS
    ch_branding["country"] = "KR"

    svc.channels().update(
        part="brandingSettings",
        body={"id": channel_id, "brandingSettings": {"channel": ch_branding}},
    ).execute()
    print("\n✅ 채널 키워드 업데이트 완료 (API)")

    print("\n📋 채널 설명은 YouTube Studio에서 위 합산 텍스트를 붙여넣기 하세요:")
    print(f"   https://studio.youtube.com/channel/{channel_id}/editing/details")


if __name__ == "__main__":
    main()
