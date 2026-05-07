"""스타일 비교 데모 영상 제작 (B1 vs A2).

B1: 크리에이터 팝 타이틀(딥 오렌지) + NanumGothic Bold 본문 (웜 골드 강조)
A2: 뉴스룸 클린 타이틀(블랙 아웃라인) + Pretendard Medium 본문 (코랄 강조)

TTS 1회 → 자막·렌더 2회 (각 스타일)
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
    "model_version": "compare-v1",
}

MOTIF = (
    "시험 이틀 전에도 기출 중심 반복 학습으로 효율을 높이는 공부법. "
    "교과서 전체를 보려 하지 말고 자주 나오는 유형에 집중해야 한다는 전략."
)

# ────────────────────────────────────────────────────────────────────
# ASS 색상: &HAABBGGRR& 형식 (AA=알파, BB=파랑, GG=초록, RR=빨강)
#   딥 오렌지 #FF8C00 → BB=00 GG=8C RR=FF → &H00008CFF&
#   웜 골드   #FFD23C → BB=3C GG=D2 RR=FF → &H003CD2FF&
#   코랄      #FF6450 → BB=50 GG=64 RR=FF → &H005064FF&
#   노랑      #FFFF00 → BB=00 GG=FF RR=FF → &H0000FFFF&
# ────────────────────────────────────────────────────────────────────

# B안 + ①: 크리에이터 팝 타이틀 + NanumGothic Bold 본문
STYLE_B1: dict = {
    "title_anim": (
        r"{\an2\pos(540,460)"
        r"\fscx0\fscy0\t(0,200,\fscx103\fscy103)\t(200,280,\fscx100\fscy100)\fad(0,250)"
        r"\fnPretendard Black\fs80\fsp0"
        r"\c&H00FFFFFF&\3c&H00008CFF&\bord4\shad2\blur0}"
    ),
    "tag_hook": (
        r"{\an5\pos(540,1060)\fnPretendard Black\fs100\c&H00FFFFFF&\3c&H00008CFF&\bord5\shad2"
        r"\fscx0\fscy0\t(0,200,\fscx104\fscy104)\t(200,280,\fscx100\fscy100)\fad(0,200)}"
    ),
    "tag_body": (
        r"{\an5\move(540,1110,540,1060,0,280)"
        r"\fnNanumGothic\b1\fs76\c&H00FFFFFF&\3c&H00101010&\bord4\shad2\fad(200,200)}"
    ),
    "tag_twist": (
        r"{\an5\pos(540,1060)\fnPretendard Black\fs96\c&H0000FFFF&\3c&H00400000&\bord5\shad2"
        r"\fscx0\fscy0\t(0,220,\fscx107\fscy107)\t(220,320,\fscx100\fscy100)\fad(0,280)}"
    ),
    "emph_hook":  (r"{\c&H003CD2FF&\fs110\blur0}", r"{\c&H00FFFFFF&\fs100\blur0}"),
    "emph_body":  (r"{\c&H003CD2FF&\fs86\blur0}",  r"{\c&H00FFFFFF&\fs76\blur0}"),
    "emph_twist": (r"{\c&H00FFFFFF&\fs106\blur1}",  r"{\c&H0000FFFF&\fs96\blur0}"),
}

# A안 + ②: 뉴스룸 클린 타이틀 + Pretendard Medium 본문
STYLE_A2: dict = {
    "title_anim": (
        r"{\an2\pos(540,460)"
        r"\fad(200,200)"
        r"\fnPretendard Black\fs78\fsp-1"
        r"\c&H00FFFFFF&\3c&H00000000&\bord3\shad3\blur0}"
    ),
    "tag_hook": (
        r"{\an5\pos(540,1060)\fnPretendard Black\fs100\c&H00FFFFFF&\3c&H00000000&\bord4\shad3"
        r"\fad(200,200)}"
    ),
    "tag_body": (
        r"{\an5\move(540,1110,540,1060,0,280)"
        r"\fnPretendard Medium\fs76\c&H00FFFFFF&\3c&H00101010&\bord3\shad2\fad(200,200)}"
    ),
    "tag_twist": (
        r"{\an5\pos(540,1060)\fnPretendard Black\fs94\c&H0000FFFF&\3c&H00101010&\bord4\shad3"
        r"\fscx0\fscy0\t(0,200,\fscx104\fscy104)\t(200,280,\fscx100\fscy100)\fad(0,250)}"
    ),
    "emph_hook":  (r"{\c&H005064FF&\fs110\blur0}", r"{\c&H00FFFFFF&\fs100\blur0}"),
    "emph_body":  (r"{\c&H005064FF&\fs86\blur0}",  r"{\c&H00FFFFFF&\fs76\blur0}"),
    "emph_twist": (r"{\c&H00FFFFFF&\fs104\blur1}",  r"{\c&H0000FFFF&\fs94\blur0}"),
}

STYLES = [
    ("B1-크리에이터팝+NanumGothic", STYLE_B1),
    ("A2-뉴스룸클린+PretendardMedium", STYLE_A2),
]


def main() -> None:
    settings = get_settings()
    setup_logging(
        log_dir=settings.section("observability").get("log_dir", "logs"),
        level=settings.secrets.log_level,
        project_root=PROJECT_ROOT,
    )
    log = get_logger("compare")
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
    print(f"[COMPARE] script_id={script_id}")

    # 3. TTS 1회
    print("[COMPARE] TTS 합성 중...")
    video_id_primary = run_tts(ctx, script_id=script_id)
    audio_rec = repos.videos.get(video_id_primary)
    audio_path = audio_rec["audio_path"]
    audio_duration = float(audio_rec.get("duration_sec") or 20.0)
    print(f"[COMPARE] TTS 완료 video_id={video_id_primary} duration={audio_duration:.1f}s")

    sub_cfg = settings.section("subtitle")
    sub_dir = PROJECT_ROOT / sub_cfg.get("output_dir", "output/subtitle")

    video_ids = [video_id_primary]

    # 4. A2용 video 행 복제 (동일 오디오 재사용)
    video_id_a2 = repos.db.execute(
        "INSERT INTO videos (script_id, speaker_id, audio_path, audio_lufs, duration_sec) VALUES (?,?,?,?,?)",
        (script_id, audio_rec["speaker_id"], audio_path, audio_rec.get("audio_lufs"), audio_duration),
    ).lastrowid
    video_ids.append(video_id_a2)

    # 5. 각 스타일로 자막 + 렌더
    results: list[tuple[str, Path]] = []
    for (style_name, style_override), video_id in zip(STYLES, video_ids):
        print(f"\n[COMPARE] [{style_name}] 자막 생성 중...")
        out_ass = sub_dir / f"video_{video_id}.ass"
        make_styled_subtitles(
            script=DEMO,
            audio_duration=audio_duration,
            out_ass=out_ass,
            style_overrides=style_override,
        )
        repos.db.execute(
            "UPDATE videos SET subtitle_path = ? WHERE id = ?",
            (str(out_ass), video_id),
        )

        print(f"[COMPARE] [{style_name}] 렌더링 중...")
        final = run_render(ctx, video_id=video_id)
        results.append((style_name, final))
        print(f"[COMPARE] [{style_name}] → {final}")

    print("\n[COMPARE] ======= 완료 =======")
    for name, path in results:
        print(f"  {name}: {path}")

    db.close()


if __name__ == "__main__":
    main()
