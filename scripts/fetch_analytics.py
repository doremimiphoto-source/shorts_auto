"""YouTube Analytics — 리텐션·완주율·트래픽 소스 수집·분석 (읽기 전용).

조회수(viewCount)만으론 '왜 안 터지나'를 모른다. Analytics API로
평균 시청률(완주율)·평균 시청시간·트래픽 소스를 가져와 1만 뷰 레버를 찾는다.

⚠️ yt-analytics.readonly 스코프 필요. 토큰에 없으면 재인증 안내 출력.
   재인증: python -m scripts.auth_youtube  (스코프에 analytics 추가됨)

실행:
  python -m scripts.fetch_analytics                # 최근 90일 분석
  python -m scripts.fetch_analytics --days 30
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_settings  # noqa: E402

DB_PATH = PROJECT_ROOT / "data" / "shorts.db"
_ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"


def _services():
    """Analytics + Data API 서비스. analytics 스코프 없으면 SystemExit 안내."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    s = get_settings().secrets
    token_path = PROJECT_ROOT / s.youtube_token_path
    if not token_path.exists():
        raise SystemExit(f"토큰 없음: {token_path}")
    import json
    scopes = json.loads(token_path.read_text()).get("scopes", [])
    if _ANALYTICS_SCOPE not in scopes:
        raise SystemExit(
            "❌ 토큰에 analytics 스코프가 없습니다.\n"
            "   재인증 필요: python -m scripts.auth_youtube\n"
            "   (스코프에 yt-analytics.readonly 가 추가돼 있습니다. 브라우저에서 재동의)")
    creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return (build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False),
            build("youtube", "v3", credentials=creds, cache_discovery=False))


def report(days: int) -> None:
    yta, _ = _services()
    end = date.today()
    start = end - timedelta(days=days)
    common = dict(ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat())

    # ── 1) 채널 전체 요약 ──
    ch = yta.reports().query(
        metrics="views,averageViewPercentage,averageViewDuration,estimatedMinutesWatched,likes,comments,shares",
        **common).execute()
    print("=" * 56)
    print(f" 채널 요약 (최근 {days}일)")
    print("=" * 56)
    hdr = ch.get("columnHeaders", [])
    row = (ch.get("rows") or [[0] * len(hdr)])[0]
    labels = {"views": "조회수", "averageViewPercentage": "평균 완주율(%)",
              "averageViewDuration": "평균 시청(초)", "estimatedMinutesWatched": "총 시청(분)",
              "likes": "좋아요", "comments": "댓글", "shares": "공유"}
    for h, v in zip(hdr, row):
        n = h["name"]
        print(f"  {labels.get(n, n):<16}: {v:,.1f}" if isinstance(v, float) else f"  {labels.get(n, n):<16}: {v:,}")

    # ── 2) 트래픽 소스 ──
    ts = yta.reports().query(
        metrics="views", dimensions="insightTrafficSourceType",
        sort="-views", **common).execute()
    print("\n" + "=" * 56)
    print(" 트래픽 소스 (어디서 유입되나)")
    print("=" * 56)
    src_ko = {"SHORTS": "Shorts 피드", "YT_SEARCH": "검색", "SUGGESTED_VIDEO": "추천영상",
              "BROWSE": "홈/구독피드", "NO_LINK_OTHER": "기타", "PLAYLIST": "재생목록",
              "CHANNEL": "채널페이지", "NOTIFICATION": "알림"}
    total = sum(r[1] for r in (ts.get("rows") or []))
    for r in (ts.get("rows") or []):
        name, v = r[0], r[1]
        pct = 100 * v / total if total else 0
        print(f"  {src_ko.get(name, name):<12} {v:>7,} ({pct:>4.1f}%)  {'█'*int(pct/2)}")

    # ── 3) 완주율 상·하위 영상 (리텐션 레버) ──
    vids = yta.reports().query(
        metrics="views,averageViewPercentage,averageViewDuration",
        dimensions="video", sort="-views", maxResults=200, **common).execute()
    rows = vids.get("rows") or []
    if rows:
        # 제목 매핑 (DB)
        db = sqlite3.connect(DB_PATH)
        title_of = {}
        for vid, t in db.execute("SELECT youtube_video_id, title FROM uploads WHERE youtube_video_id IS NOT NULL"):
            title_of[vid] = t
        db.close()
        # 완주율 기준 정렬
        enriched = [(r[0], r[1], r[2], r[3]) for r in rows]  # vid, views, avgpct, avgdur
        by_ret = sorted(enriched, key=lambda x: x[2], reverse=True)
        print("\n" + "=" * 56)
        print(" 완주율(리텐션) 상위 5 — 이런 콘텐츠가 알고리즘에 확산됨")
        print("=" * 56)
        for vid, vw, pct, dur in by_ret[:5]:
            print(f"  완주 {pct:>5.1f}% | {int(vw):>6,}뷰 | {title_of.get(vid,'?')[:34]}")
        print("\n 완주율 하위 5 — 여기서 이탈 → 훅/초반 개선 대상")
        for vid, vw, pct, dur in by_ret[-5:]:
            print(f"  완주 {pct:>5.1f}% | {int(vw):>6,}뷰 | {title_of.get(vid,'?')[:34]}")

        # 완주율↔조회수 상관 (레버 검증)
        import statistics
        highret = [x[1] for x in enriched if x[2] >= statistics.median(y[2] for y in enriched)]
        lowret = [x[1] for x in enriched if x[2] < statistics.median(y[2] for y in enriched)]
        if highret and lowret:
            print("\n" + "=" * 56)
            print(" 완주율 → 조회수 상관 (리텐션이 진짜 레버인가)")
            print("=" * 56)
            print(f"  완주율 상위 절반 평균 조회수: {statistics.mean(highret):,.0f}")
            print(f"  완주율 하위 절반 평균 조회수: {statistics.mean(lowret):,.0f}")


def retention_curves(days: int, n: int) -> None:
    """상위 조회수 영상의 리텐션 곡선 — 정확히 몇 %(초)에서 이탈하는지 (훅 진단)."""
    yta, _ = _services()
    end = date.today()
    start = end - timedelta(days=days)
    common = dict(ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat())

    top = yta.reports().query(
        metrics="views,averageViewDuration", dimensions="video",
        sort="-views", maxResults=n, **common).execute()
    vids = [r[0] for r in (top.get("rows") or [])]
    if not vids:
        print("영상 없음")
        return

    db = sqlite3.connect(DB_PATH)
    title_of = {vid: t for vid, t in
                db.execute("SELECT youtube_video_id, title FROM uploads WHERE youtube_video_id IS NOT NULL")}
    dur_of = {}
    for vid, dsec in db.execute("""SELECT u.youtube_video_id, vi.duration_sec
                                    FROM uploads u JOIN videos vi ON vi.id=u.video_id
                                    WHERE u.youtube_video_id IS NOT NULL"""):
        dur_of[vid] = dsec
    db.close()

    print("\n" + "=" * 60)
    print(f" 리텐션 곡선 — 상위 {len(vids)}편 (첫 3초 이탈 진단)")
    print("=" * 60)
    for vid in vids:
        try:
            r = yta.reports().query(
                metrics="audienceWatchRatio", dimensions="elapsedVideoTimeRatio",
                filters=f"video=={vid}", **common).execute()
        except Exception as e:
            print(f"  [{title_of.get(vid,vid)[:30]}] 리텐션 조회 실패: {repr(e)[:60]}")
            continue
        rows = sorted((float(x[0]), float(x[1])) for x in (r.get("rows") or []))
        if not rows:
            continue
        dur = dur_of.get(vid) or 30
        def at(ratio):
            # 가장 가까운 지점의 watch ratio
            return min(rows, key=lambda x: abs(x[0] - ratio))[1]
        start_wr = at(0.0) or 1.0
        print(f"\n  ▶ {title_of.get(vid, vid)[:40]}  (길이 ~{int(dur)}초)")
        print(f"    구간   시청유지  (시작=100% 기준)")
        for ratio, label in [(0.0, "0초"), (0.1, f"~{dur*0.1:.0f}초"),
                             (0.25, f"~{dur*0.25:.0f}초"), (0.5, "중간"), (1.0, "끝")]:
            wr = at(ratio)
            rel = 100 * wr / start_wr if start_wr else 0
            bar = "█" * int(rel / 3)
            print(f"    {label:<6} {rel:>5.0f}%  {bar}")
        # 첫 10% 이탈률 = 훅 성패
        drop10 = 100 * (1 - at(0.1) / start_wr) if start_wr else 0
        verdict = "✅ 훅 강함" if drop10 < 20 else ("⚠️ 초반 이탈 큼" if drop10 < 40 else "❌ 훅 약함 — 첫 3초 개선 필수")
        print(f"    → 첫 10%({dur*0.1:.0f}초)에서 {drop10:.0f}% 이탈  {verdict}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--retention", type=int, metavar="N",
                    help="상위 N편의 리텐션 곡선(첫3초 진단)만 실행")
    args = ap.parse_args()
    if args.retention:
        retention_curves(args.days, args.retention)
    else:
        report(args.days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
