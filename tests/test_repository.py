"""src.repository 테스트."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.db import open_database
from src.repository import Repositories


@pytest.fixture()
def repos(tmp_path: Path) -> Repositories:
    db = open_database(tmp_path / "t.db", init=True)
    return Repositories(db)


# ---------- SourceRepository ----------
def test_source_insert_and_pick_unused(repos: Repositories) -> None:
    sid = repos.sources.insert(source_kind="llm_creator", raw_text_hash="h1", motif="x" * 250)
    assert sid > 0
    rows = repos.sources.pick_unused(limit=1)
    assert len(rows) == 1
    assert rows[0]["id"] == sid


def test_source_find_by_hash(repos: Repositories) -> None:
    repos.sources.insert(source_kind="llm_creator", raw_text_hash="abc", motif="m" * 250)
    found = repos.sources.find_by_hash("abc")
    assert found is not None
    assert repos.sources.find_by_hash("missing") is None


def test_source_status_lifecycle(repos: Repositories) -> None:
    sid = repos.sources.insert(source_kind="llm_creator", raw_text_hash="h2", motif="m" * 250)
    repos.sources.mark_status(sid, "used")
    assert repos.sources.pick_unused(limit=10) == []


def test_source_purge_raw_text(repos: Repositories) -> None:
    sid = repos.sources.insert(source_kind="llm_creator", raw_text_hash="h3", motif="m" * 250, raw_text="원문")
    # crawled_at을 25시간 전으로 강제 (테스트용 직접 update)
    repos.db.execute(
        "UPDATE sources SET crawled_at = ? WHERE id = ?",
        ((datetime.now() - timedelta(hours=25)).isoformat(sep=" ", timespec="seconds"), sid),
    )
    purged = repos.sources.purge_raw_text_older_than(hours=24)
    assert purged == 1
    row = repos.db.fetchone("SELECT raw_text, raw_purged_at FROM sources WHERE id = ?", (sid,))
    assert row["raw_text"] is None
    assert row["raw_purged_at"] is not None


# ---------- ScriptRepository ----------
def test_script_insert_with_hashtags_json(repos: Repositories) -> None:
    sid = repos.sources.insert(source_kind="llm_creator", raw_text_hash="h4", motif="m" * 250)
    script_id = repos.scripts.insert(
        source_id=sid,
        hook="후크", body="본문", twist="반전",
        full_text="후크 본문 반전",
        title="제목",
        hashtags=["#사연", "#반전"],
        hook_pattern="question",
        model_used="gemini",
    )
    row = repos.scripts.get(script_id)
    assert row is not None
    assert row["hook_pattern"] == "question"
    import json
    assert json.loads(row["hashtags_json"]) == ["#사연", "#반전"]


def test_script_recent_hook_patterns(repos: Repositories) -> None:
    sid = repos.sources.insert(source_kind="llm_creator", raw_text_hash="h5", motif="m" * 250)
    for pattern in ["a", "b", "c", "d", "e", "f"]:
        repos.scripts.insert(source_id=sid, hook="x", body="y", twist="z", full_text="xyz", hook_pattern=pattern)
    recent = repos.scripts.list_recent_hook_patterns(limit=3)
    # 최신순으로 마지막 3개: f, e, d
    assert recent == ["f", "e", "d"]


# ---------- VideoRepository ----------
def test_video_insert_and_speakers(repos: Repositories) -> None:
    sid = repos.sources.insert(source_kind="llm_creator", raw_text_hash="h6", motif="m" * 250)
    script_id = repos.scripts.insert(source_id=sid, hook="x", body="y", twist="z", full_text="xyz")
    for speaker in ["v1", "v2", "v3", "v4"]:
        repos.videos.insert(script_id=script_id, speaker_id=speaker)
    recent = repos.videos.list_recent_speakers(limit=2)
    assert recent == ["v4", "v3"]


# ---------- UploadRepository ----------
def test_upload_quota_today(repos: Repositories) -> None:
    sid = repos.sources.insert(source_kind="llm_creator", raw_text_hash="h7", motif="m" * 250)
    script_id = repos.scripts.insert(source_id=sid, hook="x", body="y", twist="z", full_text="xyz")
    video_id = repos.videos.insert(script_id=script_id)

    uid = repos.uploads.insert(video_id=video_id, oauth_client_name="default", quota_units_used=1600, status="success")
    assert repos.uploads.quota_used_today("default") >= 1600
    repos.uploads.update_status(uid, status="failed", error_msg="test")
    row = repos.db.fetchone("SELECT status, error_msg FROM uploads WHERE id = ?", (uid,))
    assert row["status"] == "failed"
    assert row["error_msg"] == "test"


# ---------- AssetUsageRepository ----------
def test_asset_usage_record_and_blacklist(repos: Repositories) -> None:
    repos.asset_usage.record(asset_kind="bg_video", asset_path="/x.mp4")
    last = repos.asset_usage.last_used_at("bg_video", "/x.mp4")
    assert last is not None

    assert repos.asset_usage.is_blacklisted("bg_video", "/x.mp4") is False
    repos.asset_usage.blacklist("bg_video", "/x.mp4", "test")
    assert repos.asset_usage.is_blacklisted("bg_video", "/x.mp4") is True


# ---------- ApiUsageRepository ----------
def test_api_usage_count_window_and_today(repos: Repositories) -> None:
    repos.api_usage.record(api_name="gemini", units_used=1)
    repos.api_usage.record(api_name="gemini", units_used=1)
    assert repos.api_usage.count_within_window("gemini", seconds=3600) >= 2
    assert repos.api_usage.units_today("gemini") >= 2


# ---------- JobLogRepository ----------
def test_job_logs_insert_and_history(repos: Repositories) -> None:
    repos.job_logs.insert(run_id="r1", stage="crawl", status="ok", message="hello", duration_ms=12)
    repos.job_logs.insert(run_id="r1", stage="rewrite", status="fail", message="boom", duration_ms=34)
    repos.job_logs.insert(run_id="r2", stage="crawl", status="ok")
    history = repos.job_logs.stage_history("r1")
    assert len(history) == 2
    assert {h["stage"] for h in history} == {"crawl", "rewrite"}
