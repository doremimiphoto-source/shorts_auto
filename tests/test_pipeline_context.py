"""src.pipeline.context 테스트 (stage_timer + job_logs 기록 검증)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Secrets, Settings
from src.db import open_database
from src.pipeline.context import PipelineContext, StageError, StageSkipped, stage_timer
from src.repository import Repositories
from src.utils.logging import get_logger, setup_logging


@pytest.fixture()
def ctx(tmp_path: Path) -> PipelineContext:
    setup_logging(log_dir=tmp_path / "logs", level="DEBUG", project_root=tmp_path)
    db = open_database(tmp_path / "t.db", init=True)
    repos = Repositories(db)
    return PipelineContext(
        settings=Settings(secrets=Secrets(), raw={"crawler": {"raw_text_retention_hours": 24}}),
        repos=repos,
        run_id="testrun",
        log=get_logger("test"),
        project_root=tmp_path,
    )


def test_stage_timer_records_ok(ctx: PipelineContext) -> None:
    with stage_timer(ctx, "crawl"):
        pass
    rows = ctx.repos.job_logs.stage_history("testrun")
    assert len(rows) == 1
    assert rows[0]["stage"] == "crawl"
    assert rows[0]["status"] == "ok"
    assert rows[0]["duration_ms"] is not None


def test_stage_timer_records_skip(ctx: PipelineContext) -> None:
    with pytest.raises(StageSkipped):
        with stage_timer(ctx, "rewrite"):
            raise StageSkipped("no input")
    rows = ctx.repos.job_logs.stage_history("testrun")
    assert rows[0]["status"] == "skip"
    assert "no input" in (rows[0]["message"] or "")


def test_stage_timer_records_fail(ctx: PipelineContext) -> None:
    with pytest.raises(StageError):
        with stage_timer(ctx, "tts"):
            raise StageError("boom")
    rows = ctx.repos.job_logs.stage_history("testrun")
    assert rows[0]["status"] == "fail"
    assert "StageError" in (rows[0]["message"] or "") or "boom" in (rows[0]["message"] or "")
