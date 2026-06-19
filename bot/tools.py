"""shorts_auto 파이프라인 제어 도구 모음.

Claude가 tool_use로 호출하는 5개 도구:
  get_status      — DB/쿼터/소재 현황
  read_logs       — JSON 로그 조회 및 필터
  run_batch       — 배치 파이프라인 즉시 실행
  set_killswitch  — 배치 중단/재개 스위치
  read_file       — 설정·로그 파일 열람 (화이트리스트)
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "shorts.db"
LOG_DIR = PROJECT_ROOT / "logs"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "bin" / "python"

KST = timezone(timedelta(hours=9))

# read_file 허용 경로 (PROJECT_ROOT 기준 prefix)
_READABLE = [
    "config.yaml",
    "prompts/",
    "logs/",
    "data/concept_log.jsonl",
    "data/pending_notifications.jsonl",
]


# ──────────────────────────────────────────────
# 1. get_status
# ──────────────────────────────────────────────

def get_status() -> dict:
    """오늘 업로드 현황, YouTube 쿼터, 미사용 소재 수, 최근 에러 여부를 반환."""
    if not DB_PATH.exists():
        return {"error": "DB 파일 없음"}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        today = date.today().isoformat()

        # 오늘 업로드
        row = conn.execute(
            "SELECT COUNT(*) AS cnt, SUM(quota_units_used) AS quota "
            "FROM uploads WHERE date(uploaded_at) = ?", (today,)
        ).fetchone()
        uploads_today = int(row["cnt"] or 0)
        quota_used = int(row["quota"] or 0)

        # 미사용 소재
        unused = conn.execute(
            "SELECT COUNT(*) AS cnt FROM sources WHERE status = 'unused'"
        ).fetchone()["cnt"]

        # 최근 업로드 3건
        recent = conn.execute(
            "SELECT title, status, uploaded_at FROM uploads "
            "ORDER BY id DESC LIMIT 3"
        ).fetchall()
        recent_list = [dict(r) for r in recent]

        # 킬스위치 상태
        killswitch = (PROJECT_ROOT / "data" / "killswitch.flag").exists()

        # 배치 락 상태
        lock = (PROJECT_ROOT / "data" / "pipeline.lock").exists()

    finally:
        conn.close()

    # 오늘 로그에서 마지막 에러
    last_error = _last_log_error()

    return {
        "date": today,
        "uploads_today": uploads_today,
        "quota_used": quota_used,
        "quota_limit": 10000,
        "quota_remaining": 10000 - quota_used,
        "max_uploads_remaining": (10000 - quota_used) // 1600,
        "unused_sources": unused,
        "killswitch_active": killswitch,
        "batch_lock_exists": lock,
        "last_error": last_error,
        "recent_uploads": recent_list,
    }


def _last_log_error() -> str | None:
    log_file = LOG_DIR / f"{date.today().isoformat()}.log"
    if not log_file.exists():
        return None
    last_err = None
    with log_file.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("level") == "error":
                    last_err = f"[{entry.get('stage','')}] {entry.get('error', entry.get('event',''))}"
            except json.JSONDecodeError:
                pass
    return last_err


# ──────────────────────────────────────────────
# 2. read_logs
# ──────────────────────────────────────────────

def read_logs(n: int = 50, level: str | None = None, stage: str | None = None) -> list[dict]:
    """오늘 JSON 로그에서 최근 n개 항목을 반환. level/stage 필터 가능."""
    log_file = LOG_DIR / f"{date.today().isoformat()}.log"
    if not log_file.exists():
        return [{"info": "오늘 로그 파일 없음"}]

    entries: list[dict] = []
    with log_file.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if level and entry.get("level", "").lower() != level.lower():
                continue
            if stage and entry.get("stage") != stage:
                continue
            # 긴 traceback 축약
            if "exception" in entry:
                entry["exception"] = entry["exception"][:300] + "..."
            entries.append(entry)

    return entries[-n:]


# ──────────────────────────────────────────────
# 3. run_batch
# ──────────────────────────────────────────────

def run_batch(count: int = 1) -> dict:
    """배치 파이프라인을 즉시 실행하고 결과를 반환.

    최대 10분 타임아웃. killswitch가 활성 상태면 실행 거부.
    """
    if count < 1 or count > 3:
        return {"error": f"count는 1~3 범위여야 합니다: {count}"}

    if (PROJECT_ROOT / "data" / "killswitch.flag").exists():
        return {"error": "킬스위치가 활성 상태입니다. 먼저 킬스위치를 해제하세요."}

    lock = PROJECT_ROOT / "data" / "pipeline.lock"
    if lock.exists():
        try:
            import os
            pid = int(lock.read_text().strip())
            os.kill(pid, 0)
            return {"error": f"이미 배치가 실행 중입니다 (PID {pid})"}
        except (OSError, ValueError):
            pass

    try:
        result = subprocess.run(
            [str(PYTHON_EXE), "-m", "scripts.run_batch", "--count", str(count)],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
            env=_build_env(),
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[-3000:] if result.stdout else "",
            "stderr": result.stderr[-1000:] if result.stderr else "",
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"error": "10분 타임아웃 초과"}
    except Exception as e:
        return {"error": str(e)}


def _build_env() -> dict:
    import os
    env = os.environ.copy()
    env.update({
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "HF_HOME": str(Path.home() / ".cache" / "huggingface"),
        "TRANSFORMERS_CACHE": str(Path.home() / ".cache" / "huggingface" / "hub"),
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "PATH": f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '')}",
    })
    return env


# ──────────────────────────────────────────────
# 4. set_killswitch
# ──────────────────────────────────────────────

def set_killswitch(enable: bool) -> dict:
    """킬스위치 파일 생성(True) 또는 삭제(False)."""
    flag = PROJECT_ROOT / "data" / "killswitch.flag"
    flag.parent.mkdir(parents=True, exist_ok=True)
    if enable:
        flag.touch()
        return {"killswitch": True, "message": "킬스위치 활성화 — 다음 배치부터 실행되지 않습니다."}
    else:
        flag.unlink(missing_ok=True)
        return {"killswitch": False, "message": "킬스위치 해제 — 배치가 정상 실행됩니다."}


# ──────────────────────────────────────────────
# 5. read_file
# ──────────────────────────────────────────────

def read_file(path: str) -> str:
    """프로젝트 내 허용된 경로의 파일 내용을 반환 (최대 8KB)."""
    # 경로 탈출 방지
    target = (PROJECT_ROOT / path).resolve()
    if not str(target).startswith(str(PROJECT_ROOT)):
        raise PermissionError("프로젝트 디렉토리 외부 접근 불가")

    rel = str(target.relative_to(PROJECT_ROOT))
    if not any(rel == p.rstrip("/") or rel.startswith(p) for p in _READABLE):
        raise PermissionError(
            f"허용되지 않은 경로: {rel}\n"
            f"허용 목록: {', '.join(_READABLE)}"
        )

    if not target.exists():
        raise FileNotFoundError(f"파일 없음: {rel}")

    content = target.read_text(encoding="utf-8", errors="replace")
    if len(content) > 8000:
        content = content[:8000] + f"\n\n...(이하 {len(content)-8000}자 생략)"
    return content
