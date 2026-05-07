"""데모 영상 제작 스크립트 (감성 명언 포맷).

직접 작성한 감성 명언 스크립트로 TTS → 자막 → 렌더 실행.
업로드는 하지 않음.
"""

from __future__ import annotations

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
# 데모 공부법 스크립트
# hook 15자 + body 72자 + twist 17자 = 104자 / 약 18초
# emphasis_words: 자막에서 강조 (노란색 + 크기 + 글로우)
# ────────────────────────────────────────────────────────────────────
DEMO = {
    "hook": "시험 이틀 전인데 아직 아무것도 못 했다면?",
    "body": (
        "지금 당장 기출문제 하나만 잡아라. "
        "교과서 전체 말고 자주 나오는 유형 세 개만 반복하면 효율이 세 배다."
    ),
    "twist": "이틀이면 충분하다. 시작이 전부다.",
    "title": "📝 시험 이틀 전에 '기출 반복'으로 점수 올리는 법",
    "hashtags": ["#공부법", "#시험대비", "#중간고사", "#공부팁", "#Shorts"],
    "emphasis_words": ["기출문제", "반복"],
    "hook_pattern": "question",
    "model_used": "manual",
    "model_version": "demo-v3",
}

MOTIF = (
    "시험 이틀 전에도 기출 중심 반복 학습으로 효율을 높이는 공부법. "
    "교과서 전체를 보려 하지 말고 자주 나오는 유형에 집중해야 한다는 전략."
)


def main() -> None:
    settings = get_settings()
    setup_logging(
        log_dir=settings.section("observability").get("log_dir", "logs"),
        level=settings.secrets.log_level,
        project_root=PROJECT_ROOT,
    )
    log = get_logger("demo")
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

    full_text = DEMO["hook"] + " " + DEMO["body"] + " " + DEMO["twist"]
    char_count = len(full_text.replace(" ", ""))
    log.info("demo_script", chars_no_space=char_count, full_text=full_text)
    print(f"[DEMO] 스크립트 {char_count}자 | {full_text[:40]}...")

    # 1. Source 삽입
    motif_hash = text_sha256(MOTIF)
    existing_src = repos.sources.find_by_hash(motif_hash)
    if existing_src:
        source_id = existing_src["id"]
        log.info("demo_source_reuse", source_id=source_id)
    else:
        source_id = repos.sources.insert(
            source_kind="llm_creator",
            raw_text_hash=motif_hash,
            motif=MOTIF,
            raw_text=None,
            source_site=None,
            url=None,
            title=DEMO["title"],
        )
        log.info("demo_source_inserted", source_id=source_id)

    # 2. Script 삽입
    import json
    script_id = repos.db.execute(
        """INSERT INTO scripts
           (source_id, hook, body, twist, full_text, title,
            hashtags_json, hook_pattern,
            similarity_motif, similarity_30d, similarity_cum,
            model_used, model_version, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            source_id,
            DEMO["hook"], DEMO["body"], DEMO["twist"],
            full_text, DEMO["title"],
            json.dumps(DEMO["hashtags"], ensure_ascii=False),
            DEMO["hook_pattern"],
            0.0, 0.0, 0.0,
            DEMO["model_used"], DEMO["model_version"],
            "created",
        ),
    ).lastrowid
    log.info("demo_script_inserted", script_id=script_id)
    print(f"[DEMO] script_id={script_id}")

    # 3. TTS
    print("[DEMO] TTS 합성 중 (Edge TTS)...")
    video_id = run_tts(ctx, script_id=script_id)
    log.info("tts_done", video_id=video_id)
    print(f"[DEMO] TTS 완료 video_id={video_id}")

    # 4. 자막 — DEMO dict 직접 전달 (emphasis_words 포함)
    print("[DEMO] 자막 생성 중...")
    sub_cfg = settings.section("subtitle")
    out_dir = PROJECT_ROOT / sub_cfg.get("output_dir", "output/subtitle")
    out_ass = out_dir / f"video_{video_id}.ass"

    video_record = repos.videos.get(video_id)
    audio_duration = float(video_record.get("duration_sec") or 20.0)

    result = make_styled_subtitles(
        script=DEMO,
        audio_duration=audio_duration,
        out_ass=out_ass,
    )
    repos.db.execute(
        "UPDATE videos SET subtitle_path = ? WHERE id = ?",
        (str(out_ass), video_id),
    )
    log.info("subtitle_done", video_id=video_id, segments=len(result.segments))
    print(f"[DEMO] 자막 완료 segments={len(result.segments)}")

    # 5. 렌더
    print("[DEMO] 렌더링 중...")
    final_path = run_render(ctx, video_id=video_id)
    log.info("render_done", video_id=video_id, path=str(final_path))

    print(f"\n[DEMO] 완료: {final_path}")
    db.close()


if __name__ == "__main__":
    main()
