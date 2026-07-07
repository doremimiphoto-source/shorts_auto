"""YouTube 영상 조회수 수집 + 업로드 시간대별 성과 분석 (읽기 전용).

기존 파이프라인에 영향 없음 — uploads 테이블을 읽고 video_stats 테이블에만 기록.
크로스 플랫폼 (pathlib, 기존 google-api-python-client 재사용).

실행:
  python -m scripts.fetch_video_stats            # 수집 + 분석 리포트
  python -m scripts.fetch_video_stats --report   # 수집 없이 리포트만
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings  # noqa: E402

DB_PATH = PROJECT_ROOT / "data" / "shorts.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS video_stats (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    youtube_video_id TEXT NOT NULL,
    uploaded_at      TEXT,
    view_count       INTEGER,
    like_count       INTEGER,
    comment_count    INTEGER,
    fetched_at       TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_video_stats_vid ON video_stats(youtube_video_id);
"""


def _build_youtube():
    """기존 token.json 재사용해 YouTube 서비스 생성 (youtube.py와 동일 방식)."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    s = get_settings().secrets
    token_path = PROJECT_ROOT / s.youtube_token_path
    scopes = ["https://www.googleapis.com/auth/youtube",
              "https://www.googleapis.com/auth/youtube.upload"]
    if not token_path.exists():
        raise SystemExit(f"토큰 없음: {token_path} — 먼저 YouTube 인증 필요")
    creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def fetch(db: sqlite3.Connection) -> int:
    db.executescript(_SCHEMA)
    rows = db.execute(
        "SELECT youtube_video_id, uploaded_at FROM uploads "
        "WHERE youtube_video_id IS NOT NULL AND youtube_video_id != ''"
    ).fetchall()
    id_to_uploaded = {r[0]: r[1] for r in rows}
    vids = list(id_to_uploaded.keys())
    if not vids:
        print("업로드된 영상이 없습니다.")
        return 0

    yt = _build_youtube()
    n = 0
    for batch in _chunks(vids, 50):
        resp = yt.videos().list(part="statistics", id=",".join(batch)).execute()
        for item in resp.get("items", []):
            st = item.get("statistics", {})
            db.execute(
                "INSERT INTO video_stats (youtube_video_id, uploaded_at, view_count, like_count, comment_count) "
                "VALUES (?, ?, ?, ?, ?)",
                (item["id"], id_to_uploaded.get(item["id"]),
                 int(st.get("viewCount", 0)), int(st.get("likeCount", 0)),
                 int(st.get("commentCount", 0))),
            )
            n += 1
    db.commit()
    print(f"✅ {n}건 조회수 수집 완료")
    return n


def _parse_hour(ts: str | None) -> int | None:
    if not ts:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts[:19], fmt).hour
        except ValueError:
            continue
    return None


def report(db: sqlite3.Connection) -> None:
    # 각 영상의 최신 스냅샷만
    rows = db.execute("""
        SELECT s.youtube_video_id, s.uploaded_at, s.view_count, s.like_count
        FROM video_stats s
        JOIN (SELECT youtube_video_id, MAX(fetched_at) mf FROM video_stats GROUP BY youtube_video_id) m
          ON s.youtube_video_id = m.youtube_video_id AND s.fetched_at = m.mf
    """).fetchall()
    if not rows:
        print("수집된 통계가 없습니다. 먼저 수집을 실행하세요.")
        return

    views = [r[2] for r in rows]
    views_sorted = sorted(views)
    total = len(views)
    print("\n" + "=" * 56)
    print(" 조회수 요약")
    print("=" * 56)
    print(f"  영상 수     : {total}")
    print(f"  평균 조회수 : {sum(views)//total:,}")
    print(f"  중앙값      : {views_sorted[total//2]:,}")
    print(f"  최소 / 최대 : {min(views):,} / {max(views):,}")
    print(f"  1만 이상    : {sum(1 for v in views if v>=10000)}편")
    print(f"  100 미만    : {sum(1 for v in views if v<100)}편")

    # 영상 나이 보정: 하루당 조회수(views/day) = 공정한 시간대 비교 지표
    def _age_days(up: str | None) -> float:
        if not up:
            return 0.0
        try:
            d = datetime.strptime(str(up)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
            days = (datetime.now() - d).total_seconds() / 86400
            return max(days, 0.5)   # 최소 0.5일 (신규 영상 과대평가 방지)
        except ValueError:
            return 0.0

    # 업로드 시간대(시)별 성과 — 나이 보정
    by_hour: dict[int, list[float]] = defaultdict(list)
    for _, up, v, _l in rows:
        h = _parse_hour(up)
        age = _age_days(up)
        if h is not None and age > 0:
            by_hour[h].append(v / age)   # views per day
    print("\n" + "=" * 60)
    print(" 업로드 시간대별 '하루당 조회수' (나이 보정 — 공정 비교)")
    print("=" * 60)
    print(f"  {'시':>4} {'영상수':>6} {'평균 views/day':>14}")
    ranked_hours = []
    for h in sorted(by_hour):
        vpd = by_hour[h]
        avg = sum(vpd) / len(vpd)
        ranked_hours.append((h, len(vpd), avg))
    for h, n, avg in ranked_hours:
        bar = "█" * min(40, int(avg))
        print(f"  {h:>2}시 {n:>6} {avg:>14.1f}  {bar}")
    print("\n  📈 시간대 순위 (views/day, 3편 이상만):")
    strong = sorted([x for x in ranked_hours if x[1] >= 3], key=lambda x: x[2], reverse=True)
    for h, n, avg in strong[:5]:
        print(f"    {h:>2}시  {avg:>6.1f} views/day  ({n}편)")
    print("  🔻 약한 시간대:")
    for h, n, avg in strong[-3:]:
        print(f"    {h:>2}시  {avg:>6.1f} views/day  ({n}편)")

    # 상·하위 영상
    ranked = sorted(rows, key=lambda r: r[2], reverse=True)
    print("\n  🔝 조회수 상위 5:")
    for r in ranked[:5]:
        print(f"    {r[2]:>7,} views  (업로드 {str(r[1])[:16]})  {r[0]}")
    print("  🔻 조회수 하위 5:")
    for r in ranked[-5:]:
        print(f"    {r[2]:>7,} views  (업로드 {str(r[1])[:16]})  {r[0]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="수집 없이 리포트만")
    args = ap.parse_args()
    db = sqlite3.connect(DB_PATH)
    try:
        if not args.report:
            fetch(db)
        report(db)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
