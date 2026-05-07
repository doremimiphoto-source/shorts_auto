"""src.db SQLite 래퍼 테스트."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.db import Database, open_database


def test_init_schema_creates_tables(tmp_path: Path) -> None:
    db = open_database(tmp_path / "t.db", init=True)
    rows = db.fetchall("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    names = {r["name"] for r in rows}
    expected = {
        "sources", "scripts", "videos", "uploads", "job_logs",
        "asset_usage", "api_usage", "compliance_checks", "daily_kpi",
    }
    assert expected.issubset(names)
    db.close()


def test_init_schema_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "t.db"
    db = open_database(db_path, init=True)
    db.close()
    # 두 번째 호출도 IF NOT EXISTS로 통과
    db2 = open_database(db_path, init=True)
    db2.close()


def test_wal_mode_enabled(tmp_path: Path) -> None:
    db = open_database(tmp_path / "t.db", init=True)
    row = db.fetchone("PRAGMA journal_mode")
    assert row is not None
    # 결과 키는 첫 컬럼 그대로
    assert "wal" in str(list(row.values())[0]).lower()
    db.close()


def test_foreign_keys_enabled(tmp_path: Path) -> None:
    db = open_database(tmp_path / "t.db", init=True)
    row = db.fetchone("PRAGMA foreign_keys")
    assert row is not None
    assert list(row.values())[0] == 1
    db.close()


def test_transaction_commit_and_rollback(tmp_path: Path) -> None:
    db = open_database(tmp_path / "t.db", init=True)

    # 정상 commit
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO sources (source_kind, raw_text_hash, motif) VALUES (?, ?, ?)",
            ("llm_creator", "h1", "x" * 250),
        )
    rows = db.fetchall("SELECT motif FROM sources")
    assert len(rows) == 1

    # 예외 시 rollback
    with pytest.raises(RuntimeError):
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO sources (source_kind, raw_text_hash, motif) VALUES (?, ?, ?)",
                ("llm_creator", "h2", "y" * 250),
            )
            raise RuntimeError("simulated")
    rows = db.fetchall("SELECT motif FROM sources")
    assert len(rows) == 1
    db.close()


def test_backup_creates_file(tmp_path: Path) -> None:
    db = open_database(tmp_path / "t.db", init=True)
    backup = tmp_path / "backup" / "t.db"
    db.backup(backup)
    assert backup.exists()
    assert backup.stat().st_size > 0
    db.close()


def test_unique_hash_constraint(tmp_path: Path) -> None:
    db = open_database(tmp_path / "t.db", init=True)
    db.execute(
        "INSERT INTO sources (source_kind, raw_text_hash, motif) VALUES (?, ?, ?)",
        ("llm_creator", "samehash", "a" * 300),
    )
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO sources (source_kind, raw_text_hash, motif) VALUES (?, ?, ?)",
            ("llm_creator", "samehash", "b" * 300),
        )
    db.close()
