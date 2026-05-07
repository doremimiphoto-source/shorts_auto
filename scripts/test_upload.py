"""업로드 스테이지 단독 테스트 (video_id 지정).

사용:
    python -m scripts.test_upload --video-id 6
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings  # noqa: E402
from src.db import open_database  # noqa: E402
from src.pipeline.context import PipelineContext  # noqa: E402
from src.pipeline.upload_stage import run as run_upload  # noqa: E402
from src.repository import Repositories  # noqa: E402
from src.utils.logging import get_logger, setup_logging  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", type=int, required=True)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    settings = get_settings(args.config)
    setup_logging(log_dir="logs", level="INFO", project_root=PROJECT_ROOT)
    log = get_logger("test_upload")

    db_cfg = settings.section("database")
    db = open_database(settings.project_path(db_cfg.get("path", "data/shorts.db")), init=True)
    repos = Repositories(db)
    ctx = PipelineContext(
        settings=settings,
        repos=repos,
        run_id=uuid.uuid4().hex[:12],
        log=log,
        project_root=PROJECT_ROOT,
    )

    try:
        upload_id = run_upload(ctx, video_id=args.video_id)
        print(f"\n[OK] 업로드 성공: upload_id={upload_id}")

        row = repos.db.fetchone("SELECT youtube_video_id FROM uploads WHERE id = ?", (upload_id,))
        if row and row.get("youtube_video_id"):
            yt_id = row["youtube_video_id"]
            print(f"[OK] YouTube URL: https://www.youtube.com/watch?v={yt_id}")
        return 0
    except Exception as e:
        print(f"\n[FAIL] {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
