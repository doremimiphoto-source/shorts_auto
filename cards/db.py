"""cards.db 전용 DB 래퍼 (쇼츠 src/db.py 와 완전 독립).

분리 원칙:
  - src/ 패키지를 일절 import 하지 않는다 (zero src 결합).
  - 쇼츠 src.db.Database 의 _migrate()(videos 테이블 전제)를 피하기 위해
    동일 패턴의 경량 SQLite 래퍼를 자체 보유한다.
  - data/cards.db 는 data/shorts.db 와 물리적으로 분리된 파일.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from cards.config import CARDS_DB_PATH, CARDS_SCHEMA_PATH


def _row_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


class CardsDB:
    """카드 시스템 전용 SQLite 핸들 (WAL + dict row)."""

    def __init__(self, db_path: str | Path = CARDS_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = _row_factory
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        self._conn = conn
        return conn

    def init_schema(self) -> None:
        """cards/schema.sql 적용 (전부 IF NOT EXISTS → 재적용 안전)."""
        self.connect().executescript(CARDS_SCHEMA_PATH.read_text(encoding="utf-8"))

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

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

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self.connect().execute(sql, params)

    def fetchone(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        return self.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        return list(self.execute(sql, params).fetchall())


def open_cards_db() -> CardsDB:
    """cards.db 연결 + 스키마 적용."""
    db = CardsDB()
    db.connect()
    db.init_schema()
    return db


# ── 편의 함수 ────────────────────────────────────────────────────────────────

def save_content(db: CardsDB, *, vertical: str, title: str, hook_text: str,
                 slides_json: str, language: str = "en") -> int:
    cur = db.execute(
        "INSERT INTO card_contents (vertical, title, hook_text, slides_json, language) "
        "VALUES (?, ?, ?, ?, ?)",
        (vertical, title, hook_text, slides_json, language),
    )
    return int(cur.lastrowid)


def record_upload(db: CardsDB, *, content_id: int, platform: str, post_id: str | None,
                  image_ratio: str, status: str, error_msg: str | None = None) -> None:
    db.execute(
        "INSERT INTO card_uploads "
        "(content_id, platform, post_id, image_ratio, status, uploaded_at, error_msg) "
        "VALUES (?, ?, ?, ?, ?, datetime('now'), ?)",
        (content_id, platform, post_id, image_ratio, status, error_msg),
    )


def save_affiliate_link(db: CardsDB, *, vertical: str, product_id: str, platform: str,
                        partner: str, original_url: str, tracking_url: str,
                        utm_campaign: str) -> None:
    db.execute(
        "INSERT INTO affiliate_links "
        "(vertical, product_id, platform, affiliate_partner, original_url, tracking_url, utm_campaign) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (vertical, product_id, platform, partner, original_url, tracking_url, utm_campaign),
    )


def title_exists(db: CardsDB, vertical: str, title: str) -> bool:
    """동일 버티컬·제목 중복 여부 (similarity 임베딩 대체 — O-01)."""
    row = db.fetchone(
        "SELECT 1 FROM card_contents WHERE vertical = ? AND title = ? LIMIT 1",
        (vertical, title),
    )
    return row is not None
