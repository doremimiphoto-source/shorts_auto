# 기술 검토서 — 카드 이미지 콘텐츠 시스템
**문서 유형**: 기술 검토서 (Technical Review)
**버전**: v1.0
**작성일**: 2026-06-29
**상태**: 🟢 검토 완료
**대상**: shorts_auto 기존 코드베이스 전수 검토

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| v1.0 | 2026-06-29 | 최초 작성 — 기존 코드 전수 검토 후 이슈 목록 확정 |

---

## 1. 검토 대상 파일 목록

| 파일 | 역할 | 재사용 여부 |
|------|------|-----------|
| `src/renderer/card_renderer.py` | 단일 카드 이미지 생성 (Pillow) | ✅ 재사용 (대폭 수정 필요) |
| `src/renderer/bg_generator.py` | Pollinations AI 배경 이미지/영상 생성 | ✅ 재사용 (이미지 전용 함수 추가 필요) |
| `src/db.py` | SQLite WAL 래퍼 | ✅ 그대로 재사용 |
| `src/rewriter/chain.py` | LLM 폴백 체인 (Groq → Gemini → Ollama) | ✅ 그대로 재사용 |
| `src/rewriter/groq_client.py` | Groq API 클라이언트 | ✅ 그대로 재사용 |
| `src/rewriter/gemini_client.py` | Gemini API 클라이언트 | ✅ 그대로 재사용 |
| `src/config.py` | Pydantic 설정 로더 (.env + config.yaml) | ✅ 재사용 (신규 필드 추가) |
| `src/utils/similarity.py` | ko-sroberta 임베딩 유사도 | ⚠️ 영어 모델 교체 필요 |
| `src/uploader/youtube.py` | YouTube 업로더 | ❌ 참고만 (신규 업로더 별도 작성) |
| `src/notify/telegram_notifier.py` | Telegram 알림 | ✅ 그대로 재사용 |
| `src/utils/retry.py` | 재시도 데코레이터 | ✅ 그대로 재사용 |
| `src/utils/ffmpeg_path.py` | FFmpeg 바이너리 경로 탐색 | ✅ 그대로 재사용 |

---

## 2. 이슈 목록

### 2-1. CRITICAL — 미해결 시 시스템 동작 불가

---

**[C-01] card_renderer.py: 캔버스 크기 하드코딩 (W=1080, H=1920)**

- **위치**: `card_renderer.py:29` — `W, H = 1080, 1920`
- **문제**: TikTok 9:16 크기만 지원. Pinterest(1000×1500), Instagram(1080×1080) 렌더링 불가
- **단순 리사이즈 금지**: 비율이 다르면 텍스트 레이아웃이 깨짐 → 비율별 독립 레이아웃 함수 필요
- **해결**: `CarouselRenderer` 클래스로 리팩터링 — `render_pinterest()`, `render_instagram()`, `render_tiktok()` 3개 메서드 (각각 레이아웃 좌표 독립 계산)

---

**[C-02] card_renderer.py: 단일 슬라이드만 지원**

- **위치**: `render_card()` 함수 — 1장 반환
- **문제**: 캐러셀(5~10장) 생성 로직 없음
- **해결**: `carousel_renderer.py` 신규 작성 — 슬라이드 타입별(hook/context/reveal/cta) 레이아웃 분기, 슬라이드 목록 반환

---

**[C-03] card_renderer.py: Pretendard 한국어 폰트만 사용**

- **위치**: `_fb()`, `_fxb()`, `_fbd()`, `_fm()`, `_fr()` 함수 — 전부 Pretendard 폰트
- **문제**: 영어 전용 콘텐츠(@HiddenFindsDaily)에 한국어 폰트 사용 → 영문 자간·가독성 저하
- **해결**: Poppins (헤드라인), Inter (본문) 다운로드 후 폰트 함수 교체. 기존 Pretendard는 shorts_auto 파이프라인에서 그대로 사용.

---

**[C-04] card_renderer.py: 채널 태그 하드코딩**

- **위치**: `card_renderer.py:316` — `ch = "@중학생공부치트키"`
- **문제**: 모든 생성 카드 하단에 기존 채널명 노출
- **해결**: 채널명을 파라미터로 수신 (`channel_tag: str = "@HiddenFindsDaily"`)

---

**[C-05] bg_generator.py: MP4 영상만 반환, 이미지 반환 함수 없음**

- **위치**: `generate_bg_video()` 함수 — MP4 Path 또는 None 반환
- **문제**: 카드 이미지 생성에는 정적 이미지(JPG/PNG)가 필요. MP4 불필요.
- **해결**: `generate_bg_image()` 함수 추가 — 이미지 JPG만 다운로드·캐시 후 Path 반환. (Ken Burns MP4 변환 생략)

---

### 2-2. HIGH — 미해결 시 기능 오류

---

**[H-01] card_renderer.py: 한국어 텍스트 파싱 함수**

- **위치**: `_bullets()` (첫째/둘째/셋째 파싱), `_stat()` (배/시간/분 단위)
- **문제**: 영어 콘텐츠에서 불릿 파싱 실패, 수치 추출 실패
- **해결**:
  - `_bullets_en()`: 줄바꿈·번호·대시(`1.`, `-`, `•`) 기반 영어 파싱
  - `_stat_en()`: `$`, `%`, `reviews`, `K`, `M` 등 영문 단위 추출

---

**[H-02] Pinterest API v5: Idea Pins ≠ 일반 핀**

- **문제**: 멀티페이지 Idea Pins는 일반 핀(POST /v5/pins)과 다른 엔드포인트·페이로드 사용. 현재 Pinterest API v5 공개 문서에서 Idea Pins 자동 생성 API가 제한적으로 제공됨.
- **검토 결과**: 
  - 일반 핀(단일 이미지) API는 완전히 공개되어 있음 ✅
  - Idea Pins(멀티페이지) API는 파트너 승인 필요 — 승인 전까지 접근 불가 ⚠️
- **해결**: 
  - Phase 1: 일반 정적 핀(슬라이드 1장 = Hook 이미지)으로 먼저 구현 → 어필리에이트 직링크 삽입
  - Phase 2: Idea Pins 파트너 승인 후 멀티페이지로 업그레이드
  - **영향 없음**: Pinterest SEO는 일반 핀도 동일하게 작동

---

**[H-03] Meta Graph API: Access Token 60일 만료**

- **문제**: Long-lived token도 60일 후 만료. 만료 시 업로드 전체 중단.
- **해결**: 토큰 만료 7일 전 자동 갱신 + Telegram 알림 로직 구현 (`src/uploader/meta_token_manager.py`)

---

**[H-04] TikTok MP4 기술 사양 준수**

- **TikTok 요구사항**:
  - 코덱: H.264, 오디오: AAC (오디오 없어도 업로드 가능)
  - 해상도: 최소 360×360, 권장 1080×1920
  - 파일 크기: 최대 287.6 MB (60초 이내)
  - 프레임레이트: 23~60 fps
- **현재 계획**: 슬라이드당 3.5초 × 7슬라이드 = 24.5초, 약 80~120 MB → 사양 충족
- **해결**: FFmpeg 명령어 사양 명시 (코덱·해상도·fps 고정)

---

**[H-05] similarity.py: ko-sroberta 한국어 전용 모델**

- **위치**: `src/utils/similarity.py`
- **문제**: 한국어 전용 임베딩 모델 → 영어 콘텐츠 중복 탐지 품질 저하
- **해결**: `paraphrase-multilingual-MiniLM-L12-v2` (영어+한국어 지원, 무료) 로 교체. 기존 shorts_auto 파이프라인은 ko-sroberta 유지.

---

**[H-06] config.py: 신규 Secrets 필드 미정의**

- **문제**: Pinterest·Instagram·TikTok·Imgur·AliExpress 등 신규 API 키 필드가 `Secrets` 클래스에 없음
- **해결**: `config.py`의 `Secrets` 클래스에 카드 시스템 관련 필드 추가 (`.env` 자동 로딩)

---

### 2-3. MEDIUM — 운영 전 해결 필요

---

**[M-01] 출력 디렉토리 구조 미정의**

- **해결**: `output/cards/{vertical}/{YYYYMMDD}/slide_{n}.{ratio}.jpg` 구조로 통일

---

**[M-02] AliExpress Portals API 인증 플로우**

- **AliExpress API 인증**: `appkey` + `appsecret` + HMAC-MD5 서명 방식 (OAuth 아님)
- **서명 방법**: 파라미터 정렬 → 문자열 조합 → HMAC-MD5 해시 → API 호출
- **해결**: `aliexpress_feed.py`에 서명 로직 구현 (`iop-sdk` Python 라이브러리 활용 또는 직접 구현)

---

**[M-03] Imgur 업로드 후 정리**

- **문제**: Imgur에 올린 임시 이미지는 Instagram 업로드 완료 후 삭제 필요 (계정 오염 방지)
- **Imgur 무료 한도**: 1,250 uploads/day — 18게시물 × 10슬라이드 = 180/day → 충분
- **해결**: `imgur_uploader.py`에서 업로드 후 `DELETE /image/{deletehash}` 자동 호출

---

**[M-04] launchd plist 추가 필요**

- **현재**: ShortsAuto용 plist 4개 존재 (`data/*.xml`)
- **필요**: CardContent 파이프라인용 plist 추가 (TikTok·Pinterest·Instagram 각 스케줄)
- **해결**: `data/task_CardContent_*.xml` 추가 (Step 3 구현 시)

---

**[M-05] 카드 DB 스키마 분리**

- **해결**: `data/cards.db` 별도 생성 — `db.py`의 `open_database(db_path)` 파라미터로 분리 가능 (기존 코드 수정 불필요)

---

### 2-4. LOW — 품질 개선 사항

---

**[L-01] _grain() 고정 seed**

- `np.random.default_rng(37)` — 모든 카드 동일 그레인 패턴
- 카드 인덱스를 seed로 사용하면 슬라이드마다 다른 질감 부여 가능

---

**[L-02] bg_generator.py Ken Burns 변환 불필요**

- 카드 시스템에서 배경은 정적 이미지만 사용 → MP4 변환 코드는 `generate_bg_image()` 함수에서 제외

---

## 3. 재사용 가능 요소 확인

| 요소 | 재사용 여부 | 비고 |
|------|-----------|------|
| `db.py` Database 클래스 | ✅ 100% 재사용 | `open_database("data/cards.db")` |
| `rewriter/chain.py` | ✅ 100% 재사용 | 영어 prompt_template만 교체 |
| `rewriter/groq_client.py` | ✅ 100% 재사용 | GROQ_API_KEY 기존 키 재사용 |
| `rewriter/gemini_client.py` | ✅ 100% 재사용 | GEMINI_API_KEY 기존 키 재사용 |
| `notify/telegram_notifier.py` | ✅ 100% 재사용 | 알림 메시지만 추가 |
| `utils/retry.py` | ✅ 100% 재사용 | API 재시도에 적용 |
| `utils/ffmpeg_path.py` | ✅ 100% 재사용 | TikTok MP4 변환 |
| `renderer/bg_generator.py` | ✅ 수정 후 재사용 | `generate_bg_image()` 함수 추가 |
| `renderer/card_renderer.py` | ✅ 참조 후 신규 작성 | carousel_renderer.py로 재구성 |
| `config.py` Secrets | ✅ 확장 재사용 | 신규 필드 추가 |

---

## 4. 최종 판단

| 항목 | 판단 |
|------|------|
| 기존 코드 재사용 가능성 | ✅ 높음 — LLM·DB·알림·FFmpeg 전부 재사용 |
| 신규 개발 필요량 | 중간 — 렌더러·업로더 신규 작성, 나머지 확장 |
| 기술적 위험 요소 | Pinterest Idea Pins API 제한 (일반 핀으로 우회 가능) |
| 구현 가능성 | ✅ 100% 무료 스택으로 구현 가능 |
| 예상 총 구현 기간 | 3~4주 (API 심사 대기 포함 시 5~6주) |

---

*다음 문서: DEV_SPEC_v1.0.md (개발정의서)*
