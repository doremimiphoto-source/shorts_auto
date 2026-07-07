# 구현 절차 재점검 보고서 (Opus 정밀 검토)
**문서 유형**: 구현 전 감사 (Pre-Implementation Audit)
**버전**: v2.0
**작성일**: 2026-06-29
**검토 모델**: Claude Opus 4.8
**상태**: 🟢 검토 완료 — 수정 사항 반영 대기
**대상**: TECH_REVIEW_v1.0 / DEV_SPEC_v1.0 / WORK_PLAN_v1.0 + Phase 0 산출물

---

## 변경 이력

| 버전 | 날짜 | 내용 |
|------|------|------|
| v1.0 | 2026-06-29 | 1차 감사 (PRE_IMPL_AUDIT — 요구사항 단계) |
| v2.0 | 2026-06-29 | 2차 정밀 감사 (Opus) — 실제 코드 대조, 결함·과설계 식별 |

---

## 종합 판정

| 구분 | 건수 | 영향 |
|------|------|------|
| 🔴 실제 결함 (BLOCKER) | 1건 | 구현 시 런타임 에러 발생 — 반드시 수정 |
| 🟠 과설계 / 불필요 (MVP 제외 권장) | 4건 | 제거 시 개발 기간 ~30% 단축 |
| 🟡 중복 / 정리 필요 | 2건 | 코드 품질 — 정리 권장 |
| 🟢 의도된 설계 (유지) | 2건 | 오해 소지 있으나 정당함 — 문서만 보강 |

**결론**: 전체 구조는 타당. 단 **DB 재사용 가정 1건이 실제로는 깨짐**(반드시 수정). 그리고 MVP에 불필요한 모듈 4개를 빼면 "첫 매출까지 도달" 경로가 훨씬 빨라짐.

---

## 🔴 BLOCKER — 반드시 수정

### [B-01] db.py 재사용 가정이 실제로 깨짐

**계획 문서 주장** (TECH_REVIEW_v1.0 §3, DEV_SPEC_v1.0 §1):
> "db.py 100% 재사용 — `open_database('data/cards.db')`"

**실제 코드 검증 결과** — `src/db.py`:

```python
def open_database(db_path, *, init=True):
    db = Database(db_path)
    db.connect()
    if init:
        db.init_schema()          # ← 인자 없음 → 항상 src/db_schema.sql (쇼츠 스키마) 적용
    return db

def init_schema(self, schema_path=_SCHEMA_PATH):  # _SCHEMA_PATH = src/db_schema.sql
    sql = Path(schema_path).read_text()
    conn.executescript(sql)
    self._migrate(conn)            # ← 아래 문제

def _migrate(self, conn):
    _migrations = [("videos", "card_image_path", "TEXT")]   # ← videos 테이블 전제
    cur = conn.execute("PRAGMA table_info(videos)")          # cards.db엔 videos 없음
    conn.execute("ALTER TABLE videos ADD COLUMN ...")        # ← "no such table: videos" 에러
```

**문제**:
1. `open_database("data/cards.db", init=True)` 호출 시 **쇼츠용 스키마(videos, scripts...)가 cards.db에 잘못 적용**됨
2. `_migrate()`가 `videos` 테이블에 ALTER 시도 → cards.db엔 없음 → **런타임 에러**

**올바른 사실**:
- `Database` **클래스**(connect / transaction / execute / fetchone / fetchall / backup) → ✅ 100% 재사용 가능
- `init_schema` / `_migrate` / `open_database` **헬퍼** → ❌ 쇼츠 전용 (재사용 불가)

**수정안**: `cards/db.py` 신규 추가 (Database 클래스만 재사용, 자체 스키마 적용, _migrate 호출 안 함)

```python
# cards/db.py
from src.db import Database
from cards.config import CARDS_DB_PATH, CARDS_SCHEMA_PATH

def open_cards_db() -> Database:
    db = Database(CARDS_DB_PATH)
    db.connect()
    # 스키마는 Phase 0에서 이미 적용됨. 재적용은 IF NOT EXISTS라 안전하나
    # _migrate(쇼츠 전용)는 절대 호출하지 않음.
    db.connect().executescript(CARDS_SCHEMA_PATH.read_text(encoding="utf-8"))
    return db
```

> Phase 0에서 cards.db를 sqlite3로 직접 초기화한 것은 결과적으로 옳았음(이 버그를 우회). 런타임 모듈도 동일 원칙 적용.

---

## 🟠 과설계 — MVP에서 제외 권장

> 목표: "최소 비용으로 첫 매출 검증". 아래 4개는 **첫 운영에 불필요**하며, 검증 후 추가해도 늦지 않음.

### [O-01] similarity.py 영어 모델 교체 (H-05) → **MVP 제외**

- **기존 계획**: ko-sroberta → multilingual MiniLM 교체하여 콘텐츠 중복 탐지
- **문제점**:
  - SentenceTransformer 모델은 ~400MB 로딩 + 첫 호출 시 다운로드 (무겁다)
  - 카드 데이터는 **이미 구조화**됨 — V1=AliExpress product_id, V3=Naver 상품 고유값, V2=여행지명
  - 의미 임베딩 없이 **DB 유니크 제약 / 제목 SHA 해시**로 충분
- **권장**: 임베딩 dedup 제거. `card_contents.title` + `product_id` 유니크로 단순 중복만 차단.
- **효과**: 무거운 의존성 제거, H-05 작업 삭제, 별도 모델 관리 불필요

### [O-02] meta_token_manager.py (H-03 자동 갱신) → **MVP 이후로 연기**

- **이유**: Meta long-lived 토큰은 **60일 유효**. 첫 2개월은 수동 갱신으로 충분.
- **권장**: 자동 갱신 모듈 + 별도 launchd job은 운영 안정화 후 추가. 토큰 만료 임박 시 Telegram 알림만 우선.
- **효과**: Phase 4에서 모듈 1개 + plist 1개 삭감

### [O-03] temu_db.py 수동 큐레이션 CLI → **MVP 이후로 연기**

- **이유**: Temu는 V1의 **SECONDARY**. 사용자도 "AliExpress만으로 시작" 옵션을 수용한 바 있음.
- **권장**: 첫 운영은 **V1 = AliExpress 단독**. Temu는 매출 검증 후, 필요 시 CSV 1줄 import로 충분 (전용 CLI 불필요).
- **효과**: Phase 3에서 모듈 1개 삭감

### [O-04] revenue_log 테이블 + weekly_report.py → **MVP 이후로 연기**

- **이유**: 수익 추적 리포트는 **콘텐츠가 실제로 돌기 시작한 뒤** 의미가 있음. 첫 주엔 데이터가 없음.
- **권장**: revenue_log 테이블 스키마는 유지(이미 생성됨, 비용 0), `weekly_report.py` 구현만 Phase 6 → 운영 2주 후로 연기.
- **효과**: Phase 6에서 작업 1개 삭감

---

## 🟡 중복 / 정리

### [C-01] 업로드 스케줄이 3곳에 중복 정의

- **위치**: `cards/config.py:UPLOAD_TIMES`, `DEV_SPEC §5 launchd 표`, `WORK_PLAN 부록 스케줄`
- **문제**: 실제 스케줄 동작은 **launchd plist가 단일 소스**. config의 UPLOAD_TIMES는 현재 아무도 안 읽음(죽은 설정).
- **권장**: launchd plist를 SoT로 확정. `UPLOAD_TIMES`는 plist 생성 스크립트가 참조하도록 연결하거나 삭제.

### [C-02] 슬라이드 유형 5종 → 4종으로 단순화 검토

- **기존**: HOOK / CONTEXT / REVEAL / COMPARE / CTA
- **분석**: `CONTEXT`(배경 설명) 슬라이드는 HOOK과 첫 REVEAL 사이에 추가 탭을 강제 → **완독률 저하 위험**. 바이럴 캐러셀은 보통 HOOK → 즉시 본론.
- **권장**: CONTEXT 제거, HOOK 부제로 흡수. **HOOK / REVEAL / COMPARE / CTA** 4종으로 단순화.
- **효과**: 렌더러 레이아웃 1종 감소, 완독률 개선

---

## 🟢 의도된 설계 — 유지 (문서만 보강)

### [K-01] carousel_renderer가 card_renderer 헬퍼를 "복사"하는 것은 정당

- **오해 소지**: "왜 _gradient/_grain을 import 안 하고 복사하나? 중복 아닌가?"
- **정당성**:
  - `card_renderer.py`는 모듈 레벨 `W,H=1080,1920` + Pretendard 폰트에 **하드코딩** → 가변 캔버스(3비율)에 직접 재사용 불가
  - **쇼츠 파이프라인이 현재 LIVE**(하루 3~4편 운영 중) → card_renderer 리팩터링은 **프로덕션 장애 위험**
  - 따라서 carousel_renderer는 **자체 프리미티브 보유**(격리). 이는 "나쁜 중복"이 아니라 "프로덕션 격리를 위한 의도적 분리"
- **조치**: DEV_SPEC의 "이식(copy)" 표현 유지. 단 프리미티브는 size-파라미터화(W,H 인자)로 작성.

### [K-02] cards/config.py 와 src/config.py 공존은 정당

- src/config.py = **비밀(.env)** 로더 / cards/config.py = **레이아웃 상수**(캔버스·해시태그)
- 관심사 분리로 정당. 유지.

---

## 추가 발견 — 렌더링 전략 명확화 필요

### [N-01] AI 배경 이미지는 "전 슬라이드"가 아니라 "선택 적용"

- **문제**: `generate_bg_image()`를 모든 슬라이드에 쓰면 — 제품 비교(V1)·제품 목록(V3) 슬라이드는 **실제 상품 이미지**(AliExpress/Naver URL)가 주인공이어야 하는데 AI 배경이 깔리면 지저분해짐 + Pollinations 호출 낭비.
- **권장 렌더링 정책**:

| 슬라이드 유형 | 배경 |
|-------------|------|
| HOOK | AI 배경 이미지 (Pollinations) — 시선 강탈 |
| REVEAL (여행 V2) | 실제 여행지 사진 (Unsplash) |
| REVEAL (제품 V1/V3) | **실제 상품 이미지** + 단색/그라디언트 — AI 배경 미사용 |
| COMPARE | 단색 그라디언트 (좌/우 2컬럼 명확성) |
| CTA | 단색 그라디언트 + 채널 브랜딩 |

---

## 수정 반영 후 — 모듈 목록 (Before/After)

| 모듈 | v1.0 계획 | v2.0 수정 |
|------|----------|----------|
| `cards/db.py` | (없음 — db.py 재사용 가정) | ✅ **신규 추가** (B-01) |
| `similarity` 교체 | H-05 작업 | ❌ **삭제** (O-01) |
| `meta_token_manager.py` | P2 | ⏸ **연기** (O-02) |
| `temu_db.py` | P1 | ⏸ **연기** (O-03) |
| `weekly_report.py` | P6 | ⏸ **연기** (O-04) |
| 슬라이드 유형 | 5종 | 4종 (C-02) |
| carousel_renderer | 신규 | 유지 (size-파라미터화) |
| pinterest/instagram/tiktok/imgur | 유지 | 유지 |
| aliexpress_feed/travel_generator/kbeauty_data | 유지 | 유지 |
| link_manager | 유지 | 유지 |

**MVP 신규 모듈**: 10개 → **7개** (db.py +1, 연기 3개 −3, similarity −0은 기존 수정 취소)

실질 신규 작성: `cards/db.py`, `carousel_renderer.py`, `pinterest.py`, `travel_generator.py`, `link_manager.py`, `aliexpress_feed.py`, `kbeauty_data.py`, `imgur_uploader.py`, `instagram_carousel.py`, `tiktok.py`

---

## 권장 MVP 경로 (Vertical Slice 우선)

```
[1차 검증 — 가장 빠른 첫 매출 경로]
  V2(여행) → Pinterest 단독 → 어필리에이트 직링크
  필요 모듈: cards/db.py, carousel_renderer.py, travel_generator.py,
            link_manager.py, pinterest.py, cards/main.py
  → API 심사 1~3일(Pinterest)만 대기, 나머지 키 불필요
  → "콘텐츠 생성 → 업로드 → 클릭" 전 과정 1개 수직선으로 검증

[2차 확장]
  V1(AliExpress) + V3(Naver) → Pinterest 추가
  + aliexpress_feed.py, kbeauty_data.py

[3차 확장]
  Instagram (imgur + carousel) → TikTok (ffmpeg + video api)
```

---

## 사용자 확인 필요 사항

1. **O-01~O-04 연기/삭제 4건** 동의 여부 (MVP 범위 축소 → 첫 매출까지 단축)
2. **C-02 슬라이드 4종 단순화** 동의 여부
3. **Vertical Slice 경로**(V2 여행 → Pinterest 먼저) 동의 여부

---

*본 감사 반영 시 DEV_SPEC_v1.1 / WORK_PLAN_v1.1로 개정 예정*
