# 카드 이미지 콘텐츠 자동화 시스템 — 요구사항 정의서
**버전**: v1.1 (사용자 결정 사항 전면 반영)
**작성일**: 2026-06-29
**상태**: 🟢 확정 (구현 기준)

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| v0.1 | 2026-06-26 | 버티컬 초안 |
| v0.2 | 2026-06-26 | 무료 도구 + 멀티플랫폼 반영 |
| v1.0 | 2026-06-26 | 버티컬 확정 + 어필리에이트 파트너 확정 + 요구사항 최종화 |
| v1.1 | 2026-06-29 | 감사 결과 + 사용자 7개 결정 사항 반영 (채널명·V1 데이터·Amazon·Imgur·TikTok·V3 언어·V3 데이터) |

---

## 확정 결정 사항 요약 (v1.1 변경 근거)

| # | 항목 | v1.0 내용 | v1.1 확정 내용 |
|---|------|----------|--------------|
| D-01 | 채널명 | 미확정 | **@HiddenFindsDaily** (3개 플랫폼 동일) |
| D-02 | V1 Temu 수집 | Temu Affiliate Product API | **Temu 제품 피드 API 없음 → 주 1회 수동 큐레이션 DB (20~30건)** |
| D-03 | V1 AliExpress | AliExpress Affiliate API (일반) | **AliExpress Portals API (공식 어필리에이트, 딥링크 지원)** |
| D-04 | V1 Amazon | PA-API (즉시 사용) | **초기 3개월: 수동 링크 수집 → Associates 실적 후 PA-API 전환** |
| D-05 | Instagram 이미지 호스팅 | 미지정 | **Imgur API (무료 임시 호스팅) → Graph API 전달** |
| D-06 | TikTok 업로드 방식 | Photo Mode (슬라이드쇼) | **FFmpeg 이미지→MP4 변환 → Video API 업로드** |
| D-07 | V3 K-뷰티 언어 | 한/영 혼용 (이중 타겟) | **영어 전용 (글로벌 K-뷰티 팬 단독 타겟)** |
| D-08 | V3 데이터 수집 | 올리브영·지그재그·에이블리 크롤링 | **Naver Shopping Search API (공식, 무료 일 25K) + YesStyle Affiliate Feed + LLM 생성** |

---

## 1. 프로젝트 개요

### 1-1. 목적
카드 이미지(캐러셀) 기반 콘텐츠를 **완전 자동 생성·업로드**하여
TikTok · Instagram · Pinterest 3개 플랫폼에서 **바이럴 트래픽**을 만들고
**어필리에이트 링크 클릭 및 구매 전환**으로 수익을 발생시킨다.

### 1-2. 채널 브랜딩 (확정)

| 항목 | 확정 값 |
|------|--------|
| 계정명 | **@HiddenFindsDaily** (Pinterest / Instagram / TikTok 동일) |
| 채널 컨셉 | "Every day, a hidden gem — products, places, beauty" |
| 타겟 언어 | **영어 전용** (글로벌 영어권 타겟) |
| 브랜드 정체성 | "발견(Finds)" — 제품 발견 + 여행지 발견 + 뷰티 발견 |
| Linktree | linktr.ee/HiddenFindsDaily |

### 1-3. 운영 원칙
- **무료 도구만 사용** (유료 API·구독 서비스 사용 불가)
- **100% 자동화** (스케줄러 실행 후 인력 개입 없음)
- **영어 전용** (V3 포함 모든 버티컬 영어로 통일)
- **어필리에이트 공시 의무** — 모든 포스트에 "#ad" + "affiliate link" 명시 (FTC 기준)
- **콘텐츠 재활용** (버티컬별 1회 생성 → 3개 플랫폼 비율 변환 배포)

### 1-4. 운영 버티컬 (확정 3개)

| # | 버티컬명 | 핵심 콘셉트 | 주요 플랫폼 |
|---|---------|-----------|-----------|
| V1 | **글로벌 쇼핑 비교** | AliExpress vs Amazon 실제 가격·품질 비교 (Temu 보조 큐레이션 포함) | TikTok PRIMARY |
| V2 | **숨은 여행지 + 여행 정보** | 구글에 없는 여행지 + 현지 꿀팁 + 예약 연계 | Pinterest PRIMARY |
| V3 | **K-뷰티 (영어 전용)** | 한국 뷰티 제품 소개 + 글로벌 구매 링크 (영어) | Instagram PRIMARY |

---

## 2. 버티컬별 콘텐츠 요구사항

---

### V1. 글로벌 쇼핑 비교

#### 2-1-1. 콘텐츠 컨셉
AliExpress 제품을 Amazon 등과 **실제 가격·스펙·리뷰 수치** 기준으로 비교.
"Same quality, 1/10 the price"라는 충격을 시각적으로 전달.
Temu 인기 제품은 별도 수동 큐레이션 DB에서 보완 공급.

#### 2-1-2. 콘텐츠 유형

| 유형 | 포맷 | 예시 제목 |
|------|------|---------|
| 가격 비교 | 2컬럼 대결 카드 | "AliExpress $2.99 vs Amazon $24.99 — Same Product?" |
| 제품 발굴 | 순위 카드 | "7 AliExpress Finds Under $5 with 50,000+ Reviews" |
| 구매 가이드 | 단계 정보 카드 | "How to Order from AliExpress Safely (2026 Guide)" |
| Temu 특선 | 큐레이션 카드 | "5 Temu Items That Went Viral This Week" |
| 실제 후기 | 평점 비교 카드 | "AliExpress ⭐4.8 vs Amazon ⭐4.1 — Which is Worth It?" |

#### 2-1-3. 데이터 소스 (v1.1 확정)

| 소스 | 수집 방법 | 무료 여부 | 수집 정보 | 비고 |
|------|----------|---------|---------|------|
| **AliExpress Portals API** | 공식 어필리에이트 API | ✅ 무료 | 제품명·가격·이미지·평점·딥링크 | **PRIMARY — 자동화** |
| **Temu 수동 큐레이션 DB** | 주 1회 수동 등록 (20~30건) | ✅ 무료 | 제품명·가격·이미지·트래킹 URL | **SECONDARY — 수동** |
| **Amazon (수동 초기)** | 수동 링크 수집 → DB 저장 | ✅ 무료 | 가격·평점·ASIN·URL | 3개월 후 PA-API 전환 |
| **Amazon PA-API** | PA-API 5.0 | ✅ 무료 (Associates 실적 후) | 가격·평점·리뷰 수 | Associates 승인 후 전환 |
| LLM 생성 | Groq / Gemini (무료) | ✅ 무료 | 비교 설명문·훅 카피 | 자동 생성 |

**Amazon 단계 전환 계획**:
```
Phase 1 (0~3개월):  수동으로 Amazon 제품 URL 수집 → SQLite temu_amazon_products 테이블 저장
Phase 2 (3개월+):   Associates 프로그램 실적 달성 후 PA-API 신청 → 자동 가격 조회로 전환
```

#### 2-1-4. 카드 구성 (7장 기준)

```
Slide 1  [HOOK]     — 가장 충격적인 가격 차이 1개 + 제목
Slide 2  [CONTEXT]  — "Why does this price gap exist?"
Slide 3~6 [COMPARE] — 제품별 비교 (Ali/Temu가격 | Amazon가격 | 품질 평가)
Slide 7  [CTA]      — "Check the link in bio · Save for later 💾"
```

#### 2-1-5. 어필리에이트 파트너 (V1)

| 파트너 | 가입 | 수수료 | 지급 조건 | 링크 형태 |
|--------|------|--------|---------|---------|
| **AliExpress Portals** | 무료, Admitad 경유 | 4~9% | 구매 완료 후 | 공식 딥링크 (자동) |
| **Temu Affiliate** | 무료, 즉시 승인 | 3~20% | 구매 완료 후 | 수동 큐레이션 링크 |
| **Amazon Associates** | 무료 | 1~10% | 구매 완료 후 | 수동 → PA-API 전환 |

#### 2-1-6. 바이럴 공식 (V1)

```
훅 공식: [충격 가격 차이] + [신뢰 지표] + [긴장감]
예) "This $3 AliExpress item has 80,000 reviews.
     The same thing on Amazon costs $31.
     I tested both. Here's the truth 👇"

알고리즘 신호:
  저장  → "Save this before you buy anything on Amazon"
  공유  → "Tag someone who overpays on Amazon 😂"
  댓글  → "Comment which one you'd buy"
```

---

### V2. 숨은 여행지 + 여행 정보

#### 2-2-1. 콘텐츠 컨셉
구글 검색 상위에 잘 노출되지 않는 **전 세계 숨은 여행지**를 발굴.
실용적인 여행 정보(예산·최적 시기·이동 방법)를 함께 제공.
Trip.com·Booking.com 예약 링크를 통해 수익 발생.

#### 2-2-2. 콘텐츠 유형

| 유형 | 포맷 | 예시 제목 |
|------|------|---------|
| 숨은 여행지 발굴 | 장소별 카드 | "5 Secret Beaches in Southeast Asia No One Talks About" |
| 예산 여행 가이드 | 단계 카드 | "7 Days in Japan Under $800 — Complete Guide" |
| 여행 꿀팁 | 팁 목록 카드 | "10 Things Airlines Don't Want You to Know" |
| 계절별 여행지 | 인포그래픽 카드 | "Best Hidden Destinations for Summer 2026" |
| 현지 맛집/숙소 | 비교 카드 | "Stay Like a Local vs Tourist in Bali" |

#### 2-2-3. 데이터 소스

| 소스 | 수집 방법 | 무료 여부 | 수집 정보 |
|------|----------|---------|---------|
| LLM 생성 (Groq/Gemini) | 프롬프트 기반 | ✅ 무료 | 여행지 정보·꿀팁·예산 추정 |
| Pollinations AI | HTTP GET (API 키 불필요) | ✅ 무료 | 여행지 배경 이미지 |
| Unsplash API | API 키 (무료, 50 req/h) | ✅ 무료 | 실제 여행지 사진 |
| Trip.com Affiliate API | 파트너 API | ✅ 무료 (파트너 가입 후) | 호텔·항공 가격·예약 링크 |
| Booking.com Affiliate | Affiliate API | ✅ 무료 (파트너 가입 후) | 숙박 가격·예약 링크 |

#### 2-2-4. 카드 구성 (8장 기준)

```
Slide 1  [HOOK]       — 가장 아름다운 여행지 이미지 + 충격 제목
Slide 2  [INTRIGUE]   — "Why most travelers never find this place"
Slide 3~7 [REVEAL]    — 여행지별: 이름·위치·예산·최적시기·예약 링크
Slide 8  [CTA]        — "Save for your bucket list 💾 · Book via link in bio"
```

#### 2-2-5. 어필리에이트 파트너 (V2)

| 파트너 | 가입 | 수수료 | 연동 방식 |
|--------|------|--------|---------|
| Trip.com Affiliate | 무료 | 숙박 3~7%, 항공 1~2% | API + 딥링크 |
| Booking.com Partner | 무료 | 예약금액의 4~8% | API + 딥링크 |
| Agoda Affiliate | 무료 | 3~7% | 딥링크 (아시아 강점) |
| Klook Affiliate | 무료 | 액티비티 4~5% | 딥링크 |
| GetYourGuide | 무료 | 투어/액티비티 8% | 딥링크 |
| Skyscanner | 무료 | CPC $0.1~0.5/click | 검색 링크 |

#### 2-2-6. 바이럴 공식 (V2)

```
훅 공식: [비밀/희귀성] + [구체적 숫자] + [FOMO]
예) "5 beaches Google Maps doesn't show you.
     Local fishermen only. Crystal water.
     Zero tourists. Swipe to find them 🗺️"

알고리즘 신호:
  저장  → "Save this for your bucket list 💾"
  공유  → "Tag who you'd bring here ✈️"
  댓글  → "Which country is #1? Comment below"
```

---

### V3. K-뷰티 (영어 전용 — 글로벌 타겟)

#### 2-3-1. 콘텐츠 컨셉
한국 뷰티 제품을 **영어**로 소개하여 글로벌 K-뷰티 팬을 타겟.
YesStyle 등 글로벌 배송 가능 플랫폼의 구매 링크 제공.
모든 텍스트·캡션·CTA는 **영어 전용** (한국어 사용 금지).

#### 2-3-2. 콘텐츠 유형 (영어 기준)

| 유형 | 포맷 | 예시 제목 (영어) |
|------|------|---------|
| 제품 추천 | 제품별 카드 | "5 K-Beauty Products Korean Women Actually Use Daily" |
| 루틴 소개 | 단계 카드 | "Korean Glass Skin Routine Under $30 (Ships Worldwide)" |
| 트렌드 발굴 | 비교 카드 | "7 K-Beauty Products Going Viral This Month" |
| 가성비 비교 | 대결 카드 | "K-Beauty $8 vs Western Brand $80 — Same Ingredients?" |
| 시즌 기획 | 기획전 카드 | "Best Korean Skincare for Summer 2026 (All Under $15)" |

#### 2-3-3. 데이터 소스 (v1.1 확정 — 크롤링 제거)

| 소스 | 수집 방법 | 무료 여부 | 수집 정보 | 변경 이유 |
|------|----------|---------|---------|---------|
| **Naver Shopping Search API** | 공식 API (일 25,000 req) | ✅ 무료 | 제품명·가격·쇼핑몰·이미지 | 올리브영/지그재그 크롤링 대체 |
| **YesStyle Affiliate Feed** | Affiliate 파트너 피드 | ✅ 무료 | 글로벌 K-뷰티 제품·가격·링크 | 글로벌 구매 링크 소스 |
| **LLM 생성 (Groq/Gemini)** | 프롬프트 기반 | ✅ 무료 | 영어 제품 설명·훅 카피·루틴 가이드 | 콘텐츠 자동 생성 |
| Pollinations AI | HTTP GET | ✅ 무료 | 뷰티 배경 이미지 | |

> **제거된 소스 (v1.0 → v1.1)**: 올리브영 직접 크롤링, 지그재그 크롤링, 에이블리 크롤링
> **이유**: 플랫폼 ToS 위반 위험 + 법적 리스크 → Naver Shopping API (공식) + YesStyle Feed 로 대체

#### 2-3-4. 카드 구성 (8장 기준, 영어 전용)

```
Slide 1  [HOOK]        — 가장 인상적인 제품 이미지 + 영어 제목
Slide 2  [CREDIBILITY] — "Actually used in Korea · X reviews · Trending now"
Slide 3~7 [PRODUCT]   — Per product: image · name · price · effect · buy link
Slide 8  [CTA]         — "Save this 💾 · Shop via link in bio · Ships worldwide"
```

#### 2-3-5. 어필리에이트 파트너 (V3)

| 파트너 | 대상 | 가입 | 수수료 | 비고 |
|--------|------|------|--------|------|
| **YesStyle Affiliate** | 글로벌 | 무료 | 10~15% | 글로벌 배송, PRIMARY |
| **StyleKorean Affiliate** | 글로벌 | 무료 | 5~10% | 영어 K-뷰티 전문 |
| **Stylevana** | 글로벌 | 무료 | 8~12% | 글로벌 K-뷰티 |
| Amazon (K-Beauty) | 글로벌 | 무료 | 4~8% | Associates |
| 네이버 파트너스 | 국내 | 무료 | CPC | Naver API 수집 제품 |

#### 2-3-6. 바이럴 공식 (V3, 영어 전용)

```
훅 공식: [K-Authority] + [가성비 충격] + [접근성]
예) "Korean women spend $8 on this skincare.
     Western equivalent costs $80.
     Same ingredients. Ships worldwide. 👇"

알고리즘 신호:
  저장  → "Save this for your next skincare haul 💾"
  공유  → "Tag your skincare bestie who needs this"
  댓글  → "Which step are you missing? Comment below"
```

---

## 3. 플랫폼별 업로드 요구사항

### 3-1. 공통 요구사항
- 모든 업로드는 **launchd(macOS) 스케줄러**로 자동 실행
- 업로드 실패 시 **3회 재시도**, 최종 실패 시 Telegram 알림
- 업로드 이력은 SQLite DB에 기록 (platform / post_id / uploaded_at / status)
- **어필리에이트 공시 필수**: 모든 캡션에 "#ad" + "Affiliate links in bio" 포함

### 3-2. 플랫폼별 스펙

#### Pinterest

| 항목 | 스펙 |
|------|------|
| API | Pinterest API v5 (무료) |
| 포맷 | 아이디어 핀 (멀티페이지) + 일반 정적 핀 |
| 이미지 크기 | **1000 × 1500 (2:3 비율)** |
| 핀 설명 | SEO 키워드 포함 150자 이내, 영어 |
| 링크 | 핀에 직접 어필리에이트 URL 삽입 (Pinterest 직링크 허용) |
| 보드 구조 | V1: "Best Deals & Finds" / V2: "Hidden Travel Gems" / V3: "K-Beauty Picks" |
| 업로드 주기 | 1일 2~3핀 (버티컬 교차) |
| 최적 시간 | 14:00 / 20:00 |

#### Instagram

| 항목 | 스펙 |
|------|------|
| API | Meta Graph API — Content Publishing (무료) |
| 계정 | Instagram Business Account 필요 |
| 포맷 | 캐러셀 포스트 (최대 10장) |
| 이미지 크기 | **1080 × 1080 (1:1)** |
| **이미지 호스팅** | **Imgur API (무료) → 임시 HTTPS URL → Graph API 전달** |
| 캡션 | 영어 훅 문구 + "#ad" + "Affiliate links in bio" + 해시태그 20~30개 |
| 링크 | 바이오 Linktree(무료) → linktr.ee/HiddenFindsDaily |
| 업로드 주기 | 1일 1건 (버티컬 순환) |
| 최적 시간 | 09:00 / 19:00 |

**Instagram 업로드 플로우 (v1.1 확정)**:
```
[카드 이미지 로컬 생성]
  → [Imgur API 업로드] → HTTPS URL 획득
  → [Meta Graph API carousel container 생성]
  → [각 슬라이드 image container 생성 (Imgur URL 사용)]
  → [carousel 게시 (publish)]
  → [Imgur 임시 이미지 삭제 (선택)]
```

#### TikTok

| 항목 | 스펙 |
|------|------|
| API | TikTok Content Posting API — **Video 업로드 방식** |
| 포맷 | **FFmpeg 이미지→MP4 변환 후 Video API 업로드** |
| 이미지 크기 | **1080 × 1920 (9:16 세로)** |
| 영상 사양 | 슬라이드당 3~4초, BGM 없음 (TikTok 앱에서 음원 추가 가능) |
| 설명 | 영어 훅 문구 + "#ad" + "affiliate" + 해시태그 5~10개 |
| 링크 | 바이오 링크 1개 → Linktree |
| 업로드 주기 | 1일 1~2건 |
| 최적 시간 | 19:00 / 21:00 |

**TikTok 업로드 플로우 (v1.1 확정)**:
```
[카드 이미지 로컬 생성 (1080×1920)]
  → [FFmpeg: 이미지 시퀀스 → MP4 변환]
       ffmpeg -r 0.33 -i slide_%d.jpg -vcodec libx264 -pix_fmt yuv420p output.mp4
  → [TikTok Content Posting API Video 업로드]
  → [업로드 완료 후 로컬 MP4 삭제]
```

### 3-3. 통합 업로드 스케줄 (@HiddenFindsDaily)

```
        월      화      수      목      금      토      일
TikTok  V1     V3      V1      V3      V1      V3      휴식
Pinterest V2   V1      V2      V1      V2      V1      V3
Instagram V3   V2      V3      V2      V3      V2      휴식

주간 합계: TikTok 6건 + Pinterest 7건 + Instagram 5건 = 18건/주
```

---

## 4. 콘텐츠 생성 요구사항

### 4-1. 공통 바이럴 공식

```
[HOOK 공식 — 첫 슬라이드]
  구조: [충격 수치/비밀] + [대상 명시] + [긴장감/FOMO]
  언어: 영어 전용

[REVEAL 공식 — 슬라이드 2~N]
  - 정보를 1장에 1개씩 점진 공개
  - 마지막 아이템이 가장 강렬해야 함
  - 각 슬라이드에 구체적 수치 (가격/평점/후기 수/% 절약)

[CTA 공식 — 마지막 슬라이드]
  저장: "Save this 💾"
  공유: "Tag someone who needs this"
  댓글: "Which one would you pick? Comment 👇"
  링크: "All links in bio · linktr.ee/HiddenFindsDaily"
  
[어필리에이트 공시 — 모든 포스트 캡션 필수]
  "#ad • Affiliate links used — I may earn a small commission at no extra cost to you"
```

### 4-2. 이미지 카드 생성 요구사항

| 항목 | 요구사항 |
|------|---------|
| 생성 도구 | Pillow (로컬, 무료) — 기존 card_renderer.py 확장 |
| 배경 이미지 | Pollinations AI (무료) / Unsplash API (무료) |
| 폰트 | **Poppins 또는 Inter (영어 전용 — 무료 오픈소스)** |
| 카드 수 | 버티컬별 5~10장 (V1: 7장, V2: 8장, V3: 8장) |
| **비율 독립 렌더링** | **각 플랫폼별 별도 렌더링 함수 필수 (단순 리사이즈 금지)** |
| Pinterest | render_pinterest(1000×1500) — 텍스트 레이아웃 세로 최적화 |
| Instagram | render_instagram(1080×1080) — 정방형 텍스트 중앙 배치 |
| TikTok | render_tiktok(1080×1920) — 세로 풀스크린, 상단 훅/하단 CTA |
| 브랜딩 | "@HiddenFindsDaily" 워터마크 모든 슬라이드 하단 |
| 어필리에이트 URL | 마지막 슬라이드에 "linktr.ee/HiddenFindsDaily" 표시 |

---

## 5. 수익화 요구사항

### 5-1. 어필리에이트 링크 관리

| 항목 | 요구사항 |
|------|---------|
| 링크 단축 | bit.ly (무료) + UTM 파라미터 (추적용) |
| UTM 구조 | `?utm_source=tiktok&utm_medium=carousel&utm_campaign=v1_ali_wk26` |
| 링크 저장 | SQLite affiliate_links 테이블 (vertical / product_id / platform / url / created_at) |
| 링크 자동 삽입 | 콘텐츠 생성 시 해당 제품/여행지 어필리에이트 URL 자동 매핑 |
| Linktree 구성 | linktr.ee/HiddenFindsDaily → V1·V2·V3 섹션별 링크 분기 |

### 5-2. 버티컬별 링크 배치 전략

```
V1 (쇼핑 비교):
  Pinterest  → 핀에 AliExpress Portals 딥링크 직접 삽입
  Instagram  → Linktree: "Best AliExpress Deals" 섹션
  TikTok     → Linktree: 동일

V2 (여행지):
  Pinterest  → 핀에 Booking.com / Trip.com 딥링크 직접 삽입
  Instagram  → Linktree: "Book Your Trip" 섹션
  TikTok     → Linktree: 동일

V3 (K-뷰티):
  Pinterest  → 핀에 YesStyle / StyleKorean 딥링크 직접 삽입
  Instagram  → Linktree: "Shop K-Beauty" 섹션 → YesStyle / Stylevana
  TikTok     → Linktree: 동일

글로벌 구매 채널 URL (V3 마지막 슬라이드 표시):
  YesStyle       → www.yesstyle.com
  StyleKorean    → www.stylekorean.com
  Stylevana      → www.stylevana.com
  OliveYoung Global → global.oliveyoung.com
```

---

## 6. 기술 스택 요구사항

### 6-1. 완전 무료 도구 스택

| 구분 | 도구 | 용도 | 비용 |
|------|------|------|------|
| 콘텐츠 생성 | Groq API (Llama 3.3 70B) | 훅 카피·제품 설명 생성 | 무료 |
| 콘텐츠 생성 | Gemini 2.0 Flash | 보조 LLM (폴백) | 무료 |
| 콘텐츠 생성 | Ollama (로컬) | 오프라인 폴백 | 무료 |
| 이미지 생성 | Pollinations AI | 여행지·배경 이미지 | 무료 |
| 이미지 생성 | Unsplash API | 실제 사진 | 무료 |
| 카드 렌더링 | Pillow (Python) | 카드 이미지 합성 | 무료 |
| 영상 변환 | FFmpeg | 이미지→MP4 (TikTok용) | 무료 |
| 이미지 호스팅 | **Imgur API** | Instagram용 임시 HTTPS 호스팅 | 무료 |
| 업로드 | Pinterest API v5 | 핀 자동 업로드 | 무료 |
| 업로드 | Instagram Graph API | 캐러셀 자동 업로드 (Imgur URL 사용) | 무료 |
| 업로드 | TikTok Content Posting API | Video 업로드 (FFmpeg MP4) | 무료 |
| 데이터 | AliExpress Portals API | V1 제품 데이터 | 무료 |
| 데이터 | Naver Shopping Search API | V3 K-뷰티 데이터 | 무료 |
| 스케줄링 | launchd (macOS) | 자동 실행 | 무료 |
| DB | SQLite | 콘텐츠·링크·업로드 이력 | 무료 |
| 링크 관리 | Linktree (무료 플랜) | 바이오 링크 허브 | 무료 |
| 알림 | Telegram Bot | 업로드 성공/실패 알림 | 무료 |

### 6-2. 기존 재사용 가능 모듈

| 모듈 | 재사용 여부 | 수정 내용 |
|------|-----------|---------|
| `src/renderer/card_renderer.py` | ✅ 재사용 | 멀티 슬라이드 + 3가지 비율 독립 렌더링 추가 |
| `src/renderer/bg_generator.py` | ✅ 재사용 | 여행지/제품/뷰티 프롬프트 추가 |
| `src/rewriter/` (LLM 클라이언트) | ✅ 재사용 | 버티컬별 영어 프롬프트 추가 |
| `src/db.py` | ✅ 재사용 | 신규 테이블 추가 |
| `src/utils/similarity.py` | ✅ 재사용 | 콘텐츠 중복 방지 |
| `scripts/launchd/` | ✅ 재사용 | 새 스케줄 추가 |
| `bot/` (Telegram) | ✅ 재사용 | 새 알림 메시지 추가 |

### 6-3. 신규 개발 필요 모듈 (v1.1 반영)

| 모듈 | 우선순위 | 설명 | v1.0 대비 변경 |
|------|---------|------|--------------|
| `src/renderer/carousel_renderer.py` | **P0** | 멀티 슬라이드 캐러셀 렌더러 (3비율 독립 함수) | 비율별 독립 렌더링 명시 |
| `src/uploader/pinterest.py` | **P0** | Pinterest API v5 업로더 | 동일 |
| `src/crawler/aliexpress_feed.py` | **P1** | AliExpress Portals API 제품 수집기 | `temu_feed.py` → 변경 |
| `src/crawler/temu_db.py` | **P1** | Temu 수동 큐레이션 DB 관리 CLI | 신규 (수동 입력 도구) |
| `src/crawler/travel_generator.py` | **P1** | LLM 기반 여행지 정보 생성기 | 동일 |
| `src/crawler/kbeauty_data.py` | **P1** | Naver Shopping API + YesStyle Feed 수집기 | `kbeauty_crawler.py` → 변경 |
| `src/affiliate/link_manager.py` | **P1** | 어필리에이트 URL 생성·UTM 관리 | UTM 파라미터 추가 |
| `src/uploader/imgur_uploader.py` | **P2** | Imgur API 임시 이미지 호스팅 | 신규 |
| `src/uploader/instagram_carousel.py` | **P2** | Instagram 캐러셀 업로더 (Imgur 연동) | Imgur 연동 추가 |
| `src/uploader/tiktok.py` | **P3** | TikTok Video API 업로더 (FFmpeg 연동) | FFmpeg 변환 포함 |

### 6-4. SQLite 신규 DB 스키마 (data/cards.db)

```sql
-- 카드 콘텐츠 저장
CREATE TABLE card_contents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vertical TEXT NOT NULL,          -- 'v1_shopping', 'v2_travel', 'v3_kbeauty'
    title TEXT NOT NULL,
    hook_text TEXT,
    slides_json TEXT,                -- JSON: [{slide_num, text, image_path}]
    language TEXT DEFAULT 'en',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_used INTEGER DEFAULT 0
);

-- 카드 업로드 이력
CREATE TABLE card_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content_id INTEGER REFERENCES card_contents(id),
    platform TEXT NOT NULL,          -- 'pinterest', 'instagram', 'tiktok'
    post_id TEXT,
    image_ratio TEXT,                -- '1:1', '2:3', '9:16'
    status TEXT DEFAULT 'pending',
    uploaded_at DATETIME,
    error_msg TEXT
);

-- 어필리에이트 링크 관리
CREATE TABLE affiliate_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vertical TEXT,
    product_id TEXT,
    platform TEXT,
    affiliate_partner TEXT,          -- 'aliexpress', 'temu', 'amazon', 'yesstyle', etc.
    original_url TEXT,
    short_url TEXT,
    utm_params TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Temu 수동 큐레이션 DB
CREATE TABLE temu_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT NOT NULL,
    price_usd REAL,
    category TEXT,
    image_url TEXT,
    affiliate_url TEXT,
    review_count INTEGER,
    rating REAL,
    curated_at DATE,
    is_active INTEGER DEFAULT 1
);
```

---

## 7. API 자격증명 체크리스트

구현 전 준비 필요 항목:

| API / 서비스 | 목적 | 가입 URL | 무료 한도 |
|------------|------|---------|---------|
| Pinterest API v5 | 핀 업로드 | developers.pinterest.com | 무료 |
| Meta Developer App | Instagram 업로드 | developers.facebook.com | 무료 |
| Imgur API | 이미지 임시 호스팅 | api.imgur.com | 1,250 upload/day |
| AliExpress Portals | V1 제품 데이터 | portals.aliexpress.com | 무료 |
| Naver Shopping API | V3 K-뷰티 데이터 | developers.naver.com | 25,000 req/day |
| Unsplash API | 여행지 사진 | unsplash.com/developers | 50 req/h |
| TikTok Content Posting API | TikTok 업로드 | developers.tiktok.com | 무료 (승인 필요) |
| Groq API | LLM | console.groq.com | 무료 (속도 제한) |
| Gemini API | LLM 폴백 | aistudio.google.com | 무료 |
| Amazon Associates | V1 Amazon 링크 | affiliate-program.amazon.com | 무료 |
| Booking.com Partner | V2 여행 | partner.booking.com | 무료 |
| Trip.com Affiliate | V2 여행 | affiliate.trip.com | 무료 |
| YesStyle Affiliate | V3 K-뷰티 | yesstyle.com/affiliate | 무료 |
| Linktree | 바이오 링크 허브 | linktr.ee | 무료 플랜 |

---

## 8. 성공 지표 (KPIs)

### 8-1. 플랫폼별 목표

| 플랫폼 | 3개월 목표 | 6개월 목표 | 12개월 목표 |
|--------|----------|----------|-----------|
| Pinterest | 팔로워 500 / 월 핀 조회 10만 | 월 조회 50만 | 월 조회 200만 |
| Instagram | 팔로워 1,000 | 팔로워 5,000 | 팔로워 20,000 |
| TikTok | 팔로워 500 | 팔로워 5,000 | 팔로워 30,000 |

### 8-2. 수익 목표

| 기간 | 월 수익 목표 | 주요 수익원 |
|------|-----------|-----------|
| 1~3개월 | $50~150 | AliExpress Portals + Temu 초기 전환 |
| 4~6개월 | $300~600 | Pinterest SEO 누적 + Booking.com |
| 7~12개월 | $1,000~3,000 | 전 플랫폼 복리 + 브랜드 딜 가능 |

### 8-3. 콘텐츠 품질 지표

| 지표 | 목표 기준 |
|------|---------|
| 저장율 (Instagram) | 게시물당 저장 > 좋아요의 20% |
| 완독율 (TikTok) | 70% 이상 끝까지 시청 |
| 핀 클릭율 (Pinterest) | CTR > 1.5% |
| 어필리에이트 전환율 | 클릭 대비 구매 > 1% |

---

## 9. 비기능 요구사항

| 항목 | 요구사항 |
|------|---------|
| 자동화 | 스케줄러 실행 후 인력 개입 없이 완전 자동 운영 |
| 안정성 | 단계별 실패 시 재시도 3회 + Telegram 알림 |
| 확장성 | 버티컬 추가 시 프롬프트·크롤러 모듈만 추가로 확장 가능 |
| 저작권 | 이미지·음악 모두 상업 이용 가능 라이선스만 사용 |
| 개인정보 | 수집 데이터에 개인 식별 정보 없음 |
| 플랫폼 정책 | 각 플랫폼 ToS 준수 (스팸 금지, 어필리에이트 공시) |
| 어필리에이트 공시 | **모든 포스트에 "#ad" + "Affiliate links used" 필수 (FTC 기준)** |
| 언어 | **영어 전용 (한국어 사용 금지 — 글로벌 타겟)** |

---

## 10. 구현 제외 범위 (Out of Scope)

- 유료 이미지 생성 API (Midjourney, DALL-E 3 유료 플랜 등)
- 올리브영·지그재그·에이블리 직접 크롤링 (ToS 위반 위험)
- Temu 자동 수집 API (존재하지 않음 — 수동 큐레이션으로 대체)
- Amazon PA-API 초기 사용 (Associates 실적 후 전환)
- 직접 판매 / 쇼핑몰 운영
- 한국어 콘텐츠 (글로벌 영어 전용으로 확정)
- 실시간 고객 응대 / DM 자동화
- 유료 광고 집행 (Meta Ads, TikTok Ads 등)

---

## 11. 다음 단계 (구현 착수 순서)

```
Step 1: 계정 & API 셋업 (1~2주)
  ├── @HiddenFindsDaily 계정 생성 (Pinterest → Instagram → TikTok)
  ├── Linktree 설정 (linktr.ee/HiddenFindsDaily)
  ├── API 자격증명 발급 (7번 체크리스트 순서)
  └── 어필리에이트 프로그램 가입 (AliExpress / Booking.com / YesStyle / Amazon)

Step 2: P0 기술 구현 (1~2주)
  ├── carousel_renderer.py (3비율 독립 렌더링)
  └── pinterest.py (Pinterest API v5 업로더)

Step 3: P1 콘텐츠 파이프라인 (2~3주)
  ├── aliexpress_feed.py (AliExpress Portals API)
  ├── temu_db.py (Temu 수동 큐레이션 CLI)
  ├── travel_generator.py (LLM 여행 콘텐츠)
  ├── kbeauty_data.py (Naver API + YesStyle)
  └── affiliate/link_manager.py (UTM 링크 관리)

Step 4: P2 Instagram 연동 (1~2주)
  ├── imgur_uploader.py (임시 이미지 호스팅)
  └── instagram_carousel.py (Graph API 연동)

Step 5: P3 TikTok 연동 (1~2주)
  └── tiktok.py (FFmpeg + Video API)
```

---

*본 문서 v1.1은 사전 구현 감사 및 사용자 확정 결정 7개를 전면 반영한 최종 기준이다.*
*이 문서 기준으로 Step 1부터 구현에 착수한다.*
