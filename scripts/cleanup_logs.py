"""30일 경과 로그 파일 자동 삭제.

실행:
    python -m scripts.cleanup_logs [--dry-run] [--days N]
"""
from __future__ import annotations
import argparse, sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    log_dir = PROJECT_ROOT / "logs"
    cutoff = datetime.now() - timedelta(days=args.days)
    removed = 0

    for f in sorted(log_dir.glob("*.log")):
        if f.name in ("batch_stderr.log", "scheduler.log", ".gitkeep"):
            continue  # 항상 보존
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                if args.dry_run:
                    print(f"[dry-run] 삭제 예정: {f.name} ({mtime.strftime('%Y-%m-%d')})")
                else:
                    f.unlink()
                    print(f"삭제: {f.name}")
                removed += 1
        except Exception as e:
            print(f"오류: {f.name}: {e}")

    # batch_stderr.log 크기 초과(5MB) 시 초기화
    stderr_log = log_dir / "batch_stderr.log"
    if stderr_log.exists() and stderr_log.stat().st_size > 5 * 1024 * 1024:
        if args.dry_run:
            print(f"[dry-run] batch_stderr.log 초기화 예정 ({stderr_log.stat().st_size//1024}KB)")
        else:
            stderr_log.write_text("", encoding="utf-8")
            print("batch_stderr.log 초기화 완료 (5MB 초과)")

    action = "삭제 예정" if args.dry_run else "삭제"
    print(f"완료: {removed}개 파일 {action} (기준: {args.days}일)")

if __name__ == "__main__":
    main()
