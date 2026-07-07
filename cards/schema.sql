-- ==================== HiddenFindsDaily Cards DB Schema ====================
-- data/cards.db — shorts.db와 완전 분리
-- DEV_SPEC_v1.0.md 섹션 3 기준
-- =========================================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA wal_autocheckpoint = 1000;

-- ── 카드 콘텐츠 ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS card_contents (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vertical     TEXT    NOT NULL,      -- 'v1_shopping' | 'v2_travel' | 'v3_kbeauty'
    title        TEXT    NOT NULL,
    hook_text    TEXT,
    slides_json  TEXT,                  -- JSON: [{slide_num, type, text, image_path}]
    language     TEXT    DEFAULT 'en',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_used      INTEGER DEFAULT 0
);

-- ── 카드 업로드 이력 ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS card_uploads (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id   INTEGER REFERENCES card_contents(id),
    platform     TEXT    NOT NULL,      -- 'pinterest' | 'instagram' | 'tiktok'
    post_id      TEXT,
    image_ratio  TEXT,                  -- '2:3' | '1:1' | '9:16'
    status       TEXT    DEFAULT 'pending',  -- 'pending' | 'success' | 'failed'
    uploaded_at  DATETIME,
    error_msg    TEXT
);

-- ── 어필리에이트 링크 ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS affiliate_links (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    vertical          TEXT,
    product_id        TEXT,
    platform          TEXT,
    affiliate_partner TEXT,             -- 'aliexpress' | 'temu' | 'booking' | 'yesstyle' 등
    original_url      TEXT,
    tracking_url      TEXT,             -- UTM 포함
    utm_campaign      TEXT,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── Temu 수동 큐레이션 ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS temu_products (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name  TEXT    NOT NULL,
    price_usd     REAL,
    category      TEXT,
    image_url     TEXT,
    affiliate_url TEXT,
    review_count  INTEGER,
    rating        REAL,
    curated_date  DATE,
    is_active     INTEGER DEFAULT 1
);

-- ── V1 쇼핑 비교 (AliExpress vs Amazon) — 실가격 수동 큐레이션 ──────────────────
-- 원칙1(사실): 양쪽 가격은 실제로 확인한 값만 입력. LLM은 카피만 작성, 가격 발명 금지.
CREATE TABLE IF NOT EXISTS shopping_comparisons (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name     TEXT NOT NULL,          -- 영어 제품명
    category         TEXT,
    ali_price_usd    REAL NOT NULL,          -- 실제 AliExpress 가격
    ali_rating       REAL,
    ali_orders       TEXT,                   -- "12k+ sold" 등
    ali_url          TEXT,                   -- 어필리에이트 딥링크
    amazon_price_usd REAL NOT NULL,          -- 실제 Amazon 가격
    amazon_rating    REAL,
    amazon_url       TEXT,
    image_url        TEXT,
    curated_date     DATE,
    is_active        INTEGER DEFAULT 1
);

-- ── 수익 추적 ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS revenue_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    partner      TEXT,
    platform     TEXT,
    vertical     TEXT,
    clicks       INTEGER DEFAULT 0,
    conversions  INTEGER DEFAULT 0,
    revenue_usd  REAL    DEFAULT 0.0,
    period_start DATE,
    period_end   DATE,
    recorded_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── 인덱스 ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_card_contents_vertical  ON card_contents(vertical);
CREATE INDEX IF NOT EXISTS idx_card_contents_is_used   ON card_contents(is_used);
CREATE INDEX IF NOT EXISTS idx_card_uploads_platform   ON card_uploads(platform);
CREATE INDEX IF NOT EXISTS idx_card_uploads_status     ON card_uploads(status);
CREATE INDEX IF NOT EXISTS idx_affiliate_links_partner ON affiliate_links(affiliate_partner);
