"""YouTube Data API v3 업로드 (FR-6).

- OAuth 2.0 refresh_token 기반 (FR-6.2)
- 일 quota 10,000 units 자율 관리 (FR-6.7)
- 카테고리 22 (People & Blogs) 또는 24 (Entertainment), made_for_kids=false (FR-6.5, FR-6.6)
- AI 공시 다층 적용 (FR-6.8): 설명 + 해시태그 + Studio UI 토글 (별도 Playwright)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UploadMetadata:
    title: str
    description: str
    tags: list[str] = field(default_factory=list)
    category_id: str = "22"
    privacy_status: str = "public"           # public | unlisted | private
    made_for_kids: bool = False


@dataclass
class UploadResult:
    youtube_video_id: str
    upload_url: str
    quota_units_used: int


class YouTubeUploader:
    """단일 OAuth 클라이언트로 단일 채널 업로드.

    멀티 채널 운영 시 본 클래스를 채널별 인스턴스로 다중 등록 (FR-6.10).
    """

    UPLOAD_QUOTA_COST = 1600                  # 1건당 (FR-6.7)

    def __init__(
        self,
        *,
        client_secret_path: Path,
        token_path: Path,
        scopes: list[str] | None = None,
    ) -> None:
        self.client_secret_path = client_secret_path
        self.token_path = token_path
        self.scopes = scopes or [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube",
        ]
        self._service = None

    def is_available(self) -> bool:
        return self.client_secret_path.exists()

    def _ensure_service(self) -> None:
        if self._service is not None:
            return
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds: Credentials | None = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), self.scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret_path), self.scopes)
                creds = flow.run_local_server(port=0)
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")

        self._service = build("youtube", "v3", credentials=creds, cache_discovery=False)

    def upload(self, *, video_path: Path, metadata: UploadMetadata) -> UploadResult:
        self._ensure_service()
        from googleapiclient.http import MediaFileUpload

        body = {
            "snippet": {
                "title": metadata.title,
                "description": metadata.description,
                "tags": metadata.tags,
                "categoryId": metadata.category_id,
            },
            "status": {
                "privacyStatus": metadata.privacy_status,
                "selfDeclaredMadeForKids": metadata.made_for_kids,
                "madeForKids": metadata.made_for_kids,
            },
        }
        media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/*")
        assert self._service is not None
        request = self._service.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            _status, response = request.next_chunk()

        video_id = response["id"]
        return UploadResult(
            youtube_video_id=video_id,
            upload_url=f"https://www.youtube.com/watch?v={video_id}",
            quota_units_used=self.UPLOAD_QUOTA_COST,
        )

    def upload_thumbnail(self, *, youtube_video_id: str, thumbnail_path: Path) -> bool:
        """커스텀 썸네일 등록. 성공 시 True, 실패 시 False (비치명적).

        YouTube API quota: 50 units/건.
        조건: 이미지 < 2 MB, 너비 ≥ 640 px, 16:9 권장.
        """
        self._ensure_service()
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg", resumable=False)
        assert self._service is not None
        try:
            self._service.thumbnails().set(
                videoId=youtube_video_id,
                media_body=media,
            ).execute()
            return True
        except Exception:
            return False
