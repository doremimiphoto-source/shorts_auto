-- ==================== Shorts Auto Pipeline DB Schema ====================
-- SQLite WAL 모드 사용 (A2)
-- REQUIREMENTS.md §5 기준 + 운영 보강 컬럼 추가
-- =========================================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA wal_autocheckpoint = 1000;

-- ---------- 수집된 모티프 (FR-1.6) ----------
-- 원문(raw_text)은 24h 후 자동 삭제. 모티프(motif)만 영구 보관.
CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_kind     TEXT    NOT NULL,                      -- 'llm_creator' | 'reddit' | 'public_domain'
    source_site     TEXT,                                  -- 도메인 또는 서브레딧 명
    url             TEXT,
    title           TEXT,
    raw_text        TEXT,                                  -- 원문 (24h 내 NULL 처리)
    raw_text_hash   TEXT    NOT NULL UNIQUE,               -- SHA-256 (FR-1.5)
    motif           TEXT    NOT NULL,                      -- 모티프 요약 (200~1500자)
    motif_embedding BLOB,                                  -- ko-sroberta 벡터 (선택, 캐시)
    length          INTEGER,
    crawled_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_purged_at   TIMESTAMP,                             -- 원문 삭제 시각
    status          TEXT    DEFAULT 'new'                  -- 'new' | 'used' | 'rejected' | 'duplicate'
);
CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status);
CREATE INDEX IF NOT EXISTS idx_sources_crawled_at ON sources(crawled_at);

-- ---------- 각색된 대본 (FR-2) ----------
CREATE TABLE IF NOT EXISTS scripts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id           INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    hook                TEXT    NOT NULL,
    body                TEXT    NOT NULL,
    twist               TEXT    NOT NULL,
    full_text           TEXT    NOT NULL,
    title               TEXT,
    hashtags_json       TEXT,                              -- JSON array
    hook_pattern        TEXT,                              -- question/shock/number/...
    similarity_motif    REAL,                              -- 모티프 대비 (FR-2.6 ①)
    similarity_30d      REAL,                              -- 30일 대비 (FR-2.6 ②)
    similarity_cum      REAL,                              -- 누적 샘플 (FR-2.6 ③)
    model_used          TEXT,                              -- 'gemini' | 'groq' | 'ollama'
    model_version       TEXT,
    embedding           BLOB,                              -- 후속 유사도 검사용 캐시
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status              TEXT    DEFAULT 'created'          -- 'created' | 'rejected' | 'used'
);
CREATE INDEX IF NOT EXISTS idx_scripts_created_at ON scripts(created_at);
CREATE INDEX IF NOT EXISTS idx_scripts_status ON scripts(status);
CREATE INDEX IF NOT EXISTS idx_scripts_hook_pattern ON scripts(hook_pattern);

-- ---------- 생성된 음성·자막·영상 (FR-3 ~ FR-5) ----------
CREATE TABLE IF NOT EXISTS videos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id       INTEGER REFERENCES scripts(id) ON DELETE CASCADE,
    speaker_id      TEXT,                                  -- 'ko_KR-kss-medium' 등
    audio_path      TEXT,
    audio_lufs      REAL,
    subtitle_path   TEXT,
    bg_video_path   TEXT,
    bgm_path        TEXT,
    video_path      TEXT,
    duration_sec    REAL,
    width           INTEGER,
    height          INTEGER,
    rendered_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid           INTEGER DEFAULT 0                      -- 1 = validation 통과
);
CREATE INDEX IF NOT EXISTS idx_videos_rendered_at ON videos(rendered_at);
CREATE INDEX IF NOT EXISTS idx_videos_speaker_id ON videos(speaker_id);

-- ---------- 업로드 결과 (FR-6) ----------
CREATE TABLE IF NOT EXISTS uploads (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id                INTEGER REFERENCES videos(id) ON DELETE SET NULL,
    oauth_client_name       TEXT,                          -- 멀티 채널 식별 (FR-6.10)
    youtube_video_id        TEXT,
    title                   TEXT,
    description             TEXT,
    privacy_status          TEXT,                          -- public/unlisted/private
    ai_disclosure_set       INTEGER DEFAULT 0,             -- Studio UI 토글 성공 여부
    quota_units_used        INTEGER,
    status                  TEXT,                          -- 'success' | 'failed' | 'quota_exceeded' | 'queued'
    error_msg               TEXT,
    uploaded_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    content_id_checked_at   TIMESTAMP,                     -- BGM Content ID 사후 매칭 점검 시각 (A10)
    content_id_match        INTEGER DEFAULT 0              -- 1 = 매칭 발견
);
CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status);
CREATE INDEX IF NOT EXISTS idx_uploads_uploaded_at ON uploads(uploaded_at);

-- ---------- 작업 로그 (FR-8) ----------
CREATE TABLE IF NOT EXISTS job_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT    NOT NULL,                      -- 배치 실행 ID (UUID)
    stage           TEXT    NOT NULL,                      -- 'crawl' | 'rewrite' | 'tts' | 'subtitle' | 'render' | 'upload' | 'cleanup'
    status          TEXT    NOT NULL,                      -- 'ok' | 'fail' | 'skip'
    message         TEXT,
    duration_ms     INTEGER,
    logged_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_job_logs_run_id ON job_logs(run_id);
CREATE INDEX IF NOT EXISTS idx_job_logs_logged_at ON job_logs(logged_at);
CREATE INDEX IF NOT EXISTS idx_job_logs_stage_status ON job_logs(stage, status);

-- ---------- 에셋 사용 이력 (FR-5.4, FR-5.5) ----------
-- 동일 배경영상 7일 간격 강제, BGM Content ID 매칭 추적용
CREATE TABLE IF NOT EXISTS asset_usage (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_kind      TEXT    NOT NULL,                      -- 'bg_video' | 'bgm'
    asset_path      TEXT    NOT NULL,
    asset_hash      TEXT,
    used_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    video_id        INTEGER REFERENCES videos(id) ON DELETE SET NULL,
    blacklisted     INTEGER DEFAULT 0,
    blacklist_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_asset_usage_kind_path ON asset_usage(asset_kind, asset_path);
CREATE INDEX IF NOT EXISTS idx_asset_usage_used_at ON asset_usage(used_at);

-- ---------- API 호출 카운터 (Quota·Rate Limit, A3) ----------
CREATE TABLE IF NOT EXISTS api_usage (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    api_name        TEXT    NOT NULL,                      -- 'gemini' | 'groq' | 'youtube' | 'pexels' | 'pixabay'
    units_used      INTEGER DEFAULT 1,                     -- 호출 1회 = 1 (YouTube는 실제 quota cost)
    succeeded       INTEGER DEFAULT 1,
    error_code      TEXT,
    called_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_api_usage_api_called ON api_usage(api_name, called_at);

-- ---------- 일일 컴플라이언스 체크 결과 (§3.5.4) ----------
CREATE TABLE IF NOT EXISTS compliance_checks (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    check_date                  DATE    NOT NULL,
    avg_similarity_30d          REAL,
    speaker_consecutive_max     INTEGER,
    bg_reuse_min_interval_days  INTEGER,
    policy_warnings_count       INTEGER DEFAULT 0,
    passed                      INTEGER DEFAULT 1,
    notes                       TEXT,
    checked_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(check_date)
);

-- ---------- 일일 KPI 스냅샷 (Kill-Switch §12) ----------
CREATE TABLE IF NOT EXISTS daily_kpi (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date       DATE    NOT NULL,
    uploads_attempted   INTEGER DEFAULT 0,
    uploads_succeeded   INTEGER DEFAULT 0,
    uploads_failed      INTEGER DEFAULT 0,
    avg_ctr             REAL,                              -- YouTube Analytics에서 후속 수집
    avg_view_retention  REAL,
    notes               TEXT,
    snapshot_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_date)
);
