# 작업계획서 — 카드 이미지 콘텐츠 자동화 시스템
**문서 유형**: 작업계획서 (Work Plan)
**버전**: v1.0
**작성일**: 2026-06-29
**상태**: 🟢 확정
**채널**: @HiddenFindsDaily

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| v1.0 | 2026-06-29 | 최초 작성 — TECH_REVIEW_v1.0 + DEV_SPEC_v1.0 기반 |

---

## 1. 작업 브리핑 요약

### 기술 검토 결과 — 주요 발견 사항

| 구분 | 발견 항목 | 해결 방향 |
|------|---------|---------|
| **CRITICAL 5건** | 캔버스 크기 고정, 단일 슬라이드, 한국어 폰트, MP4 전용, 채널명 하드코딩 | 신규 carousel_renderer.py 작성으로 전부 해결 |
| **HIGH 6건** | Pinterest Idea Pins 제한, Meta 토큰 만료, TikTok 사양, 영어 파싱, 유사도 모델, config 확장 | 각각 별도 모듈/설정으로 해결 |
| **MEDIUM 5건** | 디렉토리 구조, AliExpress 서명, Imgur 정리, launchd 추가, DB 분리 | 구현 시 반영 |

### 핵심 결론
- **기존 코드 재사용률**: 약 60% (LLM 체인·DB·알림·FFmpeg·재시도)
- **신규 개발 필요 모듈**: 10개
- **기술적 위험 요소**: Pinterest Idea Pins API 제한 → 일반 핀으로 Phase 1 우회 확정
- **무료 도구 100% 구현 가능**: ✅ 확인

---

## 2. 구현 단계 (Phase)

```
Phase 0: 사전 준비 (코드 없음)         ← 1~2일
Phase 1: P0 코어 렌더링                ← 3~5일
Phase 2: P0 Pinterest 업로드           ← 2~3일
Phase 3: P1 콘텐츠 파이프라인          ← 5~7일
Phase 4: P2 Instagram 연동             ← 3~4일
Phase 5: P3 TikTok 연동               ← 2~3일
Phase 6: 스케줄러 + 통합 테스트        ← 2~3일
─────────────────────────────────────
총 예상 기간: 3~4주 (API 심사 제외)
API 포함 시: 5~6주
```

---

## 3. Phase 0: 사전 준비

**목표**: 구현 환경 세팅 (코드 작성 없음)

| # | 작업 | 방법 | 소요 |
|---|------|------|------|
| 0-1 | 폰트 다운로드 스크립트 실행 | `scripts/download_cards_fonts.py` | 5분 |
| 0-2 | cards.db 초기화 | `DEV_SPEC_v1.0.md` 섹션 3 스키마 적용 | 10분 |
| 0-3 | `output/cards/` 디렉토리 생성 | mkdir v1_shopping / v2_travel / v3_kbeauty | 1분 |
| 0-4 | `src/affiliate/` 패키지 생성 | `__init__.py` 추가 | 1분 |
| 0-5 | `cards/` 패키지 생성 | `__init__.py` 추가 | 1분 |
| 0-6 | `config.py` Secrets 필드 추가 | DEV_SPEC_v1.0.md 섹션 4 기준 | 15분 |

**완료 조건**: `python -c "from cards import main"` 오류 없음

---

## 4. Phase 1: P0 코어 렌더링

**목표**: API 키 없이 카드 이미지 1세트 생성 가능

### 작업 목록

| # | 파일 | 작업 내용 | 이슈 해결 | 소요 |
|---|------|---------|---------|------|
| 1-1 | `src/renderer/bg_generator.py` | `generate_bg_image()` 함수 추가 + 영어 프롬프트 매핑 추가 | C-05 | 2h |
| 1-2 | `src/renderer/carousel_renderer.py` | 신규 작성 — 3비율 × 5슬라이드 유형 | C-01, C-02, C-03, C-04, H-01 | 8h |
| 1-3 | `scripts/download_cards_fonts.py` | Poppins + Inter 폰트 다운로드 | C-03 | 1h |
| 1-4 | `src/renderer/carousel_renderer.py` | 슬라이드 유형별 레이아웃 검증 (데모 실행) | - | 2h |

### Phase 1 완료 조건

```bash
# 각 비율별 7슬라이드 생성 확인
python -c "
from src.renderer.carousel_renderer import CarouselRenderer
r = CarouselRenderer()
slides = r.render_demo(ratio='instagram', count=7)
print(f'생성된 슬라이드: {len(slides)}장')
"
```

**산출물**:
- `output/cards/demo/instagram/slide_01.jpg` ~ `slide_07.jpg`
- `output/cards/demo/pinterest/slide_01.jpg` ~ `slide_07.jpg`
- `output/cards/demo/tiktok/slide_01.jpg` ~ `slide_07.jpg`

---

## 5. Phase 2: P0 Pinterest 업로드

**목표**: Pinterest에 핀 자동 업로드 (V2 여행지 일반 핀)

**선행 조건**: Pinterest API v5 Access Token 발급 완료

### 작업 목록

| # | 파일 | 작업 내용 | 소요 |
|---|------|---------|------|
| 2-1 | `src/uploader/pinterest.py` | 신규 작성 — 단일 이미지 핀 업로드 | 3h |
| 2-2 | `src/crawler/travel_generator.py` | 신규 작성 — LLM 여행지 정보 생성 | 4h |
| 2-3 | `src/affiliate/link_manager.py` | 신규 작성 — UTM 링크 생성 | 2h |
| 2-4 | `cards/main.py` | 기본 파이프라인 작성 (V2 + Pinterest) | 3h |
| 2-5 | 통합 테스트 | V2 여행지 → 카드 생성 → Pinterest 업로드 | 1h |

### Phase 2 완료 조건

```bash
python -m cards.main --vertical v2 --platform pinterest --count 1 --dry-run
# dry-run: 업로드 직전까지 실행, 실제 업로드 생략
```

**산출물**:
- Pinterest에 핀 1개 실제 게시 확인
- `data/cards.db` card_uploads 테이블에 success 기록

---

## 6. Phase 3: P1 콘텐츠 파이프라인

**목표**: 3개 버티컬 데이터 수집 자동화

### 작업 목록

| # | 파일 | 작업 내용 | 소요 |
|---|------|---------|------|
| 3-1 | `src/crawler/aliexpress_feed.py` | AliExpress Portals API 수집기 (HMAC 서명 포함) | 4h |
| 3-2 | `src/crawler/temu_db.py` | Temu 수동 큐레이션 CLI | 2h |
| 3-3 | `src/crawler/kbeauty_data.py` | Naver Shopping API + 영어 번역 | 4h |
| 3-4 | `cards/main.py` | V1·V3 파이프라인 추가 | 3h |
| 3-5 | V1 Pinterest 통합 테스트 | AliExpress 제품 → 카드 → Pinterest | 1h |
| 3-6 | V3 Pinterest 통합 테스트 | K-뷰티 제품 → 카드 → Pinterest | 1h |

**선행 조건**:
- `ALIEXPRESS_APP_KEY`, `ALIEXPRESS_APP_SECRET` 발급
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` 발급 (즉시 가능)

### Phase 3 완료 조건
- 3개 버티컬 모두 Pinterest 자동 업로드 성공
- 주간 7건 스케줄 launchd 등록 완료

---

## 7. Phase 4: P2 Instagram 연동

**목표**: Instagram 캐러셀 자동 업로드

**선행 조건**: Meta Developer App + Instagram Graph API 설정 완료

### 작업 목록

| # | 파일 | 작업 내용 | 소요 |
|---|------|---------|------|
| 4-1 | `src/uploader/imgur_uploader.py` | Imgur API 임시 업로드 + 삭제 | 2h |
| 4-2 | `src/uploader/meta_token_manager.py` | 60일 토큰 자동 갱신 | 3h |
| 4-3 | `src/uploader/instagram_carousel.py` | Graph API 캐러셀 업로드 (H-03 해결) | 5h |
| 4-4 | `cards/main.py` | Instagram 파이프라인 통합 | 2h |
| 4-5 | 통합 테스트 | V3 K-뷰티 → 카드 → Imgur → Instagram | 1h |

### Phase 4 완료 조건
- Instagram 캐러셀 게시물 실제 게시 확인 (10장)
- Imgur 임시 이미지 자동 삭제 확인
- 주간 5건 스케줄 launchd 등록 완료

---

## 8. Phase 5: P3 TikTok 연동

**목표**: TikTok 슬라이드쇼 영상 자동 업로드

**선행 조건**: TikTok Content Posting API 심사 승인 (1~2주 소요)

### 작업 목록

| # | 파일 | 작업 내용 | 소요 |
|---|------|---------|------|
| 5-1 | `src/uploader/tiktok.py` | FFmpeg 변환 + Video API 업로드 | 5h |
| 5-2 | `cards/main.py` | TikTok 파이프라인 통합 | 2h |
| 5-3 | FFmpeg 명령 검증 | TikTok 사양 충족 확인 (H-04 해결) | 1h |
| 5-4 | 통합 테스트 | V1 쇼핑 → 카드 → MP4 → TikTok | 1h |

### Phase 5 완료 조건
- TikTok 영상 실제 게시 확인
- 주간 6건 스케줄 launchd 등록 완료

---

## 9. Phase 6: 스케줄러 + 통합 테스트

**목표**: 전체 18건/주 자동화 완성

### 작업 목록

| # | 작업 내용 | 소요 |
|---|---------|------|
| 6-1 | launchd plist 14개 생성 + 등록 | 2h |
| 6-2 | 전체 파이프라인 드라이런 (3버티컬 × 3플랫폼) | 2h |
| 6-3 | Telegram 알림 통합 (성공/실패/토큰만료) | 1h |
| 6-4 | cards.db 수익 추적 스키마 최종 확인 | 30분 |
| 6-5 | `scripts/weekly_report.py` — 주간 업로드·수익 요약 | 2h |

### 최종 완료 조건
- 48시간 자동 운영 테스트 (수동 개입 없이 6건 이상 업로드)
- Telegram으로 성공 알림 수신 확인

---

## 10. 전체 일정 요약

```
Week 1:
  Day 1~2   Phase 0: 사전 준비 (폰트·DB·패키지 구조)
  Day 3~5   Phase 1: carousel_renderer.py 구현 + 데모
  Day 6~7   Phase 2 시작: pinterest.py + travel_generator.py

Week 2:
  Day 1~2   Phase 2 완료: Pinterest V2 업로드 검증
  Day 3~5   Phase 3: V1(AliExpress) + V3(K-뷰티) 파이프라인
  Day 6~7   Phase 3 완료: 3버티컬 Pinterest 자동 업로드

Week 3:
  Day 1~3   Phase 4: Imgur + Instagram 캐러셀 업로드
  Day 4~5   Phase 4 테스트 + 수정
  Day 6~7   TikTok API 승인 대기 중 → 다른 작업 병행

Week 4:
  Day 1~2   Phase 5: TikTok 업로드 (API 승인 후)
  Day 3~4   Phase 6: launchd + 통합 테스트
  Day 5     전체 완료 검증 + 운영 시작
```

---

## 11. 구현 우선순위 결정 기준

```
P0 (즉시 구현):
  → API 키 없이도 구현·테스트 가능
  → 전체 파이프라인의 핵심 (없으면 아무것도 안 됨)

P1 (Week 2~3):
  → 데이터 수집 (API 키 필요하나 즉시 발급 가능)
  → Pinterest는 심사 1~3일로 빠름

P2 (Week 3~4):
  → Instagram은 Meta API 설정에 시간 필요
  → Imgur는 즉시 발급 가능

P3 (Week 4+):
  → TikTok API 심사 1~2주 대기 필요
  → 대기 중 P0~P2 완성
```

---

## 12. 파일 생성 순서 (구현 체크리스트)

```
Phase 0:
  [ ] scripts/download_cards_fonts.py
  [ ] cards/__init__.py
  [ ] cards/config.py
  [ ] src/affiliate/__init__.py
  [ ] config.py Secrets 필드 추가
  [ ] data/cards.db 스키마 초기화

Phase 1:
  [ ] src/renderer/bg_generator.py (generate_bg_image 추가)
  [ ] src/renderer/carousel_renderer.py (신규)

Phase 2:
  [ ] src/crawler/travel_generator.py
  [ ] src/affiliate/link_manager.py
  [ ] src/uploader/pinterest.py
  [ ] cards/main.py (V2+Pinterest 기본)

Phase 3:
  [ ] src/crawler/aliexpress_feed.py
  [ ] src/crawler/temu_db.py
  [ ] src/crawler/kbeauty_data.py
  [ ] cards/main.py (V1·V3 추가)

Phase 4:
  [ ] src/uploader/imgur_uploader.py
  [ ] src/uploader/meta_token_manager.py
  [ ] src/uploader/instagram_carousel.py
  [ ] cards/main.py (Instagram 추가)

Phase 5:
  [ ] src/uploader/tiktok.py
  [ ] cards/main.py (TikTok 추가)

Phase 6:
  [ ] data/task_Card_*.xml (launchd plists)
  [ ] scripts/weekly_report.py
```

---

## 부록. 주간 업로드 스케줄 상세

```
        월          화          수          목          금          토          일
─────────────────────────────────────────────────────────────────────────────────
09:00  IG-V3       IG-V2       IG-V3       IG-V2       IG-V3       IG-V2       -
14:00  PIN-V2      PIN-V1      PIN-V2      PIN-V1      PIN-V2      PIN-V1      PIN-V3
19:00  TIK-V1      TIK-V3      TIK-V1      TIK-V3      TIK-V1      TIK-V3      -

IG  = Instagram  |  PIN = Pinterest  |  TIK = TikTok
V1  = 쇼핑비교   |  V2  = 여행지     |  V3  = K-뷰티

주간 합계: Instagram 5건 + Pinterest 7건 + TikTok 6건 = 18건/주
```

---

*관련 문서: TECH_REVIEW_v1.0.md | DEV_SPEC_v1.0.md | REQUIREMENTS_v1.1.md*
