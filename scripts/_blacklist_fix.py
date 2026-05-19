"""손상 BG 파일 블랙리스트 등록."""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from src.db import open_database

db = open_database("data/shorts.db")

# 이전 잘못된 항목 정리
db.execute("DELETE FROM asset_usage WHERE blacklist_reason IN ('ffmpeg_timeout_13h','ffmpeg_timeout_ai_cache')")

bad_files = [
    (
        "bg_video",
        "D:\\Application\\Claude\\shorts_auto\\assets\\bg_video\\study\\pexels_7596771_planner_schedule_calendar_writing.mp4",
        "ffmpeg_timeout_13h",
    ),
    (
        "bg_video",
        "D:\\Application\\Claude\\shorts_auto\\output\\aibg_cache\\aibg_ffa758e38bda3a_full.mp4",
        "ffmpeg_timeout_ai_cache",
    ),
]

for kind, path, reason in bad_files:
    db.execute(
        "INSERT INTO asset_usage (asset_kind, asset_path, blacklisted, blacklist_reason) VALUES (?,?,1,?)",
        (kind, path, reason),
    )
    print("blacklisted:", path.split("\\")[-1])

rows = db.fetchall("SELECT asset_path, blacklist_reason FROM asset_usage WHERE blacklisted=1")
print(f"\n블랙리스트 총 {len(rows)}건:")
for r in rows:
    print(f"  {r['asset_path'].split(chr(92))[-1]}  ({r['blacklist_reason']})")
