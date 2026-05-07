"""시험 행운 부적 데모 영상 제작.

금색(Gold) 텍스트 + 진홍(Dark Red) 아웃라인으로 부적 분위기 연출.
TTS → 자막(부적 스타일) → 렌더
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings
from src.db import open_database
from src.pipeline import PipelineContext
from src.pipeline.tts_stage import run as run_tts
from src.pipeline.render_stage import run as run_render
from src.repository import Repositories
from src.subtitle.whisper_engine import make_styled_subtitles
from src.utils.logging import get_logger, setup_logging
from src.utils.similarity import text_sha256

# ────────────────────────────────────────────────────────────────────
# 부적 대본
# hook 13자 + body 61자 + twist 19자 = 93자 (행운부적 허용 90~120자)
# ────────────────────────────────────────────────────────────────────
DEMO = {
    "hook": "시험 운을 바꾸는 부적이 여기에",
    "body": (
        "지금 이 영상을 10명에게 공유하면 모든 시험 만점을 받는다는 오래된 전설이 있다. "
        "믿거나 말거나, 공유한 선배들은 정말로 성적이 올랐다고 전해진다."
    ),
    "twist": "지금 바로 10명에게 전달해, 시험 운이 열린다!",
    "title": "🍀 시험 만점 기원 행운 부적",
    "hashtags": ["#시험운", "#행운부적", "#수행평가", "#시험대비", "#공부법", "#Shorts"],
    "emphasis_words": ["만점", "10명"],
    "hook_pattern": "lucky_charm",
    "model_used": "manual",
    "model_version": "lucky-charm-v1",
}

MOTIF = (
    "시험 기간마다 떠도는 행운 부적 전설. "
    "이 영상을 10명에게 공유하면 시험 만점을 받는다는 재미있는 이야기로 학생들의 공유를 유도하는 바이럴 콘텐츠."
)

# ────────────────────────────────────────────────────────────────────
# ASS 부적 스타일: 금색(Gold) + 진홍(Dark Red) 아웃라인
#   Gold  #FFD700 → &H0000D7FF&  (BB=00 GG=D7 RR=FF)
#   Yellow #FFFF00 → &H0000FFFF& (BB=00 GG=FF RR=FF)
#   DarkRed #800000 → &H00000080& (BB=00 GG=00 RR=80)
#   Red   #FF0000 → &H000000FF& (BB=00 GG=00 RR=FF)
# ────────────────────────────────────────────────────────────────────
STYLE_LUCKY: dict = {
    "title_anim": (
        r"{\an2\pos(540,460)"
        r"\fad(300,200)"
        r"\fnGowun Dodum\fs72\fsp0"
        r"\c&H0000D7FF&\3c&H00000080&\bord3\shad3\blur0}"
    ),
    "tag_hook": (
        r"{\an5\pos(540,1060)\fnGowun Dodum\fs92\c&H0000D7FF&\3c&H00000080&\bord5\shad2"
        r"\fscx0\fscy0\t(0,220,\fscx104\fscy104)\t(220,300,\fscx100\fscy100)\fad(200,200)}"
    ),
    "tag_body": (
        r"{\an5\move(540,1110,540,1060,0,280)"
        r"\fnGowun Dodum\fs68\c&H00FFFFFF&\3c&H00000080&\bord4\shad2\fad(200,200)}"
    ),
    "tag_twist": (
        r"{\an5\pos(540,1060)\fnGowun Dodum\fs88\c&H0000FFFF&\3c&H00000080&\bord5\shad3"
        r"\fscx0\fscy0\t(0,220,\fscx108\fscy108)\t(220,320,\fscx100\fscy100)\fad(0,280)}"
    ),
    # 강조: 빨강(Red) → 복귀(Gold)
    "emph_hook":  (r"{\c&H000000FF&\fs102\blur0}", r"{\c&H0000D7FF&\fs92\blur0}"),
    "emph_body":  (r"{\c&H000000FF&\fs78\blur0}",  r"{\c&H00FFFFFF&\fs68\blur0}"),
    "emph_twist": (r"{\c&H00FFFFFF&\fs98\blur1}",  r"{\c&H0000FFFF&\fs88\blur0}"),
}


def main() -> None:
    settings = get_settings()
    setup_logging(
        log_dir=settings.section("observability").get("log_dir", "logs"),
        level=settings.secrets.log_level,
        project_root=PROJECT_ROOT,
    )
    log = get_logger("lucky_charm")
    run_id = uuid.uuid4().hex[:12]

    db_cfg = settings.section("database")
    db_path = settings.project_path(db_cfg.get("path", "data/shorts.db"))
    db = open_database(db_path, init=True)
    repos = Repositories(db)
    ctx = PipelineContext(
        settings=settings, repos=repos, run_id=run_id,
        log=log, project_root=PROJECT_ROOT,
    )

    full_text = DEMO["hook"] + " " + DEMO["body"] + " " + DEMO["twist"]
    print(f"[부적] 대본: {full_text[:50]}...")

    # 1. Source
    motif_hash = text_sha256(MOTIF)
    existing = repos.sources.find_by_hash(motif_hash)
    source_id = existing["id"] if existing else repos.sources.insert(
        source_kind="llm_creator", raw_text_hash=motif_hash,
        motif=MOTIF, raw_text=None, source_site=None, url=None, title=DEMO["title"],
    )

    # 2. Script
    script_id = repos.db.execute(
        """INSERT INTO scripts
           (source_id, hook, body, twist, full_text, title,
            hashtags_json, hook_pattern,
            similarity_motif, similarity_30d, similarity_cum,
            model_used, model_version, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            source_id, DEMO["hook"], DEMO["body"], DEMO["twist"],
            full_text, DEMO["title"],
            json.dumps(DEMO["hashtags"], ensure_ascii=False),
            DEMO["hook_pattern"], 0.0, 0.0, 0.0,
            DEMO["model_used"], DEMO["model_version"], "created",
        ),
    ).lastrowid
    print(f"[부적] script_id={script_id}")

    # 3. TTS
    print("[부적] TTS 합성 중...")
    video_id = run_tts(ctx, script_id=script_id)
    video_rec = repos.videos.get(video_id)
    audio_duration = float(video_rec.get("duration_sec") or 20.0)
    print(f"[부적] TTS 완료 video_id={video_id} ({audio_duration:.1f}s)")

    # 4. 자막 (부적 스타일 적용)
    print("[부적] 자막 생성 중 (금색+진홍 부적 스타일)...")
    sub_cfg = settings.section("subtitle")
    out_dir = PROJECT_ROOT / sub_cfg.get("output_dir", "output/subtitle")
    out_ass = out_dir / f"video_{video_id}.ass"

    result = make_styled_subtitles(
        script=DEMO,
        audio_duration=audio_duration,
        out_ass=out_ass,
        style_overrides=STYLE_LUCKY,
    )
    repos.db.execute(
        "UPDATE videos SET subtitle_path = ? WHERE id = ?",
        (str(out_ass), video_id),
    )
    print(f"[부적] 자막 완료 segments={len(result.segments)}")

    # 5. 렌더
    print("[부적] 렌더링 중...")
    final_path = run_render(ctx, video_id=video_id)

    print(f"\n[부적] 완료: {final_path}")
    db.close()


if __name__ == "__main__":
    main()
