"""업로드 단계 (FR-6).

- Quota 가드 (일 10,000 units, 1건 1,600 units)
- AI 공시 다층 적용 (FR-6.8): 설명 prefix + 해시태그 + Studio UI 토글 (별도)
- 업로드 간격 ±20분 랜덤화는 스케줄러 측 책임 (FR-6.9)
"""

from __future__ import annotations

from pathlib import Path

from ..uploader.youtube import UploadMetadata, YouTubeUploader
from .context import PipelineContext, StageError, StageSkipped, stage_timer

# 채널 고정 기본 태그 — 매 영상에 항상 포함 (알고리즘 채널 정체성 강화)
_CHANNEL_BASE_TAGS = [
    "#중학생공부법", "#공부법", "#공부루틴", "#성적올리는법",
    "#중학생", "#공부팁",
]


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

        # 일일 업로드 상한 가드 — 스케줄 배치 수(4회)와 일치, 버스트 방지
        pipeline_cfg = ctx.section("pipeline")
        daily_target = int(pipeline_cfg.get("daily_target_count", 4))
        uploaded_today = ctx.repos.uploads.count_uploaded_today(oauth_client_name=oauth_name)
        if uploaded_today >= daily_target:
            raise StageSkipped(
                f"일일 업로드 상한 도달: {uploaded_today}/{daily_target}개 — "
                f"영상은 렌더까지 완료, 내일 quota 리셋 후 배치에서 자동 업로드"
            )

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
        # 채널 고정 태그 + 콘텐츠별 태그 + LLM 생성 태그 순으로 병합
        shorts_tag = "#Shorts"
        hashtags = [t for t in hashtags if t != shorts_tag]
        extra_tags = _CHANNEL_BASE_TAGS + _content_tags(script)
        hashtags = list(dict.fromkeys([shorts_tag] + extra_tags + hashtags + required_tags))

        hook_text  = (script.get("hook")  or "").strip()
        body_text  = (script.get("body")  or "").strip()
        twist_text = (script.get("twist") or "").strip()
        title_text = (script.get("title") or "").strip()

        # 해시태그 줄바꿈 구분 — YouTube에서 클릭 가능한 해시태그로 인식
        hashtag_line = " ".join(hashtags)

        # 설명란 첫 줄 SEO 키워드 — YouTube 크롤러가 가장 먼저 읽는 위치
        seo_line = _seo_keyword_line(script)

        description_lines = [
            seo_line,
            "",
            title_text,
            "",
            "▶ " + hook_text,
            "",
            body_text,
            "",
            "💡 " + twist_text,
            "",
            "─" * 30,
            "",
            hashtag_line,
            "",
            "─" * 30,
            ai_prefix if ai_prefix else "※ 이 영상은 AI 음성·영상 도구를 활용해 제작했습니다.",
            "📌 구독과 좋아요는 더 좋은 콘텐츠 제작에 큰 힘이 됩니다!",
        ]
        description = "\n".join(line for line in description_lines)

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
            tags=_build_tags(hashtags),
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


def _content_tags(script: dict) -> list[str]:
    """스크립트 내용 분석 → 콘텐츠별 추가 태그 반환."""
    full = " ".join(filter(None, [
        script.get("hook", ""), script.get("body", ""),
        script.get("twist", ""), script.get("title", ""),
    ]))
    tags: list[str] = []
    if any(k in full for k in ("기말", "기말고사")):
        tags += ["#기말고사", "#기말고사공부법"]
    if any(k in full for k in ("중간", "중간고사")):
        tags += ["#중간고사", "#중간고사공부법"]
    if "수행평가" in full:
        tags += ["#수행평가", "#수행평가꿀팁"]
    if "포모도로" in full:
        tags += ["#포모도로공부법"]
    if any(k in full for k in ("암기", "암기법")):
        tags += ["#암기법"]
    if any(k in full for k in ("집중", "집중력")):
        tags += ["#공부집중력"]
    if "루틴" in full:
        tags += ["#공부루틴", "#하루루틴"]
    if "오답" in full:
        tags += ["#오답노트"]
    if any(k in full for k in ("시험", "D-day")):
        tags += ["#시험대비", "#시험공부"]
    return tags


def _seo_keyword_line(script: dict) -> str:
    """설명란 첫 줄 SEO 키워드 라인 생성 (최대 3개 키워드 | 구분)."""
    full = " ".join(filter(None, [
        script.get("hook", ""), script.get("body", ""),
        script.get("twist", ""), script.get("title", ""),
    ]))
    keywords = ["중학생 공부법"]
    if any(k in full for k in ("기말", "기말고사")):
        keywords.append("기말고사 대비")
    elif any(k in full for k in ("중간", "중간고사")):
        keywords.append("중간고사 대비")
    elif "시험" in full:
        keywords.append("시험 공부법")
    if "수행평가" in full:
        keywords.append("수행평가 꿀팁")
    elif "포모도로" in full:
        keywords.append("포모도로 공부법")
    elif "루틴" in full:
        keywords.append("공부 루틴")
    elif any(k in full for k in ("집중", "집중력")):
        keywords.append("공부 집중력")
    return " | ".join(keywords[:3])


def _build_tags(hashtags: list[str]) -> list[str]:
    """해시태그 리스트 → YouTube tags 배열.

    YouTube Data API v3: 태그 전체 합산 500자 이내, 태그당 최대 30자.
    # 접두사 제거 후 30자 초과 태그 제외, 누적 500자 이내로 최대한 포함.
    """
    result: list[str] = []
    total_chars = 0
    for tag in hashtags:
        clean = tag.lstrip("#").strip()
        if not clean or len(clean) > 30:
            continue
        if total_chars + len(clean) + (1 if result else 0) > 500:
            break
        result.append(clean)
        total_chars += len(clean) + (1 if len(result) > 1 else 0)
    return result
