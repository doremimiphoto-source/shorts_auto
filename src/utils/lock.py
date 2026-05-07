"""파이프라인 중복 실행 방지 Lock 파일 (FR-7.4).

PID와 시작 시각을 기록한다. 만료 시간(TTL)이 지난 stale lock은 자동 회수한다.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class LockBusy(RuntimeError):
    """다른 프로세스가 락을 점유 중일 때 발생."""


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        # Windows: signal 0 미지원 → 다른 방식 필요
        if os.name == "nt":
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    return True


def acquire(lock_path: str | Path, *, ttl_seconds: int = 3600) -> dict:
    """Lock 파일을 생성한다. 이미 존재하면 LockBusy를 발생.

    `ttl_seconds`가 지났거나 기록된 PID가 죽었으면 stale로 간주하고 회수한다.
    """
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        pid = int(data.get("pid", 0))
        started = float(data.get("started_at", 0))
        age = time.time() - started
        alive = _is_pid_alive(pid)

        if alive and age < ttl_seconds:
            raise LockBusy(f"Lock held by pid={pid} for {int(age)}s ({path})")
        # stale → 회수
        try:
            path.unlink()
        except OSError as e:
            raise LockBusy(f"Stale lock 제거 실패: {e}") from e

    payload = {
        "pid": os.getpid(),
        "started_at": time.time(),
        "host": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "unknown",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def release(lock_path: str | Path) -> None:
    path = Path(lock_path)
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


@contextmanager
def pipeline_lock(lock_path: str | Path, *, ttl_seconds: int = 3600) -> Iterator[dict]:
    """`with pipeline_lock(...) as info:` 컨텍스트로 사용."""
    info = acquire(lock_path, ttl_seconds=ttl_seconds)
    try:
        yield info
    finally:
        release(lock_path)


def killswitch_active(flag_path: str | Path) -> bool:
    """Kill-Switch flag 파일 존재 여부 (§12.2).

    main.py 부팅 시 검사하여 즉시 종료하는 데 사용한다.
    """
    return Path(flag_path).exists()
