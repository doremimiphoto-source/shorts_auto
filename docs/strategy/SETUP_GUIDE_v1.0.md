# Step 1 — 계정 & API 셋업 가이드
**버전**: v1.0
**작성일**: 2026-06-29
**상태**: 🔵 진행 중
**채널명**: @HiddenFindsDaily

---

## 진행 순서 개요

```
Phase A: 소셜 계정 생성 (Pinterest → Instagram → TikTok)
Phase B: Linktree 설정
Phase C: 플랫폼 API 신청
Phase D: 어필리에이트 프로그램 가입
Phase E: 데이터 소스 API 신청
Phase F: 자격증명 로컬 환경 등록
```

---

## Phase A. 소셜 계정 생성

### A-1. Pinterest Business 계정

**순서 (새 계정 기준)**

1. `pinterest.com` → 우상단 "Sign up"
2. 이메일 + 비밀번호로 가입 (구글 계정 연동도 가능)
3. 가입 후 `pinterest.com/settings/` → **Account type** → "Business account로 전환"
4. 비즈니스 유형: **Content creator** 선택
5. 프로필 설정:
   - 이름: `Hidden Finds Daily`
   - 사용자명: `HiddenFindsDaily` (URL: pinterest.com/HiddenFindsDaily)
   - 소개문: `Daily hidden gems — deals, travel & K-beauty 🌏 Links in bio`
   - 웹사이트: `linktr.ee/HiddenFindsDaily` (Linktree 생성 후 입력)

6. **보드 3개 생성** (버티컬별 분리):

| 보드명 | 설명 | 카테고리 |
|--------|------|---------|
| `Best Deals & Finds` | AliExpress vs Amazon hidden price gems | Products |
| `Hidden Travel Gems` | Secret destinations no one talks about | Travel |
| `K-Beauty Picks` | Korean skincare & beauty that actually works | Beauty |

> 각 보드는 비공개(Secret)로 먼저 만들고, 첫 핀 3개 이상 올린 후 공개 전환 권장

---

### A-2. Instagram Business 계정

**순서**

1. Instagram 앱 또는 `instagram.com` → 새 계정 생성
2. 사용자명: `hiddenfindsda...` (소문자, Instagram은 대소문자 구분 없음)
3. 가입 완료 후 프로필 편집:
   - 이름: `Hidden Finds Daily`
   - 카테고리: **Creator** → **Content Creator** 또는 **Shopping & Retail**
   - 소개문:
     ```
     🛍 Deals · ✈️ Travel · 💄 K-Beauty
     Daily hidden gems from around the world
     👇 Shop all links
     linktr.ee/HiddenFindsDaily
     ```
4. **Professional Account으로 전환**:
   - 설정 → 계정 → Professional Account 전환
   - 유형: **Creator** 선택
5. Facebook 페이지 연결 (Instagram Graph API 사용 필수):
   - `facebook.com` → 새 페이지 생성 → 이름: `Hidden Finds Daily`
   - Instagram 설정 → Linked accounts → Facebook 연결

> ⚠️ Facebook 페이지 연결 없이는 Meta Graph API로 자동 업로드 불가

---

### A-3. TikTok 계정

**순서**

1. TikTok 앱 → 새 계정 생성
2. 사용자명: `@HiddenFindsDaily`
3. 프로필 설정:
   - 이름: `Hidden Finds Daily`
   - 소개문:
     ```
     🛍 Deals · ✈️ Travel · 💄 K-Beauty
     Hidden gems you didn't know existed
     👇 linktr.ee/HiddenFindsDaily
     ```
4. 바이오 링크: `linktr.ee/HiddenFindsDaily`
5. **TikTok for Business 전환** (Content Posting API 사용 필수):
   - `TikTok for Business` 앱 또는 `business.tiktok.com` → 기존 계정 연결

---

## Phase B. Linktree 설정

### B-1. 계정 생성

1. `linktr.ee` → Sign up
2. URL: `linktr.ee/HiddenFindsDaily`
3. 플랜: **Free** (링크 개수 무제한, 기본 분석 제공)

### B-2. 링크 구조 설정

```
linktr.ee/HiddenFindsDaily
│
├── [섹션 헤더] 🛍 Best Deals This Week
│   ├── AliExpress Top Picks → (AliExpress Portals 어필리에이트 링크)
│   ├── Temu Finds → (Temu 어필리에이트 링크)
│   └── vs Amazon Comparison → (Amazon Associates 링크)
│
├── [섹션 헤더] ✈️ Hidden Travel Gems
│   ├── Book Hotels → (Booking.com 어필리에이트 링크)
│   ├── Find Flights → (Trip.com 어필리에이트 링크)
│   └── Activities & Tours → (Klook / GetYourGuide 링크)
│
└── [섹션 헤더] 💄 K-Beauty Shop
    ├── YesStyle → (YesStyle 어필리에이트 링크)
    ├── StyleKorean → (StyleKorean 어필리에이트 링크)
    └── OliveYoung Global → (global.oliveyoung.com)
```

> Linktree Free 플랜은 섹션 헤더 기능이 없을 수 있음. 링크 제목으로 구분:
> 예) "🛍 AliExpress Top Picks This Week"

---

## Phase C. 플랫폼 API 신청

### C-1. Pinterest API v5

1. `developers.pinterest.com` 접속 → My Apps → Create App
2. 앱 정보:
   - App name: `HiddenFindsDaily Uploader`
   - Description: `Automated pin publishing for affiliate content`
   - Website URL: `linktr.ee/HiddenFindsDaily`
3. 신청 후 **앱 심사** (보통 1~3 영업일)
4. 승인 후 발급되는 값 저장:
   - `PINTEREST_APP_ID`
   - `PINTEREST_APP_SECRET`
5. OAuth 2.0 Access Token 발급:
   - Scopes 필요: `pins:read`, `pins:write`, `boards:read`, `boards:write`

> ⚠️ Pinterest API v5는 앱 심사가 필요함. 심사 중에는 개발 환경(샌드박스)에서만 테스트 가능

---

### C-2. Meta (Instagram) Graph API

1. `developers.facebook.com` → My Apps → Create App
2. 앱 유형: **Business** 선택
3. 제품 추가: **Instagram Graph API** 선택
4. 앱 대시보드에서 발급:
   - `META_APP_ID`
   - `META_APP_SECRET`
5. Instagram Business Account 연결:
   - Graph API Explorer → 계정 선택 → `instagram_business_account` ID 확인
   - `INSTAGRAM_BUSINESS_ACCOUNT_ID` 저장
6. Long-lived Access Token 발급 (60일 유효, 자동 갱신 구현 필요):
   ```
   GET https://graph.facebook.com/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={app-id}
     &client_secret={app-secret}
     &fb_exchange_token={short-lived-token}
   ```
7. 필요 권한(Scopes): `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`

> ⚠️ 앱을 "Live" 모드로 전환해야 실제 계정에 업로드 가능 (개발 모드는 테스터 계정만)

---

### C-3. Imgur API

1. `api.imgur.com` → Register an Application
2. 앱 유형: **OAuth 2 without a callback URL (anonymous usage)** 선택
3. 발급값 저장:
   - `IMGUR_CLIENT_ID` (익명 업로드에 사용)
   - `IMGUR_CLIENT_SECRET`
4. 무료 한도: **1,250 uploads/day**, **12,500 requests/day**

> 익명 업로드(Authorization: Client-ID {id})로 충분. OAuth 로그인 불필요.

---

### C-4. TikTok Content Posting API

1. `developers.tiktok.com` → My Apps → Create App
2. 제품 선택: **Content Posting API** 체크
3. 필요 권한(Scopes): `video.upload`, `video.publish`
4. 앱 정보 입력 → **심사 신청** (1~2주 소요, 가장 긴 심사)
5. 발급값 저장:
   - `TIKTOK_CLIENT_KEY`
   - `TIKTOK_CLIENT_SECRET`
6. User Access Token 발급 (OAuth 2.0)

> ⚠️ TikTok API 심사가 가장 오래 걸림. 가장 먼저 신청 권장.
> 심사 중에는 개인 계정으로 테스트 가능 (하루 최대 5개 업로드)

---

## Phase D. 어필리에이트 프로그램 가입

### D-1. V1 (쇼핑 비교) 어필리에이트

| 파트너 | 가입 URL | 가입 난이도 | 예상 승인 기간 |
|--------|---------|-----------|-------------|
| **AliExpress Portals** (Admitad) | `portals.aliexpress.com` | ★★☆ | 3~7일 |
| **Temu Affiliate** | `temucreators.com` | ★☆☆ | 즉시~1일 |
| **Amazon Associates** | `affiliate-program.amazon.com` | ★★☆ | 즉시 (실적 심사는 180일) |

**AliExpress Portals 가입 순서**:
1. `portals.aliexpress.com` → Join now
2. 계정 유형: **Content Creator** 선택
3. 소셜 채널 URL 입력: TikTok / Instagram / Pinterest 링크
4. 승인 후 → Product links 생성 → 딥링크 API 사용 가능

**Amazon Associates 주의사항**:
- 가입 후 **180일 이내 3건 이상 판매** 없으면 계정 비활성화
- 초기에는 링크만 수동 생성, 판매 실적 쌓은 후 PA-API 신청

---

### D-2. V2 (여행지) 어필리에이트

| 파트너 | 가입 URL | 가입 난이도 | 예상 승인 기간 |
|--------|---------|-----------|-------------|
| **Booking.com Partner** | `partner.booking.com` | ★★★ | 7~14일 |
| **Trip.com Affiliate** | `affiliate.trip.com` | ★★☆ | 3~5일 |
| **Agoda Affiliate** | `partners.agoda.com` | ★★☆ | 3~5일 |
| **Klook Affiliate** | `affiliate.klook.com` | ★★☆ | 3~7일 |
| **GetYourGuide** | `partner.getyourguide.com` | ★★★ | 7~14일 |

**Booking.com 가입 순서**:
1. `partner.booking.com` → Sign up as affiliate
2. 웹사이트/채널 URL 입력 (Linktree URL 가능)
3. 트래픽 규모·콘텐츠 설명 작성 (솔직하게 작성, 신규라면 "building stage" 명시)
4. 승인 후 딥링크 생성기에서 링크 발급

---

### D-3. V3 (K-뷰티) 어필리에이트

| 파트너 | 가입 URL | 가입 난이도 | 예상 승인 기간 |
|--------|---------|-----------|-------------|
| **YesStyle** | `yesstyle.com/affiliate` | ★☆☆ | 즉시~1일 |
| **StyleKorean** | `stylekorean.com/affiliate` | ★☆☆ | 1~3일 |
| **Stylevana** | `stylevana.com/affiliate` | ★★☆ | 3~5일 |
| **네이버 파트너스** | `adcenter.naver.com` | ★★☆ | 1~3일 |

**YesStyle 가입 순서**:
1. `yesstyle.com` → Affiliate Program (하단 푸터)
2. 소셜 채널 및 콘텐츠 유형 입력
3. 승인 후 제품별 딥링크 + 배너 생성 가능

---

## Phase E. 데이터 소스 API 신청

### E-1. Naver Shopping Search API (V3 K-뷰티)

1. `developers.naver.com` → 애플리케이션 등록
2. 사용 API: **검색 → 쇼핑** 선택
3. 발급값 저장:
   - `NAVER_CLIENT_ID`
   - `NAVER_CLIENT_SECRET`
4. 무료 한도: **25,000 req/day**

---

### E-2. Unsplash API (V2 여행지 사진)

1. `unsplash.com/developers` → Your applications → New Application
2. 용도: 여행지 배경 이미지 자동 수집
3. 발급값 저장:
   - `UNSPLASH_ACCESS_KEY`
4. 무료 한도: **50 requests/hour**

---

### E-3. Groq API (LLM — 이미 사용 중)

- 기존 shorts_auto에서 사용 중 → `GROQ_API_KEY` 재사용 (추가 신청 불필요)

---

### E-4. Gemini API (LLM 폴백 — 이미 사용 중)

- 기존 shorts_auto에서 사용 중 → `GEMINI_API_KEY` 재사용 (추가 신청 불필요)

---

## Phase F. 자격증명 로컬 환경 등록

모든 자격증명을 `.env` 파일에 추가:

```bash
# 파일 위치: /Users/doremi/Developer/shorts_auto/.env
# (기존 .env에 아래 섹션 추가)

# ── Card Content System ──────────────────────────────

# Pinterest
PINTEREST_APP_ID=
PINTEREST_APP_SECRET=
PINTEREST_ACCESS_TOKEN=
PINTEREST_BOARD_V1=          # "Best Deals & Finds" 보드 ID
PINTEREST_BOARD_V2=          # "Hidden Travel Gems" 보드 ID
PINTEREST_BOARD_V3=          # "K-Beauty Picks" 보드 ID

# Instagram / Meta
META_APP_ID=
META_APP_SECRET=
META_ACCESS_TOKEN=
INSTAGRAM_BUSINESS_ACCOUNT_ID=

# TikTok
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_ACCESS_TOKEN=
TIKTOK_USER_ID=

# Imgur
IMGUR_CLIENT_ID=
IMGUR_CLIENT_SECRET=

# Affiliate — V1
ALIEXPRESS_APP_KEY=
ALIEXPRESS_APP_SECRET=
ALIEXPRESS_TRACKING_ID=
TEMU_AFFILIATE_ID=
AMAZON_ASSOCIATE_TAG=

# Affiliate — V2
BOOKING_AFFILIATE_ID=
TRIPDOTCOM_AFFILIATE_ID=
AGODA_API_KEY=
KLOOK_AFFILIATE_ID=

# Affiliate — V3
YESSTYLE_AFFILIATE_ID=
STYLEKOREAN_AFFILIATE_ID=
NAVER_PARTNERS_ID=

# Data Sources
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
UNSPLASH_ACCESS_KEY=

# Channel Info
CHANNEL_NAME=HiddenFindsDaily
LINKTREE_URL=linktr.ee/HiddenFindsDaily
```

---

## 체크리스트 (진행 상황 추적)

### Phase A — 소셜 계정
- [ ] Pinterest Business 계정 생성 + 보드 3개 생성
- [ ] Instagram Business 계정 생성 + Facebook 페이지 연결
- [ ] TikTok 계정 생성 + Business 전환

### Phase B — Linktree
- [ ] Linktree 계정 생성 (linktr.ee/HiddenFindsDaily)
- [ ] 3개 섹션(V1/V2/V3) 링크 구조 설정 (임시 링크로 먼저 채워두기)

### Phase C — 플랫폼 API
- [ ] TikTok Content Posting API 심사 신청 (가장 먼저 — 심사 오래 걸림)
- [ ] Pinterest API v5 앱 생성 + 심사 신청
- [ ] Meta Developer App 생성 + Instagram Graph API 연결
- [ ] Imgur API Client ID 발급

### Phase D — 어필리에이트
- [ ] AliExpress Portals (Admitad) 가입
- [ ] Temu Affiliate 가입
- [ ] Amazon Associates 가입
- [ ] Booking.com Partner 가입
- [ ] Trip.com Affiliate 가입
- [ ] YesStyle Affiliate 가입
- [ ] StyleKorean Affiliate 가입

### Phase E — 데이터 소스 API
- [ ] Naver Shopping Search API 신청
- [ ] Unsplash API 신청

### Phase F — 환경 설정
- [ ] .env 파일에 발급된 자격증명 입력
- [ ] API 연결 테스트 (각 플랫폼 ping)

---

## 예상 소요 시간

| Phase | 작업 시간 | 대기 시간 (심사) |
|-------|---------|--------------|
| A. 소셜 계정 | 1~2시간 | 없음 |
| B. Linktree | 30분 | 없음 |
| C-1. Pinterest API | 30분 | 1~3일 |
| C-2. Meta API | 1시간 | 없음 (즉시) |
| C-3. Imgur API | 10분 | 없음 (즉시) |
| C-4. TikTok API | 30분 | **1~2주** ← 가장 오래 걸림 |
| D. 어필리에이트 | 2~3시간 | 3~14일 (파트너별 상이) |
| E. 데이터 소스 | 30분 | 없음 (즉시) |

> **TikTok API 심사 기간(1~2주) 동안 Phase D + E + P0 구현을 병행 진행 권장**

---

## 완료 후 다음 단계

모든 Phase 완료 시:
→ **Step 2: P0 구현** — `carousel_renderer.py` + `pinterest.py` 코드 작성
