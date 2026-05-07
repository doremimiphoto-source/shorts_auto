"""특정 video_id를 YouTube에 업로드하는 단독 스크립트."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.db import open_database
from src.pipeline import PipelineContext
from src.pipeline.upload_stage import run as run_upload
from src.repository import Repositories
from src.utils.logging import get_logger, setup_logging


def main(video_id: int) -> None:
    settings = get_settings()
    setup_logging(
        log_dir=settings.section("observability").get("log_dir", "logs"),
        level=settings.secrets.log_level,
        project_root=PROJECT_ROOT,
    )
    log = get_logger("upload")
    run_id = uuid.uuid4().hex[:12]

    db_cfg = settings.section("database")
    db_path = settings.project_path(db_cfg.get("path", "data/shorts.db"))
    db = open_database(db_path, init=True)
    repos = Repositories(db)
    ctx = PipelineContext(
        settings=settings,
        repos=repos,
        run_id=run_id,
        log=log,
        project_root=PROJECT_ROOT,
    )

    upload_id = run_upload(ctx, video_id=video_id)

    upload_row = ctx.repos.db.fetchone(
        "SELECT youtube_video_id, title FROM uploads WHERE id = ?", (upload_id,)
    )
    yt_id = (upload_row or {}).get("youtube_video_id", "")
    yt_title = (upload_row or {}).get("title", "")
    print(f"\n[업로드 완료]")
    print(f"제목: {yt_title}")
    print(f"URL : https://www.youtube.com/watch?v={yt_id}")
    db.close()


if __name__ == "__main__":
    vid = int(sys.argv[1]) if len(sys.argv) > 1 else 9
    main(vid)
