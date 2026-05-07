"""파이프라인 실행 컨텍스트."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import structlog

from ..config import Settings
from ..repository import Repositories


class StageError(RuntimeError):
    """단계 실행 중 회복 불가능한 오류."""


class StageSkipped(RuntimeError):
    """사전조건 미충족으로 단계 건너뜀 (dry-run 또는 의존성 미설정)."""


@dataclass
class PipelineContext:
    settings: Settings
    repos: Repositories
    run_id: str
    log: structlog.stdlib.BoundLogger
    project_root: Path

    def section(self, key: str) -> dict[str, Any]:
        return self.settings.section(key)


@contextmanager
def stage_timer(ctx: PipelineContext, stage: str) -> Iterator[dict[str, Any]]:
    """단계 실행 시간 측정 + job_logs 자동 기록."""
    started = time.monotonic()
    state: dict[str, Any] = {"stage": stage, "status": "running"}
    ctx.log.info("stage_start", stage=stage, run_id=ctx.run_id)
    try:
        yield state
        if state.get("status") in (None, "running"):
            state["status"] = "ok"
    except StageSkipped as e:
        state["status"] = "skip"
        state["message"] = str(e)
        ctx.log.warning("stage_skipped", stage=stage, message=str(e))
        raise
    except Exception as e:
        state["status"] = "fail"
        state["message"] = repr(e)
        ctx.log.error("stage_failed", stage=stage, error=repr(e), exc_info=True)
        raise
    finally:
        duration_ms = int((time.monotonic() - started) * 1000)
        ctx.repos.job_logs.insert(
            run_id=ctx.run_id,
            stage=stage,
            status=state.get("status", "fail"),
            message=str(state.get("message", "")),
            duration_ms=duration_ms,
        )
        ctx.log.info(
            "stage_end",
            stage=stage,
            status=state.get("status"),
            duration_ms=duration_ms,
            run_id=ctx.run_id,
        )
