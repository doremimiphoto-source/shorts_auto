"""업로드 단계 (FR-6).

- Quota 가드 (일 10,000 units, 1건 1,600 units)
- AI 공시 다층 적용 (FR-6.8): 설명 prefix + 해시태그 + Studio UI 토글 (별도)
- 업로드 간격 ±20분 랜덤화는 스케줄러 측 책임 (FR-6.9)
"""

from __future__ import annotations

from pathlib import Path

from ..uploader.youtube import UploadMetadata, YouTubeUploader
from .context import PipelineContext, StageError, StageSkipped, stage_timer


def run(ctx: PipelineContext, *, video_id: int) -> int:
    """업로드 단계. upload_id 반환."""
    with stage_timer(ctx, "upload") as state:
        video = ctx.repos.videos.get(video_id)
        if video is None or not video.get("video_path"):
            raise StageError(f"video_id={video_id} 또는 video_path 미존재")
        if not video.get("valid"):
            raise StageError("영상 검증 통과하지 않음 — 업로드 차단")
        script = ctx.repos.scripts.get(video["script_id"])
        if script is None:
            raise StageError(f"script_id={video['script_id']} 미존재")

        uploader_cfg = ctx.section("uploader")
        api_cfg = uploader_cfg.get("api", {})
        meta_cfg = uploader_cfg.get("metadata", {})
        ai_cfg = uploader_cfg.get("ai_disclosure", {})
        oauth_clients = uploader_cfg.get("oauth_clients", []) or [{"name": "default"}]
        oauth_client = oauth_clients[0]
        oauth_name = oauth_client.get("name", "default")

        # Quota 가드 (FR-6.7)
        used = ctx.repos.uploads.quota_used_today(oauth_client_name=oauth_name)
        cost = int(api_cfg.get("upload_cost_units", 1600))
        margin = int(api_cfg.get("safety_margin_units", 1000))
        daily = int(api_cfg.get("daily_quota_units", 10000))
        if used + cost + margin > daily:
            raise StageSkipped(f"YouTube quota 초과 우려: used={used}, cost={cost}, daily={daily}")

        # 메타데이터 구성
        title = (script.get("title") or "사연")[:90] + str(meta_cfg.get("title_suffix", " #Shorts"))
        ai_prefix = str(ai_cfg.get("description_prefix", ""))
        required_tags = list(ai_cfg.get("required_hashtags", ["#AI", "#AIVoice"]))

        import json
        try:
            hashtags = json.loads(script.get("hashtags_json") or "[]")
        except (TypeError, ValueError):
            hashtags = []
        # #Shorts를 맨 앞에 배치 — YouTube가 쇼츠로 분류하는 핵심 신호
        shorts_tag = "#Shorts"
        hashtags = [t for t in hashtags if t != shorts_tag]
        hashtags = list(dict.fromkeys([shorts_tag] + hashtags + required_tags))

        hook_text  = (script.get("hook")  or "").strip()
        body_text  = (script.get("body")  or "").strip()
        twist_text = (script.get("twist") or "").strip()
        description_lines = [
            hook_text,
            "",
            body_text,
            "",
            twist_text,
            "",
            " ".join(hashtags),
            "",
            "—",
            ai_prefix if ai_prefix else "※ 음성·영상은 AI 도구를 활용해 제작했습니다.",
        ]
        description = "\n".join(description_lines)

        upload_id = ctx.repos.uploads.insert(
            video_id=video_id,
            oauth_client_name=oauth_name,
            title=title,
            description=description,
            privacy_status=str(meta_cfg.get("privacy_status", "public")),
            quota_units_used=cost,
            status="queued",
        )

        # 업로드 호출
        client_secret_env = oauth_client.get("client_secret_env", "YOUTUBE_CLIENT_SECRET_PATH")
        token_env = oauth_client.get("token_env", "YOUTUBE_TOKEN_PATH")
        client_secret_path = ctx.project_root / _resolve_env(ctx.settings.secrets, client_secret_env)
        token_path = ctx.project_root / _resolve_env(ctx.settings.secrets, token_env)

        if not client_secret_path.exists():
            ctx.repos.uploads.update_status(upload_id, status="failed", error_msg=f"client_secret 미존재: {client_secret_path}")
            raise StageSkipped(f"OAuth client_secret 미존재: {client_secret_path}")

        uploader = YouTubeUploader(
            client_secret_path=client_secret_path,
            token_path=token_path,
        )
        meta = UploadMetadata(
            title=title,
            description=description,
            tags=[t.lstrip("#") for t in hashtags if t][:10],
            category_id=str(meta_cfg.get("category_id", "22")),
            privacy_status=str(meta_cfg.get("privacy_status", "public")),
            made_for_kids=bool(meta_cfg.get("made_for_kids", False)),
        )

        try:
            result = uploader.upload(video_path=Path(video["video_path"]), metadata=meta)
        except Exception as e:
            ctx.repos.uploads.update_status(upload_id, status="failed", error_msg=repr(e))
            ctx.repos.api_usage.record(api_name="youtube", units_used=cost, succeeded=False, error_code=type(e).__name__)
            raise StageError(f"YouTube 업로드 실패: {e}") from e

        ctx.repos.uploads.update_youtube_id(upload_id, youtube_video_id=result.youtube_video_id, ai_disclosure_set=0)
        ctx.repos.uploads.update_status(upload_id, status="success")
        ctx.repos.api_usage.record(api_name="youtube", units_used=result.quota_units_used, succeeded=True)

        state["message"] = f"upload_id={upload_id}, youtube={result.youtube_video_id}"
        return upload_id


def _resolve_env(secrets, key: str) -> str:
    """secrets 객체의 소문자 속성으로 매핑 (예: YOUTUBE_CLIENT_SECRET_PATH → youtube_client_secret_path)."""
    attr = key.lower()
    return getattr(secrets, attr, key)
