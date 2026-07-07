# 카드 이미지 콘텐츠 자동화 시스템 — 요구사항 정의서
**버전**: v1.0 (최종 확정 기준)
**작성일**: 2026-06-26
**상태**: 🟢 확정 (구현 기준)

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| v0.1 | 2026-06-26 | 버티컬 초안 |
| v0.2 | 2026-06-26 | 무료 도구 + 멀티플랫폼 반영 |
| v1.0 | 2026-06-26 | 버티컬 확정 + 어필리에이트 파트너 확정 + 요구사항 최종화 |

---

## 1. 프로젝트 개요

### 1-1. 목적
카드 이미지(캐러셀) 기반 콘텐츠를 **완전 자동 생성·업로드**하여
TikTok · Instagram · Pinterest 3개 플랫폼에서 **바이럴 트래픽**을 만들고
**어필리에이트 링크 클릭 및 구매 전환**으로 수익을 발생시킨다.

### 1-2. 운영 원칙
- **무료 도구만 사용** (유료 API·구독 서비스 사용 불가)
- **100% 자동화** (스케줄러 실행 후 인력 개입 없음)
- **콘텐츠 재활용** (1회 생성 → 3개 플랫폼 동시 배포)
- **어필리에이트 수익** (직접 판매 없음, 클릭/구매 수수료 방식)

### 1-3. 운영 버티컬 (확정 3개)

| # | 버티컬명 | 핵심 콘셉트 | 주요 플랫폼 |
|---|---------|-----------|-----------|
| V1 | **글로벌 쇼핑 비교** | 테무/알리 vs 아마존 실제 가격·품질 비교 | TikTok > Instagram > Pinterest |
| V2 | **숨은 여행지 + 여행 정보** | 구글에 없는 여행지 + 현지 꿀팁 + 예약 연계 | Pinterest > Instagram > TikTok |
| V3 | **K-뷰티 + K-라이프** | 한국 뷰티·패션 제품 소개 + 구매 링크 제공 | Instagram > TikTok > Pinterest |

---

## 2. 버티컬별 콘텐츠 요구사항

---

### V1. 글로벌 쇼핑 비교 (테무/알리 vs 아마존 등)

#### 2-1-1. 콘텐츠 컨셉
테무·알리익스프레스 제품을 아마존·기타 플랫폼과 **실제 가격·스펙·후기 수치** 기준으로 비교.
"같은 품질을 10분의 1 가격에 살 수 있다"는 충격을 시각적으로 전달.

#### 2-1-2. 콘텐츠 유형

| 유형 | 포맷 | 예시 제목 |
|------|------|---------|
| 가격 비교 | 2컬럼 대결 카드 | "TEMU $2.99 vs AMAZON $24.99 — Same Product?" |
| 제품 발굴 | 1장씩 순위 카드 | "7 Temu Finds Under $5 with 50,000+ Reviews" |
| 구매 가이드 | 단계별 정보 카드 | "How to Order from AliExpress Safely (2026 Guide)" |
| 실제 후기 | 평점 비교 카드 | "Temu ⭐4.8 vs Amazon ⭐4.1 — Which is Worth It?" |

#### 2-1-3. 데이터 소스

| 소스 | 수집 방법 | 무료 여부 | 수집 정보 |
|------|----------|---------|---------|
| Temu Affiliate Feed | Temu 어필리에이트 Product API | ✅ 무료 | 제품명·가격·이미지·후기 수 |
| AliExpress Portals | AliExpress Affiliate API | ✅ 무료 | 제품명·가격·이미지·평점 |
| Amazon Product API | Amazon PA-API 5.0 | ✅ 무료 (Associates 가입 후) | 가격·평점·리뷰 수·ASIN |
| LLM 생성 | Groq / Gemini (무료) | ✅ 무료 | 비교 설명문·훅 카피 |

#### 2-1-4. 카드 구성 (7장 기준)

```
Slide 1  [HOOK]     — 가장 충격적인 가격 차이 1개 + 제목
Slide 2  [CONTEXT]  — "왜 이런 가격 차이가 생기는가"
Slide 3~6 [COMPARE] — 제품별 비교 (Temu가격 | Amazon가격 | 품질 평가)
Slide 7  [CTA]      — "링크 클릭해서 직접 확인하세요" + 어필리에이트 링크 안내
```

#### 2-1-5. 어필리에이트 파트너 (V1)

| 파트너 | 가입 | 수수료 | 지급 조건 | 링크 형태 |
|--------|------|--------|---------|---------|
| Temu Affiliate Program | 무료, 즉시 승인 | 3~20% (카테고리별) | 구매 완료 후 | 제품별 딥링크 |
| AliExpress Portals (Admitad) | 무료 | 4~9% | 구매 완료 후 | 제품별 딥링크 |
| Amazon Associates | 무료 | 1~10% (카테고리별) | 구매 완료 후 | 제품별 딥링크 |

#### 2-1-6. 바이럴 공식 (V1)

```
훅 공식: [충격 가격 차이] + [신뢰 지표] + [긴장감]
예) "This $3 Temu item has 80,000 reviews.
     The same thing on Amazon costs $31.
     I tested both. Here's the truth 👇"

알고리즘 신호 유발:
  저장  → "Save this before you buy anything on Amazon"
  공유  → "Tag someone who shops on Amazon 😂"
  댓글  → "Comment which one you'd buy"
```

---

### V2. 숨은 여행지 + 여행 정보

#### 2-2-1. 콘텐츠 컨셉
구글 검색 상위에 잘 노출되지 않는 **전 세계 숨은 여행지**를 발굴하고,
실용적인 여행 정보(예산·최적 시기·이동 방법)와 함께 제공.
트립닷컴·Booking.com 등 여행 예약 플랫폼 링크를 통해 수익 발생.

#### 2-2-2. 콘텐츠 유형

| 유형 | 포맷 | 예시 제목 |
|------|------|---------|
| 숨은 여행지 발굴 | 장소별 카드 | "5 Secret Beaches in Southeast Asia No One Talks About" |
| 예산 여행 가이드 | 단계 정보 카드 | "7 Days in Japan Under $800 — Complete Guide" |
| 여행 꿀팁 | 팁 목록 카드 | "10 Things Airlines Don't Want You to Know" |
| 계절별 여행지 | 인포그래픽 카드 | "Best Hidden Destinations for Summer 2026" |
| 현지 맛집/숙소 | 비교 카드 | "Stay Like a Local vs Tourist in Bali" |

#### 2-2-3. 데이터 소스

| 소스 | 수집 방법 | 무료 여부 | 수집 정보 |
|------|----------|---------|---------|
| LLM 생성 (Groq/Gemini) | 프롬프트 기반 | ✅ 무료 | 여행지 정보·꿀팁·예산 추정 |
| Pollinations AI | HTTP GET | ✅ 무료, API 키 불필요 | 여행지 배경 이미지 |
| Unsplash API | API 키 (무료 50req/h) | ✅ 무료 | 실제 여행지 사진 |
| Trip.com API | Affiliate API | ✅ 무료 (파트너 가입 후) | 호텔·항공 가격·링크 |
| Booking.com | Affiliate API | ✅ 무료 (파트너 가입 후) | 숙박 가격·예약 링크 |

#### 2-2-4. 카드 구성 (8장 기준)

```
Slide 1  [HOOK]       — 가장 아름다운 여행지 이미지 + 충격 제목
Slide 2  [INTRIGUE]   — "대부분의 여행자가 이곳을 모르는 이유"
Slide 3~7 [REVEAL]    — 여행지별: 이름·위치·예산·최적시기·예약 링크
Slide 8  [CTA]        — "Save for your next trip 💾 + Book via link"
```

#### 2-2-5. 어필리에이트 파트너 (V2)

| 파트너 | 가입 | 수수료 | 연동 방식 |
|--------|------|--------|---------|
| Trip.com Affiliate | 무료 | 숙박 3~7%, 항공 1~2% | API + 딥링크 |
| Booking.com Partner | 무료 | 예약금액의 4~8% | API + 딥링크 |
| Agoda Affiliate | 무료 | 3~7% | 딥링크 (아시아 강점) |
| Klook Affiliate | 무료 | 액티비티 4~5% | 딥링크 |
| GetYourGuide | 무료 | 투어/액티비티 8% | 딥링크 |
| Skyscanner | 무료 | CPC 클릭당 $0.1~0.5 | 검색 링크 |
| Expedia Affiliate | 무료 | 2~6% | API |

#### 2-2-6. 바이럴 공식 (V2)

```
훅 공식: [비밀/희귀성] + [구체적 숫자] + [FOMO]
예) "5 beaches Google Maps doesn't show you.
     Local fishermen only. Crystal water.
     Zero tourists. Swipe to find them 🗺️"

알고리즘 신호 유발:
  저장  → "Save this for your bucket list 💾"
  공유  → "Tag who you'd bring here ✈️"
  댓글  → "Which country is #1? Comment below"
```

---

### V3. K-뷰티 + K-라이프스타일

#### 2-3-1. 콘텐츠 컨셉
한국 뷰티·패션 플랫폼(올리브영·네이버쇼핑·지그재그·에이블리 등)의
실제 인기 제품을 소개하고, **직접 구매 가능한 제품 링크** 및 **각 사이트 URL**을 제공.
글로벌 K-컬처 관심층과 국내 한국 소비자 **이중 타겟**.

#### 2-3-2. 콘텐츠 유형

| 유형 | 포맷 | 예시 제목 | 타겟 |
|------|------|---------|------|
| 제품 추천 | 제품별 카드 | "올리브영 직원들이 몰래 쓰는 제품 5개" | 국내+글로벌 |
| 루틴 소개 | 단계 카드 | "Korean Glass Skin Routine Under ₩50,000" | 글로벌 |
| 트렌드 발굴 | 비교 카드 | "지그재그 이번 주 바이럴 아이템 7개" | 국내 |
| 가성비 비교 | 대결 카드 | "올리브영 ₩8,000 vs 백화점 ₩80,000 — 같은 성분?" | 국내+글로벌 |
| 시즌 기획 | 기획전 카드 | "올영세일 이것만 사면 됨 (직원 픽)" | 국내 |

#### 2-3-3. 데이터 소스

| 소스 | 수집 방법 | 무료 여부 | 수집 정보 |
|------|----------|---------|---------|
| 올리브영 (국내) | 웹 크롤링 (robots.txt 준수) | ✅ 무료 | 제품명·가격·평점·이미지 |
| 올리브영 글로벌 | 웹 크롤링 or Affiliate API | ✅ 무료 | 글로벌 배송 가능 제품 |
| 네이버 쇼핑 | 네이버 쇼핑 검색 API | ✅ 무료 (일 25,000 호출) | 가격·쇼핑몰·이미지 |
| 지그재그 | 웹 크롤링 | ✅ 무료 | 트렌드 상품·가격 |
| 에이블리 | 웹 크롤링 | ✅ 무료 | 트렌드 상품·가격 |
| YesStyle | Affiliate API | ✅ 무료 (파트너 가입 후) | 글로벌 K-뷰티 |
| LLM | Groq/Gemini | ✅ 무료 | 제품 설명·훅 카피 |

#### 2-3-4. 카드 구성 (8장 기준)

```
Slide 1  [HOOK]      — 가장 시각적으로 인상적인 제품 + 충격 제목
Slide 2  [CREDIBILITY] — "실제 올리브영 판매량 1위 / 리뷰 N개"
Slide 3~7 [PRODUCT]  — 제품별: 이미지·이름·가격·효능·구매 링크
Slide 8  [CTA]       — "저장하고 프로필 링크에서 바로 구매"
```

#### 2-3-5. 어필리에이트 파트너 및 링크 (V3)

| 파트너 | 대상 | 가입 | 수수료 | 제공 URL |
|--------|------|------|--------|---------|
| 올리브영 파트너스 | 국내 | 무료 신청 | 구매액 2~5% | 제품별 트래킹 URL |
| YesStyle Affiliate | 글로벌 | 무료 | 10~15% | 제품별 딥링크 |
| StyleKorean Affiliate | 글로벌 | 무료 | 5~10% | 제품별 딥링크 |
| 쿠팡 파트너스 | 국내 | 무료 | 3~10% | 제품별 단축 URL |
| 네이버 파트너스 | 국내 | 무료 | CPC 클릭당 | 쇼핑 검색 링크 |
| Stylevana | 글로벌 | 무료 | 8~12% | 제품별 딥링크 |
| Amazon (K-Beauty 섹션) | 글로벌 | 무료 | 4~8% | ASIN 딥링크 |

> **채널 URL 직접 제공 요구사항**:
> 각 카드 마지막 슬라이드에 구매 가능 채널 URL을 명시한다.
>
> | 채널 | URL | 비고 |
> |------|-----|------|
> | 올리브영 | https://www.oliveyoung.co.kr | 국내 |
> | 올리브영 글로벌 | https://global.oliveyoung.com | 해외 배송 |
> | 네이버 쇼핑 | https://shopping.naver.com | 국내 |
> | 지그재그 | https://zigzag.kr | 국내 패션 |
> | 에이블리 | https://ablely.com | 국내 패션 |
> | YesStyle | https://www.yesstyle.com | 글로벌 |

#### 2-3-6. 바이럴 공식 (V3)

```
훅 공식: [비밀/내부자 정보] + [가성비 충격] + [K-컬처 권위]
예) "올리브영 직원이 직접 쓰는 제품만 골랐습니다.
     최고가 ₩12,000. 유명 브랜드보다 효과 좋음.
     마지막 제품이 진짜임 👇"

알고리즘 신호 유발:
  저장  → "저장해놓고 올영 가서 쓸어담기"
  공유  → "같이 살 친구 태그해"
  댓글  → "몇 번 제품 살 거야?"
```

---

## 3. 플랫폼별 업로드 요구사항

### 3-1. 공통 요구사항
- 모든 업로드는 **launchd(macOS) 스케줄러**로 자동 실행
- 업로드 실패 시 **3회 재시도**, 최종 실패 시 Telegram 알림
- 업로드 이력은 SQLite DB에 기록 (platform / post_id / uploaded_at / status)

### 3-2. 플랫폼별 스펙

#### Pinterest
| 항목 | 스펙 |
|------|------|
| API | Pinterest API v5 (무료) |
| 포맷 | 아이디어 핀 (멀티페이지) + 일반 정적 핀 |
| 이미지 크기 | 1000 × 1500 (2:3 비율) |
| 핀 설명 | SEO 키워드 포함 150자 이내 |
| 링크 | 핀에 직접 어필리에이트 URL 삽입 (필수) |
| 보드 구조 | V1: "Best Deals & Finds" / V2: "Hidden Travel Gems" / V3: "K-Beauty Picks" |
| 업로드 주기 | 1일 2~3핀 (버티컬 교차) |
| 최적 시간 | 14:00 / 20:00 |

#### Instagram
| 항목 | 스펙 |
|------|------|
| API | Meta Graph API — Content Publishing (무료) |
| 계정 | Instagram Business Account 필요 |
| 포맷 | 캐러셀 포스트 (최대 10장) |
| 이미지 크기 | 1080 × 1080 (1:1) or 1080 × 1350 (4:5) |
| 캡션 | 훅 문구 + 해시태그 20~30개 |
| 링크 | 바이오 Linktree(무료) → 버티컬별 링크 분기 |
| 업로드 주기 | 1일 1건 (버티컬 순환) |
| 최적 시간 | 09:00 / 19:00 |

#### TikTok
| 항목 | 스펙 |
|------|------|
| API | TikTok Content Posting API (무료, 개발자 승인 필요) |
| 포맷 | 이미지 슬라이드쇼 (Photo Mode) |
| 이미지 크기 | 1080 × 1920 (9:16 세로) |
| 텍스트 오버레이 | 상단 1~2줄 훅, 하단 CTA |
| 음악 | TikTok 무료 라이선스 음원 자동 매칭 |
| 설명 | 훅 문구 + 해시태그 5~10개 |
| 링크 | 바이오 링크 1개 → Linktree |
| 업로드 주기 | 1일 1~2건 |
| 최적 시간 | 19:00 / 21:00 |

### 3-3. 통합 업로드 스케줄

```
        월      화      수      목      금      토      일
TikTok  V1     V3      V1      V3      V1      V3      휴식
Pinterst V2    V1      V2      V1      V2      V1      V3
Instagram V3   V2      V3      V2      V3      V2      휴식

주간 합계: TikTok 6건 + Pinterest 7건 + Instagram 5건 = 18건/주
```

---

## 4. 콘텐츠 생성 요구사항

### 4-1. 공통 바이럴 공식

모든 버티컬·플랫폼 공통으로 적용되는 **호기심 유발 + 저장 + 공유** 공식:

```
[HOOK 공식 — 첫 슬라이드 3초 법칙]
  구조: [충격 수치/비밀] + [대상 명시] + [긴장감/FOMO]
  
  ✅ 좋은 예:
    "This $3 item has 80K reviews on Temu.
     Same thing costs $29 on Amazon.
     Last slide is the best one 👇"
  
  ✅ 좋은 예:
    "5 beaches that DON'T exist on Google Maps.
     Only 200 tourists/year. All in Asia.
     Save before they get discovered 🗺️"

[REVEAL 공식 — 슬라이드 2~N]
  - 정보를 1장에 1개씩 점진 공개 (전부 보게 만들기)
  - 마지막 아이템이 가장 강렬해야 함 ("마지막 게 진짜임")
  - 각 슬라이드에 구체적 수치 (가격/평점/후기 수/% 절약)

[CTA 공식 — 마지막 슬라이드]
  저장 유도: "Save this 💾" / "저장해놓기"
  공유 유도: "Tag someone who needs this"
  댓글 유도: "Which one would you buy? Comment 👇"
  링크 유도: "All links in bio" / "프로필 링크에서 구매"
```

### 4-2. 알고리즘 최적화 요구사항

| 신호 | 요구 사항 | 구현 방법 |
|------|---------|---------|
| 저장율 | 슬라이드당 1개 저장 유발 요소 | 실용 정보 + "나중에 쓸 것" 구조 |
| 공유율 | 마지막 슬라이드에 공유 CTA | "Tag + 친구 언급" 문구 |
| 댓글율 | 질문형 CTA 필수 | "Which one?" / "Comment below" |
| 완독율 | 마지막에 가장 강한 정보 배치 | "마지막 게 진짜" 예고 |
| 클릭율 | 링크 위치 명확화 | "Link in bio" / 핀 직접 링크 |

### 4-3. 이미지 카드 생성 요구사항

| 항목 | 요구사항 |
|------|---------|
| 생성 도구 | Pillow (로컬, 무료) — 기존 card_renderer.py 확장 |
| 배경 이미지 | Pollinations AI (무료) / Unsplash API (무료) |
| 폰트 | Pretendard (한국어) / Inter or Poppins (영어) — 무료 오픈소스 |
| 카드 수 | 버티컬별 5~10장 (V1: 7장, V2: 8장, V3: 8장) |
| 비율 자동 변환 | 원본 1:1 → Pinterest 2:3 → TikTok 9:16 자동 리사이즈 |
| 슬라이드 유형 | hook / context / reveal / cta (유형별 레이아웃 템플릿) |
| 브랜딩 | 계정명 + 로고 워터마크 모든 슬라이드 하단 |
| 어필리에이트 URL | 마지막 슬라이드에 short URL 또는 QR 삽입 (Pinterest) |

---

## 5. 수익화 요구사항

### 5-1. 어필리에이트 링크 관리

| 항목 | 요구사항 |
|------|---------|
| 링크 단축 | bit.ly (무료) or 자체 단축 URL로 트래킹 |
| 링크 저장 | DB에 버티컬·제품·플랫폼별 링크 저장 |
| 링크 자동 삽입 | 콘텐츠 생성 시 해당 제품/여행지 어필리에이트 URL 자동 매핑 |
| Linktree 구성 | 플랫폼 바이오 1개 URL → 버티컬별 링크 분기 (무료 플랜) |

### 5-2. 버티컬별 링크 배치 전략

```
V1 (쇼핑 비교):
  Pinterest  → 각 핀에 제품별 Temu/Amazon 어필리에이트 링크 직접 삽입
  Instagram  → 바이오 Linktree: "이번 주 추천 제품" 섹션
  TikTok     → 바이오 Linktree: 동일

V2 (여행지):
  Pinterest  → 각 핀에 Booking.com / Trip.com 직접 어필리에이트 링크 삽입
  Instagram  → 바이오 Linktree: "여행지 예약" 섹션 → Trip.com / Booking.com
  TikTok     → 바이오 Linktree: 동일

V3 (K-뷰티):
  Pinterest  → 각 핀에 YesStyle / StyleKorean 어필리에이트 링크 삽입
  Instagram  → 바이오 Linktree: "한국 쇼핑" 섹션 → 올리브영/YesStyle
  TikTok     → 바이오 Linktree: 동일
  
  채널 URL 직접 제공 (마지막 슬라이드):
    국내: oliveyoung.co.kr / shopping.naver.com / zigzag.kr / ablely.com
    글로벌: global.oliveyoung.com / yesstyle.com
```

### 5-3. 수익 추적 요구사항
- 어필리에이트 대시보드별 클릭수·전환수 주간 DB 기록
- 버티컬별·플랫폼별 수익 비교 리포트 (월 1회 자동 생성)

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
| 업로드 | Pinterest API v5 | 핀 자동 업로드 | 무료 |
| 업로드 | Instagram Graph API | 캐러셀 자동 업로드 | 무료 |
| 업로드 | TikTok Content Posting API | 슬라이드쇼 업로드 | 무료 |
| 스케줄링 | launchd (macOS) | 자동 실행 | 무료 |
| DB | SQLite | 콘텐츠·링크·업로드 이력 | 무료 |
| 링크 관리 | Linktree (무료 플랜) | 바이오 링크 허브 | 무료 |
| 알림 | Telegram Bot | 업로드 성공/실패 알림 | 무료 |

### 6-2. 기존 재사용 가능 모듈

| 모듈 | 재사용 여부 | 수정 내용 |
|------|-----------|---------|
| `src/renderer/card_renderer.py` | ✅ 재사용 | 멀티 슬라이드 + 비율 변환 추가 |
| `src/renderer/bg_generator.py` | ✅ 재사용 | 여행지/제품 프롬프트 추가 |
| `src/rewriter/` (LLM 클라이언트) | ✅ 재사용 | 버티컬별 프롬프트 추가 |
| `src/db.py` | ✅ 재사용 | 신규 테이블 추가 |
| `scripts/launchd/` | ✅ 재사용 | 새 스케줄 추가 |
| `bot/` (Telegram) | ✅ 재사용 | 새 알림 메시지 추가 |

### 6-3. 신규 개발 필요 모듈

| 모듈 | 우선순위 | 설명 |
|------|---------|------|
| `src/renderer/carousel_renderer.py` | P0 | 멀티 슬라이드 캐러셀 렌더러 |
| `src/uploader/pinterest.py` | P0 | Pinterest API v5 업로더 |
| `src/crawler/temu_feed.py` | P1 | Temu 어필리에이트 제품 피드 수집 |
| `src/crawler/travel_generator.py` | P1 | LLM 기반 여행지 정보 생성기 |
| `src/crawler/kbeauty_crawler.py` | P1 | 올리브영·네이버쇼핑 크롤러 |
| `src/affiliate/link_manager.py` | P1 | 어필리에이트 URL 생성·관리 |
| `src/uploader/instagram_carousel.py` | P2 | Instagram 캐러셀 업로더 |
| `src/uploader/tiktok.py` | P3 | TikTok 슬라이드쇼 업로더 |

---

## 7. 성공 지표 (KPIs)

### 7-1. 플랫폼별 목표

| 플랫폼 | 3개월 목표 | 6개월 목표 | 12개월 목표 |
|--------|----------|----------|-----------|
| Pinterest | 팔로워 500 / 월 핀 조회 10만 | 월 조회 50만 | 월 조회 200만 |
| Instagram | 팔로워 1,000 | 팔로워 5,000 | 팔로워 20,000 |
| TikTok | 팔로워 500 | 팔로워 5,000 | 팔로워 30,000 |

### 7-2. 수익 목표

| 기간 | 월 수익 목표 | 주요 수익원 |
|------|-----------|-----------|
| 1~3개월 | $50~150 | Temu 어필리에이트 초기 전환 |
| 4~6개월 | $300~600 | Pinterest SEO 누적 + Booking.com |
| 7~12개월 | $1,000~3,000 | 전 플랫폼 복리 + 브랜드 딜 가능 |

### 7-3. 콘텐츠 품질 지표

| 지표 | 목표 기준 |
|------|---------|
| 저장율 (Instagram) | 게시물당 저장 > 좋아요의 20% |
| 완독율 (TikTok 슬라이드) | 70% 이상 끝까지 시청 |
| 핀 클릭율 (Pinterest) | CTR > 1.5% |
| 어필리에이트 전환율 | 클릭 대비 구매 > 1% |

---

## 8. 비기능 요구사항

| 항목 | 요구사항 |
|------|---------|
| 자동화 | 스케줄러 실행 후 인력 개입 없이 완전 자동 운영 |
| 안정성 | 단계별 실패 시 재시도 3회 + Telegram 알림 |
| 확장성 | 버티컬 추가 시 프롬프트·크롤러 모듈만 추가로 확장 가능 |
| 저작권 | 이미지·음악 모두 상업 이용 가능 라이선스만 사용 |
| 개인정보 | 수집 데이터에 개인 식별 정보 없음 |
| 플랫폼 정책 | 각 플랫폼 ToS 준수 (스팸 금지, 어필리에이트 공시) |
| 어필리에이트 공시 | 모든 플랫폼 포스트에 "#ad" 또는 "affiliate link" 표기 |

---

## 9. 구현 제외 범위 (Out of Scope)

- 유료 이미지 생성 API (Midjourney, DALL-E 3 유료 플랜 등)
- 직접 판매 / 쇼핑몰 운영
- 영상(동영상) 콘텐츠 제작 (이미지 카드만 해당)
- 실시간 고객 응대 / DM 자동화
- 유료 광고 집행 (Meta Ads, TikTok Ads 등)

---

## 10. 다음 단계

요구사항 확정 후 진행 순서:

```
Step 1: 계정 셋업
  ├── Pinterest 비즈니스 계정 + API 앱 등록
  ├── Instagram 비즈니스 계정 + Meta 개발자 앱
  ├── TikTok 개발자 계정 등록
  ├── 어필리에이트 프로그램 가입 (Temu / Booking.com / YesStyle 등)
  └── Linktree 계정 생성 + 구조 설정

Step 2: 기술 구현 (P0 우선)
  ├── carousel_renderer.py (멀티 카드 렌더러)
  └── pinterest.py (Pinterest 업로더)

Step 3: 콘텐츠 파이프라인 (P1)
  ├── temu_feed.py + travel_generator.py + kbeauty_crawler.py
  └── affiliate/link_manager.py

Step 4: 멀티플랫폼 확장 (P2~P3)
  ├── instagram_carousel.py
  └── tiktok.py
```

---

*본 문서가 확정되면 Step 1부터 순서대로 구현에 착수한다.*
