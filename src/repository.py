"""DB DAO (Repository) 계층.

각 테이블에 대한 INSERT/SELECT/UPDATE를 캡슐화한다.
SQL은 본 모듈에 한정하고, 파이프라인 단계는 Repository만 의존한다.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from .db import Database


# =============================================================================
# Sources (FR-1)
# =============================================================================
class SourceRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(
        self,
        *,
        source_kind: str,
        raw_text_hash: str,
        motif: str,
        raw_text: str | None = None,
        source_site: str | None = None,
        url: str | None = None,
        title: str | None = None,
        motif_embedding: bytes | None = None,
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO sources
              (source_kind, raw_text_hash, motif, raw_text, source_site, url, title, motif_embedding, length)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (source_kind, raw_text_hash, motif, raw_text, source_site, url, title, motif_embedding, len(motif)),
        )
        return int(cur.lastrowid or 0)

    def find_by_hash(self, raw_text_hash: str) -> dict[str, Any] | None:
        return self.db.fetchone("SELECT * FROM sources WHERE raw_text_hash = ?", (raw_text_hash,))

    def pick_unused(self, limit: int = 1) -> list[dict[str, Any]]:
        return self.db.fetchall(
            "SELECT * FROM sources WHERE status = 'new' ORDER BY crawled_at LIMIT ?",
            (limit,),
        )

    def mark_status(self, source_id: int, status: str) -> None:
        self.db.execute("UPDATE sources SET status = ? WHERE id = ?", (status, source_id))

    def purge_raw_text_older_than(self, hours: int) -> int:
        """24h 이상 경과한 sources의 raw_text를 NULL 처리 (FR-1.6)."""
        threshold = datetime.now() - timedelta(hours=hours)
        cur = self.db.execute(
            """
            UPDATE sources
               SET raw_text = NULL, raw_purged_at = CURRENT_TIMESTAMP
             WHERE raw_text IS NOT NULL
               AND crawled_at <= ?
            """,
            (threshold.isoformat(sep=" ", timespec="seconds"),),
        )
        return cur.rowcount

    def count_new(self) -> int:
        row = self.db.fetchone("SELECT COUNT(*) AS c FROM sources WHERE status = 'new'")
        return int(row["c"]) if row else 0


# =============================================================================
# Scripts (FR-2)
# =============================================================================
class ScriptRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(
        self,
        *,
        source_id: int | None,
        hook: str,
        body: str,
        twist: str,
        full_text: str,
        title: str = "",
        hashtags: list[str] | None = None,
        hook_pattern: str = "",
        similarity_motif: float | None = None,
        similarity_30d: float | None = None,
        similarity_cum: float | None = None,
        model_used: str = "",
        model_version: str = "",
        embedding: bytes | None = None,
        status: str = "created",
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO scripts
              (source_id, hook, body, twist, full_text, title, hashtags_json,
               hook_pattern, similarity_motif, similarity_30d, similarity_cum,
               model_used, model_version, embedding, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id, hook, body, twist, full_text, title,
                json.dumps(hashtags or [], ensure_ascii=False),
                hook_pattern, similarity_motif, similarity_30d, similarity_cum,
                model_used, model_version, embedding, status,
            ),
        )
        return int(cur.lastrowid or 0)

    def get(self, script_id: int) -> dict[str, Any] | None:
        return self.db.fetchone("SELECT * FROM scripts WHERE id = ?", (script_id,))

    def list_recent(self, days: int = 30, *, limit: int = 200) -> list[dict[str, Any]]:
        threshold = (datetime.now() - timedelta(days=days)).isoformat(sep=" ", timespec="seconds")
        return self.db.fetchall(
            "SELECT * FROM scripts WHERE created_at >= ? ORDER BY created_at DESC LIMIT ?",
            (threshold, limit),
        )

    def list_recent_hook_patterns(self, *, limit: int = 5) -> list[str]:
        rows = self.db.fetchall(
            "SELECT hook_pattern FROM scripts WHERE hook_pattern IS NOT NULL AND hook_pattern != '' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [r["hook_pattern"] for r in rows]

    def sample_cumulative(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.fetchall(
            "SELECT * FROM scripts ORDER BY RANDOM() LIMIT ?",
            (limit,),
        )

    def mark_status(self, script_id: int, status: str) -> None:
        self.db.execute("UPDATE scripts SET status = ? WHERE id = ?", (status, script_id))


# =============================================================================
# Videos (FR-3 ~ FR-5)
# =============================================================================
class VideoRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(
        self,
        *,
        script_id: int,
        speaker_id: str = "",
        audio_path: str = "",
        audio_lufs: float | None = None,
        subtitle_path: str = "",
        bg_video_path: str = "",
        bgm_path: str = "",
        video_path: str = "",
        duration_sec: float | None = None,
        width: int | None = None,
        height: int | None = None,
        valid: int = 0,
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO videos
              (script_id, speaker_id, audio_path, audio_lufs, subtitle_path,
               bg_video_path, bgm_path, video_path, duration_sec, width, height, valid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                script_id, speaker_id, audio_path, audio_lufs, subtitle_path,
                bg_video_path, bgm_path, video_path, duration_sec, width, height, valid,
            ),
        )
        return int(cur.lastrowid or 0)

    def get(self, video_id: int) -> dict[str, Any] | None:
        return self.db.fetchone("SELECT * FROM videos WHERE id = ?", (video_id,))

    def list_recent_speakers(self, limit: int = 3) -> list[str]:
        rows = self.db.fetchall(
            "SELECT speaker_id FROM videos WHERE speaker_id IS NOT NULL AND speaker_id != '' ORDER BY rendered_at DESC LIMIT ?",
            (limit,),
        )
        return [r["speaker_id"] for r in rows]

    def mark_valid(self, video_id: int) -> None:
        self.db.execute("UPDATE videos SET valid = 1 WHERE id = ?", (video_id,))


# =============================================================================
# Uploads (FR-6)
# =============================================================================
class UploadRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(
        self,
        *,
        video_id: int,
        oauth_client_name: str = "default",
        youtube_video_id: str = "",
        title: str = "",
        description: str = "",
        privacy_status: str = "public",
        ai_disclosure_set: int = 0,
        quota_units_used: int = 0,
        status: str = "queued",
        error_msg: str = "",
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO uploads
              (video_id, oauth_client_name, youtube_video_id, title, description,
               privacy_status, ai_disclosure_set, quota_units_used, status, error_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video_id, oauth_client_name, youtube_video_id, title, description,
                privacy_status, ai_disclosure_set, quota_units_used, status, error_msg,
            ),
        )
        return int(cur.lastrowid or 0)

    def quota_used_today(self, oauth_client_name: str = "default") -> int:
        row = self.db.fetchone(
            """
            SELECT COALESCE(SUM(quota_units_used), 0) AS used
              FROM uploads
             WHERE oauth_client_name = ?
               AND status = 'success'
               AND DATE(uploaded_at) = DATE('now', 'localtime')
            """,
            (oauth_client_name,),
        )
        return int(row["used"]) if row else 0

    def update_status(self, upload_id: int, *, status: str, error_msg: str = "") -> None:
        self.db.execute(
            "UPDATE uploads SET status = ?, error_msg = ? WHERE id = ?",
            (status, error_msg, upload_id),
        )

    def update_youtube_id(self, upload_id: int, *, youtube_video_id: str, ai_disclosure_set: int = 0) -> None:
        self.db.execute(
            "UPDATE uploads SET youtube_video_id = ?, ai_disclosure_set = ? WHERE id = ?",
            (youtube_video_id, ai_disclosure_set, upload_id),
        )


# =============================================================================
# Job Logs (FR-8)
# =============================================================================
class JobLogRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(
        self,
        *,
        run_id: str,
        stage: str,
        status: str,
        message: str = "",
        duration_ms: int | None = None,
    ) -> None:
        self.db.execute(
            "INSERT INTO job_logs (run_id, stage, status, message, duration_ms) VALUES (?, ?, ?, ?, ?)",
            (run_id, stage, status, message, duration_ms),
        )

    def stage_history(self, run_id: str) -> list[dict[str, Any]]:
        return self.db.fetchall(
            "SELECT * FROM job_logs WHERE run_id = ? ORDER BY logged_at",
            (run_id,),
        )


# =============================================================================
# Asset Usage (FR-5.4, FR-5.5)
# =============================================================================
class AssetUsageRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self,
        *,
        asset_kind: str,
        asset_path: str,
        video_id: int | None = None,
        asset_hash: str = "",
    ) -> None:
        self.db.execute(
            "INSERT INTO asset_usage (asset_kind, asset_path, asset_hash, video_id) VALUES (?, ?, ?, ?)",
            (asset_kind, asset_path, asset_hash, video_id),
        )

    def last_used_at(self, asset_kind: str, asset_path: str) -> datetime | None:
        row = self.db.fetchone(
            """
            SELECT used_at FROM asset_usage
             WHERE asset_kind = ? AND asset_path = ? AND blacklisted = 0
             ORDER BY used_at DESC LIMIT 1
            """,
            (asset_kind, asset_path),
        )
        if not row or not row["used_at"]:
            return None
        try:
            return datetime.fromisoformat(str(row["used_at"]))
        except ValueError:
            return None

    def is_blacklisted(self, asset_kind: str, asset_path: str) -> bool:
        row = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM asset_usage WHERE asset_kind = ? AND asset_path = ? AND blacklisted = 1",
            (asset_kind, asset_path),
        )
        return bool(row and int(row["c"]) > 0)

    def blacklist(self, asset_kind: str, asset_path: str, reason: str = "") -> None:
        self.db.execute(
            "INSERT INTO asset_usage (asset_kind, asset_path, blacklisted, blacklist_reason) VALUES (?, ?, 1, ?)",
            (asset_kind, asset_path, reason),
        )


# =============================================================================
# API Usage (Quota / Rate Limit)
# =============================================================================
class ApiUsageRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def record(self, *, api_name: str, units_used: int = 1, succeeded: bool = True, error_code: str = "") -> None:
        self.db.execute(
            "INSERT INTO api_usage (api_name, units_used, succeeded, error_code) VALUES (?, ?, ?, ?)",
            (api_name, units_used, 1 if succeeded else 0, error_code),
        )

    def count_within_window(self, api_name: str, *, seconds: int) -> int:
        row = self.db.fetchone(
            """
            SELECT COUNT(*) AS c FROM api_usage
             WHERE api_name = ? AND called_at >= datetime('now', ?)
            """,
            (api_name, f"-{seconds} seconds"),
        )
        return int(row["c"]) if row else 0

    def units_today(self, api_name: str) -> int:
        row = self.db.fetchone(
            """
            SELECT COALESCE(SUM(units_used), 0) AS u FROM api_usage
             WHERE api_name = ? AND DATE(called_at) = DATE('now', 'localtime')
            """,
            (api_name,),
        )
        return int(row["u"]) if row else 0


# =============================================================================
# 통합 컨테이너
# =============================================================================
class Repositories:
    """모든 Repository를 1개 객체로 묶어 주입한다."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.sources = SourceRepository(db)
        self.scripts = ScriptRepository(db)
        self.videos = VideoRepository(db)
        self.uploads = UploadRepository(db)
        self.job_logs = JobLogRepository(db)
        self.asset_usage = AssetUsageRepository(db)
        self.api_usage = ApiUsageRepository(db)
