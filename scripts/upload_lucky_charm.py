"""시험 행운 부적 데모 영상 YouTube 업로드 (조회수 최적화 메타데이터)."""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.uploader.youtube import UploadMetadata, YouTubeUploader

VIDEO_PATH = PROJECT_ROOT / "output" / "final" / "video_29.mp4"

# ── 제목: 궁금증 유발 + 숫자 + 혜택 명시 ───────────────────────────────────
TITLE = "🍀 지금 10명에게 공유하면 시험 만점?! 전설의 행운 부적 #Shorts"

# ── 설명: 스크립트 내용 + CTA + 해시태그 풀 ─────────────────────────────────
DESCRIPTION = """\
시험 운을 바꾸는 부적이 여기에

지금 이 영상을 10명에게 공유하면 모든 시험 만점을 받는다는 오래된 전설이 있다.
믿거나 말거나, 공유한 선배들은 정말로 성적이 올랐다고 전해진다.

지금 바로 10명에게 전달해, 시험 운이 열린다!

💬 친구들에게 공유하고 행운을 나눠보세요!
👍 좋아요·구독이 큰 힘이 됩니다 🙏

#Shorts #시험운 #행운부적 #중간고사 #기말고사 #수행평가 #시험대비 #공부법 \
#고등학생 #중학생 #공부자극 #시험기간 #내신 #성적향상 #공부스타그램 \
#수능 #공부팁 #학생일상 #학교생활 #AI #AIVoice

—
본 영상은 AI 음성·각색을 사용했습니다."""

# ── 태그: 조회수 높은 학생 타깃 키워드 (최대 10개) ───────────────────────────
TAGS = [
    "시험운", "행운부적", "중간고사", "기말고사",
    "수행평가", "시험대비", "공부법", "고등학생",
    "중학생", "공부자극",
]


def main() -> None:
    if not VIDEO_PATH.exists():
        sys.exit(f"[오류] 영상 파일 없음: {VIDEO_PATH}")

    client_secret = PROJECT_ROOT / "credentials" / "client_secret.json"
    token_path    = PROJECT_ROOT / "credentials" / "token.json"

    if not client_secret.exists():
        sys.exit(f"[오류] OAuth 클라이언트 시크릿 없음: {client_secret}")

    print(f"[업로드] 파일 : {VIDEO_PATH.name}  ({VIDEO_PATH.stat().st_size / 1024:.0f} KB)")
    print(f"[업로드] 제목 : {TITLE}")
    print("[업로드] YouTube 인증 중...")

    uploader = YouTubeUploader(client_secret_path=client_secret, token_path=token_path)
    meta = UploadMetadata(
        title=TITLE,
        description=DESCRIPTION,
        tags=TAGS,
        category_id="22",         # People & Blogs
        privacy_status="public",
        made_for_kids=False,
    )

    result = uploader.upload(video_path=VIDEO_PATH, metadata=meta)

    print(f"\n[완료] YouTube 업로드 성공!")
    print(f"  영상 ID : {result.youtube_video_id}")
    print(f"  URL     : {result.upload_url}")
    print(f"  Quota   : {result.quota_units_used} units 사용")


if __name__ == "__main__":
    main()
