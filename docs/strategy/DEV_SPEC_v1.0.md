# 개발정의서 — 카드 이미지 콘텐츠 자동화 시스템
**문서 유형**: 개발정의서 (Development Specification)
**버전**: v1.0
**작성일**: 2026-06-29
**상태**: 🟢 확정 (구현 기준)
**채널**: @HiddenFindsDaily

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| v1.0 | 2026-06-29 | 최초 작성 — TECH_REVIEW_v1.0 이슈 반영, 전체 아키텍처 확정 |

---

## 1. 시스템 아키텍처

### 1-1. 전체 파이프라인 흐름

```
[스케줄러 (launchd)]
       │
       ▼
[cards/main.py] ← 진입점 (버티컬·플랫폼 선택)
       │
       ├──▶ [데이터 수집 레이어]
       │         ├── aliexpress_feed.py   (V1: AliExpress Portals API)
       │         ├── temu_db.py           (V1: Temu 수동 큐레이션 DB)
       │         ├── travel_generator.py  (V2: LLM 기반 여행지 정보)
       │         └── kbeauty_data.py      (V3: Naver Shopping API + YesStyle)
       │
       ├──▶ [콘텐츠 생성 레이어]
       │         ├── RewriterChain        (기존 재사용 — 영어 프롬프트)
       │         └── affiliate/link_manager.py (UTM 어필리에이트 링크)
       │
       ├──▶ [이미지 렌더링 레이어]
       │         ├── bg_generator.py      (기존 확장 — generate_bg_image())
       │         └── carousel_renderer.py (신규 — 3비율 × 5슬라이드 유형)
       │
       ├──▶ [업로드 레이어]
       │         ├── pinterest.py         (PIN 생성 — 직링크 포함)
       │         ├── imgur_uploader.py    (Instagram용 임시 HTTPS 호스팅)
       │         ├── instagram_carousel.py (Carousel post)
       │         └── tiktok.py            (FFmpeg MP4 → Video API)
       │
       └──▶ [공통 인프라]
                 ├── db.py / cards.db     (이력·링크·상태 관리)
                 ├── telegram_notifier.py (업로드 결과 알림)
                 └── retry.py             (API 재시도)
```

### 1-2. 디렉토리 구조 (신규 추가 경로만)

```
shorts_auto/
├── cards/                          ← 신규 패키지 (카드 시스템 진입점)
│   ├── __init__.py
│   ├── main.py                     ← 파이프라인 오케스트레이터
│   └── config.py                   ← 카드 시스템 전용 설정
│
├── src/
│   ├── renderer/
│   │   └── carousel_renderer.py    ← 신규 (C-01, C-02 해결)
│   │                                  bg_generator.py 수정 (C-05)
│   │
│   ├── crawler/
│   │   ├── aliexpress_feed.py      ← 신규 (V1 자동)
│   │   ├── temu_db.py              ← 신규 (V1 수동 CLI)
│   │   ├── travel_generator.py     ← 신규 (V2 LLM)
│   │   └── kbeauty_data.py         ← 신규 (V3 Naver+YesStyle)
│   │
│   ├── uploader/
│   │   ├── pinterest.py            ← 신규
│   │   ├── imgur_uploader.py       ← 신규
│   │   ├── instagram_carousel.py   ← 신규
│   │   ├── tiktok.py               ← 신규
│   │   └── meta_token_manager.py   ← 신규 (토큰 자동 갱신)
│   │
│   └── affiliate/
│       └── link_manager.py         ← 신규 (신규 패키지)
│
├── assets/
│   └── fonts/
│       ├── Poppins-Black.ttf       ← 신규 다운로드 필요
│       ├── Poppins-Bold.ttf        ← 신규
│       ├── Poppins-Medium.ttf      ← 신규
│       └── Inter-Regular.ttf       ← 신규
│
├── data/
│   └── cards.db                    ← 신규 SQLite DB
│
└── output/
    └── cards/
        ├── v1_shopping/
        ├── v2_travel/
        └── v3_kbeauty/
```

---

## 2. 모듈별 개발정의

---

### 2-1. carousel_renderer.py [P0]

**파일 경로**: `src/renderer/carousel_renderer.py`

**역할**: 멀티슬라이드 카드 이미지 생성 (3개 비율, 5개 슬라이드 유형)

**입력**
```python
slides: list[SlideData]   # 슬라이드 목록
ratio: Literal["pinterest", "instagram", "tiktok"]
channel_tag: str = "@HiddenFindsDaily"
output_dir: Path
```

**출력**
```python
list[Path]  # 생성된 이미지 파일 경로 목록 (슬라이드 순서)
```

**슬라이드 유형 (SlideType)**
```
HOOK     — 첫 슬라이드: 충격 제목 + 배경 이미지
CONTEXT  — 배경 설명: 부제목 + 아이콘
REVEAL   — 정보 공개: 제품/여행지/제품 카드 (반복)
COMPARE  — 비교 레이아웃: 좌/우 2컬럼 (V1 전용)
CTA      — 마지막 슬라이드: 저장·공유·링크 유도
```

**캔버스 사양**
```python
CANVAS = {
    "pinterest": (1000, 1500),   # 2:3
    "instagram": (1080, 1080),   # 1:1
    "tiktok":    (1080, 1920),   # 9:16
}
```

**폰트 매핑 (영어 전용)**
```python
FONTS = {
    "headline_black": "Poppins-Black.ttf",
    "headline_bold":  "Poppins-Bold.ttf",
    "body_medium":    "Poppins-Medium.ttf",
    "body_regular":   "Inter-Regular.ttf",
}
```

**색상 팔레트**
```python
PALETTE = {
    "bg_top":   (10, 18, 38),    # 다크 네이비
    "bg_bot":   (5,  10, 22),
    "accent":   (64, 220, 180),  # 민트 (기존 유지)
    "highlight": (255, 220, 40), # 옐로우
    "main":     (255, 255, 255),
    "sub":      (160, 190, 220),
}
```

**재사용**: `_gradient()`, `_grain()`, `_rounded_box()`, `_highlighter()` — card_renderer.py에서 이식

**의존성**: Pillow, `bg_generator.generate_bg_image()`

---

### 2-2. bg_generator.py 수정 [P0]

**추가 함수**: `generate_bg_image(script, cache_dir, *, timeout_sec) -> Path | None`

- Pollinations AI에서 이미지 다운로드 후 JPG 캐시
- Ken Burns MP4 변환 **없음** (카드 전용 경량 버전)
- 반환: 이미지 Path 또는 None (실패 시)

**추가 프롬프트 매핑** (영어 키워드 기반)
```python
# V1 — 쇼핑 비교
(["aliexpress", "temu", "amazon", "deal", "price"],
 "ultra-clean product comparison flat lay on white marble, ...")

# V2 — 여행지
(["travel", "beach", "destination", "hidden", "secret"],
 "breathtaking hidden beach with crystal water, drone aerial view, ...")

# V3 — K-뷰티
(["kbeauty", "skincare", "korean beauty", "serum", "routine"],
 "elegant korean skincare products arranged on minimalist surface, ...")
```

---

### 2-3. aliexpress_feed.py [P1]

**파일 경로**: `src/crawler/aliexpress_feed.py`

**역할**: AliExpress Portals API에서 인기 제품 수집

**API**: AliExpress Portals (Admitad) — HMAC-MD5 서명 방식

**핵심 함수**
```python
def fetch_products(
    category: str,
    page_size: int = 20,
    sort_by: str = "SALE_PRICE_ASC",
) -> list[AliProduct]
```

**AliProduct 스키마**
```python
@dataclass
class AliProduct:
    product_id: str
    title: str
    original_price: float
    sale_price: float
    discount_pct: int
    rating: float
    review_count: int
    image_url: str
    affiliate_url: str   # Portals 딥링크
```

**서명 구현**
```python
import hashlib, hmac
def _sign(params: dict, app_secret: str) -> str:
    sorted_str = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    return hmac.new(app_secret.encode(), sorted_str.encode(), hashlib.md5).hexdigest().upper()
```

**의존성**: `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET`, `ALIEXPRESS_TRACKING_ID`

---

### 2-4. temu_db.py [P1]

**파일 경로**: `src/crawler/temu_db.py`

**역할**: Temu 수동 큐레이션 제품 CLI 관리 도구

**기능**
```
python -m src.crawler.temu_db add     ← 제품 추가
python -m src.crawler.temu_db list    ← 목록 확인
python -m src.crawler.temu_db fetch   ← 이번 주 큐레이션 제품 조회
```

**DB 테이블**: `temu_products` (cards.db 내)

**의존성**: `src/db.py`, `data/cards.db`

---

### 2-5. travel_generator.py [P1]

**파일 경로**: `src/crawler/travel_generator.py`

**역할**: LLM(Groq/Gemini)으로 여행지 정보 생성 + Unsplash 사진 수집

**핵심 함수**
```python
def generate_travel_content(
    region: str,          # "Southeast Asia", "Europe", "Japan" 등
    content_type: str,    # "hidden_beach", "budget_guide", "local_tip"
    count: int = 5,
) -> TravelContent
```

**TravelContent 스키마**
```python
@dataclass
class TravelContent:
    hook: str
    places: list[TravelPlace]   # 각 슬라이드용
    cta: str
    booking_link: str           # Booking.com / Trip.com 어필리에이트
```

**Unsplash 연동**: 여행지명으로 검색 → 고해상도 이미지 URL 수집

**의존성**: `RewriterChain`, `UNSPLASH_ACCESS_KEY`, `BOOKING_AFFILIATE_ID`

---

### 2-6. kbeauty_data.py [P1]

**파일 경로**: `src/crawler/kbeauty_data.py`

**역할**: Naver Shopping Search API + YesStyle Affiliate Feed로 K-뷰티 제품 수집

**Naver Shopping API**
```python
GET https://openapi.naver.com/v1/search/shop.json
    ?query={keyword}&display=10&sort=sim
Headers: X-Naver-Client-Id, X-Naver-Client-Secret
```

**핵심 함수**
```python
def fetch_kbeauty_products(
    keyword: str,         # "serum", "sunscreen", "toner" 등
    global_only: bool = True,  # YesStyle에서 구매 가능한 것만
) -> list[KBeautyProduct]
```

**KBeautyProduct 스키마**
```python
@dataclass
class KBeautyProduct:
    name_en: str          # LLM으로 영어 번역
    name_kr: str          # 원본 한국어명
    price_krw: int
    price_usd: float      # 환율 적용
    brand: str
    image_url: str
    naver_url: str
    yesstyle_url: str     # YesStyle 어필리에이트 링크 (있으면)
    rating: float
    review_count: int
```

**의존성**: `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `YESSTYLE_AFFILIATE_ID`, `RewriterChain`

---

### 2-7. link_manager.py [P1]

**파일 경로**: `src/affiliate/link_manager.py`

**역할**: 어필리에이트 링크 생성, UTM 파라미터 추가, DB 저장

**핵심 함수**
```python
def create_affiliate_link(
    partner: str,          # "aliexpress", "temu", "booking", "yesstyle" 등
    product_url: str,
    platform: str,         # "pinterest", "instagram", "tiktok"
    vertical: str,         # "v1", "v2", "v3"
    campaign: str,         # 콘텐츠 식별자 (날짜+시퀀스)
) -> str                   # UTM 포함 추적 URL
```

**UTM 구조**
```
{affiliate_url}?utm_source={platform}&utm_medium=carousel&utm_campaign={vertical}_{campaign}

예) https://s.click.aliexpress.com/e/xxx
    ?utm_source=pinterest&utm_medium=carousel&utm_campaign=v1_20260629_001
```

**의존성**: `src/db.py` (affiliate_links 테이블 저장)

---

### 2-8. pinterest.py [P0]

**파일 경로**: `src/uploader/pinterest.py`

**역할**: Pinterest API v5로 핀 자동 업로드

**구현 전략** (H-02 해결)
- Phase 1: 일반 정적 핀 (단일 이미지 — Hook 슬라이드)
  - 직접 어필리에이트 링크 삽입
  - SEO 최적화 설명문 자동 생성
- Phase 2: Idea Pins (파트너 API 승인 후)

**핵심 함수**
```python
def upload_pin(
    board_id: str,
    image_path: Path,
    title: str,
    description: str,
    link: str,             # 어필리에이트 직링크
    alt_text: str = "",
) -> str                   # pin_id
```

**API 엔드포인트**
```
POST https://api.pinterest.com/v5/pins
Authorization: Bearer {PINTEREST_ACCESS_TOKEN}

Body:
{
  "board_id": "{board_id}",
  "media_source": {"source_type": "image_url", "url": "{image_url}"},
  "title": "{title}",
  "description": "{description}",
  "link": "{affiliate_link}",
  "alt_text": "{alt_text}"
}
```

> ⚠️ Pinterest API는 이미지 URL 방식(URL 직접 전달) 또는 파일 업로드(multipart) 모두 지원.
> 이미지 파일 업로드 방식 사용 (로컬 파일 직접 전달, Imgur 불필요).

**의존성**: `PINTEREST_ACCESS_TOKEN`, `PINTEREST_BOARD_V1/V2/V3`, `retry.py`

---

### 2-9. imgur_uploader.py [P2]

**파일 경로**: `src/uploader/imgur_uploader.py`

**역할**: 로컬 이미지를 Imgur에 임시 업로드 → HTTPS URL 반환 → Instagram 업로드 후 삭제

**핵심 함수**
```python
def upload_image(image_path: Path) -> tuple[str, str]:
    """(image_url, delete_hash) 반환"""

def delete_image(delete_hash: str) -> None:
    """Instagram 업로드 완료 후 즉시 삭제"""
```

**API**
```
POST https://api.imgur.com/3/image
Authorization: Client-ID {IMGUR_CLIENT_ID}
Body: image={base64 또는 multipart}

Response: {"data": {"link": "...", "deletehash": "..."}}
```

**의존성**: `IMGUR_CLIENT_ID`, `retry.py`

---

### 2-10. instagram_carousel.py [P2]

**파일 경로**: `src/uploader/instagram_carousel.py`

**역할**: Meta Graph API로 Instagram 캐러셀 포스트 업로드

**업로드 플로우**
```python
# 1. 각 슬라이드 Imgur 업로드 → HTTPS URL 목록
urls = [imgur_uploader.upload_image(p) for p in slide_paths]

# 2. 개별 슬라이드 Container 생성
containers = [
    POST /v21.0/{ig_id}/media
        {"image_url": url, "is_carousel_item": "true"}
    for url in urls
]

# 3. 캐러셀 Container 생성
carousel = POST /v21.0/{ig_id}/media
    {"media_type": "CAROUSEL", "children": container_ids, "caption": caption}

# 4. 게시
POST /v21.0/{ig_id}/media_publish
    {"creation_id": carousel_id}

# 5. Imgur 이미지 삭제
[imgur_uploader.delete_image(dh) for dh in delete_hashes]
```

**캡션 구조**
```
{hook_text}

🔗 All links → linktr.ee/HiddenFindsDaily

#ad • Affiliate links used

#{hashtag1} #{hashtag2} ... (20~30개)
```

**의존성**: `META_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ACCOUNT_ID`, `imgur_uploader.py`, `meta_token_manager.py`

---

### 2-11. tiktok.py [P3]

**파일 경로**: `src/uploader/tiktok.py`

**역할**: 슬라이드 이미지 → FFmpeg MP4 변환 → TikTok Video API 업로드

**FFmpeg 변환 명령**
```bash
ffmpeg -y
  -framerate 0.286              # 1/3.5초 per slide
  -i slide_%02d.jpg             # 슬라이드 시퀀스
  -vf "scale=1080:1920:flags=lanczos,setsar=1"
  -c:v libx264
  -crf 20
  -preset fast
  -pix_fmt yuv420p
  -movflags +faststart          # 스트리밍 최적화
  output.mp4
```

**결과 파일**: ~24.5초, ~80~100 MB (TikTok 287 MB 한도 충족)

**TikTok Video Upload 플로우**
```python
# 1. Init upload
POST https://open.tiktokapis.com/v2/post/publish/inbox/video/init/
    {"source_info": {"source": "FILE_UPLOAD", "video_size": size, ...}}
→ upload_url, publish_id

# 2. Upload video bytes
PUT {upload_url}
    Content-Type: video/mp4
    Body: video bytes

# 3. Publish
POST https://open.tiktokapis.com/v2/post/publish/video/init/
    {"post_info": {"title": caption}, "source_info": {...}}
```

**의존성**: `TIKTOK_ACCESS_TOKEN`, `ffmpeg_path.py`, `retry.py`

---

### 2-12. meta_token_manager.py [P2]

**파일 경로**: `src/uploader/meta_token_manager.py`

**역할**: Meta Graph API Long-lived Token 자동 갱신 (H-03 해결)

**동작**
- 매일 1회 실행 (launchd)
- 토큰 만료까지 7일 이하 → 자동 갱신 API 호출
- 갱신 성공/실패 시 Telegram 알림
- 갱신된 토큰을 `.env`에 자동 저장

---

### 2-13. cards/main.py [P0]

**파일 경로**: `cards/main.py`

**역할**: 전체 파이프라인 오케스트레이터

**CLI 인터페이스**
```bash
python -m cards.main --vertical v1 --platform pinterest --count 1
python -m cards.main --vertical v2 --platform instagram --count 1
python -m cards.main --vertical v3 --platform tiktok --count 1
```

**파이프라인 단계**
```python
1. 데이터 수집 (vertical에 따라 분기)
2. LLM 콘텐츠 생성 (영어 프롬프트)
3. 어필리에이트 링크 생성 (link_manager)
4. 이미지 렌더링 (carousel_renderer, platform 비율)
5. 업로드 (platform에 따라 분기)
6. DB 기록 (card_uploads)
7. Telegram 알림
```

---

## 3. DB 스키마 (data/cards.db)

```sql
-- ── 카드 콘텐츠 ────────────────────────────────────
CREATE TABLE IF NOT EXISTS card_contents (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vertical     TEXT NOT NULL,      -- 'v1_shopping' | 'v2_travel' | 'v3_kbeauty'
    title        TEXT NOT NULL,
    hook_text    TEXT,
    slides_json  TEXT,               -- JSON: [{slide_num, type, text, image_path}]
    language     TEXT DEFAULT 'en',
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_used      INTEGER DEFAULT 0
);

-- ── 카드 업로드 이력 ────────────────────────────────
CREATE TABLE IF NOT EXISTS card_uploads (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id   INTEGER REFERENCES card_contents(id),
    platform     TEXT NOT NULL,      -- 'pinterest' | 'instagram' | 'tiktok'
    post_id      TEXT,
    image_ratio  TEXT,               -- '2:3' | '1:1' | '9:16'
    status       TEXT DEFAULT 'pending',  -- 'pending' | 'success' | 'failed'
    uploaded_at  DATETIME,
    error_msg    TEXT
);

-- ── 어필리에이트 링크 ────────────────────────────────
CREATE TABLE IF NOT EXISTS affiliate_links (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    vertical         TEXT,
    product_id       TEXT,
    platform         TEXT,
    affiliate_partner TEXT,           -- 'aliexpress' | 'temu' | 'booking' | 'yesstyle' 등
    original_url     TEXT,
    tracking_url     TEXT,            -- UTM 포함
    utm_campaign     TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── Temu 수동 큐레이션 ────────────────────────────────
CREATE TABLE IF NOT EXISTS temu_products (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    price_usd    REAL,
    category     TEXT,
    image_url    TEXT,
    affiliate_url TEXT,
    review_count INTEGER,
    rating       REAL,
    curated_date DATE,
    is_active    INTEGER DEFAULT 1
);

-- ── 수익 추적 ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS revenue_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    partner      TEXT,
    platform     TEXT,
    vertical     TEXT,
    clicks       INTEGER DEFAULT 0,
    conversions  INTEGER DEFAULT 0,
    revenue_usd  REAL DEFAULT 0.0,
    period_start DATE,
    period_end   DATE,
    recorded_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 4. config.py 확장 정의

`Secrets` 클래스에 추가할 필드:

```python
# ── Card Content System ────────────────────────
# Pinterest
pinterest_app_id: str = ""
pinterest_app_secret: str = ""
pinterest_access_token: str = ""
pinterest_board_v1: str = ""
pinterest_board_v2: str = ""
pinterest_board_v3: str = ""

# Instagram / Meta
meta_app_id: str = ""
meta_app_secret: str = ""
meta_access_token: str = ""
instagram_business_account_id: str = ""

# TikTok
tiktok_client_key: str = ""
tiktok_client_secret: str = ""
tiktok_access_token: str = ""

# Imgur
imgur_client_id: str = ""
imgur_client_secret: str = ""

# Affiliate — V1
aliexpress_app_key: str = ""
aliexpress_app_secret: str = ""
aliexpress_tracking_id: str = ""
temu_affiliate_id: str = ""
amazon_associate_tag: str = ""

# Affiliate — V2
booking_affiliate_id: str = ""
tripdotcom_affiliate_id: str = ""
klook_affiliate_id: str = ""

# Affiliate — V3
yesstyle_affiliate_id: str = ""
stylekorean_affiliate_id: str = ""

# Data Sources
naver_client_id: str = ""
naver_client_secret: str = ""
unsplash_access_key: str = ""

# Channel
channel_name: str = "HiddenFindsDaily"
linktree_url: str = "https://linktr.ee/HiddenFindsDaily"
```

---

## 5. 스케줄링 정의 (launchd plist)

신규 추가 plist 파일 목록:

| 파일명 | 실행 명령 | 시각 | 버티컬 | 플랫폼 |
|--------|---------|------|--------|--------|
| `task_Card_TikTok_V1_MON.xml` | `python -m cards.main --vertical v1 --platform tiktok` | 월 19:00 | V1 | TikTok |
| `task_Card_TikTok_V3_TUE.xml` | `python -m cards.main --vertical v3 --platform tiktok` | 화 19:00 | V3 | TikTok |
| `task_Card_Pinterest_V2_MON.xml` | `python -m cards.main --vertical v2 --platform pinterest` | 월 14:00 | V2 | Pinterest |
| `task_Card_Instagram_V3_MON.xml` | `python -m cards.main --vertical v3 --platform instagram` | 월 09:00 | V3 | Instagram |
| `task_Card_TokenRefresh.xml` | `python -m src.uploader.meta_token_manager` | 매일 06:00 | - | Meta |

> 전체 18건/주 스케줄은 `WORK_PLAN_v1.0.md` 부록 참고

---

## 6. 에러 처리 전략

| 단계 | 에러 유형 | 처리 방식 |
|------|---------|---------|
| 데이터 수집 | API 타임아웃 | retry 3회 → 전날 캐시 사용 |
| LLM 생성 | Groq 한도 초과 | Gemini 폴백 → Ollama 폴백 |
| 이미지 렌더링 | Pollinations 실패 | 단색 그라디언트 배경 폴백 |
| Imgur 업로드 | 실패 | retry 3회 → 업로드 스킵 + Telegram 알림 |
| Pinterest 업로드 | 실패 | retry 3회 → card_uploads에 failed 기록 |
| Instagram 업로드 | 토큰 만료 | meta_token_manager 자동 갱신 시도 |
| TikTok 업로드 | 실패 | retry 3회 → Telegram 알림 |
| 전체 파이프라인 | 예외 발생 | Telegram 에러 알림 + 스택 트레이스 기록 |

---

## 7. 폰트 다운로드 정의

구현 전 `scripts/download_cards_fonts.py` 실행 필요:

```python
FONTS_TO_DOWNLOAD = [
    ("Poppins-Black",  "https://fonts.gstatic.com/s/poppins/v21/pxiByp8kv8JHgFVrLBT5V1s.ttf"),
    ("Poppins-Bold",   "https://fonts.gstatic.com/s/poppins/v21/pxiByp8kv8JHgFVrLDD4V1s.ttf"),
    ("Poppins-Medium", "https://fonts.gstatic.com/s/poppins/v21/pxiByp8kv8JHgFVrLGT7V1s.ttf"),
    ("Inter-Regular",  "https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiA.woff2"),
]
```

> Google Fonts — OFL 라이선스, 상업적 사용 가능

---

*다음 문서: WORK_PLAN_v1.0.md (작업계획서)*
