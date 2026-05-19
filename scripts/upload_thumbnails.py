"""기존 업로드 영상에 썸네일 소급 등록.

실행:
    python -m scripts.upload_thumbnails          # 전체 처리
    python -m scripts.upload_thumbnails --dry-run # 생성만, YouTube 등록 생략
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from src.config import get_settings
from src.db import open_database
from src.renderer.thumbnail import ThumbnailInput, generate as gen_thumb
from src.uploader.youtube import YouTubeUploader
from src.utils.logging import get_logger, setup_logging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="썸네일 생성만, YouTube 미등록")
    parser.add_argument("--limit", type=int, default=0, help="처리 건수 제한 (0=전체)")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(
        log_dir=settings.section("observability").get("log_dir", "logs"),
        level=settings.secrets.log_level,
        project_root=PROJECT_ROOT,
    )
    log = get_logger("upload_thumbnails")

    db_cfg = settings.section("database")
    db = open_database(settings.project_path(db_cfg.get("path", "data/shorts.db")), init=True)

    # thumbnail_path 컬럼 마이그레이션 (없으면 추가)
    try:
        db.execute("ALTER TABLE videos ADD COLUMN thumbnail_path TEXT")
        print("마이그레이션: thumbnail_path 컬럼 추가")
    except Exception:
        pass

    # 업로드 성공 + youtube_video_id 있는 영상 전체 조회
    rows = db.fetchall("""
        SELECT u.id  AS uid,
               u.youtube_video_id,
               u.title,
               v.id AS vid,
               v.thumbnail_path,
               v.bg_video_path,
               s.title  AS script_title,
               s.hook,
               s.twist,
               s.hook_pattern
        FROM uploads u
        JOIN videos  v ON v.id = u.video_id
        JOIN scripts s ON s.id = v.script_id
        WHERE u.status = 'success'
          AND u.youtube_video_id IS NOT NULL
          AND u.youtube_video_id != ''
        ORDER BY u.id DESC
    """)

    if args.limit:
        rows = rows[: args.limit]

    fonts_dir   = PROJECT_ROOT / "assets" / "fonts"
    thumb_dir   = PROJECT_ROOT / "output" / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)

    # YouTube 업로더 초기화
    uploader: YouTubeUploader | None = None
    if not args.dry_run:
        uploader_cfg  = settings.section("uploader")
        oauth_clients = uploader_cfg.get("oauth_clients", []) or [{"name": "default"}]
        oauth_client  = oauth_clients[0]
        client_secret_env = oauth_client.get("client_secret_env", "YOUTUBE_CLIENT_SECRET_PATH")
        token_env         = oauth_client.get("token_env", "YOUTUBE_TOKEN_PATH")

        def _resolve(key: str) -> str:
            return getattr(settings.secrets, key.lower(), key)

        client_secret_path = PROJECT_ROOT / _resolve(client_secret_env)
        token_path         = PROJECT_ROOT / _resolve(token_env)

        if client_secret_path.exists():
            uploader = YouTubeUploader(
                client_secret_path=client_secret_path,
                token_path=token_path,
            )
        else:
            print(f"[WARN] OAuth client_secret 미존재: {client_secret_path}")
            print("       --dry-run 모드로 전환합니다.")
            args.dry_run = True

    total = len(rows)
    gen_ok = gen_fail = upload_ok = upload_fail = skip = 0

    print(f"\n처리 대상: {total}건  (dry_run={args.dry_run})\n")

    for i, r in enumerate(rows, 1):
        vid   = r["vid"]
        yt_id = r["youtube_video_id"]
        title = (r["title"] or r["script_title"] or "")[:50]
        print(f"[{i:02d}/{total}] v{vid}  yt={yt_id}  {title}")

        # ── 1. 썸네일 파일 확보 ──────────────────────────────────
        thumb_path_str = r["thumbnail_path"]
        thumb_path = Path(thumb_path_str) if thumb_path_str else None

        if thumb_path and thumb_path.exists():
            print(f"       썸네일 파일 존재: {thumb_path.name}")
        else:
            # 새로 생성
            bg = Path(r["bg_video_path"]) if r["bg_video_path"] else None
            inp = ThumbnailInput(
                title=r["script_title"] or "",
                hook=r["hook"] or "",
                twist=r["twist"] or "",
                hook_pattern=r["hook_pattern"] or "",
            )
            out = thumb_dir / f"thumb_{vid}.jpg"
            try:
                thumb_path = gen_thumb(inp, out, fonts_dir, bg_video=bg)
                db.execute(
                    "UPDATE videos SET thumbnail_path = ? WHERE id = ?",
                    (str(thumb_path), vid),
                )
                print(f"       생성 완료: {thumb_path.name}  ({thumb_path.stat().st_size // 1024} KB)")
                gen_ok += 1
            except Exception as e:
                print(f"       [ERROR] 생성 실패: {e}")
                log.error("thumb_gen_failed", vid=vid, error=repr(e))
                gen_fail += 1
                continue

        # ── 2. YouTube 썸네일 등록 ────────────────────────────────
        if args.dry_run:
            print("       [dry-run] YouTube 등록 생략")
            skip += 1
            continue

        if thumb_path.stat().st_size >= 2 * 1024 * 1024:
            print(f"       [WARN] 파일 크기 초과 ({thumb_path.stat().st_size // 1024} KB ≥ 2 MB), 건너뜀")
            skip += 1
            continue

        assert uploader is not None
        try:
            ok = uploader.upload_thumbnail(
                youtube_video_id=yt_id,
                thumbnail_path=thumb_path,
            )
            if ok:
                print(f"       YouTube 썸네일 등록 완료 ✓")
                db.execute(
                    "UPDATE api_usage SET units_used = units_used WHERE 1=0"  # no-op; 별도 기록
                )
                db.execute(
                    "INSERT INTO api_usage (api_name, units_used, succeeded) VALUES ('youtube', 50, 1)"
                )
                upload_ok += 1
            else:
                print(f"       [FAIL] YouTube 등록 실패 (권한 또는 영상 삭제 가능성)")
                upload_fail += 1
        except Exception as e:
            print(f"       [ERROR] {e}")
            log.error("thumb_upload_failed", vid=vid, yt_id=yt_id, error=repr(e))
            upload_fail += 1

    # ── 결과 요약 ────────────────────────────────────────────────
    print(f"""
══════════════════════════════════
썸네일 소급 등록 완료
  생성 성공  : {gen_ok}건
  생성 실패  : {gen_fail}건
  YouTube 등록: {upload_ok}건 성공 / {upload_fail}건 실패
  건너뜀     : {skip}건
══════════════════════════════════""")

    db.close()


if __name__ == "__main__":
    main()
