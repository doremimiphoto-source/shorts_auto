"""SQLite 래퍼.

- WAL 모드 + 외래키 강제 (A2)
- 스키마 자동 적용 (`db_schema.sql`)
- 컨텍스트 매니저로 트랜잭션 관리
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import PROJECT_ROOT


_SCHEMA_PATH = PROJECT_ROOT / "src" / "db_schema.sql"


def _row_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    """sqlite3.Row 대신 dict 반환 — JSON 직렬화·로깅에 편리."""
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


class Database:
    """싱글 SQLite 핸들 래퍼.

    파이프라인 실행 단위로 1개 인스턴스를 생성하여 공유한다.
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    # ---------- 연결 ----------
    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,            # autocommit; 트랜잭션은 BEGIN/COMMIT으로 명시
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.row_factory = _row_factory
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA wal_autocheckpoint = 1000")
        self._conn = conn
        return conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ---------- 스키마 ----------
    def init_schema(self, schema_path: str | Path = _SCHEMA_PATH) -> None:
        """스키마 SQL을 실행한다. 이미 존재하는 테이블은 IF NOT EXISTS로 보존."""
        sql = Path(schema_path).read_text(encoding="utf-8")
        conn = self.connect()
        conn.executescript(sql)

    # ---------- 트랜잭션 ----------
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        conn.execute("BEGIN")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # ---------- 백업 (A12) ----------
    def backup(self, dst_path: str | Path) -> None:
        """SQLite `.backup` 명령. WAL 일관성 보장된 사본 생성."""
        dst = Path(dst_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        src = self.connect()
        with sqlite3.connect(dst) as bck:
            src.backup(bck)

    # ---------- 편의 메서드 ----------
    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.connect().execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        cur = self.execute(sql, params)
        return cur.fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        cur = self.execute(sql, params)
        return list(cur.fetchall())


def open_database(db_path: str | Path, *, init: bool = True) -> Database:
    """`Database` 인스턴스 생성 + 옵션으로 스키마 초기화."""
    db = Database(db_path)
    db.connect()
    if init:
        db.init_schema()
    return db
