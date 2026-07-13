# 자동 게시 API 승인 절차 가이드 v1.0

카드 콘텐츠(@HiddenFindsDaily)를 Pinterest·Instagram·TikTok에 **자동 게시**하기 위한
API 승인 절차. 셋 다 무료지만 **앱 심사 관문**이 있어 승인 전까지는 수동 게시.

> 상태 요약 (2026-07 기준)
> - Pinterest: 앱 생성 완료, **승인 대기 중**
> - Instagram: 미시작 — 비즈계정+FB페이지+Meta앱심사 필요
> - TikTok: 미시작 — 사진 캐러셀 API 불가 → **슬라이드쇼 MP4를 영상으로** 게시, 앱심사+감사 필요

추천 순서: **① Instagram(가치 최고·캐러셀 지원) → ② Pinterest(이미 대기) → ③ TikTok(감사 까다로움)**

---

## ① Instagram (Meta Graph API) — 캐러셀 자동 게시

### 사전 준비 (계정)
1. **Instagram을 프로페셔널 계정으로 전환**
   - IG 앱 → 설정 → 계정 유형 및 도구 → **프로페셔널 계정으로 전환** (비즈니스 또는 크리에이터)
2. **Facebook 페이지 생성 + IG 연결**
   - facebook.com → 페이지 만들기
   - IG 앱 → 설정 → 비즈니스 → **Facebook 페이지 연결**
   - (개인 IG로는 API 게시 불가 — 반드시 프로페셔널 + 페이지 연결)

### Meta 개발자 앱
3. https://developers.facebook.com → **My Apps → Create App**
   - 유형: **Business**
4. 앱에 **Instagram** 제품 추가 (Instagram Graph API)
5. **Business Verification**(비즈니스 인증) — Meta가 요구할 수 있음 (사업자/신원 확인)
6. **개인정보처리방침 URL** 등록 (이미 Notion으로 만든 것 사용)

### 권한 + 토큰
7. **Graph API Explorer**로 액세스 토큰 발급 → **장기(long-lived) 토큰**으로 교환
8. 필요한 IG 비즈니스 계정 ID 확인 (`/me/accounts` → 페이지 → `instagram_business_account`)

### 앱 심사 (핵심 관문)
9. **App Review**에서 `instagram_business_content_publish` 권한 신청
   - 필요: 사용 사례 설명, **동작 데모 스크린캐스트**, 개인정보방침
10. 심사 **2~4주** → 승인되면 프로덕션 게시 가능

### 시스템 반영 (승인 후)
11. `.env`에 `META_APP_ID`·`META_APP_SECRET`·`META_ACCESS_TOKEN`·`INSTAGRAM_BUSINESS_ACCOUNT_ID` 입력
    (카드 시스템 `CardSecrets`에 슬롯 이미 있음)
12. IG 자동 업로더 구현 → 요청 시 개발

- 참고: 캐러셀은 최대 10장, **첫 장 비율로 크롭** → 4:5 명시 필요. 하루 100게시 제한.
- 공식: https://developers.facebook.com/docs/instagram-platform/content-publishing/

---

## ② Pinterest — (이미 앱 생성·승인 대기)

1. 승인 상태 확인: https://developers.pinterest.com → 내 앱 → **standard access** 승인 여부
2. 승인되면 `.env`의 `PINTEREST_ACCESS_TOKEN` 갱신 → 기존 업로더(`cards/uploader/pinterest.py`)로 자동 게시
3. 미승인 상태면 **수동(슬라이드쇼 MP4 영상 핀)** 유지

---

## ③ TikTok (Content Posting API) — 슬라이드쇼 MP4를 영상으로

> ⚠️ TikTok 공식 API는 **사진 캐러셀 게시 불가 = 영상만**. 우리 슬라이드쇼 MP4를 영상으로 올린다.

1. https://developers.tiktok.com → 개발자 등록 → **앱 생성**
2. **Content Posting API** 신청, `video.publish` 스코프 요청
   - 사용 사례 설명 + 동작 데모 필요
3. 수동 심사 (수일~2주)
4. **감사(Audit) 신청** — 감사 전엔 게시물이 **비공개(private)로만** 노출됨. 감사 통과해야 공개 게시
5. 승인 후 `.env`에 `TIKTOK_CLIENT_KEY`·`TIKTOK_CLIENT_SECRET`·`TIKTOK_ACCESS_TOKEN` 입력
6. TikTok 영상 업로더 구현(슬라이드쇼 MP4 게시) → 요청 시 개발

- 공식: https://developers.tiktok.com/doc/content-posting-api-get-started

---

## 정직한 판단 (지금 해야 하나?)

- 셋 다 **비즈계정 전환·페이지 연결·앱심사(2~4주)·감사** 등 **셋업 오버헤드가 큼**.
- 현재 카드 배포는 막 시작 단계 → **초기엔 수동이 현실적** (슬라이드쇼 MP4 1개로 간단).
- **트래픽/저장이 붙기 시작하면** 자동화 투자 가치가 생김. 그때 IG부터 승인받고 업로더 구현.

### 최소 노력 우선순위
1. **Instagram 프로페셔널 전환 + FB 페이지 연결** — 가장 먼저 (심사 없이 되는 사전준비)
2. Pinterest 승인 상태만 주기적 확인
3. TikTok은 후순위 (감사 관문이 까다로움)

---

*버전 이력: v1.0 (2026-07-13) 최초 작성. API 조건은 변동 가능 — 진행 시 공식 문서 재확인.*
