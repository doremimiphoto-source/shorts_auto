"""src.utils.lock 단위 테스트."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.utils.lock import LockBusy, acquire, killswitch_active, pipeline_lock, release


def test_acquire_creates_lock_file(tmp_path: Path) -> None:
    lock = tmp_path / "test.lock"
    info = acquire(lock)
    assert lock.exists()
    assert info["pid"] > 0
    data = json.loads(lock.read_text(encoding="utf-8"))
    assert data["pid"] == info["pid"]


def test_acquire_raises_when_held_by_alive_process(tmp_path: Path) -> None:
    lock = tmp_path / "test.lock"
    acquire(lock)
    with pytest.raises(LockBusy):
        acquire(lock)


def test_acquire_reclaims_stale_lock_dead_pid(tmp_path: Path) -> None:
    lock = tmp_path / "test.lock"
    # 존재하지 않는 PID + 충분히 오래된 시각
    lock.write_text(json.dumps({"pid": 99999999, "started_at": 0.0}), encoding="utf-8")
    info = acquire(lock)
    assert info["pid"] != 99999999


def test_acquire_reclaims_stale_lock_ttl_expired(tmp_path: Path) -> None:
    lock = tmp_path / "test.lock"
    # 살아있는 PID지만 TTL 초과
    lock.write_text(json.dumps({"pid": 1, "started_at": time.time() - 10000}), encoding="utf-8")
    info = acquire(lock, ttl_seconds=60)
    assert info["pid"] != 1


def test_release_removes_lock_file(tmp_path: Path) -> None:
    lock = tmp_path / "test.lock"
    acquire(lock)
    assert lock.exists()
    release(lock)
    assert not lock.exists()


def test_release_idempotent_on_missing(tmp_path: Path) -> None:
    lock = tmp_path / "missing.lock"
    release(lock)  # should not raise


def test_pipeline_lock_context_manager(tmp_path: Path) -> None:
    lock = tmp_path / "ctx.lock"
    with pipeline_lock(lock) as info:
        assert lock.exists()
        assert info["pid"] > 0
    assert not lock.exists()


def test_pipeline_lock_releases_on_exception(tmp_path: Path) -> None:
    lock = tmp_path / "ctx.lock"
    with pytest.raises(RuntimeError):
        with pipeline_lock(lock):
            assert lock.exists()
            raise RuntimeError("simulated")
    assert not lock.exists()


def test_killswitch_active(tmp_path: Path) -> None:
    flag = tmp_path / "killswitch.flag"
    assert killswitch_active(flag) is False
    flag.touch()
    assert killswitch_active(flag) is True
